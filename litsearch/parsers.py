"""Parsers for database export files: RIS, MEDLINE (PubMed/Ovid .nbib/.txt) and Web of Science tagged text."""
from __future__ import annotations

import re
from pathlib import Path

from .records import format_author, new_record

RIS_TYPES = {
    "JOUR": "JOUR", "JFULL": "JOUR", "EJOUR": "JOUR", "ABST": "JOUR", "INPR": "JOUR", "MGZN": "JOUR",
    "NEWS": "JOUR", "CHAP": "CHAP", "ECHAP": "CHAP", "BOOK": "BOOK", "EBOOK": "BOOK", "EDBOOK": "BOOK",
    "CONF": "CONF", "CPAPER": "CONF", "THES": "THES", "RPRT": "RPRT", "GEN": "GEN", "DATA": "GEN",
    "ELEC": "GEN", "SER": "JOUR",
}


def detect_format(text: str) -> str:
    head = text[:5000]
    if re.search(r"^TY  - ", head, re.M):
        return "ris"
    if re.search(r"^PMID- ", head, re.M):
        return "medline"
    if re.search(r"^(FN |PT [JBSP]\s*$)", head, re.M) and re.search(r"^ER\s*$", text, re.M):
        return "wos"
    raise ValueError("Unknown file format (supported: RIS, MEDLINE/nbib, WoS plain text)")


def parse_file(path: Path, db: str) -> list[dict]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "cp949", "latin-1"):
        try:
            text = raw.decode(enc)
            if "\x00" in text[:200]:
                continue
            break
        except UnicodeDecodeError:
            continue
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    fmt = detect_format(text)
    return {"ris": parse_ris, "medline": parse_medline, "wos": parse_wos}[fmt](text, db)


# ---------------------------------------------------------------- RIS
def _ris_entries(text: str):
    cur, last = None, None
    for line in text.split("\n"):
        m = re.match(r"^([A-Z][A-Z0-9])  -( (.*))?$", line)
        if m:
            tag, val = m.group(1), (m.group(3) or "").strip()
            if tag == "TY":
                cur = {}
            if cur is None:
                continue
            if tag == "ER":
                yield cur
                cur, last = None, None
                continue
            cur.setdefault(tag, []).append(val)
            last = tag
        elif cur is not None and last and line.strip():
            cur[last][-1] += " " + line.strip()
    if cur:
        yield cur


def _norm_author(a: str) -> str:
    a = a.strip().rstrip(".")
    if not a:
        return ""
    if "," in a:
        last, fore = [x.strip() for x in a.split(",", 1)]
        if re.fullmatch(r"([A-Z]\.?\s*)+", fore or ""):
            return format_author(last, initials=re.sub(r"[^A-Z]", "", fore))
        return format_author(last, fore)
    m = re.fullmatch(r"(.+?)\s+([A-Z]{1,4})", a)          # 'Smith JA' (MEDLINE AU style)
    if m:
        return format_author(m.group(1), initials=m.group(2))
    return a


def _pages(sp: str, ep: str) -> str:
    sp, ep = (sp or "").strip(), (ep or "").strip()
    if sp and ep and sp != ep:
        return f"{sp}-{ep}"
    return sp or ep


def parse_ris(text: str, db: str) -> list[dict]:
    out = []
    for e in _ris_entries(text):
        g = lambda *tags: next((e[t][0] for t in tags if e.get(t) and e[t][0]), "")
        gl = lambda *tags: [v for t in tags for v in e.get(t, []) if v]
        ty = RIS_TYPES.get(g("TY").upper(), "GEN")
        title = g("TI", "T1", "CT")
        journal = g("T2", "JF", "JO", "JA", "J2", "BT", "T3")
        if ty == "CHAP" and not title:
            title = g("T2")
        allvals = " ".join(" ".join(v) for v in e.values())
        pmid = ""
        m = re.search(r"PMID[:\s]*(\d{6,9})", allvals)
        if m:
            pmid = m.group(1)
        else:
            for t in ("C5", "AN", "PM"):
                v = g(t)
                if re.fullmatch(r"\d{6,9}", v) and (t != "AN" or db in ("pubmed", "ovid_medline")):
                    pmid = v
                    break
        doi = g("DO") or next((u for u in gl("UR", "L2", "L3", "LK", "M3", "N1") if "10." in u and "doi" in u.lower()), "")
        out.append(new_record(
            db, type=ty, title=title,
            authors=[x for x in (_norm_author(a) for a in gl("AU", "A1")) if x],
            year=g("PY", "Y1", "DA", "Y2"), journal=journal, volume=g("VL"), issue=g("IS"),
            pages=_pages(g("SP"), g("EP")), abstract=" ".join(gl("AB", "N2")),
            keywords=gl("KW"), pubtypes=gl("M3"), doi=doi, pmid=pmid, issn=g("SN"),
            urls=gl("UR", "L1", "L2", "LK"), language=g("LA"), address="; ".join(gl("AD")),
            accession=g("AN", "ID", "U2"), db_label=g("DB", "DP"), notes=" ".join(gl("N1"))[:2000],
        ))
    return out


# ---------------------------------------------------------------- MEDLINE
def _medline_entries(text: str):
    for block in re.split(r"\n\s*\n(?=PMID- )", text.strip()):
        cur, last = {}, None
        for line in block.split("\n"):
            m = re.match(r"^([A-Z][A-Z0-9 ]{1,3})- (.*)$", line)
            if m:
                last = m.group(1).strip()
                cur.setdefault(last, []).append(m.group(2).strip())
            elif last and line.startswith("      "):
                cur[last][-1] += " " + line.strip()
        if cur.get("PMID"):
            yield cur


def parse_medline(text: str, db: str) -> list[dict]:
    out = []
    for e in _medline_entries(text):
        g = lambda t: e.get(t, [""])[0]
        doi = ""
        for v in e.get("LID", []) + e.get("AID", []):
            if v.endswith("[doi]"):
                doi = v[:-5].strip()
                break
        pts = e.get("PT", [])
        ty = "JOUR"
        if "Book" in " ".join(pts) or e.get("BTI"):
            ty = "CHAP" if e.get("TI") and e.get("BTI") else "BOOK"
        if "Preprint" in pts:
            ty = "PREPRINT"
        authors = [_fau(a) for a in e.get("FAU", [])] or [_norm_author(a) for a in e.get("AU", [])]
        pmc = g("PMC")
        out.append(new_record(
            db, type=ty, title=g("TI") or g("BTI"), authors=[a for a in authors if a],
            year=g("DP"), journal=g("JT") or g("TA") or g("BTI"), volume=g("VI"), issue=g("IP"),
            pages=g("PG"), abstract=" ".join(e.get("AB", [])),
            keywords=e.get("MH", []) + e.get("OT", []), pubtypes=pts, doi=doi, pmid=g("PMID"),
            pmcid=pmc, issn=g("IS"), language=g("LA"), address="; ".join(dict.fromkeys(e.get("AD", [])))[:1000],
            accession=g("PMID"),
            urls=[f"https://pubmed.ncbi.nlm.nih.gov/{g('PMID')}/"],
            db_label="MEDLINE" if g("STAT") == "MEDLINE" else "PubMed",
        ))
    return out


def _fau(a: str) -> str:
    if "," in a:
        last, fore = a.split(",", 1)
        return format_author(last, fore)
    return a


# ---------------------------------------------------------------- Web of Science tagged
def parse_wos(text: str, db: str) -> list[dict]:
    out, cur, last = [], None, None
    for line in text.split("\n"):
        if line.startswith("ER"):
            if cur:
                out.append(_wos_record(cur, db))
            cur, last = None, None
            continue
        m = re.match(r"^([A-Z][A-Z0-9]) (.*)$", line)
        if m and m.group(1) not in ("FN", "VR", "EF"):
            last = m.group(1)
            if last == "PT":
                cur = {}
            if cur is not None:
                cur.setdefault(last, []).append(m.group(2).strip())
        elif cur is not None and last and line.startswith("   "):
            cur[last].append(line.strip())
    return out


def _wos_record(e: dict, db: str) -> dict:
    g = lambda t: " ".join(e.get(t, []))
    kws = [k.strip() for t in ("DE", "ID") for k in g(t).split(";") if k.strip()]
    pt = g("PT")
    return new_record(
        db, type={"J": "JOUR", "B": "BOOK", "S": "JOUR", "P": "GEN"}.get(pt, "JOUR"),
        title=g("TI"), authors=[_norm_author(a) for a in e.get("AU", [])], year=g("PY"),
        journal=g("SO"), volume=g("VL"), issue=g("IS"), pages=_pages(g("BP"), g("EP")) or g("AR"),
        abstract=g("AB"), keywords=kws, pubtypes=[g("DT")] if g("DT") else [], doi=g("DI"),
        pmid=g("PM"), issn=g("SN"), language=g("LA"), address="; ".join(e.get("C1", []))[:1000],
        accession=g("UT"), db_label="Web of Science",
    )
