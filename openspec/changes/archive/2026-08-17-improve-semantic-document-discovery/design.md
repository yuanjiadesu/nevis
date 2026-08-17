## Context

The previous policy used PostgreSQL lexical retrieval, BGE-small vectors, reciprocal rank fusion (RRF), and a `0.70` cosine admission threshold. For `address proof`, the address-change negative scored `0.6647`, the utility-bill positive scored `0.6240`, and the utility-investment negative scored `0.5203`.

No vector cutoff could accept the required positive and reject the higher negative. Previews also returned the first 280 characters instead of the strongest evidence.

## Goals / Non-Goals

**Goals:**

- Separate candidate recall from final relevance
- Keep identifier lookup precise
- Return the passage supporting each document result

**Non-Goals:**

- Generated summaries or query rewriting
- Fuzzy matching or another search store
- Inferring documents from client metadata
- Model fine-tuning without representative failures

## Decisions

### Route only complete identifiers

A deterministic classifier sends valid emails and domains to client and document lexical retrieval. Other input uses hybrid retrieval.

Literal document matching remains available because a document can contain the identifier. A model classifier was rejected for latency, reproducibility, and query disclosure.

### Match each field deliberately

Client emails and queries share punctuation boundaries. Client identity and document titles accept token prefixes. Document content uses whole-term PostgreSQL full-text search.

Client and document branches remain independent. A client match does not admit its documents. Exact email and full-name bands keep higher precedence.

### Retrieve broadly and rerank narrowly

Natural-language search retrieves bounded lexical and vector chunks after tenant filtering. RRF combines their ranks. A small cross-encoder scores only the resulting candidates, selects the winning passage per document, and controls final admission.

The vector floor limits work rather than deciding relevance. Lowering the old threshold was rejected because the hard negative outranked the positive. Query expansion also failed to repair the ordering.

The model bake-off compared MiniLM MS MARCO and a BGE reranker on CPU. A model could ship only if it passed required ordering, corpus metrics, empty-result behavior, and p95 latency.

### Report reranker failure

If evidence ranking fails, return authorised hybrid candidates as `hybrid_unreranked`. Embedding failure remains `lexical_degraded`. Database, authorisation, and audit failures return no partial results.

`mixed-rrf-v3` binds routing, candidates, model revision, admission, cursors, and modes. Audit metadata identifies the policy without queries, excerpts, content, or model inputs.

### Return the winning passage

Literal results use a bounded window around matched terms. Natural-language results use the winning reranked chunk. The system falls back to the chunk start only when no safe match window exists.

The preview uses stored source text and adds no generation or summary boundary.

### Evaluate retrieval and ranking separately

Candidate Recall@k measures first-stage coverage. Final Precision@5, mean reciprocal rank (MRR), normalized discounted cumulative gain at 10 (NDCG@10), required ordering, empty results, result mix, and p95 latency gate the full policy.

Required cases cannot fail behind an aggregate improvement.

## Risks / Trade-offs

- **One-case improvement**: Require case-level and aggregate regression gates
- **High latency**: Bound candidates and benchmark on CPU
- **Reranker outage**: Return `hybrid_unreranked`
- **Ambiguous dotted prose**: Require a complete identifier shape
- **Broad excerpts**: Keep existing text bounds, tenant checks, and audit exclusions
- **Model drift**: Pin revisions and rerun evaluation
- **Cursor incompatibility**: Reject v2 cursors under v3

## Migration Plan

Run the offline bake-off before adding the model. Deploy the selected reranker, routing, candidate policy, evidence preview, modes, and `mixed-rrf-v3` together.

No stored data migration is required. Rollback restores v2 and invalidates cursors from the other version.
