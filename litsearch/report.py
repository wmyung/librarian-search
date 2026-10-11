"""Statistics, PRISMA-S items, methods paragraph, reply-letter draft, RIS export and md->docx."""
from __future__ import annotations

import re
from pathlib import Path

from .classify import FLAGS
from .project import db_info


def fmt_date_en(d: str) -> str:
    import datetime as dt
    try:
        x = dt.date.fromisoformat(d)
        return x.strftime("%-d %B %Y")
    except ValueError:
        return d


def db_dates(strategy: dict, ctx: dict) -> dict:
    out = {}
    for e in strategy.get("databases", []):
        out[e["id"]] = e.get("search_date") or ctx["search_date"]
    return out


def prisma_s(strategy: dict, ctx: dict) -> list[tuple]:
    dbs = [d for d in ctx["db_order"] if d not in ("ctgov", "ictrp", "citation")]
    regs = [d for d in ctx["db_order"] if d in ("ctgov", "ictrp")]
    dates = db_dates(strategy, ctx)
    cit = ctx.get("citation_log") or []
    order = " > ".join(db_info(d)["short"] for d in ctx["db_order"])
    return [
        (1, "Database name", "; ".join(f"{db_info(d)['name']} ({db_info(d)['platform']})" for d in dbs)),
        (2, "Multi-database searching", "Each database was searched separately (no simultaneous multi-database searching)."),
        (3, "Study registries", "; ".join(db_info(d)["platform"] for d in regs) or "Not searched"),
        (4, "Online resources and browsing", strategy.get("other_sources", "Not applicable")),
        (5, "Citation searching", (f"Backward (reference lists) and forward (citing articles) citation searching of {len(cit)} key "
                                   f"articles using OpenAlex ({ctx.get('citation_date', '')})") if cit
         else "Not performed (recommended once key trials and systematic reviews are identified)"),
        (6, "Contacts", strategy.get("contacts", "Not applicable")),
        (7, "Other methods", strategy.get("other_methods", "Not applicable")),
        (8, "Full search strategies", "All strategies are in the 'Search strategy' sheet of this workbook (suitable as a supplementary table)"),
        (9, "Limits and restrictions", strategy.get("limits_en") or strategy.get("limits", "")),
        (10, "Search filters", strategy.get("filters", "No study-design search filters were used")),
        (11, "Prior work", strategy.get("prior_work", "Not applicable")),
        (12, "Updates", strategy.get("updates", "Not applicable")),
        (13, "Dates of searches", "; ".join(f"{db_info(d)['short']}: {dates.get(d, ctx['search_date'])}" for d in ctx["db_order"] if d != "citation")),
        (14, "Peer review", strategy.get("peer_review", "No formal peer review of the search strategy (PRESS); librarian review recommended if required")),
        (15, "Total records", "; ".join(f"{db_info(d)['short']} {ctx['retrieved'].get(d, 0)}" for d in ctx["db_order"]) +
         f" (total {ctx['total_retrieved']})"),
        (16, "Deduplication", f"Automated deduplication on DOI or PMID match, or normalised title + publication year (+/-1) + first author; "
                              f"the record from the highest-priority source was kept ({order}). {ctx['n_dups']} duplicates removed, "
                              f"{ctx['n_unique']} unique records. Removed records remain in the EndNote library Trash for audit."),
    ]


def methods_en(strategy: dict, ctx: dict) -> str:
    dates = db_dates(strategy, ctx)
    dbs = [d for d in ctx["db_order"] if d not in ("ctgov", "ictrp", "citation", "europepmc")]
    phr = {"pubmed": "MEDLINE (via PubMed)", "ovid_medline": "MEDLINE (via Ovid)", "embase": "Embase (via Embase.com)",
           "cochrane": "the Cochrane Library (Cochrane Database of Systematic Reviews and CENTRAL)",
           "wos": "Web of Science Core Collection", "scopus": "Scopus", "psycinfo": "APA PsycInfo", "cinahl": "CINAHL"}
    names = [phr.get(d, db_info(d)["name"]) for d in dbs]
    if "europepmc" in ctx["db_order"]:
        names.append("Europe PMC")
    lst = ", ".join(names[:-1]) + (", and " if len(names) > 2 else " and ") + names[-1] if len(names) > 1 else (names[0] if names else "")
    uniq_dates = sorted({dates.get(d, ctx["search_date"]) for d in ctx["db_order"] if d != "citation"})
    when = fmt_date_en(uniq_dates[0]) if len(uniq_dates) == 1 else "between " + fmt_date_en(uniq_dates[0]) + " and " + fmt_date_en(uniq_dates[-1])
    concepts = [c for c in strategy.get("concepts", []) if c.get("name")]
    cpt = "; ".join(f"{c['name']} ({', '.join(c.get('terms', [])[:12])})" for c in concepts)
    p = [f"A comprehensive literature search was conducted in {lst} from inception to {when}."]
    if cpt:
        vocab = [v for d, v in (("pubmed", "MeSH"), ("ovid_medline", "MeSH"), ("embase", "Emtree"), ("cochrane", "MeSH"),
                                ("psycinfo", "APA Thesaurus"), ("cinahl", "CINAHL Headings")) if d in ctx["db_order"]]
        vocab = list(dict.fromkeys(vocab))
        vtxt = f"controlled vocabulary ({' and '.join(vocab)}) and " if vocab else ""
        p.append(f"Search strategies combined {vtxt}free-text terms for the following concepts: {cpt}.")
    p.append(strategy.get("limits_en") or strategy.get("limits") or "No restrictions on study design, language, or publication date were applied.")
    if any(d in ctx["db_order"] for d in ("ctgov", "ictrp")):
        regs = [("ClinicalTrials.gov" if d == "ctgov" else "the WHO ICTRP") for d in ctx["db_order"] if d in ("ctgov", "ictrp")]
        p.append(f"Ongoing and unpublished studies were sought in {' and '.join(regs)}.")
    if ctx.get("citation_log"):
        n = len([s for s in ctx["citation_log"] if not s.get("error")])
        p.append(f"Backward and forward citation searching of {n} key article{'s' if n != 1 else ''} was performed using OpenAlex"
                 f" on {fmt_date_en(ctx.get('citation_date', ctx['search_date']))}.")
        fa = (strategy.get("citation") or {}).get("filter_applied")
        if fa:
            p.append(f"Of the {fa['before']:,} citation records, {fa['after']:,} whose title, abstract, or keywords contained "
                     "terms for both key concepts were retained.")
    p.append(f"In total, {ctx['total_retrieved']:,} records were retrieved; after removal of {ctx['n_dups']:,} duplicates "
             f"(matching on DOI, PMID, and normalised title, publication year, and first author; EndNote 21), "
             f"{ctx['n_unique']:,} unique records remained for screening.")
    p.append("The full search strategies for each source are provided in Supplementary Table S1.")
    return " ".join(p)


def letter_draft(strategy: dict, ctx: dict) -> str:
    t = strategy.get("title")
    dates = db_dates(strategy, ctx)
    if ctx.get("citation_date"):
        dates["citation"] = ctx["citation_date"]
    multi = len({dates.get(d, ctx["search_date"]) for d in ctx["db_order"]}) > 1
    rows = "\n".join(f"| {db_info(d)['name']} | " + (f"{dates.get(d, ctx['search_date'])} | " if multi else "") +
                     f"{ctx['retrieved'].get(d, 0):,} | {ctx['contributed'].get(d, 0):,} |" for d in ctx["db_order"])
    head = ("| Source | Search date | Records retrieved | Unique contribution |\n|---|---|---:|---:|" if multi
            else "| Source | Records retrieved | Unique contribution |\n|---|---:|---:|")
    total = f"| **Total** | {'| ' if multi else ''}**{ctx['total_retrieved']:,}** | **{ctx['n_unique']:,}** |"
    when = "The results were as follows." if multi else f"The results as of {fmt_date_en(ctx['search_date'])} were as follows."
    flags = ", ".join(f"{lbl} {ctx['flag_counts'].get(k, 0)}" for k, lbl, _t, _r in FLAGS if ctx["flag_counts"].get(k))
    concepts = "\n".join(f"- **{c['name']}**: {', '.join(c.get('terms', []))}" for c in strategy.get("concepts", []) if c.get("name"))
    cit = ctx.get("citation_log") or []
    cit_txt = (f"Reference lists and citing articles of {len(cit)} key article{'s' if len(cit) != 1 else ''} were checked, "
               f"adding {ctx['contributed'].get('citation', 0)} records not found by the database searches."
               if cit else "Once the key trials or systematic reviews are identified, we recommend checking their reference lists "
                           "and citing articles (citation searching).")
    sources = ", ".join(db_info(d)["name"] for d in ctx["db_order"] if d != "citation")
    return f"""Dear Researcher,

Thank you for your request regarding "{t}". We have completed the literature search and summarise it below.

## 1. Search strategy

{{{{2-3 sentences on how the scope was set in light of the review objective (e.g., no restriction by study design or outcome)}}}}

We searched {sources}, combining each database's controlled vocabulary with free-text terms for every concept.

{concepts}

## 2. Results and screening

{when}

{head}
{rows}
{total}

After deduplication, {ctx['n_unique']:,} unique records remain. To support screening, records are flagged by title, abstract and keywords ({flags}). These flags are screening aids, not search limits; every record is retained.

{{{{2-3 sentences of screening advice suited to the review type}}}}

## 3. Supplementary searching

{cit_txt}

## 4. Attachments

- Search strategy workbook (.xlsx): full line-by-line strategies with hit counts, record list for screening, deduplication log, PRISMA-S
- EndNote library (.zip): one group per source, smart groups (random*, systematic review, placebo, meta-analysis, etc.), duplicates kept in the Trash
- RIS file for other tools (Zotero, Covidence, Rayyan)
- Draft methods text for the manuscript: methods_PRISMA-S.md

We hope this is helpful for your research.

Kind regards,
"""


# ---------------------------------------------------------------- RIS export
RIS_TY = {"JOUR": "JOUR", "BOOK": "BOOK", "CHAP": "CHAP", "CONF": "CONF", "THES": "THES", "RPRT": "RPRT",
          "TRIAL": "DBASE", "PREPRINT": "JOUR", "GEN": "GEN"}


def write_ris(path: Path, recs: list[dict]) -> None:
    out = []
    for r in recs:
        L = [f"TY  - {RIS_TY.get(r['type'], 'GEN')}", f"ID  - {r['uid']}"]
        L += [f"AU  - {a}" for a in r["authors"]]
        for tag, key in (("TI", "title"), ("T2", "journal"), ("PY", "year"), ("VL", "volume"), ("IS", "issue"),
                         ("AB", "abstract"), ("DO", "doi"), ("SN", "issn"), ("LA", "language"), ("AD", "address")):
            if r.get(key):
                L.append(f"{tag}  - {r[key]}")
        if r["pages"]:
            sp, _, ep = r["pages"].partition("-")
            L.append(f"SP  - {sp}")
            if ep:
                L.append(f"EP  - {ep}")
        L += [f"KW  - {k}" for k in dict.fromkeys(r["keywords"])]
        L += [f"UR  - {u}" for u in dict.fromkeys(r["urls"])]
        if r["pmid"]:
            L.append(f"AN  - {r['pmid']}")
        elif r["accession"]:
            L.append(f"AN  - {r['accession']}")
        L.append(f"DB  - {', '.join(db_info(d)['short'] for d in r.get('found_in', [r['db']]))}")
        L.append("ER  - ")
        out.append("\n".join(L))
    path.write_text("\n\n".join(out) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- markdown -> docx
def md_to_docx(md: str, path: Path) -> None:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)

    def add_runs(par, text):
        for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
            if part:
                run = par.add_run(part)
                run.bold = i % 2 == 1

    lines = md.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|"):
            tbl = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    tbl.append(cells)
                i += 1
            t = doc.add_table(rows=len(tbl), cols=max(len(r) for r in tbl))
            t.style = "Table Grid"
            for r, row in enumerate(tbl):
                for c, val in enumerate(row):
                    add_runs(t.cell(r, c).paragraphs[0], val)
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", ln)
        if m:
            doc.add_heading(m.group(2), level=len(m.group(1)))
        elif re.match(r"^\s*[-*]\s+", ln):
            add_runs(doc.add_paragraph(style="List Bullet"), re.sub(r"^\s*[-*]\s+", "", ln))
        elif re.match(r"^\s*\d+\.\s+", ln):
            add_runs(doc.add_paragraph(style="List Number"), re.sub(r"^\s*\d+\.\s+", "", ln))
        elif ln.strip():
            add_runs(doc.add_paragraph(), ln)
        i += 1
    doc.save(path)
