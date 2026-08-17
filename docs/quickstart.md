# Verify the main workflow

This walkthrough creates a client, adds a document, waits for indexing, and finds the document through workspace search.

## Before you begin

Start Nevis and provision `local-advisor` through [Start locally](../README.md#start-locally). These commands use the local non-browser identity boundary.

Document summaries stay off in the default stack. Enable them only for fictional data through [Model providers](model-providers.md).

## Create a client

Set the local request context and create Ada Lovelace:

```bash
export NEVIS_QUICKSTART_URL=http://localhost:8001
export NEVIS_QUICKSTART_TENANT=nevis-global
export NEVIS_QUICKSTART_ADVISOR=local-advisor

CLIENT_RESPONSE="$(
  curl --fail --silent --show-error "$NEVIS_QUICKSTART_URL/v1/clients" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-Nevis-Tenant: $NEVIS_QUICKSTART_TENANT" \
    -H "X-Nevis-Advisor: $NEVIS_QUICKSTART_ADVISOR" \
    -H "Idempotency-Key: quickstart-client-v1" \
    -d '{
      "first_name": "Ada",
      "last_name": "Lovelace",
      "email": "ada.quickstart@nevis.test",
      "description": "Pension planning client",
      "social_links": [],
      "source_type": "quickstart",
      "source_reference": "quickstart-client"
    }'
)"
export NEVIS_QUICKSTART_CLIENT_ID="$(
  printf '%s' "$CLIENT_RESPONSE" |
    uv run python -c 'import json, sys; print(json.load(sys.stdin)["id"])'
)"
```

## Add a document

Attach a pension note to the new client:

```bash
DOCUMENT_RESPONSE="$(
  curl --fail --silent --show-error \
    "$NEVIS_QUICKSTART_URL/v1/clients/$NEVIS_QUICKSTART_CLIENT_ID/documents" \
    -X POST \
    -H "Content-Type: application/json" \
    -H "X-Nevis-Tenant: $NEVIS_QUICKSTART_TENANT" \
    -H "X-Nevis-Advisor: $NEVIS_QUICKSTART_ADVISOR" \
    -H "Idempotency-Key: quickstart-document-v1" \
    -d '{
      "source_reference": "quickstart",
      "external_document_id": "pension-note-v1",
      "title": "Pension allowance note",
      "content": "Review the annual pension allowance before the next meeting."
    }'
)"
export NEVIS_QUICKSTART_VERSION_ID="$(
  printf '%s' "$DOCUMENT_RESPONSE" |
    uv run python -c \
      'import json, sys; print(json.load(sys.stdin)["document_version_id"])'
)"
```

## Wait for indexing

Poll the immutable version until indexing completes:

```bash
VERSION_URL="$NEVIS_QUICKSTART_URL/v1/document-versions"

while true; do
  VERSION_RESPONSE="$(
    curl --fail --silent --show-error \
      "$VERSION_URL/$NEVIS_QUICKSTART_VERSION_ID" \
      -H "X-Nevis-Tenant: $NEVIS_QUICKSTART_TENANT" \
      -H "X-Nevis-Advisor: $NEVIS_QUICKSTART_ADVISOR"
  )"
  VERSION_STATUS="$(
    printf '%s' "$VERSION_RESPONSE" |
      uv run python -c \
        'import json, sys; print(json.load(sys.stdin)["indexing_status"])'
  )"
  test "$VERSION_STATUS" = completed && break
  test "$VERSION_STATUS" = failed && printf '%s\n' "$VERSION_RESPONSE" && exit 1
  sleep 1
done
```

## Search the workspace

Search for evidence from the document:

```bash
curl --fail --silent --show-error --get "$NEVIS_QUICKSTART_URL/search" \
  -H "X-Nevis-Tenant: $NEVIS_QUICKSTART_TENANT" \
  -H "X-Nevis-Advisor: $NEVIS_QUICKSTART_ADVISOR" \
  --data-urlencode "q=annual pension allowance" |
  uv run python -m json.tool
```

The response should use `mixed-rrf-v5` and include document, version, tenant, and authorisation provenance. Repeat the workflow to confirm both writes return `outcome: replayed` without creating duplicates.
