"""Text-pattern flags used for screening aids (xlsx columns and EndNote smart groups).

These are not filters: every record stays in the library. They mirror common librarian EndNote smart groups
(random*, systematic review, placebo, meta-analysis) and add a few more screening buckets.
"""
from __future__ import annotations

import re

# (key, label, EndNote smart-group search term, regex over title+abstract+keywords+pubtypes)
FLAGS = [
    ("rct", "random*", "random*", r"\brandomi[sz]|\brandom(ly)? (assign|allocat)|\brandomised|\brandomized|\brct\b"),
    ("sr", "systematic review", "systematic", r"systematic(al)? (literature )?review|systematic search"),
    ("placebo", "placebo", "placebo", r"\bplacebo"),
    ("ma", "meta-analysis", "meta-analy", r"meta-?analy|network meta|pooled analysis"),
    ("case", "case report/series", "case report", r"\bcase reports?\b|\bcase series\b|\ba case of\b"),
    ("review", "review", "review", r"\breview\b"),
    ("guideline", "guideline", "guideline", r"\bguidelines?\b|consensus statement|practice parameter"),
    ("trialreg", "trial registration", "", r"$^"),
]


def flags(r: dict) -> dict:
    text = " ".join([r["title"], r["abstract"], " ".join(r["keywords"]), " ".join(r["pubtypes"])]).lower()
    out = {}
    for key, _label, _term, rx in FLAGS:
        out[key] = bool(re.search(rx, text))
    if any("randomized controlled trial" in p.lower() for p in r["pubtypes"]):
        out["rct"] = True
    if any(p.lower() in ("review", "systematic review") for p in r["pubtypes"]):
        out["review"] = True
    out["trialreg"] = r["type"] == "TRIAL"
    return out
