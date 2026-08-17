## Why

Nevis had client, ingestion, and search APIs but no adviser interface. This change added a compact React console over those authorised contracts.

## What Changes

- Add a same-origin React console built with TypeScript and Vite
- Serve compiled assets from FastAPI without Node in the runtime image
- Add client directory, client record, document collection, and focused dialogs
- Add global client and document search through a `Cmd/Ctrl+K` palette
- Add the authorised list, update, and timeline endpoints required by the console

## Capabilities

### New Capabilities

- `advisor-console-ui`: Console shell, search, record workflows, brand treatment, and footprint budget

### Modified Capabilities

- `client-records`: Paginated client listing and bounded updates
- `document-retrieval`: Client document and version timelines
- `platform-runtime`: Same-origin console delivery

## Impact

Added a pinned pnpm, Vite, and TypeScript workspace under `web/`, generated OpenAPI types, protected management endpoints, and Playwright coverage.

The change did not add production browser authentication, file upload, optical character recognition, deletion, bulk operations, tenant administration, or server-side rendering.
