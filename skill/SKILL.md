---
name: librarian-search
description: Run a medical-librarian-style systematic literature search and produce a librarian's deliverables (reply letter, line-by-line search strategy workbook with hit counts, native EndNote library, RIS, PRISMA-S methods text). Trigger on requests such as "do a literature search for my review", "build a search strategy", "systematic search", "find prior studies on X", "search like a librarian", or when the user hands over a search request (text, file, or Google Docs link).
---

# Librarian-style systematic literature search (librarian-search)

Tool: `uv run --project <repo> librarian-search <cmd>` (abbreviated `LS` below), where `<repo>` is the parent directory of this skill's base directory (the skill lives in `<repo>/skill`). Code and docs: `<repo>/README.md`.
Citation searching (`LS cite`) requires `OPENALEX_API_KEY` in the environment.
Read [syntax.md](syntax.md) before writing any search lines.

**All outputs are in English**: strategy, letter, methods, workbook and EndNote group names. Never put the requester's name, institution, or other identifying details into any output.

## Deliverables (same structure as a medical library's reply)
1. **Reply letter** (.docx + .md): search strategy → hits per source and after deduplication → screening advice → supplementary (citation) searching → attachments
2. **Search strategy workbook** (.xlsx): `Search strategy` (line number, query, hits per source + retrieved/after-dedup summary), `Records` (screening list with flags, abstract, include/exclude columns), `Source overlap`, `Validation` (when a validation set is given), `Duplicates`, `PRISMA-S`
3. **EndNote library** (.zip with .enl + .Data): one group per source ("PubMed 192"), smart groups by study type, duplicates in the Trash
4. **RIS** (Zotero, Covidence, Rayyan), **methods_PRISMA-S.md** (manuscript methods paragraph + the 16 PRISMA-S items), **PRISMA_2020_flow.svg** (identification stage filled in) and an **ASReview CSV** (known relevant studies pre-labelled)

## Procedure

### 1. Intake
- `LS init <folder> --request <Google Docs URL | .gdoc path | file | "text">`
  Default folder: `<repo>/projects/<YYYYMMDD>_<short-topic>`
- Read `request.md` and confirm in one paragraph: question/objective, review type (narrative/systematic/scoping/meta-analysis), core concepts (usually 2–3: intervention/exposure × population/condition [× outcome]), scope (efficacy, safety, ...), and any draft strategy supplied by the requester.
- Ask only when genuinely ambiguous. Otherwise follow librarian practice: **no limits by study design or outcome**, no language or date limits, and as few concepts as possible (usually intervention AND condition). Every extra concept lowers sensitivity.

### 2. Write the strategy (`strategy.json`)
- Gather terms per concept:
  - `LS mesh "<term>"` for MeSH headings and entry terms (for drugs include supplementary concepts, brand names, development codes, chemical names)
  - synonyms, abbreviations, spelling variants, brand names, and broader/narrower condition terms
  - check abbreviations for false hits; they are acceptable when ANDed with another concept
  - instruments without MeSH (questionnaires, scales): search the acronym and full name as free text, and check a sample of hits for noise
- **Diagnostic test accuracy reviews**: index tests are often reported only in the full text (benchmark lesson: a CRP/procalcitonin review lost 8 of 23 included studies on the index-test concept). OR the reference-standard terms into the index-test concept (e.g. `procalcitonin OR CRP OR … OR DMSA OR scintigraphy`), or drop the index-test concept when the condition × population literature is small enough to screen. Avoid population concepts that abstracts may not state (e.g. "alcohol" for alcoholic liver disease cohorts) unless the set is otherwise unmanageable.
- Translate the **same logic** into each database's syntax (syntax.md). Each database block is line-by-line, like a librarian's worksheet:
  concept-1 lines → `#1 OR …` → concept-2 lines → `#… OR …` → final `#a AND #b`. `#n` references are expanded automatically for automatic sources.
- Default sources:
  - automatic: `pubmed` (MEDLINE), `europepmc`, `ctgov`
  - manual (institutional subscription; the user runs the search and exports): `embase`, `cochrane`, `wos` (+ `psycinfo`, `cinahl`, `scopus`, `koreamed`, `kmbase`, `ictrp` by topic)
- Fill `title`, `file_stem`, `concepts` (name + term list; reused verbatim in the letter and methods), `limits` (English).

### 3. Run and check the automatic sources
- `LS count <folder>`: inspect per-line counts. Zero-hit lines (typo or syntax), suspiciously large lines (missing Europe PMC parentheses, split acronyms), and whether the final count is plausible for the topic. PubMed phrase-not-found warnings are printed.
- Iterate, then `LS run <folder>` to retrieve records.
- **Validation set (always do this)**: collect 5–15 known relevant studies (named in the request, included in an existing review, or found with a quick precise search), confirm them with the user, then
  `LS validate <folder> --known <PMID|DOI> …`. For each miss it reports whether the study is in PubMed and which concept line (`#n`) failed. Fix that concept (add the missing synonym, OR in reference-standard terms, or drop an over-restrictive concept), rerun `count`/`run`, and validate again. Out-of-scope misses are fine; say so in the letter.
- `LS suggest <folder> [--from-known]` lists frequent MeSH headings/keywords in the results (or in the validation studies) that the strategy does not mention; use it to find missed synonyms.

### 4. Manual databases (Embase, Cochrane, WoS, ...)
- Give the user the paste-ready lines per database (also stored in strategy.json) and these instructions:
  - Embase.com: Advanced search, one line at a time → select all results of the final line → Export → **RIS** (split if there is an export limit)
  - Cochrane Library: Advanced search → Search manager → final line results for Trials (CENTRAL) and Reviews (CDSR) → Export → **RIS**
  - Web of Science: Advanced search → lines → final line → Export → **RIS** (1,000 per export)
  - Access is through the user's own institutional remote access; never log in on their behalf.
- When the user reports per-line counts: `LS set-counts <folder> --db embase 15862 4398 … --date YYYY-MM-DD`
- Exports: `LS import <folder> --db embase <files> --date YYYY-MM-DD` (several files allowed; `--append` later). A warning appears if the imported count differs from the final-line count; check for missing exports.
- If the user skips manual databases, proceed with automatic sources only, state the limitation in the letter and methods, and warn that reviewers often expect Embase.

### 5. Update searches
- To rerun a previous search, pass the earlier export(s): `LS build <folder> --previous old_library.ris`. Records already screened are marked; the EndNote library gets "New since previous search" and "Previously screened" groups, and the letter/methods report the counts.

### 6. Citation searching (recommended)
- Pick 2–5 key trials or systematic reviews from the results, confirm with the user, then
  `LS cite <folder> --seed <DOI|PMID> …`. If the results drift off-topic, set `citation.filter` in strategy.json to a regex requiring both concepts, e.g. `^(?=.*(vitamin d|cholecalciferol))(?=.*fracture)`, and rerun. Report the filter in the letter (the methods text does this automatically).

### 7. Build and write the letter
- `LS build <folder>` writes the workbook, EndNote zip, RIS, methods, PRISMA 2020 flow (SVG), ASReview CSV and stats.json to `out/`, plus `letter_draft.md` in the folder. Records flagged "retracted" (retracted publications and retraction notices) are listed in their own EndNote group; mention them in the letter if any are relevant.
- Fill the `{{…}}` placeholders in `letter_draft.md` for the review objective, polish, and save as `letter.md`. Keep the librarian's structure: greeting, 1. Search strategy / 2. Results and screening / 3. Supplementary searching / 4. Attachments, closing. Do not sign with a person's or institution's name.
  - Screening advice by review type: for a narrative review, consider comparative clinical, observational, retrospective, case reports and prior reviews, not only RCTs, and do not restrict by "randomized" or "placebo" at the search stage. For a systematic review, recommend dual independent screening and a PRISMA flow diagram.
  - If the requester supplied a draft strategy, add a paragraph on what it lacked and how it was improved.
  - Introduce the flag counts (random*, systematic review, placebo, meta-analysis, case report/series, review, guideline) as a starting point for screening.
  - Explain notable term decisions (e.g. noisy acronyms restricted, concepts that exclude certain populations) and offer a broader or narrower variant.
- Run `LS build <folder>` again to produce the final zip including the reply letter .docx (`out/*_literature_search_*.zip`).
- Report to the user: zip path, hits per source, unique count, and the methods paragraph. Send the zip with SendUserFile.

## Principles
- Report only real hit counts and search dates. Never estimate manual-database counts.
- Flags are screening aids, not filters: every record stays in the library.
- No bulk full-text downloading (library proxies are for checking individual papers).
