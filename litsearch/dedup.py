"""Cross-database de-duplication.

Records are linked when they share a PMID; when they share a DOI and their titles and first pages are
compatible (conference supplements often carry one DOI for a whole issue of abstracts); or when their
normalised titles match (exactly, or one is a >=40-character prefix of the other, e.g. Embase titles carrying
an appended translation) with publication years within one year, a compatible first author, and no
conflicting first page, DOI or PMID. Benchmarked on the ASySD labelled test set (benchmarks/dedup_asysd.py). Each cluster keeps the record from the
highest-priority database (typical librarian order: MEDLINE > Embase > Cochrane > WoS > ...); the rest
become duplicates, mirroring EndNote's "move duplicates to trash" workflow.
"""
from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher

from .records import first_author_key, title_key

ENRICH = ["abstract", "doi", "pmid", "pmcid", "keywords", "volume", "issue", "pages", "issn", "language", "address"]


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[max(a, b)] = min(a, b)


def _years_ok(a: str, b: str) -> bool:
    if not a or not b:
        return True
    return abs(int(a) - int(b)) <= 1


def _authors_ok(a: dict, b: dict) -> bool:
    ka, kb = first_author_key(a), first_author_key(b)
    return not ka or not kb or ka == kb or ka.startswith(kb) or kb.startswith(ka)


def _is_trial(r: dict) -> bool:
    return r["type"] == "TRIAL"


def _first_page(r: dict) -> str:
    m = re.match(r"\s*([A-Za-z]?\d+)", r.get("pages") or "")
    return m.group(1).lower() if m else ""


def _titles_compatible(ka: str, kb: str) -> bool:
    if not ka or not kb:
        return True
    if ka == kb or (min(len(ka), len(kb)) >= 40 and (ka.startswith(kb) or kb.startswith(ka))):
        return True
    return SequenceMatcher(None, ka, kb).ratio() >= 0.9


def _pages_ok(a: dict, b: dict) -> bool:
    pa, pb = _first_page(a), _first_page(b)
    return not pa or not pb or pa == pb


def deduplicate(records: list[dict], priority: list[str]) -> tuple[list[dict], list[dict]]:
    """Return (unique, duplicates). Adds keys: uid, found_in, dup_of, dup_reason."""
    rank = {db: i for i, db in enumerate(priority)}
    order = sorted(range(len(records)), key=lambda i: (rank.get(records[i]["db"], 999), i))
    recs = [records[i] for i in order]
    n = len(recs)
    uf = _UF(n)
    reason = {}

    by_doi, by_pmid, by_nct = defaultdict(list), defaultdict(list), defaultdict(list)
    for i, r in enumerate(recs):
        if r["doi"]:
            by_doi[r["doi"]].append(i)
        if r["pmid"]:
            by_pmid[r["pmid"]].append(i)
        if _is_trial(r) and r["accession"]:
            by_nct[r["accession"]].append(i)
    tk = [title_key(r["title"]) for r in recs]
    for label, idx in (("DOI", by_doi), ("PMID", by_pmid), ("NCT", by_nct)):
        for ids in idx.values():
            for x, a in enumerate(ids):
                for b in ids[x + 1:]:
                    ra, rb = recs[a], recs[b]
                    same_paper = (_titles_compatible(tk[a], tk[b]) and _pages_ok(ra, rb)) or (
                        first_author_key(ra) and first_author_key(ra) == first_author_key(rb)
                        and _years_ok(ra["year"], rb["year"]) and _first_page(ra) and _first_page(ra) == _first_page(rb))
                    if label == "DOI" and not same_paper:
                        continue   # e.g. conference supplements: one DOI for a whole issue of abstracts
                    if uf.find(a) != uf.find(b):
                        reason.setdefault(b, label)
                    uf.union(a, b)

    blocks = defaultdict(list)
    for i, k in enumerate(tk):
        if len(k) >= 20:
            blocks[k[:30]].append(i)
    for ids in blocks.values():
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                a, b = ids[x], ids[y]
                ra, rb = recs[a], recs[b]
                if _is_trial(ra) != _is_trial(rb):
                    continue
                if ra["doi"] and rb["doi"] and ra["doi"] != rb["doi"]:
                    # different DOIs: only Embase-style conference abstract vs article may still match; keep apart
                    continue
                if ra["pmid"] and rb["pmid"] and ra["pmid"] != rb["pmid"]:
                    continue   # two PubMed records, e.g. an article and its erratum or a reprint under the same title
                ka, kb = tk[a], tk[b]
                same = ka == kb or (min(len(ka), len(kb)) >= 40 and (ka.startswith(kb) or kb.startswith(ka)))
                if same and _years_ok(ra["year"], rb["year"]) and _authors_ok(ra, rb) and _pages_ok(ra, rb):
                    if uf.find(a) != uf.find(b):
                        reason.setdefault(b, "Title/Year/Author")
                    uf.union(a, b)

    clusters = defaultdict(list)
    for i in range(n):
        clusters[uf.find(i)].append(i)

    unique, dups = [], []
    for i, r in enumerate(recs):
        r["uid"] = i + 1
    for root, members in clusters.items():
        members.sort()
        keep = recs[members[0]]
        keep["found_in"] = list(dict.fromkeys(recs[m]["db"] for m in members))
        keep["dup_of"] = None
        for m in members[1:]:
            d = recs[m]
            d["dup_of"] = keep["uid"]
            d["dup_reason"] = reason.get(m, "linked")
            for f in ENRICH:
                if not keep.get(f) and d.get(f):
                    keep[f] = d[f]
            dups.append(d)
        unique.append(keep)
    unique.sort(key=lambda r: r["uid"])
    dups.sort(key=lambda r: r["uid"])
    return unique, dups
