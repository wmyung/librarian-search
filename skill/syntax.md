# Database syntax cheat sheet (translate the same logic for every database)

Example concepts: intervention (vitamin D) AND condition (fracture).

| Feature | PubMed | Ovid MEDLINE | Embase.com | Cochrane Library | Web of Science | Europe PMC |
|---|---|---|---|---|---|---|
| Controlled vocabulary, exploded | `"Vitamin D"[Mesh]` | `exp Vitamin D/` | `'vitamin d'/exp` | `MeSH descriptor: [Vitamin D] explode all trees` | (none) | `(MESH:"Vitamin D")` |
| Controlled vocabulary, not exploded | `"X"[Mesh:NoExp]` | `X/` | `'x'/de` | `... single term` | — | — |
| Major topic | `[Majr]` | `*X/` | `'x'/mj` | — | — | — |
| Title/abstract | `term[tiab]` | `term.ti,ab.` | `term:ab,ti` | `term:ti,ab,kw` | `TS=(term)` (title, abstract, keywords) | `(TITLE_ABS:(term))` |
| Truncation | `fracture*` | `fracture*` / `$` | `fracture*` | `fracture*` | `fracture*` | `fracture*` |
| 0–1 character | — | `fracture$1` | `fracture$` | — | `fracture$` | — |
| Phrase | `"hip fracture"[tiab]` | `"hip fracture".ti,ab.` | `'hip fracture':ab,ti` | `"hip fracture"` | `"hip fracture"` | `"hip fracture"` |
| Proximity | `"hip fracture"[tiab:~3]` (phrases only, no truncation) | `(hip adj3 fractur*).ti,ab.` | `(hip NEAR/3 fractur*):ab,ti` | `(hip near/3 fractur*):ti,ab,kw` | `hip NEAR/3 fractur*` | `"hip fracture"~3` |
| Line references | `#1 OR #2` (expanded by litsearch) | `1 or 2` | `#1 OR #2` | `#1 OR #2` | `#1 OR #2` | `#1 OR #2` (expanded by litsearch) |

## Pitfalls
- **PubMed**: `[tiab:~N]` proximity works only on quoted phrases and cannot be truncated, so list the variants (`"hip fracture"[tiab:~3] OR "hip fractures"[tiab:~3] …`). Chemical names containing hyphens or brackets often return 0 with `[tiab]`; that is expected. Check MeSH tree positions with `litsearch mesh` before choosing a heading versus its parent.
- **Europe PMC**: **always wrap each fielded clause in parentheses.** Without them, a fielded clause after `OR` (`TITLE_ABS:(a) OR MESH:"b"`) leaks into full-text search and inflates counts; write `(TITLE_ABS:(a)) OR (MESH:"b")`. Unfielded terms search the full text. Hyphenated acronyms (e.g. `"SF-36"`) are split into tokens and can match unrelated or non-English text; AND the acronym with a concept word, and compare the count with PubMed. Preprints are included (SRC:PPR).
- **ClinicalTrials.gov**: a line is `{"query.cond": "...", "query.intr": "..."}` (separate condition and intervention fields, automatic synonym expansion). A plain string is used as `query.term`.
- **Embase.com**: Emtree headings can differ from MeSH (e.g. `'colecalciferol'/exp`). Drug `/exp` headings are broad because they include records that merely mention the drug; the final AND narrows them. Embase includes many conference abstracts; mention this in the letter.
- **Cochrane Library**: `:ti,ab,kw` is the default field set; "word variations have been searched" is the automatic stemming option. Record Reviews (CDSR) and Trials (CENTRAL) counts separately for the final line if possible.
- **Web of Science**: `TS=` covers title, abstract, author keywords and Keywords Plus. No controlled vocabulary. `NEAR/n`. Exports are limited to 1,000 records each.
- **Ovid**: line references have no `#` (`1 or 2`); `adjN` proximity; `exp X/` explodes.
- OR within a concept, AND between concepts. Avoid NOT (it silently drops relevant records).
- For narrative reviews, do not apply study-design filters (e.g. RCT filters); use the screening flags instead.
