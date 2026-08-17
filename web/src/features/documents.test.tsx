import { renderToStaticMarkup } from "react-dom/server";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type DocumentSummary } from "../api";
import { renderWithQuery } from "../test/render";
import {
  DocumentCollection,
  DocumentDialog,
  DocumentSummaryState,
  DocumentSummaryText,
} from "./documents";

function documentRecord(overrides: Partial<DocumentSummary> = {}): DocumentSummary {
  return {
    client_id: "client-1",
    created_at: "2026-08-17T10:00:00Z",
    current_document_version_id: "version-1",
    current_version_number: 1,
    document_id: "document-1",
    indexing_status: "completed",
    summary: "The plan preserves a six-month emergency fund.",
    summary_status: "ready",
    title: "Annual plan",
    ...overrides,
  };
}

afterEach(() => vi.restoreAllMocks());

describe("document summaries", () => {
  it("labels and escapes generated text", () => {
    const markup = renderToStaticMarkup(
      <DocumentSummaryText summary={'<script>alert("unsafe")</script>'} />
    );

    expect(markup).toContain("AI-generated summary · Check against document");
    expect(markup).toContain("&lt;script&gt;");
    expect(markup).not.toContain("<script>");
  });

  it("shows every absent or incomplete summary state", () => {
    expect(renderToStaticMarkup(<DocumentSummaryState status="not_requested" summary={null} />))
      .toContain("AI summary not requested");
    expect(renderToStaticMarkup(<DocumentSummaryState status="pending" summary={null} />))
      .toContain("AI summary pending");
    expect(renderToStaticMarkup(<DocumentSummaryState status="processing" summary={null} />))
      .toContain("AI summary processing");
    expect(renderToStaticMarkup(<DocumentSummaryState status="failed" summary={null} />))
      .toContain("AI summary unavailable");
    expect(renderToStaticMarkup(<DocumentSummaryState status="ready" summary={null} />))
      .toContain("AI summary unavailable");
  });
});

describe("document management", () => {
  it("shows loading, empty, and error collection states", async () => {
    vi.spyOn(api, "documents").mockReturnValueOnce(new Promise<never>(() => undefined));
    const loading = renderWithQuery(
      <DocumentCollection clientId="client-1" onOpenDocument={vi.fn()} />
    );
    expect(screen.getByText("Loading documents…")).toBeInTheDocument();
    loading.unmount();

    vi.spyOn(api, "documents").mockResolvedValueOnce({ documents: [], next_cursor: null });
    const empty = renderWithQuery(
      <DocumentCollection clientId="client-1" onOpenDocument={vi.fn()} />
    );
    expect(await screen.findByText("No documents yet.")).toBeInTheDocument();
    empty.unmount();

    vi.spyOn(api, "documents").mockRejectedValueOnce(new Error("Documents unavailable"));
    renderWithQuery(<DocumentCollection clientId="client-1" onOpenDocument={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Documents unavailable");
  });

  it("filters, opens, and paginates documents", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    vi.spyOn(api, "documents")
      .mockResolvedValueOnce({ documents: [documentRecord()], next_cursor: "next-document" })
      .mockResolvedValueOnce({
        documents: [documentRecord({ document_id: "document-2", title: "Tax review" })],
        next_cursor: null,
      });

    renderWithQuery(<DocumentCollection clientId="client-1" onOpenDocument={onOpen} />);
    await user.click(await screen.findByRole("button", { name: "Annual plan" }));
    expect(onOpen).toHaveBeenCalledWith("document-1");
    expect(screen.getByText(/six-month emergency fund/)).toBeInTheDocument();

    await user.type(screen.getByRole("searchbox", { name: "Filter documents" }), "missing");
    expect(await screen.findByText(/No documents match/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filter" }));
    await user.click(screen.getByRole("button", { name: "Load more documents" }));
    expect(await screen.findByRole("button", { name: "Tax review" })).toBeInTheDocument();
    expect(api.documents).toHaveBeenLastCalledWith("client-1", "next-document");
  });

  it("validates and adds a document", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "documents").mockResolvedValue({ documents: [], next_cursor: null });
    vi.spyOn(api, "addDocument").mockResolvedValue({
      client_id: "client-1",
      document_id: "document-1",
      document_version_id: "version-1",
      indexing_status: "pending",
      outcome: "created",
      version_number: 1,
    });

    renderWithQuery(<DocumentCollection clientId="client-1" onOpenDocument={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Add document" }));
    await user.click(screen.getByRole("button", { name: "Add document" }));
    expect(await screen.findByText("Enter a document title.")).toBeInTheDocument();
    expect(screen.getByText("Add the document text.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Document title"), "Annual plan");
    await user.type(screen.getByLabelText("Plain-text content"), "Fictional plan content");
    await user.click(screen.getByRole("button", { name: "Add document" }));
    await waitFor(() => expect(api.addDocument).toHaveBeenCalledWith("client-1", {
      title: "Annual plan",
      content: "Fictional plan content",
    }));
    expect(await screen.findByText(/Version 1 added/)).toBeInTheDocument();
  });

  it("loads current document paragraphs and reports failures", async () => {
    vi.spyOn(api, "documentEdit").mockResolvedValueOnce({
      client_id: "client-1",
      content: "First paragraph.\n\nSecond paragraph.",
      current_document_version_id: "version-2",
      current_version_number: 2,
      document_id: "document-1",
      title: "Annual plan",
    });
    const loaded = renderWithQuery(
      <DocumentDialog documentId="document-1" onClose={vi.fn()} />
    );
    expect(await screen.findByRole("heading", { name: "Annual plan" })).toBeInTheDocument();
    expect(screen.getByText("Second paragraph.")).toBeInTheDocument();
    loaded.unmount();

    vi.spyOn(api, "documentEdit").mockRejectedValueOnce(new Error("Content unavailable"));
    renderWithQuery(<DocumentDialog documentId="document-2" onClose={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Content unavailable");
  });

  it("shows version history and saves a revision", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "documents").mockResolvedValue({
      documents: [documentRecord()],
      next_cursor: null,
    });
    vi.spyOn(api, "versions").mockResolvedValue({
      versions: [{
        created_at: "2026-08-17T10:00:00Z",
        document_id: "document-1",
        document_version_id: "version-1",
        indexing_status: "completed",
        version_number: 1,
      }],
    });
    vi.spyOn(api, "versionContent").mockResolvedValue({
      content: "Archived content",
      document_id: "document-1",
      document_version_id: "version-1",
      version_number: 1,
    });
    vi.spyOn(api, "documentEdit").mockResolvedValue({
      client_id: "client-1",
      content: "Original content",
      current_document_version_id: "version-1",
      current_version_number: 1,
      document_id: "document-1",
      title: "Annual plan",
    });
    vi.spyOn(api, "reviseDocument").mockResolvedValue({
      client_id: "client-1",
      document_id: "document-1",
      document_version_id: "version-2",
      indexing_status: "pending",
      outcome: "revised",
      version_number: 2,
    });

    renderWithQuery(<DocumentCollection clientId="client-1" onOpenDocument={vi.fn()} />);
    await screen.findByRole("button", { name: "Annual plan" });
    await user.click(screen.getByRole("button", { name: "Actions for Annual plan" }));
    await user.click(await screen.findByText("Version history"));
    await user.click(await screen.findByRole("button", { name: "View content" }));
    expect(await screen.findByText("Archived content")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close" }));

    await user.click(screen.getByRole("button", { name: "Actions for Annual plan" }));
    await user.click(await screen.findByText("Edit document"));
    const content = await screen.findByLabelText("Plain-text content");
    await user.clear(content);
    await user.type(content, "Revised content");
    await user.click(screen.getByRole("button", { name: "Save new version" }));
    await waitFor(() => expect(api.reviseDocument).toHaveBeenCalledWith(
      "document-1",
      { title: "Annual plan", content: "Revised content" }
    ));
  });
});
