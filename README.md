# librarian-search

**A medical librarian's literature search, as code.** One search request in; a librarian's reply letter, a line-by-line search-strategy workbook with hit counts, a native EndNote library, and PRISMA-S methods text out. Benchmarked on 26 Cochrane reviews: **95% recall**.

[![Release](https://img.shields.io/github/v/release/wmyung/librarian-search)](https://github.com/wmyung/librarian-search/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code skill](https://img.shields.io/badge/Claude%20Code-skill-d97757)](skill/SKILL.md)
[![Search recall](https://img.shields.io/badge/recall%20on%2026%20Cochrane%20reviews-95%25-success)](#benchmarks)
[![Dedup](https://img.shields.io/badge/dedup%20(ASySD%20set)-588%20vs%20584%20true-success)](#benchmarks)
[![PRISMA-S](https://img.shields.io/badge/reporting-PRISMA--S-6f42c1)](https://doi.org/10.1186/s13643-020-01542-z)

Ask a medical library for a literature search for your review and you get three things back: a **reply letter**, a **search-strategy spreadsheet** (every database, every line, every hit count), and an **EndNote library** with one group per database and duplicates in the Trash. librarian-search produces that same package in minutes, and every line can be audited by a librarian, a co-author, or a journal reviewer.

- **A Claude Code skill** reads the request, builds concept blocks (MeSH lookup, synonyms, brand names, spelling variants), translates the same logic into PubMed, Europe PMC, ClinicalTrials.gov, Embase, Cochrane and Web of Science syntax, checks sensitivity against known studies, and writes the reply letter.
- **A deterministic Python CLI** runs the searches line by line, imports exports from subscription databases, deduplicates across sources, and writes every deliverable.

No vector search and no black-box "AI search": every record comes from a Boolean query you can paste into the database yourself.

---

## At a glance

| | |
|---|---|
| **Search recall** | 89.3% of included studies with the PubMed strategy alone, **95.2% with citation searching** (766/805, 26 Cochrane reviews, strategies written blind from the title) |
| **Deduplication** | 588 records kept vs 584 true unique studies on the ASySD gold-standard set (ASySD: 586, EndNote default: 949) |
| **Against a real librarian** | 192 vs 189 records (PubMed vs the librarian's Ovid MEDLINE); 1,204 vs 1,216 unique Embase records after dedup |
| **Retrieval** | Every record, not a top-50: PubMed, Europe PMC and ClinicalTrials.gov automatically; Embase, Cochrane, WoS, Scopus, PsycInfo and CINAHL via RIS / MEDLINE / WoS exports |
| **Output** | Reply letter (.docx), strategy workbook (.xlsx), native EndNote 20/21 library, RIS, PRISMA-S methods paragraph, PRISMA 2020 flow diagram, ASReview import file |
| **Setup** | `uv tool install` from GitHub, Python 3.10+, no paid API. Citation searching requires an OpenAlex API key |

---

## Why librarian-search?

What only it does, among the tools we surveyed:

1. **The librarian's deliverable package.** A line-by-line strategy with hit counts for every database, a native EndNote library with database groups, smart groups and Trash, a PRISMA-S methods paragraph and a reply letter, together. Other tools stop at a list of records or a report.
2. **Subscription databases are first-class.** Most automated tools cannot touch Embase, Cochrane or Web of Science. librarian-search writes the paste-ready lines, then imports the RIS export from your institutional access. That is the realistic route to a search that journals accept.
3. **Complete retrieval.** Multi-source search tools commonly cap results at 50 per call or per source. A systematic search needs every record: librarian-search retrieves all of them (891 PubMed records in one test, 9,540 in another).
4. **Reproducible and reported.** Every line can be pasted back into the database to reproduce its count, and the PRISMA-S items are filled in for you.
5. **Validated, not just plausible.** Search recall and deduplication are benchmarked against public gold standards, and the benchmarks ship with the code.

---

## Comparison with alternatives

| | **librarian-search** | TrialMind | K-Dense literature-review skill | LitSearch II (MCP) | SR-Accelerator | CiteSource + ASySD | ASReview |
|---|---|---|---|---|---|---|---|
| **Type** | Skill + CLI | Research pipeline | Agent skill | MCP server | Web tools | R packages | Screening app |
| **Retrieves all records** | ✅ PubMed, Europe PMC, CT.gov | ✅ PubMed | partial (web + databases) | ❌ 50 per call | ❌ | ❌ | ❌ |
| **Embase / Cochrane / WoS imports** | ✅ | ❌ | ❌ | ❌ | ✅ (dedup) | ✅ | ✅ (import) |
| **Line-by-line strategy with hit counts** | ✅ | ❌ | ❌ | ❌ | translation only | ❌ | ❌ |
| **Cross-database dedup, benchmarked** | ✅ | ❌ | ❌ | DOI/title merge | ✅ | ✅ | ❌ |
| **Native EndNote library** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **PRISMA-S text + reply letter** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Screening / data extraction** | ❌ (hands off to ASReview, Covidence, Rayyan) | ✅ | guidance | ❌ | ❌ | ❌ | ✅ screening |
| **Published recall benchmark** | ✅ 26 Cochrane reviews | ✅ | ❌ | ❌ | — | dedup only | screening |

End-to-end LLM review pipelines such as TrialMind, otto-SR (not released) and AgentSLR go further downstream, into screening and extraction. librarian-search does the step before them the way librarians and journals expect, and its output feeds straight into a screening tool.

---

## What you get

| File | Contents |
|---|---|
| `*_reply_letter.docx` / `.md` | Search strategy rationale, hits per source and after deduplication, validation-set result, screening advice, citation searching, attachment guide |
| `*_search_strategy_YYYYMMDD.xlsx` | `Search strategy` (DB × line no. × query × hits, plus a retrieved / after-dedup summary), `Records` (screening sheet with study-type and retraction flags, abstract, include/exclude columns), `Source overlap`, `Validation`, `Duplicates`, `PRISMA-S` |
| `*_EndNote.zip` | Native EndNote 20/21 library (`.enl` + `.Data`): groups `"<DB> <n>"`, smart groups (random\*, systematic review, placebo, meta-analysis, case report/series, review, guideline), retracted records, validation-set and update-search groups, duplicates in the Trash with the reason in Research Notes |
| `*_N.ris` | Deduplicated records for Zotero, Covidence or Rayyan |
| `methods_PRISMA-S.md` | A ready-to-edit Methods paragraph plus all 16 PRISMA-S items filled in |
| `PRISMA_2020_flow.svg` | PRISMA 2020 flow diagram with the identification stage completed |
| `*_asreview.csv` | Import file for [ASReview](https://github.com/asreview/asreview) active-learning screening, with validation-set studies pre-labelled as relevant |

The `Search strategy` sheet looks like a librarian's worksheet:

| DB | Search | Query | Results |
|---|---|---|---|
| MEDLINE (PubMed) | 1 | `"Vitamin D"[Mesh] OR "Cholecalciferol"[Mesh] OR "Ergocalciferols"[Mesh]` | 75,287 |
| | 2 | `"vitamin D"[tiab] OR cholecalciferol[tiab] OR …` | 99,794 |
| | 3 | `#1 OR #2` | 117,743 |
| | … | … | … |
| | 7 | **`#3 AND #6`** | **9,540** |

---

## How it works

```
search request (text, file, Google Docs link)
   │  skill: concepts, MeSH and synonyms, database-specific syntax
   ▼
strategy.json  ── count ──▶ per-line hit counts (iterate until plausible)
   │
   ├─ run ────▶ PubMed, Europe PMC, ClinicalTrials.gov (every record)
   ├─ import ─▶ Embase, Cochrane, WoS, ... exports from your institution
   ├─ cite ───▶ OpenAlex reference lists and citing articles of key reviews
   ├─ validate ▶ known relevant studies found? which concept lost the rest?
   ▼
build ─▶ dedup (priority order) ─▶ workbook, EndNote, RIS, PRISMA-S, PRISMA 2020, ASReview, letter draft
```

---

## Quick start

```bash
# install the CLI
uv tool install git+https://github.com/wmyung/librarian-search
# or work from a clone (and enable the Claude Code skill)
git clone https://github.com/wmyung/librarian-search ~/librarian-search
cd ~/librarian-search && uv sync
ln -s ~/librarian-search/skill ~/.claude/skills/librarian-search

LS="librarian-search"          # or: uv run --project ~/librarian-search librarian-search
$LS init projects/vitd --request "Vitamin D supplementation and fracture prevention: narrative review"
cp examples/vitamin_d_fracture_strategy.json projects/vitd/strategy.json
$LS mesh "cholecalciferol"                 # MeSH headings + entry terms
$LS count projects/vitd                    # per-line hit counts (iterate on the strategy)
$LS run projects/vitd                      # retrieve records from automatic sources
$LS validate projects/vitd --known 12345678 10.xxxx/known-study   # recall of known relevant studies + diagnosis
$LS suggest projects/vitd --from-known     # frequent MeSH/keywords the strategy does not cover yet

# Subscription databases: run the lines from the workbook via your institution, export RIS, then
$LS set-counts projects/vitd --db embase 98765 54321 … --date 2026-10-01
$LS import projects/vitd --db embase embase_export.ris --date 2026-10-01

export OPENALEX_API_KEY=...                # required for citation searching
$LS cite projects/vitd --seed 10.xxxx/your-key-review 12345678   # backward + forward citation searching
$LS build projects/vitd                    # dedup + deliverables + letter_draft.md
# edit letter_draft.md -> letter.md, run build again -> final zip with the reply letter .docx
$LS build projects/vitd --previous last_year.ris   # update search: mark records screened last time
```

With the skill installed, just tell Claude Code: *"Do a literature search for my narrative review on vitamin D and fracture prevention."*

---

## Databases

| id | Mode | How it is reported |
|---|---|---|
| `pubmed` | automatic (NCBI E-utilities) | MEDLINE via PubMed |
| `europepmc` | automatic (REST API) | Europe PMC |
| `ctgov` | automatic (API v2) | ClinicalTrials.gov (trial registry) |
| `citation` | automatic (OpenAlex) | backward/forward citation searching using OpenAlex |
| `embase`, `cochrane`, `wos`, `scopus`, `psycinfo`, `cinahl`, `ovid_medline`, `koreamed`, `kmbase`, `ictrp` | manual: search on the vendor platform through your institution, export RIS / MEDLINE / WoS plain text, then `import` | official database and platform names |

Citation searching requires an OpenAlex API key (`OPENALEX_API_KEY`). `NCBI_API_KEY` is optional (faster PubMed requests).

Search syntax pitfalls we hit and encoded in the skill, such as Europe PMC fielded clauses leaking into full-text search without parentheses, or hyphenated acronyms being tokenised, are documented in [skill/syntax.md](skill/syntax.md).

---

## Benchmarks

All benchmarks are scripts in [`benchmarks/`](benchmarks/) that download public data and can be rerun:

```bash
uv run python benchmarks/clef_tar_recall.py                  # 8 diagnostic accuracy reviews
uv run python benchmarks/clef_tar_recall.py --set 2019int    # 18 intervention reviews (add --cite for citation searching)
uv run python benchmarks/dedup_asysd.py                      # deduplication
```

### Search recall: 8 Cochrane diagnostic accuracy reviews (CLEF eHealth TAR 2017)

PubMed strategies were written **from the review title only**, as the skill does, without consulting the original Cochrane search. Recall was measured against the studies finally included in each review.

| Review | Included studies found | Our records (to review date) | Original Cochrane query |
|---|---|---|---|
| CD008081 OCT for diabetic macular oedema | **10/10** | 2,848 | 970 |
| CD009135 Rapid tests for visceral leishmaniasis | **19/19** | 2,510 | 791 |
| CD009185 PCT/CRP/ESR for pyelonephritis in children | 15/23 | 316 | 1,615 |
| CD009519 PET-CT for mediastinal staging in NSCLC | **46/46** | 2,309 | 5,971 |
| CD009551 PCR for invasive aspergillosis | **16/16** | 4,337 | 1,911 |
| CD010023 CT/MRI/bone scan for scaphoid fracture | **14/14** | 1,849 | 981 |
| CD010542 Transient elastography in alcoholic liver disease | 6/8 | 147 | 348 |
| CD010772 IQCODE for dementia | **11/11** | 196 | 316 |
| **Total** | **137/147 (93.2%)**, 100% in 6/8 reviews | median 1.9× the original | |

All 10 misses were diagnosed by `validate`. In CD009185 every missed study failed the index-test concept: their abstracts never mention CRP, procalcitonin or ESR. In CD010542 both misses failed the "alcohol" concept. These lessons are now rules in the skill: OR reference-standard terms into the index-test concept for diagnostic reviews, avoid population concepts that abstracts may omit, and always run a validation set. Real searches also go through Embase, Cochrane and citation searching, which this PubMed-only benchmark leaves out.

### Search recall: 18 Cochrane intervention reviews (CLEF eHealth TAR 2019)

Same protocol: strategies written from the title only, no RCT filter, PubMed only.

| Review | Found | Review | Found |
|---|---|---|---|
| CD000996 Inhaled corticosteroids, bronchiectasis | **6/6** | CD010558 Psychotherapy, treatment-resistant depression | 15/16 |
| CD001261 Typhoid vaccines | **26/26** | CD010753 Antidepressants for insomnia | 20/21 |
| CD004414 Occupational hand dermatitis prevention | **13/13** | CD011571 Antistreptococcal treatment, psoriasis | **6/6** |
| CD006468 Anticoagulation, cancer + CVC | 13/15 | CD011768 Complementary feeding education | 29/31 |
| CD007867 Hypocaloric nutrition, ICU | 14/15 | CD011977 Blue-light filtering IOLs | 37/38 |
| CD009069 HPV vaccination | **6/6** | CD012069 Methylphenidate adverse events (non-randomised) | 268/327 |
| CD009642 IV lidocaine, postoperative | 67/72 | CD012164 SEPS for venous ulcers | **3/3** |
| CD010038 Parent education, childhood vaccination | 11/12 | CD012455 Melatonin in ICU | **5/5** |
| CD010239 Oxygen for preterm resuscitation | 11/12 | CD012551 Chronic prostatitis/pelvic pain | 32/34 |
| **Total** | **582/658 (88.4%)**, 100% in 7/18 | without CD012069 | **314/331 (94.9%)** |

Most CD012069 misses are trial reports that say "medication management" without naming the drug (now a skill rule: add drug-class terms and trial acronyms for adverse-event reviews). About a third of the sampled misses are unrelated to the topic (for example a plant-genetics paper), which suggests label noise in the benchmark itself.

**Adding citation searching** (`--cite`): seeds were chosen blindly, as up to three systematic reviews from our own results that predate the target review and best match its title. Adding their reference lists via OpenAlex raised intervention-review recall from **88.4% to 95.6% (629/658)**, recovering 45 of the 59 CD012069 misses. It added nothing to the diagnostic reviews: the one diagnostic topic with misses had no suitable systematic reviews to seed from.

| Benchmark (26 Cochrane reviews) | PubMed strategy only | + backward citation searching |
|---|---|---|
| 8 diagnostic accuracy reviews | 137/147 (93.2%) | 137/147 (93.2%) |
| 18 intervention reviews | 582/658 (88.4%) | 629/658 (95.6%) |
| **All** | **719/805 (89.3%)** | **766/805 (95.2%)** |

### Deduplication: ASySD labelled test set (1,845 records, 584 true unique studies)

| Method | Unique records kept |
|---|---|
| EndNote default deduplication | 949 |
| ASySD (reported) | 586 |
| **librarian-search** | **588** (2 distinct studies wrongly merged, 6 duplicates missed) |

The first version of our deduplication merged 54 distinct conference abstracts, because whole conference supplements share a single DOI. DOI matches now also require compatible titles and first pages, as ASySD does.

### Against a librarian

Translated to PubMed, a medical librarian's Ovid MEDLINE strategy returned 192 records against the librarian's 189 (searched about six weeks earlier). With the same Embase export, deduplication left 1,204 unique Embase records against 1,216 from the librarian's EndNote deduplication. EndNote 21 opens the generated libraries with groups, smart groups and Trash intact.


---

## What benchmarking fixed

Benchmarks are only useful if they change the code. These did:

- **Over-merging deduplication.** The first version merged 54 distinct conference abstracts on the ASySD set, because a whole conference supplement can carry a single DOI. DOI matches now also require compatible titles and first pages (588 kept vs 584 true, previously 533).
- **Diagnostic accuracy searches.** Every study missed in the procalcitonin/CRP review failed the index-test concept, because abstracts often omit the index test. The skill now ORs reference-standard terms into the index-test concept and warns against population concepts that abstracts may not state.
- **Adverse-event searches.** Most misses in the methylphenidate review were trial reports that say "medication management" without naming the drug. The skill now adds drug-class terms and trial acronyms.
- **Validation sets are mandatory.** `validate` reports, for every missed known study, whether it is in PubMed and which concept line lost it, so a gap is fixed before the search is delivered.
- **Robustness.** OpenAlex lookups fall back to the DOI recorded in PubMed when a PMID is not linked, and API responses with control characters no longer break parsing.

---

## Deduplication

Records are linked by PMID or NCT number; by DOI when titles and first pages are also compatible (conference supplements often share one DOI); or by normalised title (exact, or a ≥40-character prefix match for titles with appended translations) + publication year ±1 + compatible first author + no conflicting first page. The record from the highest-priority source is kept (default MEDLINE > Embase > Cochrane > WoS > …, configurable). Empty fields such as abstract or DOI are filled in from its duplicates. Every removed record stays in the EndNote Trash and in the `Duplicates` sheet, with its match basis.

---

## Ideas borrowed from other tools

librarian-search adapts good ideas from established evidence-synthesis tools:

| Feature | Inspired by |
|---|---|
| Deduplication that guards against shared supplement DOIs; benchmark data | [ASySD](https://github.com/camaradesuk/ASySD) (CAMARADES) |
| Source overlap and unique-contribution analysis | [CiteSource](https://github.com/ESHackathon/CiteSource) |
| Update searches that separate new records from ones already screened | [SR-Accelerator Deduplicator](https://sr-accelerator.com/) (Bond University) |
| Validation-set recall checks for generated queries | Librarian practice; [TrialMind](https://arxiv.org/abs/2406.17755); Wang et al. (SIGIR 2025) |
| Candidate term suggestions from retrieved records | [litsearchr](https://github.com/elizagrames/litsearchr) |
| Retraction flags | Citation verification in [LitSearch II](https://github.com/seun-john/litsearch-ii) |
| Screening handoff | [ASReview](https://github.com/asreview/asreview) |
| Search-recall benchmark topics | [CLEF eHealth TAR](https://github.com/CLEF-TAR/tar) |

---

## Limitations

- **Search and retrieval only.** Screening and data extraction are out of scope; hand the RIS or ASReview file to a screening tool.
- **Benchmarks cover PubMed plus citation searching.** Embase, Cochrane and Web of Science add records in real searches but are not part of the automated benchmark, because they require institutional access.
- **Strategy quality depends on the model.** The skill writes the strategy, so quality can vary by topic. That is why validation-set checks are part of the workflow, and why a librarian's PRESS review is still recommended for systematic reviews.
- **Citation searching requires an OpenAlex API key.**

---

## For AI agents

| User says | You do |
|---|---|
| "Do a literature search / find prior studies on X" | Load the `librarian-search` skill → `init` → write `strategy.json` → `count` → `run` |
| "These papers must be found" | `validate --known …`; fix the concept line it reports, rerun, validate again |
| "Here are my Embase / Cochrane / WoS exports" | `set-counts` and `import` for each source |
| "Also check references and citing papers" | `cite` with 2–5 key trials or reviews; add `citation.filter` if off-topic |
| "Update last year's search" | `build --previous <old export>` |
| "Give me the package" | `build` → fill `letter_draft.md` → `letter.md` → `build` → send the zip |

Rules the skill enforces: report only real counts and dates, never limit by study design for narrative reviews, always run a validation set, keep every record (flags are screening aids), and put no names or institutions in outputs.

---

## Project layout (one search request)

```
request.md  strategy.json  letter_draft.md  letter.md
records/<db>.jsonl   runs/counts.json   runs/validation.json   runs/citation_log.json
out/   <- deliverables and *_literature_search_YYYYMMDD.zip
```

## Tests

```bash
uv run --project ~/librarian-search python -m pytest ~/librarian-search/tests -q
```

---

## Related projects

- **[wmyung/endnote-fieldcode-converter](https://github.com/wmyung/endnote-fieldcode-converter)**: turn plain-text citations in a DOCX manuscript into EndNote field codes. A good next step after screening the librarian-search library.
- **[wmyung/endnote-fieldcode-gui](https://github.com/wmyung/endnote-fieldcode-gui)**: an offline Mac app for the same conversion.
- **[wmyung/paper-to-llm-wiki-digest](https://github.com/wmyung/paper-to-llm-wiki-digest)**: digest included papers into an LLM-ready research wiki.
- **[wmyung/manuscript-to-editable-slides](https://github.com/wmyung/manuscript-to-editable-slides)**: turn the finished manuscript into an editable slide deck.

## Notes

EndNote is a trademark of Clarivate. librarian-search is not affiliated with Clarivate, NLM, EMBL-EBI, Elsevier, Wiley or OpenAlex. It writes EndNote's SQLite library format for interoperability. Respect each database's terms of use; subscription databases are searched by you, through your own access.

## License

MIT
