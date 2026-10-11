"""Europe PMC REST API."""
from __future__ import annotations

import sys

from .. import net
from ..records import format_author, new_record

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def count(query: str) -> tuple[int, str]:
    d = net.get_json(API, {"query": query, "format": "json", "pageSize": 1, "resultType": "idlist"}, min_interval=0.2)
    return int(d.get("hitCount", 0)), ""


def fetch(query: str, limit: int = 20000) -> list[dict]:
    cursor, recs, total = "*", [], None
    while True:
        d = net.get_json(API, {"query": query, "format": "json", "pageSize": 1000, "resultType": "core",
                               "cursorMark": cursor}, min_interval=0.2, timeout=180)
        total = d.get("hitCount", 0)
        if total > limit:
            raise RuntimeError(f"Europe PMC returned {total} records: narrow the search (limit {limit})")
        res = d.get("resultList", {}).get("result", [])
        recs.extend(_record(r) for r in res)
        print(f"  Europe PMC {len(recs)}/{total}", file=sys.stderr)
        nxt = d.get("nextCursorMark")
        if not res or not nxt or nxt == cursor:
            break
        cursor = nxt
    return recs


def _record(r: dict) -> dict:
    ji = r.get("journalInfo") or {}
    j = ji.get("journal") or {}
    authors = []
    for a in (r.get("authorList") or {}).get("author", []):
        if a.get("lastName"):
            authors.append(format_author(a["lastName"], a.get("firstName", ""), a.get("initials", "")))
        elif a.get("collectiveName"):
            authors.append(a["collectiveName"])
    src = r.get("source", "")
    pubtypes = (r.get("pubTypeList") or {}).get("pubType", [])
    ty = "PREPRINT" if src == "PPR" else ("BOOK" if (r.get("bookOrReportDetails") and not j) else "JOUR")
    kws = (r.get("keywordList") or {}).get("keyword", [])
    kws += [m.get("descriptorName", "") for m in (r.get("meshHeadingList") or {}).get("meshHeading", [])]
    urls = []
    if r.get("pmid"):
        urls.append(f"https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}/")
    urls.append(f"https://europepmc.org/article/{src}/{r.get('id')}")
    return new_record(
        "europepmc", type=ty, title=r.get("title", ""), authors=authors,
        year=r.get("pubYear") or str(ji.get("yearOfPublication", "")),
        journal=j.get("title", "") or (r.get("bookOrReportDetails") or {}).get("publisher", ""),
        volume=ji.get("volume", ""), issue=ji.get("issue", ""), pages=r.get("pageInfo", ""),
        abstract=r.get("abstractText", ""), keywords=kws, pubtypes=pubtypes, doi=r.get("doi", ""),
        pmid=r.get("pmid", ""), pmcid=r.get("pmcid", ""), issn=j.get("issn", "") or j.get("essn", ""),
        urls=urls, language=r.get("language", ""), address=r.get("affiliation", ""),
        accession=f"{src}:{r.get('id')}", db_label=f"Europe PMC ({src})",
    )
