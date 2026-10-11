# librarian-search

**Librarian-grade systematic literature search, automated. Line-by-line strategies, multi-database retrieval, deduplication, a native EndNote library, and a PRISMA-S methods paragraph, from one search request.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Claude Code skill](https://img.shields.io/badge/Claude%20Code-skill-d97757)](skill/SKILL.md)
[![PRISMA-S](https://img.shields.io/badge/reporting-PRISMA--S-6f42c1)](https://doi.org/10.1186/s13643-020-01542-z)
[![Search recall](https://img.shields.io/badge/recall%20on%208%20Cochrane%20reviews-93%25-success)](#benchmarks)
[![Dedup](https://img.shields.io/badge/dedup%20(ASySD%20set)-588%20vs%20584%20true-success)](#benchmarks)

When you ask a medical librarian for a literature search for a review, you get back a **reply letter**, a **search-strategy spreadsheet** (every database, every line, every hit count), and an **EndNote library** with one group per database and duplicates in the Trash. librarian-search produces that same package. The search runs in minutes, and a librarian or reviewer can audit every line.

- **A Claude Code skill** reads the request, builds concept blocks (MeSH lookup, synonyms, brand names, spelling variants), translates the same logic into PubMed, Europe PMC, ClinicalTrials.gov, Embase, Cochrane and Web of Science syntax, and writes the reply letter.
- **A deterministic Python CLI** runs the searches line by line, imports exports from subscription databases, deduplicates across sources, and writes the deliverables.

No vector search, no black-box "AI search". Every record comes from a reproducible query you can paste into the database yourself.

---

## What you get

| File | Contents |
|---|---|
| `*_reply_letter.docx` / `.md` | Search strategy rationale, hits per source and after deduplication, screening advice, citation searching, attachment guide |
| `*_search_strategy_YYYYMMDD.xlsx` | `Search strategy` (DB × line no. × query × hits, plus a retrieved / after-dedup summary table), `Records` (screening sheet with study-type and retraction flags, abstract, include/exclude columns), `Source overlap` (what each database found, alone and in common), `Validation` (which known relevant studies were found, and which concept line lost the rest), `Duplicates` (what was removed and why), `PRISMA-S` |
| `*_EndNote.zip` | Native EndNote 20/21 library (`.enl` + `.Data`): groups `"<DB> <n>"`, smart groups (random\*, systematic review, placebo, meta-analysis, case report/series, review, guideline), duplicates in the Trash with the reason in Research Notes |
| `*_N.ris` | Deduplicated records for Zotero, Covidence or Rayyan |
| `methods_PRISMA-S.md` | A ready-to-edit Methods paragraph plus all 16 PRISMA-S items filled in |
| `PRISMA_2020_flow.svg` | PRISMA 2020 flow diagram with the identification stage completed (records per source, duplicates removed, records to screen) |
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

## Why

| | Librarian request | AI search assistants | Single-purpose tools | **librarian-search** |
|---|---|---|---|---|
| Line-by-line strategy with hit counts | ✅ | ❌ | translation only | ✅ |
| Reproducible, pasteable queries | ✅ | ❌ | ✅ | ✅ |
| Multi-database retrieval | ✅ | partial | ❌ | ✅ automatic + import |
| Cross-database deduplication with audit trail | ✅ (EndNote) | ❌ | dedup only | ✅ |
| Native EndNote library with groups | ✅ | ❌ | ❌ | ✅ |
| PRISMA-S reporting text | sometimes | ❌ | ❌ | ✅ |
| Validation-set recall check with diagnosis | sometimes | ❌ | ❌ | ✅ (which concept lost each missed study) |
| Update searches (new vs previously screened) | ✅ | ❌ | dedup tools | ✅ |
| Published benchmark | n/a | rarely | some | ✅ [below](#benchmarks) |
| Turnaround | days to weeks | minutes | per step | minutes |

librarian-search doesn't replace a librarian's judgement. It gives you a librarian-structured first pass that a librarian can review quickly (PRESS), and that a journal reviewer can audit.

Compared with end-to-end LLM review pipelines (TrialMind, otto-SR, AgentSLR), librarian-search does less: it stops at a screened-ready, deduplicated record set. It does that step the way journals and librarians expect: Boolean, multi-database, reproducible, and reported to PRISMA-S. Its output feeds screening tools such as ASReview, Covidence or Rayyan.

---

## Benchmarks

Both benchmarks are scripts in [`benchmarks/`](benchmarks/) that download public data and can be rerun.

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

## Quick start

```bash
git clone https://github.com/wmyung/librarian-search ~/librarian-search
cd ~/librarian-search && uv sync               # Python 3.10+, installs openpyxl and python-docx
ln -s ~/librarian-search/skill ~/.claude/skills/librarian-search   # optional: Claude Code skill

LS="uv run --project ~/librarian-search librarian-search"
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

## Deduplication

Records are linked by PMID or NCT number; by DOI when titles and first pages are also compatible (conference supplements often share one DOI); or by normalised title (exact, or a ≥40-character prefix match for titles with appended translations) + publication year ±1 + compatible first author + no conflicting first page. The record from the highest-priority source is kept (default MEDLINE > Embase > Cochrane > WoS > …, configurable). Empty fields such as abstract or DOI are filled in from its duplicates. Every removed record stays in the EndNote Trash and in the `Duplicates` sheet, with its match basis.

---

## For AI agents

| User says | You do |
|---|---|
| "Do a literature search / find prior studies on X" | Load the `librarian-search` skill → `init` → write `strategy.json` → `count` → `run` |
| "Here are my Embase / Cochrane / WoS exports" | `set-counts` and `import` for each source |
| "These papers must be found" | `validate --known …`; fix the concept line it reports, rerun, validate again |
| "Update last year's search" | `build --previous <old export>` |
| "Also check references and citing papers" | `cite` with 2–5 key trials or reviews; add `citation.filter` if off-topic |
| "Give me the package" | `build` → fill `letter_draft.md` → `letter.md` → `build` → send the zip |

Rules the skill enforces: report only real counts and dates, never limit by study design for narrative reviews, keep every record (flags are screening aids), and put no names or institutions in outputs.

---

## Project layout (one search request)

```
request.md  strategy.json  letter_draft.md  letter.md
records/<db>.jsonl   runs/counts.json   runs/citation_log.json
out/   <- deliverables and *_literature_search_YYYYMMDD.zip
```

## Tests

```bash
uv run --project ~/librarian-search python -m pytest ~/librarian-search/tests -q
```

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

## Related projects

- **[wmyung/endnote-fieldcode-converter](https://github.com/wmyung/endnote-fieldcode-converter)**: turn plain-text citations in a DOCX manuscript into EndNote field codes. A good next step after screening the librarian-search library.
- **[wmyung/endnote-fieldcode-gui](https://github.com/wmyung/endnote-fieldcode-gui)**: an offline Mac app for the same conversion.
- **[wmyung/paper-to-llm-wiki-digest](https://github.com/wmyung/paper-to-llm-wiki-digest)**: digest included papers into an LLM-ready research wiki.
- **[wmyung/manuscript-to-editable-slides](https://github.com/wmyung/manuscript-to-editable-slides)**: turn the finished manuscript into an editable slide deck.

## Notes

EndNote is a trademark of Clarivate. librarian-search is not affiliated with Clarivate, NLM, EMBL-EBI, Elsevier, Wiley or OpenAlex. It writes EndNote's SQLite library format for interoperability. Respect each database's terms of use; subscription databases are searched by you, through your own access.

## License

MIT
