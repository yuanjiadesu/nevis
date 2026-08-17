## Why

A misspelled client name, document title, or semantic query term can currently return nothing. Exact and prefix matching cover `inheri` but not `inheritence`, while semantic retrieval can lose an otherwise successful paraphrase when its final word is one character short, such as `investment opportunit`.

## What Changes

- Add bounded trigram similarity fallback over client full names and document titles
- Run each fallback only when the existing client or document lexical family produced no candidate
- When the ordinary non-identifier search returns nothing, use a deterministic local spellchecker to correct one eligible final token and retry document retrieval once
- Rank every approximate candidate below all exact and general matches in a new lowest match band
- Keep email and domain queries literal, keep document content matching whole-term, and do not let the content reranker reject fuzzy-title candidates
- Bump the mixed ranking policy to `mixed-rrf-v4` and add focused misspelling regression cases

## Capabilities

### Modified Capabilities

- `document-search`: Recover client-name, document-title, and empty-result semantic matches from bounded misspellings in a lowest-precedence band
- `client-records`: Allow bounded trigram full-name candidates when no lexical client evidence exists

## Impact

Add two trigram indexes, the PostgreSQL `pg_trgm` extension, and one local spellchecker with its bundled English dictionary. This needs no generated column, multicolumn GIN index, network spelling service, or runtime service change.

Two repository fallback queries, one bounded semantic retry, one match band, and one ranking version change. Existing candidate limits are reused and correction bounds are fixed by the ranking policy, so no new settings or response fields are added. Authorization, tenant isolation, chunking, embedding profiles, and the document indexing pipeline do not change. Cursors issued under `mixed-rrf-v3` become invalid through the existing ranking-version check.

Ordinary semantic retrieval and identifier routing keep their current behavior. The corrected query is used only for one document retrieval retry after the ordinary search is empty; the submitted query remains authoritative everywhere else. Fuzzy-title candidates bypass content-reranker admission because title similarity is their evidence. No client or document family is answered by trigram evidence while its existing lexical retrieval has a candidate.
