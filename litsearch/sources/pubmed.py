"""PubMed via NCBI E-utilities."""
from __future__ import annotations

import datetime as dt
import os
import sys

from .. import net
from ..parsers import parse_medline

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
MAX_ESEARCH = 9999


def _base() -> dict:
    p = {"tool": "litsearch"}
    if os.environ.get("NCBI_API_KEY"):
        p["api_key"] = os.environ["NCBI_API_KEY"]
    return p


def _interval() -> float:
    return 0.11 if os.environ.get("NCBI_API_KEY") else 0.35


def count(query: str) -> tuple[int, str]:
    """Return (hit count, PubMed's query translation)."""
    d = net.post_json(EUTILS + "esearch.fcgi",
                      {**_base(), "db": "pubmed", "term": query, "retmode": "json", "rettype": "count"},
                      min_interval=_interval())
    r = d["esearchresult"]
    if "ERROR" in r:
        raise RuntimeError(f"PubMed error: {r['ERROR']}")
    warn = r.get("warninglist") or {}
    if warn.get("phrasesnotfound") or warn.get("quotedphrasesnotfound"):
        print(f"  ! PubMed warning: {warn}", file=sys.stderr)
    return int(r["count"]), r.get("querytranslation", "")


def _ids(query: str, mindate: str | None = None, maxdate: str | None = None) -> list[str]:
    data = {**_base(), "db": "pubmed", "term": query, "retmode": "json", "retmax": MAX_ESEARCH}
    if mindate:
        data.update({"datetype": "pdat", "mindate": mindate, "maxdate": maxdate})
    d = net.post_json(EUTILS + "esearch.fcgi", data, min_interval=_interval())["esearchresult"]
    n = int(d["count"])
    if n <= MAX_ESEARCH:
        return d["idlist"]
    lo = int((mindate or "1800")[:4])
    hi = int((maxdate or str(dt.date.today().year + 1))[:4])
    if lo >= hi:
        raise RuntimeError(f"{n} records in year {lo} alone: narrow the search")
    mid = (lo + hi) // 2
    return _ids(query, f"{lo}/01/01", f"{mid}/12/31") + _ids(query, f"{mid + 1}/01/01", f"{hi}/12/31")


def fetch(query: str) -> list[dict]:
    ids = list(dict.fromkeys(_ids(query)))
    recs = []
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        txt = net.request(EUTILS + "efetch.fcgi",
                          data={**_base(), "db": "pubmed", "id": ",".join(chunk), "rettype": "medline", "retmode": "text"},
                          min_interval=_interval(), timeout=120).decode("utf-8", "replace")
        recs.extend(parse_medline(txt, "pubmed"))
        print(f"  PubMed {min(i + 200, len(ids))}/{len(ids)}", file=sys.stderr)
    return recs


def titles(query: str, n: int = 20) -> list[tuple[str, str, str]]:
    """(PMID, year, title) of the first n records, most recent first (for reviewing what a line adds or loses)."""
    d = net.post_json(EUTILS + "esearch.fcgi", {**_base(), "db": "pubmed", "term": query, "retmode": "json", "retmax": n},
                      min_interval=_interval())["esearchresult"]
    ids = d.get("idlist") or []
    if not ids:
        return []
    s = net.post_json(EUTILS + "esummary.fcgi", {**_base(), "db": "pubmed", "id": ",".join(ids), "retmode": "json"},
                      min_interval=_interval())["result"]
    return [(i, (s.get(i, {}).get("pubdate") or "")[:4], s.get(i, {}).get("title", "")) for i in ids]


def mesh_lookup(term: str, limit: int = 8) -> list[dict]:
    """Find MeSH descriptors for a term, with tree numbers and entry terms (for strategy building)."""
    d = net.get_json(EUTILS + "esearch.fcgi", {**_base(), "db": "mesh", "term": term, "retmode": "json", "retmax": limit},
                     min_interval=_interval())
    ids = d["esearchresult"]["idlist"]
    if not ids:
        return []
    s = net.get_json(EUTILS + "esummary.fcgi", {**_base(), "db": "mesh", "id": ",".join(ids), "retmode": "json"},
                     min_interval=_interval())["result"]
    out = []
    for i in ids:
        r = s.get(i, {})
        terms = r.get("ds_meshterms", [])
        out.append({
            "uid": i,
            "heading": terms[0] if terms else "",
            "entry_terms": terms[1:],
            "scope": (r.get("ds_scopenote") or "")[:400],
            "trees": [t.get("treenum") for t in r.get("ds_idxlinks", []) if t.get("treenum")],
            "type": r.get("ds_recordtype", ""),
        })
    return out
