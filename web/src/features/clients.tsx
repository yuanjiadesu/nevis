import { zodResolver } from "@hookform/resolvers/zod";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { useForm, type UseFormReturn } from "react-hook-form";
import { z } from "zod";

import { api, type Client } from "../api";
import { countLabel } from "../lib";
import { FormDialog } from "../ui/dialog";
import { AddIcon, ArrowLeft, ClientsIcon, CloseIcon, LinkIcon } from "../ui/icons";
import { ActionMenu } from "../ui/menu";
import { Button, SearchField, Skeleton, TextAreaField, TextField } from "../ui/primitives";
import { TableEmpty } from "../ui/table";
import { DocumentCollection, DocumentDialog } from "./documents";

const clientSchema = z.object({
  first_name: z.string().trim().min(1, "Enter a first name.").max(100),
  last_name: z.string().trim().min(1, "Enter a last name.").max(100),
  email: z.string().trim().email("Enter a valid email.").max(320),
  description: z.string().max(2_000).optional(),
  social_links: z.array(
    z.string().trim().url("Enter a complete URL.").max(500).refine(
      (value) => /^https?:\/\//i.test(value),
      "Use an HTTP(S) URL."
    )
  ).max(10, "Add up to 10 links."),
});
type ClientInput = z.infer<typeof clientSchema>;

export function ClientDirectory({ selectedClientId, onSelect }: {
  selectedClientId: string | null;
  onSelect: (clientId: string) => void;
}) {
  const [filter, setFilter] = useState("");
  const needle = useDeferredValue(filter.trim().toLocaleLowerCase());
  const clients = useInfiniteQuery({
    queryKey: ["clients"],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => api.clients(pageParam),
    getNextPageParam: (page) => page.next_cursor || undefined,
  });
  const records = useMemo(() => clients.data?.pages.flatMap((page) => page.clients) ?? [], [clients.data]);
  const selectedIsLoaded = selectedClientId ? records.some((client) => client.id === selectedClientId) : false;
  const selectedClient = useQuery({
    queryKey: ["client", selectedClientId],
    queryFn: () => api.client(selectedClientId as string),
    enabled: Boolean(selectedClientId && !selectedIsLoaded),
  });
  const selectedRecord = records.find((client) => client.id === selectedClientId) ?? selectedClient.data;
  const visible = useMemo(
    () => records.filter((client) => [client.first_name, client.last_name, client.email, client.description ?? ""]
      .join(" ")
      .toLocaleLowerCase()
      .includes(needle)),
    [records, needle]
  );
  const navigationRecords = useMemo(() => {
    if (!selectedRecord || visible.some((client) => client.id === selectedRecord.id)) return visible;
    return [selectedRecord, ...visible];
  }, [selectedRecord, visible]);
  const selectedItemRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    selectedItemRef.current?.scrollIntoView({ block: "nearest" });
  }, [selectedClientId, records.length, selectedClient.data?.id]);

  return (
    <section className="client-directory">
      <header className="client-directory__header">
        <div>
          <h1>Clients</h1>
          <p className="muted">{records.length ? countLabel(records.length, "client") : "Your client relationships"}</p>
        </div>
        <NewClient onCreated={onSelect} />
      </header>

      {clients.isPending ? <div className="client-directory__loading"><Skeleton lines={7} /></div> : null}
      {clients.isError ? <p className="form-error client-directory__error" role="alert">{clients.error.message}</p> : null}
      {clients.isSuccess && records.length === 0 ? <EmptyClients onCreated={onSelect} /> : null}

      {records.length ? (
        <div className="client-directory__body">
          <div className="client-directory__search">
            <SearchField
              label="Search clients"
              placeholder="Search clients"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
          </div>
          {navigationRecords.length === 0 ? (
            <TableEmpty title={`No clients match “${filter}”.`}>
              <Button kind="ghost" size="sm" onClick={() => setFilter("")}>Clear filter</Button>
            </TableEmpty>
          ) : (
            <nav className="client-list" aria-label="Clients">
              {navigationRecords.map((client) => {
                const isSelected = client.id === selectedClientId;
                return (
                  <button
                    type="button"
                    className="client-list-item"
                    key={client.id}
                    ref={isSelected ? selectedItemRef : undefined}
                    aria-current={isSelected ? "page" : undefined}
                    onClick={() => onSelect(client.id)}
                  >
                    <span className="client-list-item__avatar" aria-hidden="true">
                      {client.first_name.charAt(0)}{client.last_name.charAt(0)}
                    </span>
                    <span className="client-list-item__copy">
                      <strong>{client.first_name} {client.last_name}</strong>
                      <small>{client.email}</small>
                    </span>
                  </button>
                );
              })}
            </nav>
          )}
        </div>
      ) : null}

      {clients.hasNextPage ? (
        <Button className="client-directory__more" kind="ghost" size="sm" onClick={() => clients.fetchNextPage()} disabled={clients.isFetchingNextPage}>
          {clients.isFetchingNextPage ? "Loading…" : "Load more clients"}
        </Button>
      ) : null}
    </section>
  );
}

function EmptyClients({ onCreated }: { onCreated: (clientId: string) => void }) {
  return (
    <div className="empty-state">
      <ClientsIcon size={28} />
      <h2>No clients yet</h2>
      <p>Create the first one to begin.</p>
      <NewClient onCreated={onCreated} />
    </div>
  );
}

export function ClientRecord({ clientId, selectedDocumentId, onBack, onOpenDocument, onCloseDocument }: {
  clientId: string;
  selectedDocumentId: string | null;
  onBack: () => void;
  onOpenDocument: (documentId: string) => void;
  onCloseDocument: () => void;
}) {
  const client = useQuery({ queryKey: ["client", clientId], queryFn: () => api.client(clientId) });

  if (client.isPending) return <div className="loading-block"><Skeleton heading lines={6} /></div>;
  if (client.isError) return <p className="form-error" role="alert">{client.error.message}</p>;

  return (
    <section className="client-page">
      <Button className="back-button" kind="ghost" size="sm" icon={<ArrowLeft size={16} />} onClick={onBack}>
        All clients
      </Button>

      <header className="record-heading">
        <div className="record-heading__identity">
          <span className="record-avatar" aria-hidden="true">
            {client.data.first_name.charAt(0)}{client.data.last_name.charAt(0)}
          </span>
          <div>
            <p className="record-kicker">Client profile</p>
            <h1>{client.data.first_name} {client.data.last_name}</h1>
            <a className="record-email" href={`mailto:${client.data.email}`}>{client.data.email}</a>
          </div>
        </div>
        <ClientActions client={client.data} />
      </header>

      <section className="relationship-section" aria-label="Relationship context">
        <h2>Context</h2>
        <p>{client.data.description || "No context recorded."}</p>
      </section>

      {client.data.social_links.length > 0 ? (
        <section className="relationship-section relationship-section--links" aria-label="Social links">
          <h2>Social links</h2>
          <ul className="social-links">
            {client.data.social_links.map((link, index) => (
              <li key={`${link}-${index}`}>
                <LinkIcon size={15} aria-hidden="true" />
                <a href={link} target="_blank" rel="noreferrer">{link}</a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <DocumentCollection clientId={clientId} onOpenDocument={onOpenDocument} />
      <DocumentDialog documentId={selectedDocumentId} onClose={onCloseDocument} />
    </section>
  );
}

function ClientActions({ client }: { client: Client }) {
  const [editOpen, setEditOpen] = useState(false);
  return (
    <>
      <ActionMenu
        label={`Actions for ${client.first_name} ${client.last_name}`}
        actions={[{ label: "Edit client", onSelect: () => setEditOpen(true) }]}
      />
      <EditClient client={client} open={editOpen} onClose={() => setEditOpen(false)} />
    </>
  );
}

function NewClient({ onCreated }: { onCreated: (clientId: string) => void }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const form = useForm<ClientInput>({
    resolver: zodResolver(clientSchema),
    defaultValues: { first_name: "", last_name: "", email: "", description: "", social_links: [] },
  });
  const mutation = useMutation({
    mutationFn: (input: ClientInput) => api.createClient(input),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["clients"] });
      form.reset();
      setOpen(false);
      onCreated(created.id);
    },
  });

  return (
    <>
      <Button aria-label="New client" title="New client" icon={<AddIcon size={16} />} onClick={() => setOpen(true)}>New client</Button>
      <FormDialog
        open={open}
        onClose={() => setOpen(false)}
        heading="New client"
        size="sm"
        submitLabel={mutation.isPending ? "Creating…" : "Create client"}
        busy={mutation.isPending}
        onSubmit={() => void form.handleSubmit((input) => mutation.mutate(input))()}
      >
        <ClientFields form={form} />
        {mutation.isError ? <p className="form-error" role="alert">{mutation.error.message}</p> : null}
      </FormDialog>
    </>
  );
}

function EditClient({ client, open, onClose }: { client: Client; open: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const form = useForm<ClientInput>({
    resolver: zodResolver(clientSchema),
    values: {
      first_name: client.first_name,
      last_name: client.last_name,
      email: client.email,
      description: client.description || "",
      social_links: client.social_links,
    },
  });
  const mutation = useMutation({
    mutationFn: (input: ClientInput) => api.updateClient(client.id, {
      ...input,
      description: input.description || null,
    }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["client", client.id] }),
        queryClient.invalidateQueries({ queryKey: ["clients"] }),
      ]);
      onClose();
    },
  });

  return (
    <FormDialog
      open={open}
      onClose={onClose}
      heading="Edit client"
      size="sm"
      submitLabel={mutation.isPending ? "Saving…" : "Save changes"}
      busy={mutation.isPending}
      onSubmit={() => void form.handleSubmit((input) => mutation.mutate(input))()}
    >
      <ClientFields form={form} />
      {mutation.isError ? <p className="form-error" role="alert">{mutation.error.message}</p> : null}
    </FormDialog>
  );
}

function ClientFields({ form }: { form: UseFormReturn<ClientInput> }) {
  const errors = form.formState.errors;
  const socialLinks = form.watch("social_links");
  const setSocialLinks = (next: string[]) => {
    form.setValue("social_links", next, { shouldDirty: true, shouldValidate: true });
  };
  return (
    <div className="form-stack">
      <div className="field-grid">
        <TextField id="first-name" label="First name" autoComplete="given-name" error={errors.first_name?.message} {...form.register("first_name")} />
        <TextField id="last-name" label="Last name" autoComplete="family-name" error={errors.last_name?.message} {...form.register("last_name")} />
      </div>
      <TextField id="client-email" label="Email" type="email" autoComplete="email" error={errors.email?.message} {...form.register("email")} />
      <TextAreaField id="client-context" label="Relationship context" rows={5} error={errors.description?.message} {...form.register("description")} />
      <fieldset className="social-links-editor">
        <legend className="visually-hidden">Social links</legend>
        <div className="social-links-editor__header">
          <span>Social links <small>Optional, up to 10</small></span>
          <Button
            kind="secondary"
            size="sm"
            icon={<AddIcon size={15} />}
            disabled={socialLinks.length >= 10}
            onClick={() => setSocialLinks([...socialLinks, ""])}
          >
            Add link
          </Button>
        </div>
        {socialLinks.length > 0 ? (
          <div className="social-links-editor__entries">
            {socialLinks.map((_, index) => (
              <div className="social-links-editor__entry" key={`social-link-${index}`}>
                <TextField
                  id={`social-link-${index}`}
                  label={`Link ${index + 1}`}
                  type="url"
                  inputMode="url"
                  autoComplete="url"
                  placeholder="https://linkedin.com/in/name"
                  error={errors.social_links?.[index]?.message}
                  {...form.register(`social_links.${index}`)}
                />
                <Button
                  aria-label={`Remove link ${index + 1}`}
                  kind="ghost"
                  size="sm"
                  icon={<CloseIcon size={16} />}
                  onClick={() => setSocialLinks(socialLinks.filter((_, itemIndex) => itemIndex !== index))}
                />
              </div>
            ))}
          </div>
        ) : null}
        {errors.social_links?.message ? <p className="field__error" role="alert">{errors.social_links.message}</p> : null}
      </fieldset>
    </div>
  );
}
