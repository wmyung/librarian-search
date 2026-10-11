"""Features adapted from other evidence-synthesis tools.

* validation set recall (librarian practice; TrialMind / Wang et al. seed-study checks)
* source overlap (CiteSource)
* previously screened records for update searches (SR-Accelerator Deduplicator)
* ASReview handoff CSV (ASReview)
* PRISMA 2020 flow diagram, identification stage (PRISMA 2020)
* candidate term suggestions from controlled vocabulary and keywords (litsearchr)
"""
from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

from .dedup import deduplicate
from .project import db_info, expand_line
from .records import norm_doi


# ------------------------------------------------------------------ validation set
def parse_known(items: list[str]) -> list[dict]:
    out = []
    for it in items:
        it = it.strip()
        if not it or it.startswith("#"):
            continue
        if re.fullmatch(r"(pmid:)?\d{5,9}", it, re.I):
            out.append({"id": it, "pmid": re.sub(r"\D", "", it), "doi": ""})
        elif norm_doi(it):
            out.append({"id": it, "pmid": "", "doi": norm_doi(it)})
    return out


def match_known(known: list[dict], unique: list[dict], dups: list[dict]) -> list[dict]:
    """For each known study: found or not, and in which sources."""
    allrecs = unique + dups
    res = []
    for k in known:
        hits = [r for r in allrecs if (k["pmid"] and r["pmid"] == k["pmid"]) or (k["doi"] and r["doi"] == k["doi"])]
        dbs = sorted({r["db"] for r in hits})
        res.append({**k, "found": bool(hits), "sources": dbs,
                    "title": (hits[0]["title"] if hits else ""), "uid": (hits[0].get("dup_of") or hits[0]["uid"]) if hits else None})
    return res


def diagnose_pubmed(strategy: dict, missed_pmids: list[str]) -> dict:
    """Which PubMed strategy lines each missed PMID fails to match (shows the concept that lost it)."""
    from .sources import pubmed
    entry = next((e for e in strategy.get("databases", []) if e["id"] == "pubmed"), None)
    if not entry or not missed_pmids:
        return {}
    out = {}
    for pmid in missed_pmids:
        exists, _ = pubmed.count(f"{pmid}[uid]")
        if not exists:
            out[pmid] = {"in_pubmed": False, "failed_lines": []}
            continue
        failed = []
        for i, ln in enumerate(entry["lines"]):
            if not re.search(r"#\d", str(ln["q"])) or i == len(entry["lines"]) - 1:
                continue        # only check concept OR-combination lines
            n, _ = pubmed.count(f"({expand_line(entry['lines'], i)}) AND {pmid}[uid]")
            if not n:
                failed.append(i + 1)
        out[pmid] = {"in_pubmed": True, "failed_lines": failed}
    return out


# ------------------------------------------------------------------ source overlap
def overlap(unique: list[dict], db_order: list[str]) -> dict:
    found = [set(r["found_in"]) for r in unique]
    total = {d: sum(1 for f in found if d in f) for d in db_order}
    only = {d: sum(1 for f in found if f == {d}) for d in db_order}
    matrix = {a: {b: sum(1 for f in found if a in f and b in f) for b in db_order} for a in db_order}
    return {"in_source": total, "only_in_source": only, "matrix": matrix}


# ------------------------------------------------------------------ update searches
def mark_previous(unique: list[dict], previous: list[dict]) -> set[int]:
    """Return uids of current records already present in a previous search export."""
    if not previous:
        return set()
    cur = [dict(r, _uid=r["uid"], db="current") for r in unique]
    prev = [dict(r, db="previous") for r in previous]
    u, d = deduplicate(prev + cur, ["previous", "current"])
    prev_uids = {r["uid"] for r in u if r["db"] == "previous"}
    seen = set()
    for x in d:
        if x["db"] == "current" and x["dup_of"] in prev_uids:
            seen.add(x["_uid"])
    return seen


# ------------------------------------------------------------------ ASReview
def write_asreview_csv(path: Path, unique: list[dict], relevant_uids: set[int]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["record_id", "title", "abstract", "authors", "year", "journal", "doi", "pmid", "keywords", "included"])
        for r in unique:
            w.writerow([r["uid"], r["title"], r["abstract"], "; ".join(r["authors"]), r["year"], r["journal"],
                        r["doi"], r["pmid"], "; ".join(r["keywords"][:30]), 1 if r["uid"] in relevant_uids else ""])


# ------------------------------------------------------------------ PRISMA 2020 flow (identification)
def prisma_svg(ctx: dict) -> str:
    dbs = [d for d in ctx["db_order"] if d not in ("ctgov", "ictrp", "citation")]
    regs = [d for d in ctx["db_order"] if d in ("ctgov", "ictrp")]
    other = [d for d in ctx["db_order"] if d == "citation"]
    n = lambda ds: sum(ctx["retrieved"].get(d, 0) for d in ds)
    db_lines = [f"Databases (n = {n(dbs):,})"] + [f"  {db_info(d)['name']} (n = {ctx['retrieved'][d]:,})" for d in dbs]
    if regs:
        db_lines += [f"Registers (n = {n(regs):,})"] + [f"  {db_info(d)['name']} (n = {ctx['retrieved'][d]:,})" for d in regs]
    oth_lines = ([f"Citation searching (n = {n(other):,})"] if other else ["Other methods (n = )"])
    W, H = 900, 780

    def box(x, y, w, h, lines, bold_first=False):
        t = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="#fff" stroke="#333"/>']
        for i, ln in enumerate(lines):
            weight = ' font-weight="bold"' if bold_first and i == 0 else ""
            indent = 24 if ln.startswith("  ") else 10
            t.append(f'<text x="{x + indent}" y="{y + 22 + i * 18}" font-size="13"{weight}>{escape(ln.strip())}</text>')
        return "\n".join(t)

    def arrow(x1, y1, x2, y2):
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#333" marker-end="url(#a)"/>'

    h1 = max(80, 30 + 18 * len(db_lines))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H + h1 - 80}" font-family="Arial, sans-serif">',
        '<defs><marker id="a" markerWidth="10" markerHeight="7" refX="10" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#333"/></marker></defs>',
        f'<rect width="100%" height="100%" fill="#fff"/>',
        '<text x="20" y="28" font-size="15" font-weight="bold">PRISMA 2020 flow diagram (identification completed by librarian-search; screening counts to be filled in)</text>',
        box(20, 50, 420, h1, ["Records identified from:"] + db_lines, True),
        box(470, 50, 410, 80, ["Records removed before screening:", f"  Duplicate records removed (n = {ctx['n_dups']:,})"], True),
        arrow(440, 90, 470, 90),
    ]
    y = 50 + h1 + 40
    parts += [
        arrow(230, 50 + h1, 230, y),
        box(20, y, 420, 60, ["Records screened", f"(n = {ctx['n_unique']:,})"], True),
        box(470, y, 410, 60, ["Records excluded", "(n = )"], True), arrow(440, y + 30, 470, y + 30),
    ]
    y2 = y + 100
    parts += [arrow(230, y + 60, 230, y2), box(20, y2, 420, 60, ["Reports sought for retrieval", "(n = )"], True),
              box(470, y2, 410, 60, ["Reports not retrieved", "(n = )"], True), arrow(440, y2 + 30, 470, y2 + 30)]
    y3 = y2 + 100
    parts += [arrow(230, y2 + 60, 230, y3), box(20, y3, 420, 60, ["Reports assessed for eligibility", "(n = )"], True),
              box(470, y3, 410, 80, ["Reports excluded:", "  Reason 1 (n = )", "  Reason 2 (n = )"], True), arrow(440, y3 + 30, 470, y3 + 30)]
    y4 = y3 + 120
    parts += [arrow(230, y3 + 60, 230, y4), box(20, y4, 420, 60, ["Studies included in review", "(n = )"], True)]
    if other:
        parts.append(f'<text x="20" y="{y4 + 90}" font-size="12" fill="#555">{escape(oth_lines[0])} (identification via other methods) '
                     'was deduplicated together with the database and register records;</text>')
        parts.append(f'<text x="20" y="{y4 + 106}" font-size="12" fill="#555">the duplicates removed above include these records.</text>')
    parts.append("</svg>")
    return "\n".join(parts)


# ------------------------------------------------------------------ term suggestions
def suggest_terms(records: list[dict], strategy: dict, top: int = 30) -> list[tuple[str, int, str]]:
    """Frequent MeSH headings / keywords in the given records that the strategy text does not mention."""
    text = " ".join(str(ln.get("q", "")) for e in strategy.get("databases", []) for ln in e.get("lines", [])).lower()
    text += " " + " ".join(t.lower() for c in strategy.get("concepts", []) for t in c.get("terms", []))
    cnt, kind = Counter(), {}
    for r in records:
        seen = set()
        for k in r["keywords"]:
            k = re.sub(r"[*]", "", k).split("/")[0].strip()
            if 2 < len(k) < 60 and k.lower() not in seen:
                seen.add(k.lower())
                cnt[k] += 1
                kind.setdefault(k, "keyword/MeSH")
    stop = {"humans", "female", "male", "adult", "middle aged", "aged", "adolescent", "child", "animals", "infant",
            "young adult", "aged, 80 and over", "retrospective studies", "prospective studies", "treatment outcome",
            "surveys and questionnaires", "cross-sectional studies", "reproducibility of results", "risk factors",
            "cohort studies", "case-control studies", "follow-up studies", "longitudinal studies", "time factors",
            "psychometrics", "comorbidity", "prevalence", "incidence", "severity of illness index", "regression analysis",
            "logistic models", "odds ratio", "sex factors", "age factors", "socioeconomic factors", "pilot projects"}
    stems = set(re.findall(r"([a-z]{3,})\*", text))
    covered = lambda w: w in text or any(w.startswith(s) for s in stems)
    out = []
    for k, c in cnt.most_common():
        kl = k.lower()
        if kl in stop or kl in text or all(covered(w) for w in re.findall(r"[a-z]{4,}", kl)):
            continue
        out.append((k, c, kind[k]))
        if len(out) >= top:
            break
    return out
