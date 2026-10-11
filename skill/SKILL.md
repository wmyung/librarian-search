---
name: lit-search
description: Run a medical-librarian-style systematic literature search and produce a librarian's deliverables (reply letter, line-by-line search strategy workbook with hit counts, native EndNote library, RIS, PRISMA-S methods text). Trigger on requests such as "do a literature search for my review", "build a search strategy", "systematic search", "find prior studies on X", "search like a librarian", or when the user hands over a search request (text, file, or Google Docs link).
---

# Librarian-style systematic literature search (litsearch)

Tool: `uv run --project ~/lit-search litsearch <cmd>` (abbreviated `LS` below). Code and docs: `~/lit-search/README.md`.
Read [syntax.md](syntax.md) before writing any search lines.

**All outputs are in English**: strategy, letter, methods, workbook and EndNote group names. Never put the requester's name, institution, or other identifying details into any output.

## Deliverables (same structure as a medical library's reply)
1. **Reply letter** (.docx + .md): search strategy → hits per source and after deduplication → screening advice → supplementary (citation) searching → attachments
2. **Search strategy workbook** (.xlsx): `Search strategy` (line number, query, hits per source + retrieved/after-dedup summary), `Records` (screening list with flags, abstract, include/exclude columns), `Duplicates`, `PRISMA-S`
3. **EndNote library** (.zip with .enl + .Data): one group per source ("PubMed 192"), smart groups by study type, duplicates in the Trash
4. **RIS** (Zotero, Covidence, Rayyan) and **methods_PRISMA-S.md** (manuscript methods paragraph + the 16 PRISMA-S items)

## Procedure

### 1. Intake
- `LS init <folder> --request <Google Docs URL | .gdoc path | file | "text">`
  Default folder: `~/lit-search/projects/<YYYYMMDD>_<short-topic>`
- Read `request.md` and confirm in one paragraph: question/objective, review type (narrative/systematic/scoping/meta-analysis), core concepts (usually 2–3: intervention/exposure × population/condition [× outcome]), scope (efficacy, safety, ...), and any draft strategy supplied by the requester.
- Ask only when genuinely ambiguous. Otherwise follow librarian practice: **no limits by study design or outcome**, no language or date limits, and as few concepts as possible (usually intervention AND condition). Every extra concept lowers sensitivity.

### 2. Write the strategy (`strategy.json`)
- Gather terms per concept:
  - `LS mesh "<term>"` for MeSH headings and entry terms (for drugs include supplementary concepts, brand names, development codes, chemical names)
  - synonyms, abbreviations, spelling variants, brand names, and broader/narrower condition terms
  - check abbreviations for false hits; they are acceptable when ANDed with another concept
  - instruments without MeSH (questionnaires, scales): search the acronym and full name as free text, and check a sample of hits for noise
- Translate the **same logic** into each database's syntax (syntax.md). Each database block is line-by-line, like a librarian's worksheet:
  concept-1 lines → `#1 OR …` → concept-2 lines → `#… OR …` → final `#a AND #b`. `#n` references are expanded automatically for automatic sources.
- Default sources:
  - automatic: `pubmed` (MEDLINE), `europepmc`, `ctgov`
  - manual (institutional subscription; the user runs the search and exports): `embase`, `cochrane`, `wos` (+ `psycinfo`, `cinahl`, `scopus`, `koreamed`, `kmbase`, `ictrp` by topic)
- Fill `title`, `file_stem`, `concepts` (name + term list; reused verbatim in the letter and methods), `limits` (English).

### 3. Run and check the automatic sources
- `LS count <folder>`: inspect per-line counts. Zero-hit lines (typo or syntax), suspiciously large lines (missing Europe PMC parentheses, split acronyms), and whether the final count is plausible for the topic. PubMed phrase-not-found warnings are printed.
- Iterate, then `LS run <folder>` to retrieve records.
- Validate sensitivity: look up a few known key papers (from the request, a Cochrane review, etc.) and check that their PMIDs are in `records/pubmed.jsonl`. Add terms if any are missing, or explain why they are out of scope.

### 4. Manual databases (Embase, Cochrane, WoS, ...)
- Give the user the paste-ready lines per database (also stored in strategy.json) and these instructions:
  - Embase.com: Advanced search, one line at a time → select all results of the final line → Export → **RIS** (split if there is an export limit)
  - Cochrane Library: Advanced search → Search manager → final line results for Trials (CENTRAL) and Reviews (CDSR) → Export → **RIS**
  - Web of Science: Advanced search → lines → final line → Export → **RIS** (1,000 per export)
  - Access is through the user's own institutional remote access; never log in on their behalf.
- When the user reports per-line counts: `LS set-counts <folder> --db embase 15862 4398 … --date YYYY-MM-DD`
- Exports: `LS import <folder> --db embase <files> --date YYYY-MM-DD` (several files allowed; `--append` later). A warning appears if the imported count differs from the final-line count; check for missing exports.
- If the user skips manual databases, proceed with automatic sources only, state the limitation in the letter and methods, and warn that reviewers often expect Embase.

### 5. Citation searching (recommended)
- Pick 2–5 key trials or systematic reviews from the results, confirm with the user, then
  `LS cite <folder> --seed <DOI|PMID> …`. If the results drift off-topic, set `citation.filter` in strategy.json to a regex requiring both concepts, e.g. `^(?=.*(vitamin d|cholecalciferol))(?=.*fracture)`, and rerun. Report the filter in the letter (the methods text does this automatically).

### 6. Build and write the letter
- `LS build <folder>` writes the workbook, EndNote zip, RIS, methods and stats.json to `out/`, plus `letter_draft.md` in the folder.
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
