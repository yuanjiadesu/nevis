## 1. Serialize ingestion

- [x] 1.1 Add a transaction-scoped advisory-lock helper for tenant idempotency and logical document identities
- [x] 1.2 Acquire both locks before reading idempotency, source, document, or version state
- [x] 1.3 Map concurrent uniqueness failures to replay or `409` outcomes

## 2. Verify concurrency

- [x] 2.1 Test equivalent concurrent requests create one version and one replay
- [x] 2.2 Test concurrent revisions create distinct sequential versions
- [x] 2.3 Test concurrent idempotency conflicts return `409` without rejected records
- [x] 2.4 Run focused tests, formatting, typing, and strict OpenSpec validation
