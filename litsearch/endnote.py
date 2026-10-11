"""Write a native EndNote 20/21 library (.enl + .Data) in the layout a medical library typically delivers.

Layout follows a typical medical-library deliverable:
  * every retrieved record is in the library; duplicates are in the Trash (trash_state=1)
  * one group per database, named "<DB> <retrieved count>", holding the records that database contributed
    after de-duplication (priority order)
  * a "By topic" group set with smart groups (random*, systematic review, placebo, meta-analysis, ...)
The schema (DDL) comes from an EndNote 21 library; EndNote-specific SQL functions/collations used by its
triggers are registered here so inserts behave as they do inside EndNote.
"""
from __future__ import annotations

import json
import random
import shutil
import sqlite3
import string
import struct
import time
import unicodedata
import uuid
from pathlib import Path
from xml.sax.saxutils import escape

from .classify import FLAGS
from .project import db_info

TEMPLATE = json.loads((Path(__file__).parent / "endnote_template.json").read_text(encoding="utf-8"))

REF_TYPE = {"JOUR": 0, "BOOK": 1, "THES": 2, "CONF": 3, "CHAP": 7, "RPRT": 10, "GEN": 31, "TRIAL": 31, "PREPRINT": 31}
TYPE_OF_WORK = {"TRIAL": "Clinical trial registration", "PREPRINT": "Preprint"}


def _fold_upper(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).upper()


def en_make_sort_key(text, field, _n=None):
    """Approximation of EndNote's EN_MAKE_SORT_KEY: authors -> 'LAST INIT', padded; others upper-cased."""
    text = text or ""
    if field == 2:
        parts = []
        for a in text.replace("\n", "\r").split("\r"):
            a = a.strip()
            if not a:
                continue
            last, _, fore = a.partition(",")
            last = "".join(c for c in _fold_upper(last) if c.isalnum() or c == " ").strip()
            init = "".join(c for c in _fold_upper(fore) if c.isalpha())
            parts.append(f"{last} {init.ljust(4)}")
        return "".join(parts)
    if field == 3:
        return text
    return _fold_upper(text)


def _collate(a: str, b: str) -> int:
    a, b = _fold_upper(a or ""), _fold_upper(b or "")
    return (a > b) - (a < b)


def _connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.create_function("EN_MAKE_SORT_KEY", 3, en_make_sort_key)
    con.create_collation("ENCI_Base", _collate)
    con.create_collation("ENCIN_ko_KR", _collate)
    return con


def _members(ids: list[int]) -> bytes:
    return struct.pack(f"<ii{len(ids)}i", 0x02000000, len(ids), *ids)


def _group_xml(gid: str, name: str, now: int, smart_term: str | None = None) -> str:
    rules = "<rule>TYPE;3</rule>"
    if smart_term:
        fields = [("3", "Title"), ("7", "Keywords"), ("25", "Abstract")]
        flat = f"((('Title' CONTAINS [{smart_term}]) Or ('Keywords' CONTAINS [{smart_term}])) Or ('Abstract' CONTAINS [{smart_term}]))"
        terms = ""
        for i, (fid, fname) in enumerate(fields, 1):
            op = '<boolean opID="20003"></boolean>' if i == 1 else '<boolean opID="20001">Or</boolean>'
            terms += (f'<term order="{i}">{op}<qualifier qualifierID="20005">Contains</qualifier>'
                      f'<field RSSfldID="{fid}">{fname}</field><text>{escape(smart_term)}</text></term>')
        q = ("<ENQuery><MatchCase>0</MatchCase><MatchWholeWords>0</MatchWholeWords><UseIndexes>0</UseIndexes>"
             f"<RecNumOptional>0</RecNumOptional><FlatQuery>{escape(flat)}</FlatQuery>"
             f"<StructuredQuery><terms>{terms}</terms></StructuredQuery></ENQuery>")
        rules = f"<rule>TYPE;4</rule><rule>SEARCH;{escape(q, {chr(39): '&apos;', chr(34): '&quot;'})}</rule>"
    return ('<?xml version="1.0" encoding="UTF-8"?><group version="1"><ids>'
            f"<id>{gid}</id><name>{escape(name)}</name></ids><times>"
            f'<created format="UTC">{now}</created><modified format="UTC">{now}</modified></times>'
            f"<rules>{rules}</rules></group>")


def _set_xml(sid: str, name: str, now: int, member_ids: list[str]) -> str:
    mem = "".join(f"<member>{m}</member>" for m in member_ids)
    return ('<?xml version="1.0" encoding="UTF-8"?><groupset version="1"><ids>'
            f"<id>{sid}</id><name>{escape(name)}</name></ids><times>"
            f'<created format="UTC">{now}</created><modified format="UTC">{now}</modified></times>'
            f'<members complex="true">{mem}</members></groupset>')


def _row(r: dict, now: int, trash: bool) -> dict:
    info = db_info(r["db"])
    found = r.get("found_in") or [r["db"]]
    research = ""
    if trash:
        research = f"Duplicate of record #{r['dup_of']} ({r.get('dup_reason', '')})"
    return {
        "trash_state": 1 if trash else 0,
        "reference_type": REF_TYPE.get(r["type"], 0),
        "author": "\r".join(r["authors"]),
        "year": r["year"],
        "title": r["title"],
        "pages": r["pages"],
        "secondary_title": r["journal"],
        "volume": r["volume"],
        "number": r["issue"],
        "keywords": "\r".join(dict.fromkeys(r["keywords"])),
        "type_of_work": TYPE_OF_WORK.get(r["type"], "; ".join(r["pubtypes"][:4])),
        "abstract": r["abstract"],
        "label": "; ".join(db_info(d)["short"] for d in found),
        "url": "\r".join(dict.fromkeys(r["urls"])),
        "notes": r.get("notes", ""),
        "isbn": r["issn"],
        "accession_number": r["pmid"] or r["accession"],
        "electronic_resource_number": r["doi"],
        "name_of_database": r.get("db_label") or info["name"],
        "database_provider": info["platform"],
        "research_notes": research,
        "language": r["language"],
        "author_address": r["address"][:2000],
        "custom_7": r["pmcid"],
        "added_to_library": now,
        "record_last_updated": now,
    }


def write_library(path: Path, unique: list[dict], dups: list[dict], db_order: list[str],
                  retrieved: dict[str, int], flag_map: dict[int, dict],
                  extra_groups: dict[str, set[int]] | None = None) -> Path:
    """Create <path>.enl and <path>.Data. Record numbers equal record 'uid'."""
    path = Path(path).with_suffix(".enl")
    data_dir = path.with_suffix(".Data")
    for p in (path, data_dir):
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    now = int(time.time())
    con = _connect(path)
    con.execute("PRAGMA page_size=4096")
    for ddl in TEMPLATE["enl_ddl"]:
        con.execute(ddl)
    for code, sub, val in TEMPLATE["misc"]:
        con.execute("INSERT INTO misc(code,subcode,value) VALUES(?,?,?)", (code, sub, val.encode("utf-8")))
    lib_id = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(36))
    con.execute("INSERT INTO misc VALUES(14,0,?)", (lib_id.encode(),))
    con.execute("INSERT INTO misc VALUES(22,0,?)", (b"1",))

    allrecs = sorted([(r, False) for r in unique] + [(d, True) for d in dups], key=lambda x: x[0]["uid"])
    for r, trash in allrecs:
        row = _row(r, now, trash)
        cols = ["id"] + list(row)
        con.execute(f"INSERT INTO refs({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                    [r["uid"]] + list(row.values()))

    gid_num = 1
    db_group_uuids, smart_uuids = [], []
    for db in db_order:
        ids = [r["uid"] for r in unique if r["db"] == db]
        if not retrieved.get(db) and not ids:
            continue
        gu = str(uuid.uuid4()).upper()
        name = f"{db_info(db)['short']} {retrieved.get(db, len(ids))}"
        con.execute("INSERT INTO groups(group_id,recs_stamp,spec,members) VALUES(?,?,?,?)",
                    (gid_num, 0, _group_xml(gu, name, now).encode(), _members(ids)))
        db_group_uuids.append(gu)
        gid_num += 1
    for key, label, term, _rx in FLAGS:
        if key == "trialreg":
            continue
        ids = [r["uid"] for r in unique if flag_map.get(r["uid"], {}).get(key)]
        if not term and not ids:
            continue
        gu = str(uuid.uuid4()).upper()
        con.execute("INSERT INTO groups(group_id,recs_stamp,spec,members) VALUES(?,?,?,?)",
                    (gid_num, 0, _group_xml(gu, label, now, smart_term=term or None).encode(), _members(ids)))
        smart_uuids.append(gu)
        gid_num += 1
    for label, ids in (extra_groups or {}).items():
        if not ids:
            continue
        gu = str(uuid.uuid4()).upper()
        con.execute("INSERT INTO groups(group_id,recs_stamp,spec,members) VALUES(?,?,?,?)",
                    (gid_num, 0, _group_xml(gu, label, now).encode(), _members(sorted(ids))))
        smart_uuids.append(gu)
        gid_num += 1
    trial_ids = [r["uid"] for r in unique if r["type"] == "TRIAL"]
    if trial_ids:
        gu = str(uuid.uuid4()).upper()
        con.execute("INSERT INTO groups(group_id,recs_stamp,spec,members) VALUES(?,?,?,?)",
                    (gid_num, 0, _group_xml(gu, "Trial registrations", now).encode(), _members(trial_ids)))
        db_group_uuids.append(gu)
        gid_num += 1

    s1, s2 = str(uuid.uuid4()).upper(), str(uuid.uuid4()).upper()
    con.execute("INSERT INTO misc VALUES(17,1,?)", (_set_xml(s1, "By database", now, db_group_uuids).encode(),))
    con.execute("INSERT INTO misc VALUES(17,2,?)", (_set_xml(s2, "By topic", now, smart_uuids).encode(),))
    setlist = ('<?xml version="1.0" encoding="UTF-8"?><setlist version="1"><sets>'
               f'<set collapsed="false">{s1}</set><set collapsed="false">{s2}</set></sets></setlist>')
    con.execute("INSERT INTO misc VALUES(18,0,?)", (setlist.encode(),))
    con.commit()
    con.execute("VACUUM")
    con.close()

    sdb = data_dir / "sdb"
    sdb.mkdir(parents=True)
    shutil.copyfile(path, sdb / "sdb.eni")
    pcon = sqlite3.connect(sdb / "pdb.eni")
    for ddl in TEMPLATE["pdb_ddl"]:
        pcon.execute(ddl)
    pcon.commit()
    pcon.close()
    return path
