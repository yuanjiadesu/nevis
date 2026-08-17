import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "./api";

describe("advisor API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  const ok = (body: object = {}) => new Response(JSON.stringify(body), { status: 200 });

  it("does not expose identity headers in browser requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ clients: [], next_cursor: null }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.clients();

    const [, request] = fetchMock.mock.calls[0] as [string, RequestInit | undefined];
    const headers = new Headers(request?.headers);
    expect(headers.get("X-Nevis-Tenant")).toBeNull();
    expect(headers.get("X-Nevis-Advisor")).toBeNull();
    expect(headers.get("Authorization")).toBeNull();
  });

  it("encodes mixed-search queries and opaque cursors", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ mode: "hybrid", ranking_version: "mixed-rrf-v2", results: [], next_cursor: null }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);

    await api.search("Ada & annual review", "cursor/+value");

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/search?q=Ada%20%26%20annual%20review&limit=20&cursor=cursor%2F%2Bvalue"
    );
  });

  it("returns the API's safe search failure message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "search unavailable" }), { status: 503 })
    ));

    await expect(api.search("annual review")).rejects.toThrow("search unavailable");
  });

  it("uses a generic error when a failed response has no safe detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("not-json", { status: 500 })));

    await expect(api.context()).rejects.toThrow("Request failed. Try again.");
  });

  it("encodes opaque pagination and resource identifiers", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(ok({})));
    vi.stubGlobal("fetch", fetchMock);

    await api.clients("next/+client");
    await api.documents("client/id", "next/+document");
    await api.versions("document/id");
    await api.versionContent("version/id");

    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      "/v1/clients?limit=50&cursor=next%2F%2Bclient",
      "/v1/clients/client/id/documents?limit=50&cursor=next%2F%2Bdocument",
      "/v1/documents/document/id/versions",
      "/v1/document-versions/version/id/content",
    ]);
  });

  it("sends bounded client mutation bodies and idempotency metadata", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(ok({ id: "client-1" })));
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(globalThis.crypto, "randomUUID").mockReturnValue(
      "00000000-0000-4000-8000-000000000001"
    );

    await api.createClient({
      first_name: "Ada",
      last_name: "Lovelace",
      email: "ada@example.com",
      description: null,
      social_links: [],
    });
    await api.updateClient("client-1", {
      first_name: "Augusta",
      last_name: "Lovelace",
      email: "ada@example.com",
      description: "Updated",
      social_links: [],
    });

    const [, createRequest] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(createRequest.method).toBe("POST");
    expect(new Headers(createRequest.headers).get("Idempotency-Key")).toBe(
      "00000000-0000-4000-8000-000000000001"
    );
    expect(JSON.parse(createRequest.body as string)).toMatchObject({
      first_name: "Ada",
      source_type: "advisor-console",
      source_reference: "advisor-console",
    });

    const [, updateRequest] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(updateRequest.method).toBe("PATCH");
    expect(new Headers(updateRequest.headers).get("Idempotency-Key")).toBeNull();
    expect(JSON.parse(updateRequest.body as string)).toMatchObject({
      first_name: "Augusta",
      description: "Updated",
    });
  });

  it("sends document creation and revision bodies to their distinct routes", async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(ok({ document_id: "document-1" }))
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(globalThis.crypto, "randomUUID")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000002")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000003")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000004");

    await api.addDocument("client-1", { title: "Plan", content: "Body" });
    await api.reviseDocument("document-1", { title: "Plan v2", content: "New body" });

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/v1/clients/client-1/documents");
    const addRequest = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(addRequest.body as string)).toMatchObject({
      title: "Plan",
      content: "Body",
      source_reference: "advisor-console",
      external_document_id: "00000000-0000-4000-8000-000000000002",
    });
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/v1/documents/document-1/revisions");
    expect(JSON.parse((fetchMock.mock.calls[1]?.[1] as RequestInit).body as string)).toEqual({
      title: "Plan v2",
      content: "New body",
    });
  });
});
