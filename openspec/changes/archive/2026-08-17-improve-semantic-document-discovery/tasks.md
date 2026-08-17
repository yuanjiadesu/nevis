## 1. Establish the evidence gate

- [x] 1.1 Add graded address evidence, hard negatives, identifiers, paraphrases, nonsense, and a regression subset.
- [x] 1.2 Measure candidate Recall@k, final Precision@5, MRR, NDCG@10, ordering, empty results, result mix, and p95.
- [x] 1.3 Compare MiniLM and BGE rerankers on CPU. Pin a revision only if every gate passes.

## 2. Route queries

- [x] 2.1 Recognise complete emails and domains; send ambiguous input to natural-language search.
- [x] 2.2 Skip embeddings for identifiers while keeping client and document lexical retrieval.
- [x] 2.3 Gather bounded lexical and vector chunks after tenant and lifecycle filters.

## 3. Rank document evidence

- [x] 3.1 Add the pinned local reranker behind a bounded, timed interface with health reporting.
- [x] 3.2 Rerank chunks, apply admission, select one passage per document, and preserve exact-client precedence.
- [x] 3.3 Return `hybrid_unreranked` on ranker failure and `lexical_degraded` on embedding failure.

## 4. Return evidence previews

- [x] 4.1 Return a bounded lexical match window or winning reranked chunk without generation.
- [x] 4.2 Test later matches, passage selection, bounds, escaping, typed results, tenant isolation, degradation, and audit exclusion.

## 5. Publish and verify v3

- [x] 5.1 Bind routing, candidates, reranker, admission, modes, cursors, and audit metadata to `mixed-rrf-v3`.
- [x] 5.2 Document the evidence-first flow, model choice, degraded modes, previews, and exclusion of summaries.
- [x] 5.3 Run unit, integration, real-model, failure, formatting, lint, typing, latency, and strict OpenSpec checks.

## 6. Match fields predictably

- [x] 6.1 Normalize email punctuation while preserving exact email and full-name precedence.
- [x] 6.2 Add token-prefix matching to client identity and document titles; keep content whole-term.
- [x] 6.3 Verify result types, prefixes, tenant isolation, and v3 relevance metrics.
