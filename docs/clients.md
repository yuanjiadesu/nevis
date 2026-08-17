# Work with client records

A client is a tenant-owned record. Advisers can create, update, list, retrieve, and find clients through workspace search.

## Data ownership

The client module owns names, email, description, social links, source provenance, and creation idempotency. Documents reference clients but belong to the [document module](documents.md).

| Record | Purpose |
| --- | --- |
| `clients` | Current fields and creation provenance |
| `client_creation_requests` | Idempotency key, request fingerprint, and resulting client |

Normalised email is unique within a tenant; different tenants can reuse the same email.

## Respect client limits

These limits apply after surrounding whitespace is removed:

| Value | Limit |
| --- | ---: |
| First or last name | 100 characters |
| Email | 320 characters; one address with a dotted domain |
| Description | 2,000 characters |
| Social links | 10 HTTPS or HTTP links, 500 characters each, 5,500 characters combined |
| Source type | 80 characters |
| Source reference | 200 characters |
| Idempotency key | 255 characters |
| Client list | 25 by default, 100 maximum |
| List cursor lifetime | 15 minutes by default |

## Create a client

Client creation runs in one transaction:

1. Record the authorisation decision
2. Normalise and validate client fields
3. Hash the request without its idempotency key
4. Check the tenant’s idempotency key and normalised email
5. Insert the client, idempotency record, and safe audit event
6. Commit the records together

Reusing a key with the same request returns the original client; reusing it with different data returns `409`. A database constraint resolves concurrent email conflicts.

## Read and update clients

Every query includes `tenant_id` and client ID, and unknown and cross-tenant clients return the same `404`. Lists use keyset pagination over creation time and ID, with the signed cursor bound to the tenant and collection.

Updates replace all editable fields, so name, email, description, and social links must be sent together. They preserve identity, tenant, source provenance, and the creation decision. There is no version precondition, so concurrent writes are last-write-wins, and email conflicts return `409`.

## Search clients

PostgreSQL indexes name, email, and description with a generated text-search vector and Generalized Inverted Index (GIN). Separate exact-email and exact-name branches take the highest client precedence.

Client records never reach the embedding provider or evidence ranker. See [Search engine](search-engine.md) for retrieval and ranking.

## Audit client actions

The application records allow, deny, replay, conflict, found, and not-found outcomes. Audit metadata can carry safe identifiers and reason codes, but excludes client fields, idempotency keys, and credentials. Validation returns `422` and conflicts return `409`.

The integration suite covers normalisation, replay, conflicts, concurrent uniqueness, pagination, tenant isolation, and audit redaction:

```bash
uv run pytest tests/integration/test_client_api.py
```

See the [client requirements](../openspec/specs/client-records/spec.md) for the observable contract.
