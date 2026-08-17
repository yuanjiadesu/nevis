import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type Client } from "../api";
import { renderWithQuery } from "../test/render";
import { ClientDirectory, ClientRecord } from "./clients";

function record(id = "client-1", firstName = "Ada"): Client {
  return {
    id,
    tenant_id: "tenant-1",
    first_name: firstName,
    last_name: "Lovelace",
    email: `${firstName.toLocaleLowerCase()}@example.com`,
    description: "Long-term relationship",
    social_links: ["https://example.com/profile"],
    source_type: "fixture",
    source_reference: "fixture",
    creation_authorization_decision_id: "decision-1",
    retrieval_authorization_decision_id: "decision-2",
    created_at: "2026-08-17T10:00:00Z",
    updated_at: "2026-08-17T10:00:00Z",
  };
}

afterEach(() => vi.restoreAllMocks());

describe("client management", () => {
  it("shows loading, empty, and failure states", async () => {
    const pending = new Promise<never>(() => undefined);
    vi.spyOn(api, "clients").mockReturnValueOnce(pending);
    const loading = renderWithQuery(
      <ClientDirectory selectedClientId={null} onSelect={vi.fn()} />
    );
    expect(loading.container.querySelector(".client-directory__loading")).toBeInTheDocument();
    loading.unmount();

    vi.spyOn(api, "clients").mockResolvedValueOnce({ clients: [], next_cursor: null });
    const empty = renderWithQuery(
      <ClientDirectory selectedClientId={null} onSelect={vi.fn()} />
    );
    expect(await screen.findByText("No clients yet")).toBeInTheDocument();
    empty.unmount();

    vi.spyOn(api, "clients").mockRejectedValueOnce(new Error("Directory unavailable"));
    renderWithQuery(<ClientDirectory selectedClientId={null} onSelect={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Directory unavailable");
  });

  it("filters, selects, and paginates loaded clients", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    vi.spyOn(api, "clients")
      .mockResolvedValueOnce({ clients: [record()], next_cursor: "next-page" })
      .mockResolvedValueOnce({ clients: [record("client-2", "Grace")], next_cursor: null });

    renderWithQuery(<ClientDirectory selectedClientId={null} onSelect={onSelect} />);
    await user.click(await screen.findByRole("button", { name: /Ada Lovelace/ }));
    expect(onSelect).toHaveBeenCalledWith("client-1");

    await user.type(screen.getByRole("searchbox", { name: "Search clients" }), "nobody");
    expect(await screen.findByText(/No clients match/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filter" }));
    expect(screen.getByRole("button", { name: /Ada Lovelace/ })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Load more clients" }));
    expect(await screen.findByRole("button", { name: /Grace Lovelace/ })).toBeInTheDocument();
    expect(api.clients).toHaveBeenLastCalledWith("next-page");
  });

  it("validates and creates a client", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    vi.spyOn(api, "clients").mockResolvedValue({ clients: [], next_cursor: null });
    vi.spyOn(api, "createClient").mockResolvedValue(record());

    renderWithQuery(<ClientDirectory selectedClientId={null} onSelect={onSelect} />);
    await screen.findByText("No clients yet");
    await user.click(screen.getAllByRole("button", { name: "New client" })[0]);
    await user.click(await screen.findByRole("button", { name: "Create client" }));
    expect(await screen.findByText("Enter a first name.")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid email.")).toBeInTheDocument();

    await user.type(screen.getByLabelText("First name"), "Ada");
    await user.type(screen.getByLabelText("Last name"), "Lovelace");
    await user.type(screen.getByLabelText("Email"), "ada@example.com");
    await user.type(screen.getByLabelText("Relationship context"), "Trusted client");
    await user.click(screen.getByRole("button", { name: "Create client" }));

    await waitFor(() => expect(api.createClient).toHaveBeenCalledWith({
      first_name: "Ada",
      last_name: "Lovelace",
      email: "ada@example.com",
      description: "Trusted client",
      social_links: [],
    }));
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith("client-1"));
  });

  it("loads a client and saves an update", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "client").mockResolvedValue(record());
    vi.spyOn(api, "documents").mockResolvedValue({ documents: [], next_cursor: null });
    vi.spyOn(api, "updateClient").mockResolvedValue(record("client-1", "Augusta"));

    renderWithQuery(
      <ClientRecord
        clientId="client-1"
        selectedDocumentId={null}
        onBack={vi.fn()}
        onOpenDocument={vi.fn()}
        onCloseDocument={vi.fn()}
      />
    );
    await screen.findByRole("heading", { name: "Ada Lovelace" });
    await user.click(screen.getByRole("button", { name: "Actions for Ada Lovelace" }));
    await user.click(await screen.findByText("Edit client"));
    const firstName = await screen.findByLabelText("First name");
    await user.clear(firstName);
    await user.type(firstName, "Augusta");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(api.updateClient).toHaveBeenCalledWith(
      "client-1",
      expect.objectContaining({ first_name: "Augusta" })
    ));
  });
});
