import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type Client, type SearchResult } from "../api";
import { renderWithQuery } from "../test/render";
import { GlobalSearch } from "./global-search";

type DocumentSearchResult = Extract<SearchResult, { type: "document" }>;

const client: Client = {
  id: "client-1",
  tenant_id: "tenant-1",
  first_name: "Ada",
  last_name: "Lovelace",
  email: "ada@example.com",
  description: null,
  social_links: [],
  source_type: "fixture",
  source_reference: "fixture",
  creation_authorization_decision_id: "decision-1",
  retrieval_authorization_decision_id: "decision-2",
  created_at: "2026-08-17T10:00:00Z",
  updated_at: "2026-08-17T10:00:00Z",
};

const ranks = {
  client_lexical: null,
  document_lexical: 1,
  document_reranker: 1,
  document_semantic: null,
};

function documentResult(
  overrides: Partial<DocumentSearchResult> = {}
): DocumentSearchResult {
  return {
    type: "document",
    title: "Annual plan",
    client_name: "Ada Lovelace",
    snippet: "Emergency fund evidence",
    fused_score: 0.9,
    match_band: 1,
    ranks,
    scores: { lexical: 1, semantic: null, reranker: 0.8 },
    provenance: {
      client_id: "client-1",
      document_id: "document-1",
      document_version_id: "version-1",
      embedding_profile_id: "profile-1",
      indexing_authorization_decision_id: "decision-1",
      search_authorization_decision_id: "decision-2",
      source_id: "source-1",
      tenant_id: "tenant-1",
    },
    ...overrides,
  };
}

function clientResult(): SearchResult {
  return {
    type: "client",
    title: "Ada Lovelace",
    email: "ada@example.com",
    excerpt: null,
    fused_score: 1,
    match_band: 0,
    ranks: { ...ranks, client_lexical: 1, document_lexical: null, document_reranker: null },
    provenance: {
      client_id: "client-1",
      creation_authorization_decision_id: "decision-1",
      search_authorization_decision_id: "decision-2",
      tenant_id: "tenant-1",
    },
  } as SearchResult;
}

async function openAndSubmit(user: ReturnType<typeof userEvent.setup>, query: string) {
  await user.click(screen.getByRole("button", { name: "Search clients and documents" }));
  const input = await screen.findByRole("combobox", { name: "Search clients and documents" });
  await user.type(input, query);
  await user.keyboard("{Enter}");
}

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe("global search", () => {
  it("opens from the keyboard and routes a client suggestion", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    vi.spyOn(api, "clients").mockResolvedValue({ clients: [client], next_cursor: "more" });
    vi.spyOn(api, "search").mockResolvedValue({
      mode: "hybrid",
      ranking_version: "mixed-rrf-v5",
      results: [],
      next_cursor: null,
    });
    renderWithQuery(<GlobalSearch onSelect={onSelect} />);

    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(await screen.findByRole("heading", { name: "Search workspace" })).toBeInTheDocument();
    await user.type(screen.getByRole("combobox"), "ada");
    expect(await screen.findByText("Matching loaded clients only — press Enter to search all."))
      .toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: /Ada Lovelace/ }));
    expect(onSelect).toHaveBeenCalledWith({ clientId: "client-1", documentId: null });
  });

  it("shows pending, empty, and error search feedback", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "clients").mockResolvedValue({ clients: [], next_cursor: null });
    vi.spyOn(api, "search").mockReturnValueOnce(new Promise<never>(() => undefined));
    const pending = renderWithQuery(<GlobalSearch onSelect={vi.fn()} />);
    await openAndSubmit(user, "pending query");
    expect(await screen.findByText("Searching workspace…")).toBeInTheDocument();
    pending.unmount();

    vi.spyOn(api, "search").mockResolvedValueOnce({
      mode: "hybrid",
      ranking_version: "mixed-rrf-v5",
      results: [],
      next_cursor: null,
    });
    const empty = renderWithQuery(<GlobalSearch onSelect={vi.fn()} />);
    await openAndSubmit(userEvent.setup(), "nothing here");
    expect(await screen.findByText(/No matches for “nothing here”/)).toBeInTheDocument();
    empty.unmount();

    vi.spyOn(api, "search").mockRejectedValueOnce(new Error("Search unavailable"));
    renderWithQuery(<GlobalSearch onSelect={vi.fn()} />);
    await openAndSubmit(userEvent.setup(), "broken query");
    expect(await screen.findByRole("alert")).toHaveTextContent("Search unavailable");
  });

  it("renders mixed degraded results, filters, paginates, and selects safely", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const unsafeTitle = '<script>alert("unsafe")</script>';
    vi.spyOn(api, "clients").mockResolvedValue({ clients: [], next_cursor: null });
    vi.spyOn(api, "search")
      .mockResolvedValueOnce({
        mode: "lexical_degraded",
        ranking_version: "mixed-rrf-v5",
        results: [clientResult(), documentResult({ title: unsafeTitle })],
        next_cursor: "next-search",
      })
      .mockResolvedValueOnce({
        mode: "lexical_degraded",
        ranking_version: "mixed-rrf-v5",
        results: [documentResult({
          title: "Tax review",
          provenance: { ...documentResult().provenance, document_id: "document-2" },
        })],
        next_cursor: null,
      });
    const view = renderWithQuery(<GlobalSearch onSelect={onSelect} />);

    await openAndSubmit(user, "annual plan");
    expect(await screen.findByText(/Semantic search unavailable/)).toBeInTheDocument();
    expect(screen.getByText(unsafeTitle)).toBeInTheDocument();
    expect(view.container.querySelector("script")).toBeNull();

    await user.click(screen.getByRole("button", { name: /Documents/ }));
    expect(screen.queryByRole("option", { name: /ada@example.com/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Load more results" }));
    expect(await screen.findByRole("option", { name: /Tax review/ })).toBeInTheDocument();
    expect(api.search).toHaveBeenLastCalledWith("annual plan", "next-search");

    await user.click(screen.getByRole("option", { name: /Tax review/ }));
    expect(onSelect).toHaveBeenCalledWith({ clientId: "client-1", documentId: "document-2" });
  });

  it("stores and reuses recent query suggestions", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "clients").mockResolvedValue({ clients: [], next_cursor: null });
    vi.spyOn(api, "search").mockResolvedValue({
      mode: "hybrid",
      ranking_version: "mixed-rrf-v5",
      results: [],
      next_cursor: null,
    });
    renderWithQuery(<GlobalSearch onSelect={vi.fn()} />);
    await openAndSubmit(user, "annual review");
    await waitFor(() => expect(window.localStorage.getItem("nevis:recent-searches:v1"))
      .toContain("annual review"));
    await user.click(screen.getByRole("button", { name: "Close" }));
    await user.click(screen.getByRole("button", { name: "Search clients and documents" }));
    await user.clear(screen.getByRole("combobox", { name: "Search clients and documents" }));
    expect(await screen.findByRole("option", { name: /annual review/ })).toBeInTheDocument();
  });
});
