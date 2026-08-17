"""Verify preview ingestion, indexing, title search, and summary delivery."""

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import cast

TITLE = "Nevis Zephyr Pipeline Check"
CONTENT = "This fictional note describes PostgreSQL indexes and JSONB storage."


def http_client(
    base_url: str, tenant: str, advisor: str
) -> tuple[
    Callable[[str], dict[str, object]],
    Callable[[str, dict[str, object], str], dict[str, object]],
]:
    headers = {"X-Nevis-Tenant": tenant, "X-Nevis-Advisor": advisor}

    def read(path: str) -> dict[str, object]:
        request = urllib.request.Request(f"{base_url}{path}", headers=headers)
        with urllib.request.urlopen(request, timeout=30) as response:
            return cast(dict[str, object], json.load(response))

    def write(path: str, payload: dict[str, object], key: str) -> dict[str, object]:
        request = urllib.request.Request(
            f"{base_url}{path}",
            data=json.dumps(payload).encode(),
            method="POST",
            headers={**headers, "Content-Type": "application/json", "Idempotency-Key": key},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return cast(dict[str, object], json.load(response))

    return read, write


def verify(
    read: Callable[[str], dict[str, object]],
    write: Callable[[str, dict[str, object], str], dict[str, object]],
    *,
    timeout_seconds: int,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, str]:
    clients = read("/v1/clients?limit=1")
    client_rows = clients.get("clients")
    if not isinstance(client_rows, list) or not client_rows:
        raise RuntimeError("client stage failed")
    client_id = str(client_rows[0]["id"])
    accepted = write(
        f"/v1/clients/{client_id}/documents",
        {
            "source_reference": "preview-pipeline-check",
            "external_document_id": "preview-pipeline-check-v1",
            "title": TITLE,
            "content": CONTENT,
        },
        "preview-pipeline-check-v1",
    )
    document_id = str(accepted["document_id"])
    version_id = str(accepted["document_version_id"])
    deadline = time.monotonic() + timeout_seconds
    indexed = False
    summary_ready = False
    while time.monotonic() < deadline:
        version = read(f"/v1/document-versions/{version_id}")
        if version.get("indexing_status") == "failed":
            raise RuntimeError("indexing stage failed")
        indexed = version.get("indexing_status") == "completed"
        document = read(f"/v1/documents/{document_id}")
        if document.get("summary_status") == "failed":
            raise RuntimeError("summary stage failed")
        summary_ready = document.get("summary_status") == "ready" and bool(document.get("summary"))
        if indexed and summary_ready:
            break
        sleep(1)
    if not indexed:
        raise RuntimeError("indexing stage timed out")
    if not summary_ready:
        raise RuntimeError("summary stage timed out")
    query = urllib.parse.quote(TITLE)
    search = read(f"/search?q={query}&limit=20")
    results = search.get("results")
    if not isinstance(results, list) or not any(
        item.get("type") == "document"
        and item.get("provenance", {}).get("document_id") == document_id
        for item in results
    ):
        raise RuntimeError("title-search stage failed")
    return {"status": "ok", "document_id": document_id, "version_id": version_id}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--tenant", default="nevis-global")
    parser.add_argument("--advisor", default="local-advisor")
    parser.add_argument("--timeout", type=int, default=180)
    arguments = parser.parse_args()
    read, write = http_client(arguments.base_url.rstrip("/"), arguments.tenant, arguments.advisor)
    try:
        result = verify(read, write, timeout_seconds=arguments.timeout)
    except (KeyError, RuntimeError, urllib.error.URLError) as error:
        raise SystemExit(str(error)) from None
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
