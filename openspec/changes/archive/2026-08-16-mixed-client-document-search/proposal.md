## Why

The platform can now represent clients and their documents, but search still returns documents only. Grigory explicitly requires one mixed result list, and the completed ownership model now makes it possible to add that behavior without weakening tenant authorization or provenance.

## What Changes

- Add tenant-authorized client matching across normalized email, name, and description, with exact identity matches preferred and no maintained keyword or synonym mappings.
- Extend the existing document-search pipeline to combine client matches with current-version document matches through deterministic rank fusion rather than incomparable raw scores.
- **BREAKING** Change `GET /search` results to a discriminated mixed contract with `type: client` and `type: document` variants and a stable total order.
- Preserve authorization-before-retrieval, signed pagination, lexical degradation, relevance thresholds, credential-safe audit data, and complete type-appropriate provenance.
- Add labelled mixed-search evaluation, tenant-isolation, pagination, performance, and real-provider smoke coverage for the declared workload.
- Keep client embeddings, fuzzy/trigram matching, manual keyword mappings, LLM query rewriting, and a second search endpoint out of this increment.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `client-records`: Add authorized, bounded, deterministic client matching and client-result provenance.
- `document-search`: Replace the document-only response with one mixed client/document result list while retaining the existing hybrid document behavior, failure semantics, authorization boundary, pagination, and auditability.

## Impact

- Changes the `/search` domain and HTTP response models, cursor state/version, repositories, ranking service, telemetry, and audit metadata.
- Adds tenant-leading PostgreSQL client-search support and an Alembic migration without changing the embedding-provider or indexing-worker contracts.
- Requires contract consumers to branch on the result discriminator and use type-specific provenance.
- Extends unit, PostgreSQL integration, HTTP contract, E2E, relevance, query-plan, and performance coverage plus README/API/runbook/master-plan documentation.
