# Use the adviser console

The console lets an adviser manage clients and documents and search one authorised workspace.

## Open the console

Start Nevis and provision `local-advisor` through [Run](../README.md#run), then open `http://localhost:8001`. The hosted UAT console is [nevis.syntax.fitness](https://nevis.syntax.fitness); Cloudflare Access admits named users only.

The local console loads `local-advisor` in `nevis-global`. A signed, HttpOnly marker preserves that fixed context, so the browser sends no adviser or tenant headers.

## Complete the main workflow

1. Create or open a client
2. Update the client when needed
3. Add or revise a plain-text document
4. Check indexing status and version history
5. Press `Cmd/Ctrl+K` and submit a search
6. Open a result and inspect its client, source, and document version

Global search calls the server after submission. Client and document filters narrow only the rows already loaded in the browser.

## Check expected behavior

The interface should preserve these behaviors:

- New and revised documents show their indexing state
- Documents show ready, pending, processing, failed, or not-requested summary states
- Failed indexing shows a safe status without provider details
- Search reports lexical or reranker degradation
- Selected clients and documents remain in the URL after reload
- Unknown and cross-tenant records reveal no data
- Browser requests contain no identity headers or tokens

## Run console tests

Static frontend checks run from `web/`:

```bash
pnpm lint
pnpm test
pnpm build
```

The browser workflow runs from the repository root and covers workspace loading, keyboard search, client updates, document creation and revision, history, filtering, responsive layout, and header-free identity:

```bash
uv run playwright install chromium
uv run pytest tests/browser
```

## Know the console limits

The console supports fictional plain-text data and labelled document summaries. It has no production browser authentication, file upload, deletion, bulk actions, tenant administration, or generated answers.

The source lives in `web/src/`, and the generated `web/src/api.generated.ts` types keep it aligned with the root `openapi.json` contract.
