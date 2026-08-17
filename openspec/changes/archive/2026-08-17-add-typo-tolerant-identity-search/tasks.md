## 1. Index client names and document titles

- [x] 1.1 Add the local `pyspellchecker` dependency and lock its compatible version.
- [x] 1.2 Create the `pg_trgm` extension and GIN trigram indexes over the client full-name expression and document title, with a reversible downgrade.
- [x] 1.3 Verify representative tenant-scoped client and document fallback queries use acceptable plans; defer `btree_gin` unless measurements require it.

## 2. Retrieve and rank trigram candidates

- [x] 2.1 Add client full-name and document-title fallback queries using the `mixed-rrf-v4` threshold of `0.5`, `<<%`, `strict_word_similarity`, existing candidate limits, and all tenant and lifecycle predicates.
- [x] 2.2 Reuse the existing document candidate joins and leading-content snippet for title trigram candidates. Leave content matching whole-term.
- [x] 2.3 Add `MatchBand.FUZZY` beneath `GENERAL`, combine approximate branch positions with fixed unit-weight RRF and stable tie-breakers, and bump the ranking policy and settings literal to `mixed-rrf-v4` without adding settings or response fields.
- [x] 2.4 Execute the client fallback only when all existing client lexical branches are empty and the document fallback only when combined document lexical retrieval is empty; never run either fallback on the identifier route.
- [x] 2.5 Preserve fuzzy-title candidates outside content-reranker admission while leaving existing lexical and semantic reranking unchanged.

## 3. Retry empty semantic searches

- [x] 3.1 Add a deterministic local corrector that considers only an alphabetic final token of at least five characters and returns a correction only for one unique dictionary candidate at edit distance one.
- [x] 3.2 After an ordinary non-identifier search returns no exact or general result, retry document lexical, semantic, and reranker retrieval once with the corrected query and place admitted results in `FUZZY`; do not rerun client matching or recurse.
- [x] 3.3 Keep the submitted query authoritative for response behavior, cursor fingerprints, authorization, audit, and telemetry; record only a `spelling_fallback_used` boolean.

## 4. Present and document approximate matches

- [x] 4.1 Preserve the existing audit and response shapes, record approximate results through the existing match band, and add no correction text, new rank fields, or sensitive text.
- [x] 4.2 Label fuzzy results in the console as suggestions using the existing returned match band.
- [x] 4.3 Document name/title recovery, empty-result spelling recovery, coarse family gating, the whole-term content boundary, literal identifier behavior, and invalidation of `mixed-rrf-v3` cursors.

## 5. Verify behavior

- [x] 5.1 Add focused labelled cases for `investment opportunit`, a successful query that must not be corrected, ambiguous and ineligible corrections, a misspelled client name and document title, short-name collision, nonsense query, misspelled content term, and near-miss complete identifier.
- [x] 5.2 Test the one-retry bound, submitted-query cursor binding and audit privacy, both coarse family gates, fuzzy-title survival outside reranker admission, band precedence, tenant isolation, identifier exclusion, deterministic pagination, and `mixed-rrf-v3` cursor rejection.
- [x] 5.3 Confirm existing labelled relevance metrics do not regress, measure empty-result retry latency, inspect representative query plans, and run formatting, linting, typing, focused tests, and strict OpenSpec validation.
