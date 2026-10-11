"""Search recall on CLEF eHealth TAR Cochrane reviews.

Strategies in benchmarks/clef_tar*/<topic>.json were written from the review *title only*, as the skill would,
without consulting the original Cochrane query. Recall is measured against the studies finally included in each
review (content-level qrels).

  uv run python benchmarks/clef_tar_recall.py                 # 2017 diagnostic accuracy topics
  uv run python benchmarks/clef_tar_recall.py --set 2019int   # 2019 intervention topics
  uv run python benchmarks/clef_tar_recall.py --set 2019int --cite   # + backward citation searching (OpenAlex)

--cite picks up to 3 systematic reviews from our own PubMed results that predate the target review
(PMID below the newest included study) and whose titles best match the review title, and adds their reference
lists, as the skill recommends. The included-study list is never used to choose seeds.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from litsearch import net  # noqa: E402
from litsearch.project import expand_line  # noqa: E402
from litsearch.sources import openalex, pubmed  # noqa: E402

SETS = {
    "2017dta": ("benchmarks/clef_tar", "https://raw.githubusercontent.com/CLEF-TAR/tar/master/2017-TAR/testing/qrels/qrel_content_test.txt", True),
    "2019int": ("benchmarks/clef_tar_2019_intervention",
                "https://raw.githubusercontent.com/CLEF-TAR/tar/master/2019-TAR/Task1/Testing/Intervention/qrels/task1.test.content.intervention.2019.qrels", False),
}


STOP = {"for", "and", "the", "with", "in", "of", "to", "or", "versus", "people", "patients", "adults", "children",
        "treating", "treatment", "preventing", "prevention", "interventions", "diagnosis", "detection", "a", "an", "at"}


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", s.lower()) if w not in STOP}


def backward_refs(query: str, cutoff: int, title: str, n: int = 3) -> tuple[set[str], list[str]]:
    """Seeds: systematic reviews in our results, older than the target review, whose titles best match the
    review title (what a searcher would pick; the included-study list is not used)."""
    srs = [x for x in pubmed._ids(f"({query}) AND systematic[sb]") if int(x) < cutoff]
    tw, scored = _words(title), []
    for i in range(0, len(srs), 200):
        s = net.post_json(pubmed.EUTILS + "esummary.fcgi", {"db": "pubmed", "id": ",".join(srs[i:i + 200]), "retmode": "json"})
        for pid in s["result"].get("uids", []):
            scored.append((len(tw & _words(s["result"][pid].get("title", ""))), int(pid), pid))
    seeds = [pid for sc, _n, pid in sorted(scored, reverse=True) if sc >= 2][:n]
    refs = set()
    for s in seeds:
        try:
            w = openalex.resolve(s)
        except Exception as e:  # noqa: BLE001
            print(f"    seed {s}: {e}", file=sys.stderr)
            continue
        for x in openalex._batch(w.get("referenced_works", [])):
            pm = ((x.get("ids") or {}).get("pmid") or "").rsplit("/", 1)[-1]
            if pm:
                refs.add(pm)
    return refs, seeds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="2017dta", choices=SETS)
    ap.add_argument("--cite", action="store_true")
    a = ap.parse_args()
    folder, qurl, has_original = SETS[a.set]
    qrels = {}
    for line in urllib.request.urlopen(qurl, timeout=60).read().decode().splitlines():
        p = line.split()
        if len(p) >= 4:
            qrels.setdefault(p[0], {})[p[2]] = int(p[3])
    rows = []
    for f in sorted((ROOT / folder).glob("*.json")):
        t = json.loads(f.read_text())
        topic = t["topic"]
        rel = {pid for pid, r in qrels.get(topic, {}).items() if r == 1}
        if not rel:
            continue
        query = expand_line(t["pubmed"], len(t["pubmed"]) - 1)
        ours = set(pubmed._ids(query))
        cutoff = max(int(x) for x in (qrels[topic] if has_original else rel))
        size = sum(1 for x in ours if int(x) <= cutoff)
        found = rel & ours
        extra, seeds = set(), []
        if a.cite:
            refs, seeds = backward_refs(query, max(int(x) for x in rel), t["title"])
            extra = (rel & refs) - ours
        orig = f" vs original {len(qrels[topic]):,}" if has_original else ""
        cite_txt = f"  +citation {len(extra)} (seeds {','.join(seeds) or 'none'})" if a.cite else ""
        print(f"{topic}: recall {len(found)}/{len(rel)}  size {size:,}{orig}{cite_txt}  missed {sorted(rel - ours - extra)}", flush=True)
        rows.append((topic, len(rel), len(found), len(extra), size))
    R = sum(r[1] for r in rows); F = sum(r[2] for r in rows); E = sum(r[3] for r in rows)
    print(f"\nPubMed strategy recall: {F}/{R} = {F / R:.1%}; topics at 100%: {sum(1 for r in rows if r[1] == r[2])}/{len(rows)}")
    if a.cite:
        print(f"With backward citation searching: {F + E}/{R} = {(F + E) / R:.1%}; topics at 100%: "
              f"{sum(1 for r in rows if r[1] == r[2] + r[3])}/{len(rows)}")


if __name__ == "__main__":
    main()
