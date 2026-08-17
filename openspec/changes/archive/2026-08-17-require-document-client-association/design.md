## Context

`documents.client_id` was nullable only to preserve documents created before client records. Every unassociated code path followed from that temporary state.

## Goals / Non-Goals

**Goals:**

- Require exactly one client for every document
- Make document search results understandable without another request

**Non-Goals:**

- Guessing an owner for unassociated documents
- Changing ranking, authorisation, or other search behavior

## Decisions

### Delete unowned documents

The migration deletes documents without clients and their dependent records. Quarantine would preserve the invalid state, and no owner can be inferred.

The downgrade restores a nullable column but cannot restore deleted rows.

### Join the client in search

The authorised search relation already joins documents. It also joins the owning client and returns the display name.

Resolving each client separately could add 20 requests to a result page. Server-side resolution avoids that fan-out.

### Keep display names outside provenance

Provenance stores audit identities: tenant, client, source, version, and authorisation decisions. `client_name` is presentation data beside title and snippet.

## Risks / Trade-offs

- **Irreversible deletion**: Delete only unowned records and follow foreign-key order
- **Dropped search rows**: Apply `NOT NULL` in the same migration as the inner join assumption
