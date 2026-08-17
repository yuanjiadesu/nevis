## 1. Require client ownership

- [x] 1.1 Delete unowned documents and dependent records, then set `documents.client_id` to `NOT NULL`.
- [x] 1.2 Require `client_id` in storage, document responses, edit responses, and search provenance.

## 2. Return the client in search

- [x] 2.1 Join the owning client in authorised search and title matching.
- [x] 2.2 Add `client_name` to document results and require provenance `client_id`.

## 3. Remove legacy paths

- [x] 3.1 Remove the revision guard for documents without clients.
- [x] 3.2 Remove non-navigable legacy results and show the client above each document title.

## 4. Verify the migration

- [x] 4.1 Update unit fixtures, browser mocks, and generated console types.
- [x] 4.2 Assert in browser tests that each document result shows its client.
- [x] 4.3 Run the migration on populated data and confirm every search document resolves a client.
