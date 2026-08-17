import type { components } from "./api.generated";

export type ConsoleContext = components["schemas"]["ConsoleContextResponse"];
export type Client = components["schemas"]["ClientResponse"];
export type DocumentSummary = components["schemas"]["ClientDocumentTimelineItemResponse"];
export type DocumentVersion = components["schemas"]["DocumentVersionTimelineItemResponse"];
export type EditableDocument = components["schemas"]["DocumentEditResponse"];
export type DocumentVersionContent = components["schemas"]["DocumentVersionContentResponse"];
export type SearchResponse = components["schemas"]["SearchResponse"];
export type SearchResult = SearchResponse["results"][number];
export type IngestedDocument = components["schemas"]["IngestDocumentResponse"];
type ClientPage = components["schemas"]["ClientPageResponse"];
type DocumentPage = components["schemas"]["ClientDocumentPageResponse"];
type VersionPage = components["schemas"]["DocumentVersionTimelineResponse"];
type UpdateClientInput = components["schemas"]["UpdateClientRequest"];
type CreateClientInput = components["schemas"]["CreateClientRequest"];

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "Request failed. Try again.");
  }
  return response.json() as Promise<T>;
}

function json(method: string, body: unknown, idempotent = false): RequestInit {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (idempotent) headers["Idempotency-Key"] = crypto.randomUUID();
  return { method, headers, body: JSON.stringify(body) };
}

function page(path: string, limit: number, cursor?: string): string {
  return `${path}?limit=${limit}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`;
}

export const api = {
  context: () => request<ConsoleContext>("/ui/context"),
  logout: () => request<{ status: "signed_out" }>("/ui/logout", { method: "POST" }),
  clients: (cursor?: string) => request<ClientPage>(page("/v1/clients", 50, cursor)),
  search: (query: string, cursor?: string) => request<SearchResponse>(
    `/search?q=${encodeURIComponent(query)}&limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`
  ),
  client: (clientId: string) => request<Client>(`/v1/clients/${clientId}`),
  updateClient: (clientId: string, input: UpdateClientInput) => request<Client>(
    `/v1/clients/${clientId}`,
    json("PATCH", input)
  ),
  createClient: (input: Pick<CreateClientInput, "first_name" | "last_name" | "email" | "description" | "social_links">) => request<Client>(
    "/v1/clients",
    json("POST", { ...input, source_type: "advisor-console", source_reference: "advisor-console" }, true)
  ),
  documents: (clientId: string, cursor?: string) => request<DocumentPage>(
    page(`/v1/clients/${clientId}/documents`, 50, cursor)
  ),
  versions: (documentId: string) => request<VersionPage>(`/v1/documents/${documentId}/versions`),
  documentEdit: (documentId: string) => request<EditableDocument>(`/v1/documents/${documentId}/edit`),
  versionContent: (versionId: string) => request<DocumentVersionContent>(`/v1/document-versions/${versionId}/content`),
  reviseDocument: (documentId: string, input: { title: string; content: string }) => request<IngestedDocument>(
    `/v1/documents/${documentId}/revisions`,
    json("POST", input, true)
  ),
  addDocument: (clientId: string, input: { title: string; content: string }) => request<IngestedDocument>(
    `/v1/clients/${clientId}/documents`,
    json("POST", { ...input, source_reference: "advisor-console", external_document_id: crypto.randomUUID() }, true)
  )
};
