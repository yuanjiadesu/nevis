## Context

The API already owned tenant-authorised client, document, and search behavior. The console needed to remain a client of those contracts without duplicating domain logic.

## Goals / Non-Goals

**Goals:**

- Expose the completed backend as one product
- Avoid a second runtime service
- Preserve the Nevis palette, typography, and operational density

**Non-Goals:**

- Server-side rendering or a Node runtime
- A component framework or generic dashboard
- Public-site code, media, or remote fonts
- Production browser authentication or tenant administration

## Decisions

### Use headless behavior and project styling

`@base-ui/react` supplies dialog and menu behavior. `lucide-react` supplies directly imported icons. One project stylesheet owns visual identity.

Component frameworks were rejected because their global styles produced about 94% of the compiled CSS for the measured console. The final budget was 8 kB gzip for CSS and 175 kB gzip for JavaScript.

### Keep one destination

The client directory and selected client record form one destination. The header contains workspace identity, adviser identity, and global search. A navigation rail would list only one item.

### Separate search from filtering

The `Cmd/Ctrl+K` palette sends tenant-wide queries to `/search`. It groups typed results, reports degraded retrieval, stores versioned recent queries, and opens result context.

`Filter clients` and `Filter documents` narrow loaded rows only. Labels and placement distinguish local filtering from workspace search.

### Keep server state in TanStack Query

TanStack Query owns requests, mutations, caching, and invalidation. React Hook Form and Zod validate forms. Generated OpenAPI types surface contract drift during compilation.

### Use semantic collections

Clients and documents render as tables with one primary action. Titles open records; secondary actions use one row menu. Below 720 px, tables become stacked rows.

### Add management contracts before screens

Client lists use opaque cursors. Updates accept bounded fields and record authorisation. Document and version timelines return safe metadata without content. Unknown and cross-tenant records share the same `404`.

## Risks / Trade-offs

- **Owned visual states**: Keep primitives shared and review one stylesheet
- **Longer builds**: Pin and cache the frontend toolchain; exclude Node from the runtime image
- **Wider read surface**: Reuse tenant checks, opaque cursors, generic `404` responses, and cross-tenant tests
- **Loaded-row filters**: Label their scope when more pages exist
- **Legacy documents without clients**: Show them without inventing a client route

## Migration Plan

1. Add management contracts and tests
2. Add the frontend workspace and static delivery
3. Build search, client, and document workflows
4. Update containers, continuous integration, documentation, and browser tests

Rollback redeploys the previous image. The change requires no stored-data rollback.
