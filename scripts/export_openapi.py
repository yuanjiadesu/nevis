"""Export Nevis's OpenAPI document for the advisor console type generator."""

import json
from pathlib import Path

from nevis.main import create_app
from nevis.settings import Settings

Path("openapi.json").write_text(
    json.dumps(
        create_app(
            Settings(
                _env_file=None,
                environment="local",
                identity_provider="local-header",
                document_summaries_enabled=False,
                fictional_test_data=False,
            )
        ).openapi(),
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
