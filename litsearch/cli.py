"""litsearch command line.

  librarian-search init DIR --request (FILE | Google Docs URL | .gdoc) [--profile systematic]   new request folder + strategy.json skeleton
  librarian-search mesh TERM ...                                          look up MeSH headings and entry terms
  librarian-search count DIR [--db pubmed]                                per-line hit counts for automatic sources (iterate)
  librarian-search run DIR [--db pubmed]                                  counts + retrieve records for the final line
  librarian-search lint DIR                                               syntax checks of every search line (manual databases too)
  librarian-search dropped DIR --from 6 --to 12                           PubMed records a later line loses (what an extra concept costs)
  librarian-search import DIR --db embase FILE [FILE ...]                 import manual-database exports (RIS/MEDLINE/WoS)
  librarian-search set-counts DIR --db embase 15862 4398 ...              record per-line counts for a manual database
  librarian-search cite DIR [--seed DOI|PMID ...] [--direction both]      OpenAlex citation searching (comprehensive profile)
  librarian-search build DIR                                              deduplicate + deliverables (xlsx, EndNote, RIS, methods, letter draft)
  librarian-search validate DIR --known PMID|DOI ...               recall of a validation set + diagnosis
  librarian-search suggest DIR [--from-known]                      candidate terms missing from the strategy
  librarian-search build DIR --previous OLD.ris                    update search: mark previously screened
  librarian-search status DIR                                             progress summary
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
import zipfile
from collections import Counter
from pathlib import Path

from . import net
from .checks import (NOT_SYSTEMATIC, SYSTEMATIC_SOURCES, lint_strategy, noise_report, profile, profile_problems,
                     systematic_gaps)
from .classify import flags as compute_flags
from .dedup import deduplicate
from .endnote import write_library
from .excel import build_workbook
from .extras import (diagnose_pubmed, mark_previous, match_known, overlap, parse_known, prisma_svg,
                     suggest_terms, write_asreview_csv)
from .parsers import parse_file
from .project import DEFAULT_PRIORITY, SKELETON, Project, db_info, expand_line, final_index
from .records import load_jsonl, save_jsonl
from .report import letter_draft, md_to_docx, methods_en, prisma_s, write_ris
from .sources import ctgov, europepmc, openalex, pubmed

AUTO = {"pubmed": pubmed, "europepmc": europepmc, "ctgov": ctgov}


def today() -> str:
    return dt.date.today().isoformat()


def _say(msg: str) -> None:
    print(msg, file=sys.stderr)


# ------------------------------------------------------------------ init
def read_request(src: str) -> str:
    p = Path(src).expanduser()
    doc_id = None
    if p.exists() and p.suffix == ".gdoc":
        doc_id = json.loads(p.read_text())["doc_id"]
    elif p.exists():
        if p.suffix.lower() == ".docx":
            from docx import Document
            return "\n".join(par.text for par in Document(p).paragraphs)
        return p.read_text(encoding="utf-8")
    else:
        m = re.search(r"/document/d/([A-Za-z0-9_-]+)", src)
        if m:
            doc_id = m.group(1)
    if doc_id:
        try:
            return net.request(f"https://docs.google.com/document/d/{doc_id}/export", {"format": "txt"}).decode("utf-8-sig")
        except RuntimeError as e:
            raise SystemExit(f"Could not read the Google Doc (check sharing, or save the text to a file): {e}")
    return src  # treat as literal request text


def cmd_init(a):
    root = Path(a.dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    proj = Project(root)
    if a.request:
        (root / "request.md").write_text(read_request(a.request).strip() + "\n", encoding="utf-8")
        _say(f"Request saved: {root / 'request.md'}")
    if not proj.strategy_path.exists():
        st = json.loads(json.dumps(SKELETON))
        st["profile"] = a.profile
        if a.profile == "systematic":
            st["databases"].insert(5, {"id": "psycinfo", "platform": "", "lines": [{"q": "", "results": None}], "final": None})
            st["citation"] = {"seeds": [], "platform": "scopus"}
        proj.save(st)
        _say(f"strategy.json skeleton created ({a.profile} profile): {proj.strategy_path}")
    print(root)


def cmd_mesh(a):
    for term in a.terms:
        res = pubmed.mesh_lookup(term)
        print(json.dumps({"query": term, "results": res}, ensure_ascii=False, indent=1))


# ------------------------------------------------------------------ count / run
def _auto_entries(strategy, only):
    for e in strategy.get("databases", []):
        if e["id"] in AUTO and (not only or e["id"] in only) and e.get("lines") and any(l.get("q") for l in e["lines"]):
            yield e


def _count_entry(e) -> list[dict]:
    mod = AUTO[e["id"]]
    out = []
    for i, ln in enumerate(e["lines"]):
        q = expand_line(e["lines"], i)
        n, trans = mod.count(q)
        out.append({"line": i + 1, "q": ln["q"], "expanded": q, "count": n, "translation": trans})
        _say(f"  {db_info(e['id'])['short']} #{i + 1}: {n:>8,}  {str(ln['q'])[:90]}")
    return out


def cmd_count(a, fetch=False):
    proj = Project(Path(a.dir).expanduser())
    st = proj.load()
    counts_path = proj.runs_dir / "counts.json"
    counts = json.loads(counts_path.read_text()) if counts_path.exists() else {}
    for e in _auto_entries(st, a.db):
        db = e["id"]
        _say(f"[{db_info(db)['name']}]")
        res = _count_entry(e)
        counts[db] = {"date": today(), "lines": res}
        for ln, r in zip(e["lines"], res):
            ln["results"] = r["count"]
        if fetch:
            fi = final_index(e)
            q = expand_line(e["lines"], fi)
            recs = AUTO[db].fetch(q)
            save_jsonl(proj.records_dir / f"{db}.jsonl", recs)
            e["search_date"] = today()
            _say(f"  -> retrieved {len(recs):,} records (final line #{fi + 1}: {res[fi]['count']:,})")
    _report_lint(st)
    proj.runs_dir.mkdir(parents=True, exist_ok=True)
    counts_path.write_text(json.dumps(counts, ensure_ascii=False, indent=1), encoding="utf-8")
    if fetch:
        st["search_date"] = today()
    proj.save(st)


def cmd_run(a):
    cmd_count(a, fetch=True)


def _report_lint(st) -> int:
    issues = lint_strategy(st)
    for db, n, msg in issues:
        _say(f"  ! {db_info(db)['short']} #{n}: {msg}")
    return len(issues)


def cmd_lint(a):
    st = Project(Path(a.dir).expanduser()).load()
    if not _report_lint(st):
        _say("No syntax issues found.")


def cmd_dropped(a):
    """PubMed records matched by line --from but not by line --to: what a later concept (AND) removes."""
    st = Project(Path(a.dir).expanduser()).load()
    e = next((x for x in st.get("databases", []) if x["id"] == "pubmed"), None)
    if not e:
        raise SystemExit("No PubMed block in strategy.json")
    q = f"({expand_line(e['lines'], a.from_line - 1)}) NOT ({expand_line(e['lines'], a.to_line - 1)})"
    n, _ = pubmed.count(q)
    _say(f"PubMed #{a.from_line} NOT #{a.to_line}: {n:,} records lost by the later line(s)")
    for pmid, year, title in pubmed.titles(q, a.sample):
        print(f"{pmid}\t{year}\t{title}")


# ------------------------------------------------------------------ import / set-counts
def cmd_import(a):
    proj = Project(Path(a.dir).expanduser())
    st = proj.load()
    recs = []
    for f in a.files:
        got = parse_file(Path(f).expanduser(), a.db)
        _say(f"  {f}: {len(got):,} records")
        recs.extend(got)
    for problem in profile_problems(st, [a.db]):
        raise SystemExit(f"Systematic profile: {problem}. Set \"allow_nonstandard_sources\": true to override.")
    dest = proj.records_dir / f"{a.db}.jsonl"
    if a.append:
        recs = load_jsonl(dest) + recs
    save_jsonl(dest, recs)
    e = proj.db_entry(st, a.db)
    e["search_date"] = a.date or e.get("search_date") or today()
    e["imported_files"] = sorted(set(e.get("imported_files", []) + [Path(f).name for f in a.files]))
    proj.save(st)
    fi = final_index(e) if e.get("lines") else None
    expected = e["lines"][fi].get("results") if fi is not None and e["lines"] else None
    _say(f"[{db_info(a.db)['name']}] imported {len(recs):,} records" + (f" (final search line: {expected:,})" if expected else ""))
    if expected and abs(expected - len(recs)) > 0:
        _say("  ! Imported count differs from the final search count. Check for incomplete exports (e.g., per-export limits).")
    nr = noise_report(st, recs)
    if nr and nr["share"] > 0.2 and not a.db.startswith("citation"):
        _say(f"  ! {nr['no_concept_term']:,} of {nr['records']:,} records ({nr['share']:.0%}) contain no term of a concept "
             f"({', '.join(f'{k} {v}' for k, v in nr['by_concept'].items())}; languages {nr['languages']}; "
             f"{nr['without_abstract']} without abstract). Check the search lines for unquoted phrases or noisy "
             f"acronyms (librarian-search lint). Examples:")
        for t in nr["sample_titles"][:5]:
            _say(f"      - {t[:110]}")


def cmd_set_counts(a):
    proj = Project(Path(a.dir).expanduser())
    st = proj.load()
    e = proj.db_entry(st, a.db)
    if len(a.counts) != len(e.get("lines", [])):
        raise SystemExit(f"{a.db}: {len(e.get('lines', []))} search lines but {len(a.counts)} counts given")
    for ln, n in zip(e["lines"], a.counts):
        ln["results"] = int(str(n).replace(",", ""))
    if a.date:
        e["search_date"] = a.date
    proj.save(st)
    _say("Counts recorded.")


# ------------------------------------------------------------------ cite
def cmd_cite(a):
    proj = Project(Path(a.dir).expanduser())
    st = proj.load()
    for problem in profile_problems(st, ["citation"]):
        raise SystemExit(f"Systematic profile: {problem}. Export the references and citing documents of the seeds "
                         f"from Scopus or Web of Science and import them with --db citation_scopus / citation_wos.")
    cfg = st.setdefault("citation", {})
    seeds = a.seed or cfg.get("seeds", [])
    if not seeds:
        raise SystemExit("Give seed articles (DOI/PMID) with --seed or in strategy.json citation.seeds")
    cfg["seeds"] = seeds
    direction = a.direction or cfg.get("direction", "both")
    recs, log = openalex.citation_search(seeds, direction)
    if cfg.get("filter"):
        rx = re.compile(cfg["filter"], re.I)
        before = len(recs)
        recs = [r for r in recs if rx.search(" ".join([r["title"], r["abstract"], " ".join(r["keywords"])]))]
        _say(f"  topic filter '{cfg['filter']}': {before} -> {len(recs)}")
        cfg["filter_applied"] = {"before": before, "after": len(recs)}
    save_jsonl(proj.records_dir / "citation.jsonl", recs)
    (proj.runs_dir).mkdir(parents=True, exist_ok=True)
    (proj.runs_dir / "citation_log.json").write_text(json.dumps({"date": today(), "seeds": log}, ensure_ascii=False, indent=1))
    cfg["date"] = today()
    proj.save(st)
    _say(f"Saved {len(recs):,} citation records (deduplicated against database results at build)")


# ------------------------------------------------------------------ build
def _stem(st) -> str:
    s = st.get("file_stem") or st.get("title") or "literature_search"
    return re.sub(r'[\\/:*?"<>|]+', "", s).strip()[:60]


def _load_all(proj, st):
    priority = st.get("priority") or DEFAULT_PRIORITY
    files = {p.stem: p for p in proj.records_dir.glob("*.jsonl")} if proj.records_dir.exists() else {}
    if not files:
        raise SystemExit("records/ is empty. Run run / import / cite first")
    db_order = [d for d in priority if d in files] + sorted(d for d in files if d not in priority)
    allrecs, retrieved = [], {}
    for d in db_order:
        rs = load_jsonl(files[d])
        retrieved[d] = len(rs)
        allrecs.extend(rs)
    unique, dups = deduplicate(allrecs, db_order)
    return files, db_order, allrecs, retrieved, unique, dups


def cmd_validate(a):
    """Check that known relevant studies (validation set) are retrieved; diagnose misses on PubMed lines."""
    proj = Project(Path(a.dir).expanduser())
    st = proj.load()
    v = st.setdefault("validation", {})
    items = list(a.known or [])
    if a.known_file:
        items += Path(a.known_file).expanduser().read_text(encoding="utf-8").split()
    if items:
        v["known"] = items
    known = parse_known(v.get("known", []))
    if not known:
        raise SystemExit("Give known relevant studies (PMID or DOI) with --known or --known-file")
    _files, _order, _all, _ret, unique, dups = _load_all(proj, st)
    res = match_known(known, unique, dups)
    missed = [k["pmid"] for k in res if not k["found"] and k["pmid"]]
    diag = diagnose_pubmed(st, missed)
    for k in res:
        if k["pmid"] in diag:
            k["diagnosis"] = diag[k["pmid"]]
    proj.runs_dir.mkdir(parents=True, exist_ok=True)
    (proj.runs_dir / "validation.json").write_text(json.dumps({"date": today(), "results": res}, ensure_ascii=False, indent=1))
    proj.save(st)
    found = sum(1 for k in res if k["found"])
    _say(f"Validation set: {found}/{len(res)} retrieved (recall {found / len(res):.0%})")
    for k in res:
        if not k["found"]:
            d = k.get("diagnosis") or {}
            why = ("not in PubMed" if d.get("in_pubmed") is False else
                   f"fails PubMed line(s) {', '.join('#' + str(x) for x in d.get('failed_lines', []))}" if d else "")
            _say(f"  MISSED {k['id']}  {why}")


def cmd_suggest(a):
    """Suggest candidate terms (frequent MeSH/keywords not yet in the strategy), as litsearchr does."""
    proj = Project(Path(a.dir).expanduser())
    st = proj.load()
    _files, _order, _all, _ret, unique, dups = _load_all(proj, st)
    base = unique
    vpath = proj.runs_dir / "validation.json"
    if a.from_known and vpath.exists():
        uids = {k["uid"] for k in json.loads(vpath.read_text())["results"] if k["found"]}
        base = [r for r in unique if r["uid"] in uids]
    for term, n, kind in suggest_terms(base, st, a.top):
        print(f"{n:>5}  {term}")


def cmd_build(a):
    proj = Project(Path(a.dir).expanduser())
    st = proj.load()
    files, db_order, allrecs, retrieved, unique, dups = _load_all(proj, st)
    problems = profile_problems(st, db_order)
    if problems:
        raise SystemExit("Systematic profile: these sources are not reportable; remove their records/ files or set "
                         "\"allow_nonstandard_sources\": true:\n  " + "\n  ".join(problems))
    for gap in systematic_gaps(st, db_order):
        _say(f"  ! Systematic profile: {gap}")
    _report_lint(st)
    contributed = Counter(r["db"] for r in unique)
    fl = {r["uid"]: compute_flags(r) for r in unique}
    flag_counts = Counter(k for f in fl.values() for k, v in f.items() if v)

    line_counts, fidx = {}, {}
    for e in st.get("databases", []):
        if e.get("lines"):
            fidx[e["id"]] = final_index(e)
            line_counts[e["id"]] = {i: ln.get("results") for i, ln in enumerate(e["lines"]) if ln.get("results") is not None}
    cit_path = proj.runs_dir / "citation_log.json"
    cit = json.loads(cit_path.read_text()) if cit_path.exists() and "citation" in files else {}
    ctx = {
        "db_order": db_order, "retrieved": retrieved, "contributed": dict(contributed),
        "unique": unique, "dups": dups, "flags": fl, "flag_counts": dict(flag_counts),
        "n_unique": len(unique), "n_dups": len(dups), "total_retrieved": len(allrecs),
        "search_date": st.get("search_date") or today(), "line_counts": line_counts, "final_index": fidx,
        "citation_log": cit.get("seeds", []), "citation_date": cit.get("date", ""),
        "profile": profile(st), "systematic_gaps": systematic_gaps(st, db_order),
        "nonstandard_used": [NOT_SYSTEMATIC.get(d, db_info(d)["name"]).split(" (")[0] for d in db_order
                             if d.split(":")[0] not in SYSTEMATIC_SOURCES],
    }
    ctx["overlap"] = overlap(unique, db_order)
    if getattr(a, "previous", None):
        st["previous_files"] = [str(Path(f).expanduser().resolve()) for f in a.previous]
        proj.save(st)
    prev_recs = []
    for f in st.get("previous_files", []):
        prev_recs += parse_file(Path(f), "previous")
    ctx["previous_uids"] = mark_previous(unique, prev_recs)
    ctx["n_previous_records"] = len(prev_recs)
    known = parse_known((st.get("validation") or {}).get("known", []))
    if known:
        res = match_known(known, unique, dups)
        vpath = proj.runs_dir / "validation.json"
        if vpath.exists():
            old = {k["id"]: k.get("diagnosis") for k in json.loads(vpath.read_text())["results"]}
            for k in res:
                if old.get(k["id"]):
                    k["diagnosis"] = old[k["id"]]
        ctx["validation"] = res
        ctx["known_uids"] = {k["uid"] for k in res if k["found"]}
    ctx["prisma_s"] = prisma_s(st, ctx)

    out = proj.out_dir
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    stem = _stem(st)
    date_tag = ctx["search_date"].replace("-", "")
    xlsx = build_workbook(out / f"{stem}_search_strategy_{date_tag}.xlsx", st, ctx)

    enl_dir = out / "_endnote"
    enl_dir.mkdir()
    groups = {"Known relevant (validation set)": ctx.get("known_uids", set())}
    if prev_recs:
        groups["New since previous search"] = {r["uid"] for r in unique} - ctx["previous_uids"]
        groups["Previously screened"] = ctx["previous_uids"]
    enl = write_library(enl_dir / f"{stem}.enl", unique, dups, db_order, retrieved, fl, groups)
    enl_zip = out / f"{stem}_EndNote.zip"
    with zipfile.ZipFile(enl_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(enl_dir.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(enl_dir))

    ris = out / f"{stem}_{len(unique)}.ris"
    write_ris(ris, unique)
    methods = methods_en(st, ctx)
    mpath = out / "methods_PRISMA-S.md"
    mpath.write_text("# Literature search — methods text (draft)\n\n" + methods + "\n\n## PRISMA-S\n\n" +
                     "\n".join(f"{n}. **{item}**: {desc}" for n, item, desc in ctx["prisma_s"]) + "\n", encoding="utf-8")
    (proj.root / "letter_draft.md").write_text(letter_draft(st, ctx), encoding="utf-8")
    letter_md = proj.root / "letter.md"
    prisma = out / "PRISMA_2020_flow.svg"
    prisma.write_text(prisma_svg(ctx), encoding="utf-8")
    asr = out / f"{stem}_asreview.csv"
    write_asreview_csv(asr, unique, ctx.get("known_uids", set()))
    deliver = [xlsx, enl_zip, ris, mpath, prisma, asr]
    if letter_md.exists():
        docx = out / f"{stem}_reply_letter.docx"
        md_to_docx(letter_md.read_text(encoding="utf-8"), docx)
        shutil.copyfile(letter_md, out / f"{stem}_reply_letter.md")
        deliver = [docx, out / f"{stem}_reply_letter.md"] + deliver
    stats = {k: ctx[k] for k in ("db_order", "retrieved", "contributed", "flag_counts", "n_unique", "n_dups",
                                 "total_retrieved", "search_date", "citation_log", "overlap")}
    if ctx.get("validation"):
        stats["validation"] = {"found": len(ctx["known_uids"]), "known": len(ctx["validation"])}
    if prev_recs:
        stats["previously_screened"] = len(ctx["previous_uids"])
    stats["methods_en"] = methods
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    package = out / f"{stem}_literature_search_{date_tag}.zip"
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as z:
        for p in deliver:
            z.write(p, p.name)

    _say("\n=== Results ===")
    for d in db_order:
        _say(f"  {db_info(d)['name']:<34} retrieved {retrieved[d]:>6,}   unique contribution {contributed.get(d, 0):>6,}")
    _say(f"  {'Total':<34} retrieved {len(allrecs):>6,}   unique {len(unique):>6,} (duplicates {len(dups):,})")
    _say(f"  Screening flags: " + ", ".join(f"{k} {v}" for k, v in sorted(flag_counts.items())))
    if not letter_md.exists():
        _say(f"\n  Letter draft: {proj.root / 'letter_draft.md'} -> edit and save as letter.md, then run build again to produce the .docx")
    print(package)


def cmd_status(a):
    proj = Project(Path(a.dir).expanduser())
    st = proj.load()
    for e in st.get("databases", []):
        f = proj.records_dir / f"{e['id']}.jsonl"
        n = sum(1 for _ in open(f)) if f.exists() else 0
        lines = e.get("lines", [])
        fin = lines[final_index(e)].get("results") if lines else None
        print(f"{db_info(e['id'])['name']:<34} mode={db_info(e['id'])['mode']:<6} lines={len(lines):<3} final={fin}  records={n}  date={e.get('search_date', '')}")
    c = proj.records_dir / "citation.jsonl"
    if c.exists():
        print(f"{'Citation searching':<34} records={sum(1 for _ in open(c))}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="librarian-search", description="Medical-librarian-style systematic literature search")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("init"); p.add_argument("dir"); p.add_argument("--request")
    p.add_argument("--profile", choices=["comprehensive", "systematic"], default="comprehensive",
                   help="systematic: only sources reportable in a systematic review (no OpenAlex)"); p.set_defaults(f=cmd_init)
    p = sp.add_parser("mesh"); p.add_argument("terms", nargs="+"); p.set_defaults(f=cmd_mesh)
    for name, fn in (("count", cmd_count), ("run", cmd_run)):
        p = sp.add_parser(name); p.add_argument("dir"); p.add_argument("--db", nargs="*"); p.set_defaults(f=fn)
    p = sp.add_parser("import"); p.add_argument("dir"); p.add_argument("--db", required=True)
    p.add_argument("files", nargs="+"); p.add_argument("--append", action="store_true"); p.add_argument("--date")
    p.set_defaults(f=cmd_import)
    p = sp.add_parser("set-counts"); p.add_argument("dir"); p.add_argument("--db", required=True)
    p.add_argument("counts", nargs="+"); p.add_argument("--date"); p.set_defaults(f=cmd_set_counts)
    p = sp.add_parser("cite"); p.add_argument("dir"); p.add_argument("--seed", nargs="*")
    p.add_argument("--direction", choices=["both", "backward", "forward"]); p.set_defaults(f=cmd_cite)
    p = sp.add_parser("build"); p.add_argument("dir"); p.add_argument("--previous", nargs="*",
                                                                     help="exports of a previous search (update searches)")
    p.set_defaults(f=cmd_build)
    p = sp.add_parser("validate"); p.add_argument("dir"); p.add_argument("--known", nargs="*")
    p.add_argument("--known-file"); p.set_defaults(f=cmd_validate)
    p = sp.add_parser("suggest"); p.add_argument("dir"); p.add_argument("--top", type=int, default=30)
    p.add_argument("--from-known", action="store_true"); p.set_defaults(f=cmd_suggest)
    p = sp.add_parser("status"); p.add_argument("dir"); p.set_defaults(f=cmd_status)
    p = sp.add_parser("lint"); p.add_argument("dir"); p.set_defaults(f=cmd_lint)
    p = sp.add_parser("dropped"); p.add_argument("dir"); p.add_argument("--from", dest="from_line", type=int, required=True)
    p.add_argument("--to", dest="to_line", type=int, required=True); p.add_argument("--sample", type=int, default=20)
    p.set_defaults(f=cmd_dropped)
    a = ap.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
