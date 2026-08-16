"""Exercise the trusted plain-text ingestion path inside the Compose network."""

import asyncio
import json
import time
import urllib.request

from sqlalchemy import text

from nevis.infrastructure.database import build_engine
from nevis.settings import get_settings

identity_headers = {
    "Content-Type": "application/json",
    "X-Nevis-Tenant": "nevis-global",
    "X-Nevis-Advisor": "compose-smoke-advisor",
}
client_request = urllib.request.Request(
    "http://127.0.0.1:8000/v1/clients",
    data=json.dumps(
        {
            "first_name": "Nevis",
            "last_name": "Indexing",
            "email": "compose-mixed-fixture-v3@nevis.test",
            "description": "Mixed client and document search smoke fixture",
            "social_links": [],
            "source_type": "smoke",
            "source_reference": "compose-mixed-client-v3",
        }
    ).encode(),
    headers={**identity_headers, "Idempotency-Key": "compose-mixed-client-v3"},
    method="POST",
)
with urllib.request.urlopen(client_request) as response:
    client_id = json.load(response)["id"]

payload = json.dumps(
    {
        "source_reference": "compose-smoke",
        "external_document_id": "mixed-client-associated-fixture-v3",
        "title": "Mixed Compose smoke fixture",
        "content": "A harmless Nevis indexing smoke-test document.",
    }
).encode()
request = urllib.request.Request(
    f"http://127.0.0.1:8000/v1/clients/{client_id}/documents",
    data=payload,
    headers={
        **identity_headers,
        "Idempotency-Key": "compose-smoke-mixed-client-document-v3",
    },
    method="POST",
)
with urllib.request.urlopen(request) as response:
    accepted = json.load(response)

for _ in range(30):
    status_request = urllib.request.Request(
        f"http://127.0.0.1:8000/v1/document-versions/{accepted['document_version_id']}",
        headers={"X-Nevis-Tenant": "nevis-global", "X-Nevis-Advisor": "compose-smoke-advisor"},
    )
    with urllib.request.urlopen(status_request) as response:
        document_status = json.load(response)
    if document_status["indexing_status"] == "completed":
        assert document_status["chunk_count"] > 0
        break
    time.sleep(1)
else:
    raise RuntimeError("fixture indexing did not complete")


async def verify_lineage() -> None:
    engine = build_engine(get_settings().database_url)
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    text(
                        "SELECT c.tenant_id, c.source_id, c.document_id, "
                        "c.document_version_id, c.embedding_profile_id, "
                        "c.authorization_decision_id "
                        "FROM document_chunks c WHERE c.document_version_id = :version_id"
                    ),
                    {"version_id": str(accepted["document_version_id"])},
                )
            ).one()
            assert all(value is not None for value in row[:5])
            assert row[5] is not None
    finally:
        await engine.dispose()


asyncio.run(verify_lineage())
