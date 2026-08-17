import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import expect, sync_playwright

CONSOLE_DIRECTORY = Path(__file__).parents[2] / "src" / "nevis" / "ui" / "dist"
CLIENT = {
    "id": "client-1",
    "tenant_id": "tenant-1",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
    "description": "Retirement planning client",
    "social_links": [],
    "source_type": "advisor-console",
    "source_reference": "advisor-console",
    "creation_authorization_decision_id": "decision-1",
    "retrieval_authorization_decision_id": "decision-2",
    "created_at": "2026-08-16T00:00:00+00:00",
    "updated_at": "2026-08-16T00:00:00+00:00",
}


class ConsoleServer(ThreadingHTTPServer):
    daemon_threads = True


class ConsoleHandler(BaseHTTPRequestHandler):
    request_headers: ClassVar[list[dict[str, str]]] = []
    documents: ClassVar[list[dict[str, object]]] = []
    document_content: ClassVar[str] = ""
    document_version: ClassVar[int] = 0
    version_contents: ClassVar[dict[int, str]] = {}

    @staticmethod
    def context() -> dict[str, object]:
        return {
            "advisor": "local-advisor",
            "workspace": {"slug": "nevis-global", "name": "Local workspace"},
        }

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return None

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _asset(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Length", str(len(body)))
        content_type = {
            ".css": "text/css",
            ".html": "text/html",
            ".js": "text/javascript",
        }.get(path.suffix, "application/octet-stream")
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._asset(CONSOLE_DIRECTORY / "index.html")
        elif self.path.startswith("/assets/"):
            self._asset(CONSOLE_DIRECTORY / self.path.removeprefix("/"))
        elif self.path == "/ui/context":
            self._json(self.context())
        elif self.path.startswith("/v1/clients?"):
            self._headers()
            self._json({"clients": [CLIENT], "next_cursor": None})
        elif self.path == "/v1/clients/client-1":
            self._headers()
            self._json(CLIENT)
        elif self.path.startswith("/v1/clients/client-1/documents?"):
            self._headers()
            self._json({"documents": self.documents, "next_cursor": None})
        elif self.path.startswith("/search?"):
            self._headers()
            query = parse_qs(urlparse(self.path).query).get("q", [""])[0].lower()
            results: list[dict[str, object]] = []
            if "ada" in query:
                results.append(
                    {
                        "type": "client",
                        "title": "Ada Lovelace",
                        "email": "ada@example.com",
                        "excerpt": "Retirement planning client",
                        "fused_score": 1.0,
                        "match_band": 0,
                        "ranks": {
                            "client_lexical": 1,
                            "document_lexical": None,
                            "document_semantic": None,
                        },
                        "provenance": {
                            "tenant_id": "tenant-1",
                            "client_id": "client-1",
                            "creation_authorization_decision_id": "decision-1",
                            "search_authorization_decision_id": "decision-search",
                        },
                    }
                )
            if ("annual" in query or "anual" in query) and self.documents:
                results.append(
                    {
                        "type": "document",
                        "title": "Annual review",
                        "client_name": "Ada Lovelace",
                        "snippet": "Updated trusted planning notes.",
                        "fused_score": 0.9,
                        "match_band": 3 if "anual" in query else 2,
                        "ranks": {
                            "client_lexical": None,
                            "document_lexical": 1,
                            "document_semantic": 1,
                        },
                        "scores": {"lexical": 0.8, "semantic": 0.9},
                        "provenance": {
                            "tenant_id": "tenant-1",
                            "client_id": "client-1",
                            "source_id": "source-1",
                            "document_id": "document-1",
                            "document_version_id": f"version-{self.document_version}",
                            "embedding_profile_id": "profile-1",
                            "indexing_authorization_decision_id": "decision-index",
                            "search_authorization_decision_id": "decision-search",
                        },
                    }
                )
            self._json(
                {
                    "mode": "hybrid",
                    "ranking_version": "mixed-rrf-v5",
                    "results": results,
                    "next_cursor": None,
                }
            )
        elif self.path == "/v1/documents/document-1/edit":
            self._headers()
            self._json(
                {
                    "document_id": "document-1",
                    "client_id": "client-1",
                    "title": "Annual review",
                    "content": self.document_content,
                    "current_document_version_id": f"version-{self.document_version}",
                    "current_version_number": self.document_version,
                }
            )
        elif self.path.startswith("/v1/document-versions/version-") and self.path.endswith(
            "/content"
        ):
            self._headers()
            version = int(self.path.split("version-")[1].split("/")[0])
            self._json(
                {
                    "document_version_id": f"version-{version}",
                    "document_id": "document-1",
                    "version_number": version,
                    "content": self.version_contents[version],
                }
            )
        elif self.path == "/v1/documents/document-1/versions":
            self._headers()
            self._json(
                {
                    "versions": [
                        {
                            "document_version_id": f"version-{version}",
                            "document_id": "document-1",
                            "version_number": version,
                            "indexing_status": "queued",
                            "created_at": "2026-08-16T00:00:00+00:00",
                        }
                        for version in range(self.document_version, 0, -1)
                    ]
                }
            )
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def _headers(self) -> None:
        ConsoleHandler.request_headers.append(dict(self.headers.items()))

    def do_POST(self) -> None:  # noqa: N802
        self._headers()
        if self.path == "/ui/logout":
            self._json({"status": "signed_out"})
        elif self.path == "/v1/clients":
            self._json(CLIENT, HTTPStatus.CREATED)
        elif self.path == "/v1/clients/client-1/documents":
            ConsoleHandler.document_content = "Trusted planning notes."
            ConsoleHandler.document_version = 1
            ConsoleHandler.version_contents = {1: ConsoleHandler.document_content}
            ConsoleHandler.documents = [
                {
                    "document_id": "document-1",
                    "client_id": "client-1",
                    "title": "Annual review",
                    "current_document_version_id": "version-1",
                    "current_version_number": 1,
                    "indexing_status": "queued",
                    "created_at": "2026-08-16T00:00:00+00:00",
                    "summary_status": "not_requested",
                    "summary": None,
                }
            ]
            self._json(
                {
                    "client_id": "client-1",
                    "document_id": "document-1",
                    "document_version_id": "version-1",
                    "indexing_status": "queued",
                    "outcome": "created",
                    "version_number": 1,
                },
                HTTPStatus.ACCEPTED,
            )
        elif self.path == "/v1/documents/document-1/revisions":
            ConsoleHandler.document_content = "Updated trusted planning notes."
            ConsoleHandler.document_version = 2
            ConsoleHandler.version_contents[2] = ConsoleHandler.document_content
            ConsoleHandler.documents[0]["current_document_version_id"] = "version-2"
            ConsoleHandler.documents[0]["current_version_number"] = 2
            self._json(
                {
                    "client_id": "client-1",
                    "document_id": "document-1",
                    "document_version_id": "version-2",
                    "version_number": 2,
                    "indexing_status": "queued",
                    "outcome": "accepted",
                },
                HTTPStatus.ACCEPTED,
            )
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:  # noqa: N802
        self._headers()
        if self.path != "/v1/clients/client-1":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        for field in ("first_name", "last_name", "email", "description", "social_links"):
            if field in payload:
                CLIENT[field] = payload[field]
        self._json(CLIENT)


def test_advisor_console_uses_local_entry_and_management_workflows() -> None:
    ConsoleHandler.request_headers = []
    ConsoleHandler.documents = []
    ConsoleHandler.document_content = ""
    ConsoleHandler.document_version = 0
    ConsoleHandler.version_contents = {}
    server = ConsoleServer(("127.0.0.1", 0), ConsoleHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.set_default_timeout(5_000)
            page.goto(f"http://127.0.0.1:{server.server_port}")
            page.get_by_role("button", name="Search clients and documents").wait_for()
            page.keyboard.press("Control+K")
            search_input = page.get_by_role("combobox", name="Search clients and documents")
            search_input.fill("Ada")
            expect(search_input).to_have_attribute("aria-expanded", "true")
            search_input.press("Enter")
            active_option = page.get_by_role("option", name="Ada Lovelace")
            active_option.wait_for()
            assert page.evaluate(
                "document.activeElement.getAttribute('aria-activedescendant')"
            ) == active_option.get_attribute("id")
            page.locator(".search-type-filter__option").filter(has_text="Documents").click()
            page.get_by_text("No documents for “Ada”.").wait_for()
            expect(active_option).to_have_count(0)
            page.locator(".search-type-filter__option").filter(has_text="Clients").click()
            active_option.wait_for()
            page.keyboard.press("Escape")
            expect(page.get_by_role("button", name="Search clients and documents")).to_be_focused()
            page.get_by_role("button", name="Ada Lovelace").click()
            page.get_by_text("Retirement planning client").wait_for()
            page.get_by_role("button", name="Actions for Ada Lovelace").click()
            page.get_by_role("menuitem", name="Edit client").click()
            edit_client = page.locator("[role='dialog']:visible").filter(has_text="Edit client")
            edit_client.get_by_role("button", name="Add link").click()
            edit_client.get_by_role("textbox", name="Link 1", exact=True).fill(
                "https://www.linkedin.com/in/ada-lovelace"
            )
            edit_client.get_by_role("button", name="Save changes").click()
            page.get_by_role("link", name="https://www.linkedin.com/in/ada-lovelace").wait_for()
            page.get_by_role("button", name="Add document").click()
            page.get_by_label("Document title").fill("Annual review")
            page.get_by_label("Plain-text content").fill("Trusted planning notes.")
            page.get_by_role("button", name="Add document", exact=True).last.click()
            page.get_by_text("Version 1 added — queued.").wait_for()
            page.get_by_role("button", name="Close", exact=True).last.click()
            page.get_by_role("button", name="Annual review", exact=True).click()
            page.get_by_text("Trusted planning notes.").wait_for()
            page.get_by_role("button", name="Close", exact=True).last.click()
            page.get_by_role("searchbox", name="Filter documents").fill("missing")
            page.get_by_text("No documents match “missing”.").wait_for()
            page.get_by_role("button", name="Clear filter").click()
            document_row = page.locator("tr").filter(has_text="Annual review")
            document_row.get_by_role("button", name="Actions for Annual review").click()
            page.get_by_role("menuitem", name="Edit document").click()
            edit_dialog = page.locator("[role='dialog']:visible").filter(has_text="Edit document")
            edit_dialog.get_by_label("Plain-text content").fill("Updated trusted planning notes.")
            edit_dialog.get_by_role("button", name="Save new version").click()
            page.get_by_text("Version 2", exact=True).wait_for()
            document_row.get_by_role("button", name="Actions for Annual review").click()
            page.get_by_role("menuitem", name="Version history").click()
            page.get_by_text("Version 1", exact=True).wait_for()
            page.get_by_role("cell", name="Version 1", exact=True).locator("..").get_by_role(
                "button", name="View content"
            ).click()
            page.get_by_text("Trusted planning notes.").wait_for()
            page.get_by_role("button", name="Close", exact=True).last.click()
            page.keyboard.press("Control+K")
            search_input.fill("Anual")
            search_input.press("Enter")
            fuzzy_result = page.get_by_role("option", name="Annual review")
            expect(fuzzy_result.get_by_text("suggestion", exact=True)).to_be_visible()
            search_input.fill("Annual")
            search_input.press("Enter")
            document_result = page.get_by_role("option", name="Annual review")
            expect(document_result.locator(".result-parent")).to_have_text("Ada Lovelace")
            document_result.click()
            expect(page.locator(".document-content:visible")).to_have_text(
                "Updated trusted planning notes."
            )
            page.get_by_role("button", name="Close", exact=True).last.click()

            page.set_viewport_size({"width": 390, "height": 844})
            expect(page.get_by_role("button", name="Search clients and documents")).to_be_visible()
            page.get_by_role("button", name="Annual review", exact=True).wait_for()
            assert (
                page.evaluate(
                    "getComputedStyle(document.querySelector("
                    "'.data-table td[data-label=\"Version\"]')).display"
                )
                == "flex"
            )
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.get_by_role("button", name="Open session menu for local-advisor").click()
            page.get_by_role("menuitem", name="Sign out").click()
            page.get_by_role("heading", name="Signed out").wait_for()
            expect(page.get_by_role("button", name="Return to workspace")).to_be_visible()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

    assert all(
        "X-Nevis-Tenant" not in headers and "x-nevis-tenant" not in headers
        for headers in ConsoleHandler.request_headers
    )
    assert all(
        "X-Nevis-Advisor" not in headers and "x-nevis-advisor" not in headers
        for headers in ConsoleHandler.request_headers
    )
    assert any(
        "Idempotency-Key" in headers or "idempotency-key" in headers
        for headers in ConsoleHandler.request_headers
    )
