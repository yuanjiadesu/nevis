import os
import re
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from nevis.domain.identity import IdentityMode, IdentityProviderHealth
from nevis.infrastructure.local_console import LocalConsoleCookieCodec
from nevis.main import create_app
from nevis.settings import Settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class OIDCProvider:
    mode = IdentityMode.OIDC

    async def authenticate(self, credentials):  # pragma: no cover - route fixture only
        raise AssertionError

    async def healthcheck(self) -> IdentityProviderHealth:
        return IdentityProviderHealth(True, self.mode)

    async def aclose(self) -> None:
        return None


def test_importing_main_does_not_load_runtime_settings() -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "NEVIS_DOCUMENT_SUMMARIES_ENABLED": "true",
            "NEVIS_FICTIONAL_TEST_DATA": "true",
            "NEVIS_LLM_API_KEY": "",
        }
    )

    result = subprocess.run(
        [sys.executable, "-c", "import nevis.main"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_alembic_offline_mode_reads_only_database_settings() -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "NEVIS_DOCUMENT_SUMMARIES_ENABLED": "true",
            "NEVIS_FICTIONAL_TEST_DATA": "true",
            "NEVIS_LLM_API_KEY": "",
        }
    )

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_local_console_marker_rejects_missing_and_forged_values() -> None:
    codec = LocalConsoleCookieCodec("test-signing-key")
    marker = codec.issue()

    assert codec.accepts(marker)
    assert not codec.accepts(None)
    assert not codec.accepts(f"{marker}x")


def test_workspace_and_assets_are_served_with_local_identity_mode() -> None:
    app = create_app(Settings(_env_file=None, environment="local"))
    with TestClient(app) as client:
        workspace = client.get("/")
        assert workspace.status_code == 200
        assert workspace.headers["cache-control"] == "no-store"
        assert "Nevis Advisor Console" in workspace.text
        assert "/assets/" in workspace.text
        asset = re.search(r'(?:src|href)="(/assets/[^"]+)"', workspace.text)
        assert asset is not None
        assert client.get(asset.group(1)).status_code == 200
        favicon = client.get("/favicon.svg")
        assert favicon.status_code == 200
        assert favicon.headers["content-type"] == "image/svg+xml"
        assert client.get("/health/live").json() == {"status": "ok"}


def test_workspace_is_not_served_in_production() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        oidc_issuer="https://issuer.example",
        oidc_audience="nevis-workspace",
        search_cursor_signing_key="x" * 32,
    )
    app = create_app(settings, identity_provider=OIDCProvider())
    with TestClient(app) as client:
        response = client.get("/")
        favicon = client.get("/favicon.svg")
        context = client.get("/ui/context")
    assert response.status_code == 404
    assert favicon.status_code == 404
    assert context.status_code == 404
