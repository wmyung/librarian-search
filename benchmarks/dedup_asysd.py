"""Benchmark deduplication on the ASySD labelled test set (Hair et al., CAMARADES).

The set has 1,845 records from multiple databases; the 'source' column marks the record kept per true study
('unique', 584) versus its duplicates. EndNote's automatic dedup kept 949 records ('label' == In_database);
ASySD keeps 586. Data are downloaded at run time (GPL-3, not redistributed here).

  uv run python benchmarks/dedup_asysd.py
"""
from __future__ import annotations

import csv
import io
import re
import sys
import urllib.request
from collections import Counter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from litsearch.dedup import deduplicate  # noqa: E402
from litsearch.records import new_record  # noqa: E402

URL = "https://raw.githubusercontent.com/camaradesuk/ASySD/HEAD/tests/testthat/labelled_test_set.csv"


def split_authors(s: str) -> list[str]:
    # 'Adeli K.Lewis G. F.' -> ['Adeli, K.', 'Lewis, G. F.']
    out = []
    for m in re.finditer(r"([^\s.][^.]*?)\s+((?:[A-Z]\.\s?)+)", s or ""):
        last = m.group(1).strip().lstrip(".")
        if last:
            out.append(f"{last}, {m.group(2).strip()}")
    return out


def load():
    raw = urllib.request.urlopen(URL, timeout=60).read().decode("utf-8", "replace")
    rows = list(csv.DictReader(io.StringIO(raw)))
    recs = []
    for r in rows:
        na = lambda v: "" if v in ("NA", None) else v
        rec = new_record("db", title=na(r["title"]), authors=split_authors(na(r["author"])), year=na(r["year"]),
                         journal=na(r["journal"]), volume=na(r["volume"]), issue=na(r["number"]),
                         pages=na(r["pages"]), abstract=na(r["abstract"]), doi=na(r["doi"]), issn=na(r["isbn"]))
        rec["_truth"] = r["source"]
        rec["_endnote"] = r["label"]
        rec["_id"] = r["record_id"]
        recs.append(rec)
    return recs


def main():
    recs = load()
    unique, dups = deduplicate(recs, ["db"])
    truth_unique = sum(1 for r in recs if r["_truth"] == "unique")
    endnote_unique = sum(1 for r in recs if r["_endnote"] == "In_database")
    # a cluster containing two records both marked 'unique' merges two distinct studies (false merge)
    by_keep = Counter()
    for r in unique:
        if r["_truth"] == "unique":
            by_keep[r["uid"]] += 1
    for d in dups:
        if d["_truth"] == "unique":
            by_keep[d["dup_of"]] += 1
    false_merges = sum(v - 1 for v in by_keep.values() if v > 1)
    print(f"records               {len(recs)}")
    print(f"true unique studies   {truth_unique}")
    print(f"EndNote (default)     {endnote_unique}")
    print("ASySD (reported)      586")
    print(f"librarian-search      {len(unique)}  (false merges of distinct studies: {false_merges}; "
          f"residual duplicates: {len(unique) - truth_unique + false_merges})")
    print("match basis:", dict(Counter(d['dup_reason'] for d in dups)))


if __name__ == "__main__":
    main()
