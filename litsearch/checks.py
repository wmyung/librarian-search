"""Search-line checks and search profiles.

* lint_strategy: syntax slips that silently change a manual-database search (unquoted phrases on platforms that AND
  bare words, single-letter tokens, another platform's operators). Lesson from a librarian's PsycInfo line
  `XB (TEMPS A)`: unquoted on EBSCOhost it matched the French word "temps", and 88% of the 3,578 records were noise.
* noise_report: share of imported records with no term of a strategy concept in title/abstract/keywords.
* profiles: "comprehensive" (default) adds OpenAlex citation searching; "systematic" uses only sources that
  journals accept as reportable, reproducible searches (PRISMA-S).
"""
from __future__ import annotations

import re
from collections import Counter

from .project import db_info

PROFILES = ("comprehensive", "systematic")
# Sources accepted in the systematic profile: bibliographic databases and trial registries searched with a
# reproducible query, and citation searching done in a citation index (exported and imported).
SYSTEMATIC_SOURCES = {"pubmed", "ovid_medline", "embase", "cochrane", "wos", "scopus", "psycinfo", "cinahl",
                      "koreamed", "kmbase", "europepmc", "ctgov", "ictrp", "citation_scopus", "citation_wos"}
NOT_SYSTEMATIC = {"citation": "OpenAlex citation searching (open index whose reference lists and coverage change "
                              "between snapshots; do citation searching in Scopus or Web of Science instead)"}


def profile(strategy: dict) -> str:
    p = strategy.get("profile") or "comprehensive"
    if p not in PROFILES:
        raise SystemExit(f"strategy.json profile must be one of {', '.join(PROFILES)} (got {p!r})")
    return p


def profile_problems(strategy: dict, db_ids) -> list[str]:
    """Sources that the systematic profile does not allow, with the reason."""
    if profile(strategy) != "systematic" or strategy.get("allow_nonstandard_sources"):
        return []
    return [f"{db_info(d)['name']}: {NOT_SYSTEMATIC.get(d.split(':')[0], 'not a reportable bibliographic source')}"
            for d in db_ids if d.split(":")[0] not in SYSTEMATIC_SOURCES]


def systematic_gaps(strategy: dict, db_ids) -> list[str]:
    """Usual minimum for a systematic review (Cochrane Handbook ch. 4: MEDLINE, Embase, CENTRAL + subject databases)."""
    if profile(strategy) != "systematic":
        return []
    have = {d.split(":")[0] for d in db_ids}
    out = []
    if not have & {"pubmed", "ovid_medline"}:
        out.append("MEDLINE (PubMed or Ovid) is missing")
    if "embase" not in have:
        out.append("Embase is missing")
    if "cochrane" not in have:
        out.append("Cochrane Library (CENTRAL) is missing")
    if not have & {"ctgov", "ictrp"}:
        out.append("no trial registry (ClinicalTrials.gov or WHO ICTRP)")
    for d in strategy.get("subject_databases", []):
        if d not in have:
            out.append(f"subject database {db_info(d)['name']} is planned but has no records")
    return out


# ------------------------------------------------------------------ line lint
_OVID = {"ovid_medline"}
_EBSCO = {"cinahl"}
_OPS = re.compile(r"^(and|or|not|near(/\d+)?|next(/\d+)?|adj\d*|n\d+|w\d+|pre/\d+|same|w/\d+)$", re.I)
_TOKEN = r"[A-Za-z][\w\-]*(?:/\d+)?\*?"
_FIELD_SUFFIX = re.compile(r"(\.[a-z]{2}(,[a-z]{2})*\.|:[a-z]{2,3}(,[a-z]{2,3})*|/(exp|de|mj)\b|\[[^\]]*\])", re.I)
_PREFIX = re.compile(r"\b(TS|TI|AB|AK|KP|TITLE-ABS-KEY|TITLE|ABS|KEY|XB|TX|MH|MM|SU|ZU)\s*=?\s*(?=\()", re.I)
# EBSCOhost field codes before a bare term (TI temperament OR AB temperament): upper case only, so the words ab/ti stay
_EBSCO_CODE = re.compile(r"\b(TI|AB|XB|TX|MH|MM|SU|ZU|DE|KW|SO|AU)\s+(?=[\w\"(])")


def _platform(entry: dict) -> str:
    plat = (entry.get("platform") or "").lower()
    base = entry["id"].split(":")[0]
    if "ovid" in plat or base in _OVID:
        return "ovid"
    if "ebsco" in plat or base in _EBSCO:
        return "ebsco"
    return base


def _bare(q: str) -> str:
    """The query with quoted phrases, field tags and line references removed."""
    q = re.sub(r"MeSH descriptor: \[[^\]]*\]( explode all trees| this term only)?", " ", q, flags=re.I)
    q = re.sub(r'"[^"]*"|\'[^\']*\'', " ", q)
    q = _FIELD_SUFFIX.sub(" ", q)
    q = _PREFIX.sub(" ", q)
    q = _EBSCO_CODE.sub(" ", q)
    q = re.sub(r"#\d+|\bS\d+\b", " ", q)
    return q


def lint_line(entry: dict, q) -> list[str]:
    if not isinstance(q, str) or not q.strip():
        return []
    plat = _platform(entry)
    out = []
    if plat == "ovid" and re.search(r"#\d", q):
        out.append("Ovid line references have no '#': write '1 or 2'")
    if plat != "ovid" and re.search(r"\badj\d*\b", q, re.I):
        out.append("'adjN' is Ovid syntax; use NEAR/n (Embase, Cochrane, WoS), Nn (EBSCO) or [tiab:~n] (PubMed)")
    if plat == "ovid" and re.search(r"\b(near|next)/\d", q, re.I):
        out.append("NEAR/n is not Ovid syntax; use adjN")
    if plat not in ("pubmed", "europepmc") and re.search(r"\[(tiab|mesh|tw|ti|ab)\b", q, re.I):
        out.append("PubMed field tags ([tiab], [Mesh]) in a non-PubMed line")
    if plat in ("pubmed", "ovid"):
        bare_ok = True   # adjacent words are a phrase (PubMed via ATM/phrase index, Ovid always)
    else:
        bare_ok = False
    words = re.findall(_TOKEN, _bare(q))
    single = sorted({w for w in words if len(w) == 1 and not _OPS.match(w)})
    if single:
        out.append(f"bare single-letter token(s) {', '.join(single)}: stop words are dropped, so the rest of the phrase "
                   f"matches on its own (e.g. TEMPS A -> TEMPS, which also matches French 'temps'); quote the phrase")
    if not bare_ok:
        toks = re.findall(r"\(|\)|" + _TOKEN, _bare(q))
        runs, cur = [], []
        for t in toks + [")"]:
            if t in "()" or _OPS.match(t):
                if len(cur) >= 2:
                    runs.append(" ".join(cur))
                cur = []
            else:
                cur.append(t)
        if runs:
            out.append(f"unquoted multi-word term(s) {'; '.join(repr(r) for r in runs[:4])}: on this platform bare words "
                       f"are ANDed, not searched as a phrase; quote them or use a proximity operator")
    return out


def lint_strategy(strategy: dict, only_manual: bool = False) -> list[tuple[str, int, str]]:
    """[(db id, line number, message)] for every search line."""
    out = []
    for e in strategy.get("databases", []):
        if only_manual and db_info(e["id"])["mode"] != "manual":
            continue
        for i, ln in enumerate(e.get("lines", [])):
            for msg in lint_line(e, ln.get("q")):
                out.append((e["id"], i + 1, msg))
    return out


# ------------------------------------------------------------------ concept noise check
def _term_patterns(concept: dict) -> list[re.Pattern]:
    if concept.get("check"):
        return [re.compile(concept["check"], re.I)]
    pats = []
    for term in concept.get("terms", []):
        t = re.sub(r"\[[^\]]*\]", " ", term)
        for piece in re.split(r"[/;]| OR ", t):
            piece = " ".join(piece.split()).strip(" ,.\"'")
            if len(piece) < 3:
                continue
            rx = re.escape(piece).replace(r"\*", r"\w*").replace(r"\-", r"[\s\-]?").replace(r"\ ", r"[\s\-]+")
            pats.append(re.compile(r"(?<![a-z0-9])" + rx, re.I))
    return pats


def noise_report(strategy: dict, records: list[dict]) -> dict:
    """Records with no term of a concept in title, abstract or keywords. Terms come from strategy concepts (or their
    'check' regex). Records without an abstract are counted separately because title-only matching misses terms."""
    concepts = [c for c in strategy.get("concepts", []) if c.get("name") and (c.get("terms") or c.get("check"))]
    if not concepts or not records:
        return {}
    # Each concept is an AND block unless "noise_groups" lists the concepts that the search ORs together,
    # e.g. [["TEMPS-A", "affective temperament"], ["mood disorders"]].
    by_name = {c["name"]: _term_patterns(c) for c in concepts}
    groups = strategy.get("noise_groups") or [[c["name"]] for c in concepts]
    pats = [(" OR ".join(g), [p for name in g for p in by_name.get(name, [])]) for g in groups]
    miss, miss_by, langs, sample, no_abs = 0, Counter(), Counter(), [], 0
    for r in records:
        text = " ".join([r.get("title") or "", r.get("abstract") or "", " ".join(r.get("keywords") or [])])
        failed = [name for name, ps in pats if ps and not any(p.search(text) for p in ps)]
        if failed:
            miss += 1
            miss_by.update(failed)
            langs[(r.get("language") or "?").lower()[:3]] += 1
            no_abs += not r.get("abstract")
            if len(sample) < 8:
                sample.append(r.get("title") or "")
    return {"records": len(records), "no_concept_term": miss, "share": miss / len(records), "by_concept": dict(miss_by),
            "languages": dict(langs.most_common(5)), "without_abstract": no_abs, "sample_titles": sample}
