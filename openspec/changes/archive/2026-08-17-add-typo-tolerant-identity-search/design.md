## Context

`mixed-rrf-v3` routes complete emails and domains to literal retrieval and everything else to hybrid retrieval. Client candidates come from exact normalized email, exact full name, and a full-text vector over names, punctuation-split email, and description. Document candidates come from a full-text vector over titles with a prefix variant, a whole-term vector over chunk content, and pgvector similarity, fused by weighted reciprocal rank and reranked by MiniLM.

Every lexical branch is a lexeme match. A misspelled token produces a lexeme that exists in no index, so the affected branch returns nothing. Semantic retrieval can also cross its candidate or reranker admission threshold for `investment opportunity` but not the one-character-short `investment opportunit`; the relevant seeded documents contain neither word, so content-prefix matching cannot recover that case.

The declared envelope remains approximately 10,000 clients with 10 to 100 short documents each. `pg_trgm` is available in the deployed PostgreSQL image and unused.

## Goals / Non-Goals

**Goals:**

- Recover client full-name and document-title matches from misspelled queries
- Recover an otherwise successful document search when the final semantic query token has one edit
- Guarantee that no trigram candidate outranks any exact, prefix, or full-text match
- Keep the labelled nonsense query empty and bound approximate noise with an explicit floor
- Leave every existing labelled case measurably unchanged

**Non-Goals:**

- Trigram matching over client email, description, document content, or chunk text
- Accent folding, locale-aware collation, phonetic matching, or maintained synonyms
- LLM query rewriting, multi-token correction, corrections beyond one edit, or a suggestions endpoint
- Client embeddings, a new retrieval mode value, or a second search endpoint
- Changing chunking, embedding profiles, the document indexing pipeline, existing lexical or semantic reranking, or the response schema

## Decisions

### 1. Add a lowest match band without a new fusion branch

Add `MatchBand.FUZZY` below `GENERAL`. `mixed_order_key` already orders by match band before score, so an approximate candidate cannot outrank an exact identity match or a genuine lexical or semantic result. Rank each approximate branch first, convert branch position to unit-weight reciprocal rank with the existing RRF constant, then use the existing result-type and record-identity tie-breakers. This avoids comparing trigram similarity with corrected semantic scores directly.

Configurable approximate-branch weights and new rank fields were rejected because the match band already establishes precedence and fixed unit weights are sufficient for the fallback set. `match_band` is carried in the cursor, audit evidence, and result contract, so the console can label a suggestion without changing the response shape.

### 2. Run trigram retrieval only when its field family found nothing

Execute the client-name fallback only when exact email, exact name, and lexical client retrieval all returned zero candidates. Execute the document-title fallback only when the existing combined title/content lexical retrieval returned zero candidates. Gate these two existing families independently rather than on an empty page, so a mistyped client name is still recovered when a weak semantic document clears its floor.

This coarse family gate is intentional: a client description match suppresses fuzzy-name retrieval, and a document-content match suppresses fuzzy-title retrieval. Splitting the existing lexical queries into finer field families was rejected to keep this change small and to preserve current successful queries unchanged.

Never execute either branch on the identifier route. A complete email or domain is a literal assertion; approximate matching of `neviswealth.com` against `nevisweath.com` would silently answer a different question and would contradict the literal routing guarantee.

This gating makes the change provably neutral on every query that works today, which is what allows the existing labelled set to act as the regression control.

### 3. Filter with `strict_word_similarity` above an explicit floor

Use `strict_word_similarity` so the query is compared against word boundaries in the target. Fix the floor at `0.5` as part of `mixed-rrf-v4`, set it transaction-locally through `pg_trgm.strict_word_similarity_threshold`, filter with `<<%` so the index applies, and compute ordering with the function. Reuse the existing client and lexical candidate limits instead of adding settings.

The PostgreSQL default of `0.3` was rejected because it admits unrelated short names. The labelled nonsense case and a short-name collision case act as regression checks; the floor is a measured policy boundary rather than a guarantee for every future corpus.

Configurable thresholds and `levenshtein` were deferred. They add settings and calibration machinery without improving the first useful slice.

### 4. Use two trigram indexes

Add a GIN trigram expression index over the concatenated client full name and a GIN trigram index over `documents.title`. Every query still includes the tenant predicate and existing lifecycle predicates. Existing tenant indexes may be combined with the trigram indexes by PostgreSQL.

A generated identity column and tenant-leading multicolumn GIN indexes with `btree_gin` were rejected for the initial slice. They add schema and extension complexity; representative `EXPLAIN` checks will determine whether they are needed later.

### 5. Reuse the existing document candidate shape

The title fallback reuses the joins already in `search_lexical_candidates`: match the title, join chunks of the current successfully indexed version under the active profile, and return the leading content window as the snippet, exactly as the existing non-content-match path does.

Title similarity is sufficient admission evidence. Fuzzy-title candidates bypass the content-reranker threshold and remain in the `FUZZY` band; otherwise a relevant title could be discarded because its leading content does not repeat the title. Existing lexical and semantic candidates keep their current reranking behavior.

### 6. Retry an empty semantic search with one local correction

Add `pyspellchecker` as a local, deterministic dependency and use its bundled English frequency dictionary. Only after the ordinary non-identifier search has no admitted exact or general result, inspect the final whitespace-delimited token. Attempt a correction only when that token is alphabetic, at least five characters long, absent from the dictionary, and has exactly one highest-frequency candidate at Levenshtein distance one. Otherwise do not retry.

Replace only that final token and rerun document lexical retrieval, query embedding, semantic retrieval, and evidence reranking once with the corrected query. Do not rerun client matching, recurse into correction, or use the corrected text for the response, cursor fingerprint, authorization, audit, or telemetry. Rank admitted retry results in `FUZZY`. This preserves every successful original search and confines the extra embedding and reranker calls to a bounded empty-result path.

Always correcting before the first embedding was rejected because finance terms and proper nouns absent from a general dictionary could silently change successful searches. Content-prefix matching was rejected for this failure because the known relevant documents contain neither `opportunity` nor an inflected form.

### 7. Version the ranking policy and let old cursors fail

Bump `MIXED_RANKING_VERSION` and the settings literal to `mixed-rrf-v4`. Ordering semantics change, so cursors issued under `mixed-rrf-v3` must not continue. The existing cursor check rejects them as generic invalid cursors; no translation is added.

Record the band and a `spelling_fallback_used` boolean through existing audit metadata. Do not add correction text, new rank fields, query text, similarity scores of unreturned candidates, or client identity text to the response, audit, or telemetry.

## Risks / Trade-offs

- [A trigram guess is presented as a real match] → Rank it in the lowest band, gate it on an empty family, and expose the band so the console can label it a suggestion
- [The floor admits unrelated records] → Keep the nonsense and short-name cases in the selection split and assert the expected results before merge
- [Short names produce high similarity against unrelated short names] → Use `strict_word_similarity` at word boundaries and label short-name misspellings in the evaluation set
- [A dictionary correction changes the user's meaning] → Retry only after an empty ordinary search, correct only one eligible final token at edit distance one, require a unique best candidate, and keep results in the fuzzy band
- [Empty searches become slower] → Perform correction locally and allow at most one additional document retrieval, embedding, and reranker pass
- [Separate tenant and trigram indexes produce an inefficient plan] → Check representative plans and add a tenant-leading `btree_gin` index only if measurements require it
- [Ranking version bumps invalidate active cursors] → Accept it as the documented cursor contract and deploy the application and evaluation fixtures together
- [Fuzzy matching creeps into document content] → State the whole-term content rule in the modified requirement so the boundary is spec-enforced rather than conventional

## Migration Plan

1. Create `pg_trgm` and the client-name and document-title trigram indexes.
2. Deploy the two trigram fallbacks, local spelling dependency, bounded semantic retry, match band, ranking version, focused fixtures, and documentation as one increment.
3. Verify tenant isolation, family gates, identifier exclusion, fuzzy-title admission, `investment opportunit`, ambiguous/no-correction behavior, nonsense and short-name cases, and representative query plans before release.
4. Roll back the application to restore `mixed-rrf-v3`. Drop the two indexes through the migration downgrade when operationally appropriate.
