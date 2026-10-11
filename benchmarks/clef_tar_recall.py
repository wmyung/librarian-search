"""Search recall on CLEF eHealth TAR 2017 test topics (Cochrane diagnostic test accuracy reviews).

For each topic in benchmarks/clef_tar/*.json we run a PubMed strategy written from the review *title only*
(as the skill would, without consulting the original Cochrane query) and measure recall of the studies finally
included in the review (content-level qrels). The size of the original Cochrane query's PubMed result set is
shown for comparison; our result size is also reported restricted to PMIDs no newer than the original set
(a proxy for the review's search date).

  uv run python benchmarks/clef_tar_recall.py
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from litsearch.project import expand_line  # noqa: E402
from litsearch.sources import pubmed  # noqa: E402

BASE = "https://raw.githubusercontent.com/CLEF-TAR/tar/master/2017-TAR/testing/"


def get(url):
    return urllib.request.urlopen(url, timeout=60).read().decode()


def main():
    qrels = {}
    for line in get(BASE + "qrels/qrel_content_test.txt").splitlines():
        p = line.split()
        if len(p) >= 4:
            qrels.setdefault(p[0], {})[p[2]] = int(p[3])
    rows = []
    for f in sorted((ROOT / "benchmarks/clef_tar").glob("*.json")):
        t = json.loads(f.read_text())
        topic = t["topic"]
        rel = {pid for pid, r in qrels[topic].items() if r == 1}
        original = set(qrels[topic])
        query = expand_line(t["pubmed"], len(t["pubmed"]) - 1)
        ours = set(pubmed._ids(query))
        found = rel & ours
        cutoff = max(int(x) for x in original)
        ours_dated = {x for x in ours if int(x) <= cutoff}
        rows.append((topic, len(rel), len(found), len(ours_dated), len(original), sorted(rel - ours)))
        print(f"{topic}: recall {len(found)}/{len(rel)}  ours {len(ours_dated):,} (to review date) vs original {len(original):,}"
              f"  missed {sorted(rel - ours)}", flush=True)
    tot_rel = sum(r[1] for r in rows)
    tot_found = sum(r[2] for r in rows)
    print(f"\nOverall recall: {tot_found}/{tot_rel} = {tot_found / tot_rel:.1%};  topics with 100% recall: "
          f"{sum(1 for r in rows if r[1] == r[2])}/{len(rows)};  median size ratio (ours/original): "
          f"{sorted(r[3] / r[4] for r in rows)[len(rows) // 2]:.2f}")


if __name__ == "__main__":
    main()
