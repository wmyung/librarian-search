"""Common bibliographic record shape and normalisation helpers.

A record is a plain dict:
  db            source database id (pubmed, embase, cochrane, wos, europepmc, ctgov, citation, ...)
  type          JOUR | CHAP | BOOK | CONF | THES | RPRT | TRIAL | PREPRINT | GEN
  title, authors (list of "Last, F. M."), year, journal, volume, issue, pages,
  abstract, keywords (list), pubtypes (list), doi, pmid, pmcid, issn,
  urls (list), language, address, accession, db_label, notes
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from pathlib import Path

FIELDS = ["db", "type", "title", "authors", "year", "journal", "volume", "issue", "pages",
          "abstract", "keywords", "pubtypes", "doi", "pmid", "pmcid", "issn", "urls",
          "language", "address", "accession", "db_label", "notes"]
LIST_FIELDS = {"authors", "keywords", "pubtypes", "urls"}


def new_record(db: str, **kw) -> dict:
    r = {f: ([] if f in LIST_FIELDS else "") for f in FIELDS}
    r["db"] = db
    r["type"] = "JOUR"
    for k, v in kw.items():
        if v is None:
            continue
        r[k] = v
    return clean(r)


_TAG = re.compile(r"<[^>]+>")


def strip_markup(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub(" ", s or ""))).strip()


def clean(r: dict) -> dict:
    for f in FIELDS:
        v = r.get(f)
        if f in LIST_FIELDS:
            if isinstance(v, str):
                v = [v] if v else []
            r[f] = [strip_markup(str(x)) for x in (v or []) if str(x).strip()]
        else:
            r[f] = strip_markup(str(v)) if v not in (None,) else ""
    r["doi"] = norm_doi(r["doi"])
    r["pmid"] = re.sub(r"\D", "", r["pmid"])
    m = re.search(r"(1[5-9]\d\d|20\d\d)", r["year"])
    r["year"] = m.group(1) if m else ""
    return r


def norm_doi(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", s)
    s = re.sub(r"^doi:\s*", "", s)
    m = re.search(r"10\.\d{4,9}/\S+", s)
    return m.group(0).rstrip(".,;)]}") if m else ""


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def title_key(title: str) -> str:
    t = fold(title).lower()
    t = re.sub(r"[^a-z0-9]+", "", t)        # PubMed wraps translated titles in [...]: keep the words
    return t


def first_author_key(r: dict) -> str:
    if not r["authors"]:
        return ""
    last = r["authors"][0].split(",")[0]
    return re.sub(r"[^a-z]", "", fold(last).lower())


def format_author(last: str, fore: str = "", initials: str = "") -> str:
    """Return 'Last, F. M.' (EndNote/RIS convention)."""
    last = (last or "").strip()
    if not initials and fore:
        initials = "".join(p[0] for p in re.split(r"[\s\-.]+", fore.strip()) if p)
    initials = re.sub(r"[^A-Za-zÀ-￿]", "", initials or "")
    if not last:
        return fore.strip()
    if not initials:
        return last
    return f"{last}, " + " ".join(f"{c.upper()}." for c in initials)


def split_display_name(name: str) -> str:
    """'John A. Smith' -> 'Smith, J. A.'  (best effort for OpenAlex/CT.gov display names)."""
    name = (name or "").strip()
    if not name:
        return ""
    if "," in name:
        last, fore = name.split(",", 1)
        return format_author(last, fore)
    parts = name.split()
    if len(parts) == 1:
        return parts[0]
    particles = {"van", "von", "de", "der", "den", "da", "di", "del", "la", "le", "du"}
    i = len(parts) - 1
    while i > 1 and parts[i - 1].lower() in particles:
        i -= 1
    return format_author(" ".join(parts[i:]), " ".join(parts[:i]))


def save_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
