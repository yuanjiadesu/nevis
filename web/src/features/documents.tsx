import { zodResolver } from "@hookform/resolvers/zod";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";
import { useForm, type UseFormReturn } from "react-hook-form";
import { z } from "zod";

import { api, type DocumentSummary } from "../api";
import { formatDate, statusLabel, statusTone } from "../lib";
import { Dialog, FormDialog } from "../ui/dialog";
import { AddIcon, DocumentIcon } from "../ui/icons";
import { ActionMenu } from "../ui/menu";
import { Button, SearchField, Spinner, Tag, TextAreaField, TextField } from "../ui/primitives";
import { SectionHeading, TableCard, TableEmpty } from "../ui/table";

const documentSchema = z.object({
  title: z.string().trim().min(1, "Enter a document title.").max(500),
  content: z.string().trim().min(1, "Add the document text.").max(500_000),
});
type DocumentInput = z.infer<typeof documentSchema>;

export function DocumentCollection({ clientId, onOpenDocument }: {
  clientId: string;
  onOpenDocument: (documentId: string) => void;
}) {
  const [filter, setFilter] = useState("");
  const needle = useDeferredValue(filter.trim().toLocaleLowerCase());
  const documents = useInfiniteQuery({
    queryKey: ["documents", clientId],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => api.documents(clientId, pageParam),
    getNextPageParam: (page) => page.next_cursor || undefined,
  });
  const loaded = useMemo(() => documents.data?.pages.flatMap((page) => page.documents) ?? [], [documents.data]);
  const visible = useMemo(
    () => loaded.filter((record) => record.title.toLocaleLowerCase().includes(needle)),
    [loaded, needle]
  );

  return (
    <section className="documents-section" aria-label="Documents">
      <SectionHeading
        title="Documents"
        meta={loaded.length ? `${visible.length} of ${loaded.length}` : undefined}
      />
      <TableCard
        toolbar={
          <>
            <SearchField
              glyph="filter"
              label="Filter documents"
              placeholder="Filter documents"
              value={filter}
              onChange={(event) => setFilter(event.target.value)}
            />
            <AddDocument clientId={clientId} />
          </>
        }
      >
        {documents.hasNextPage ? (
          <p className="loaded-scope">Filtering loaded documents only.</p>
        ) : null}

        {documents.isPending ? <div className="table-loading"><Spinner label="Loading documents…" /></div> : null}

        {!documents.isPending && loaded.length === 0 ? (
          <TableEmpty icon={<DocumentIcon size={24} />} title="No documents yet.">
            <span>Add the first one for this client.</span>
          </TableEmpty>
        ) : null}

        {loaded.length > 0 && visible.length === 0 ? (
          <TableEmpty title={`No documents match “${filter}”.`}>
            <Button kind="ghost" size="sm" onClick={() => setFilter("")}>Clear filter</Button>
          </TableEmpty>
        ) : null}

        {visible.length > 0 ? (
          <table className="data-table" aria-label="Client documents">
            <thead>
              <tr>
                <th scope="col">Document</th>
                <th scope="col">Version</th>
                <th scope="col">Created</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((record) => (
                <tr key={record.document_id}>
                  <td data-label="Document">
                    <button type="button" className="table-primary-link" onClick={() => onOpenDocument(record.document_id)}>
                      {record.title}
                    </button>
                    <DocumentSummaryState status={record.summary_status} summary={record.summary} />
                  </td>
                  <td data-label="Version">Version {record.current_version_number}</td>
                  <td data-label="Created">{formatDate(record.created_at)}</td>
                  <td data-label="Status"><Tag tone={statusTone(record.indexing_status)}>{statusLabel(record.indexing_status)}</Tag></td>
                  <td className="data-table__actions"><DocumentActions record={record} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
      </TableCard>

      {documents.isError ? <p className="form-error" role="alert">{documents.error.message}</p> : null}
      {documents.hasNextPage ? (
        <Button kind="ghost" size="sm" onClick={() => documents.fetchNextPage()} disabled={documents.isFetchingNextPage}>
          {documents.isFetchingNextPage ? "Loading…" : "Load more documents"}
        </Button>
      ) : null}
    </section>
  );
}

export function DocumentSummaryText({ summary }: { summary: string }) {
  return (
    <div className="document-summary">
      <span>AI-generated summary · Check against document</span>
      <p>{summary}</p>
    </div>
  );
}

export function DocumentSummaryState({ status, summary }: {
  status: DocumentSummary["summary_status"];
  summary: string | null;
}) {
  if (status === "ready") {
    return summary
      ? <DocumentSummaryText summary={summary} />
      : <p className="document-summary-status">AI summary unavailable</p>;
  }
  const labels: Record<Exclude<DocumentSummary["summary_status"], "ready">, string> = {
    not_requested: "AI summary not requested",
    pending: "AI summary pending",
    processing: "AI summary processing",
    failed: "AI summary unavailable",
  };
  return <p className="document-summary-status">{labels[status]}</p>;
}

function DocumentActions({ record }: { record: DocumentSummary }) {
  const [editOpen, setEditOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  return (
    <>
      <ActionMenu
        size="sm"
        label={`Actions for ${record.title}`}
        actions={[
          { label: "Edit document", onSelect: () => setEditOpen(true) },
          { label: "Version history", onSelect: () => setHistoryOpen(true) },
        ]}
      />
      <EditDocument documentId={record.document_id} open={editOpen} onClose={() => setEditOpen(false)} />
      <VersionHistory record={record} open={historyOpen} onClose={() => setHistoryOpen(false)} />
    </>
  );
}

export function DocumentDialog({ documentId, onClose }: { documentId: string | null; onClose: () => void }) {
  const current = useQuery({
    queryKey: ["document-edit", documentId],
    queryFn: () => api.documentEdit(documentId!),
    enabled: Boolean(documentId),
  });
  const paragraphs = current.data?.content
    ? current.data.content.split(/\n\s*\n/).map((paragraph) => paragraph.trim()).filter(Boolean)
    : [];

  return (
    <Dialog
      open={Boolean(documentId)}
      onClose={onClose}
      label={current.data ? `Current version ${current.data.current_version_number}` : "Document"}
      heading={current.data?.title || "Document content"}
      size="lg"
    >
      {current.isPending ? <Spinner label="Loading document…" /> : null}
      {current.isError ? <p className="form-error" role="alert">{current.error.message}</p> : null}
      {current.data ? (
        <article className="document-content" aria-label="Document content">
          {paragraphs.map((paragraph, index) => (
            <p key={`${paragraph.slice(0, 12)}-${index}`}>{paragraph}</p>
          ))}
        </article>
      ) : null}
    </Dialog>
  );
}

function VersionHistory({ record, open, onClose }: {
  record: DocumentSummary;
  open: boolean;
  onClose: () => void;
}) {
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const versions = useQuery({
    queryKey: ["versions", record.document_id],
    queryFn: () => api.versions(record.document_id),
    enabled: open,
  });
  const content = useQuery({
    queryKey: ["version-content", selectedVersionId],
    queryFn: () => api.versionContent(selectedVersionId!),
    enabled: open && Boolean(selectedVersionId),
  });
  const close = () => {
    setSelectedVersionId(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={close} label="Version history" heading={record.title} size="lg">
      {versions.isPending ? <Spinner label="Loading version history…" /> : null}
      {versions.isError ? <p className="form-error" role="alert">{versions.error.message}</p> : null}
      {versions.data ? (
        <div className="version-layout">
          <table className="version-table" aria-label={`Versions of ${record.title}`}>
            <thead>
              <tr>
                <th scope="col">Version</th>
                <th scope="col">Created</th>
                <th scope="col">Status</th>
                <th scope="col"><span className="visually-hidden">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {versions.data.versions.map((version) => (
                <tr key={version.document_version_id}>
                  <td>Version {version.version_number}</td>
                  <td>{formatDate(version.created_at)}</td>
                  <td>{statusLabel(version.indexing_status)}</td>
                  <td>
                    <Button kind="ghost" size="sm" onClick={() => setSelectedVersionId(version.document_version_id)}>
                      View content
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {selectedVersionId ? (
            <section className="version-preview" aria-live="polite">
              <h3>Version {content.data?.version_number ?? ""}</h3>
              {content.isPending ? <Spinner label="Loading version content…" /> : null}
              {content.isError ? <p className="form-error" role="alert">{content.error.message}</p> : null}
              {content.data ? (
                <article className="document-content" aria-label={`Version ${content.data.version_number} content`}>
                  {content.data.content
                    .split(/\n\s*\n/)
                    .map((paragraph) => paragraph.trim())
                    .filter(Boolean)
                    .map((paragraph, index) => (
                      <p key={`${paragraph.slice(0, 12)}-${index}`}>{paragraph}</p>
                    ))}
                </article>
              ) : null}
            </section>
          ) : (
            <p className="search-hint">Select a version to view its content.</p>
          )}
        </div>
      ) : null}
    </Dialog>
  );
}

function AddDocument({ clientId }: { clientId: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const form = useForm<DocumentInput>({ resolver: zodResolver(documentSchema), defaultValues: { title: "", content: "" } });
  const mutation = useMutation({
    mutationFn: (input: DocumentInput) => api.addDocument(clientId, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents", clientId] });
      form.reset();
    },
  });
  const close = () => {
    mutation.reset();
    setOpen(false);
  };

  return (
    <>
      <Button icon={<AddIcon size={16} />} size="sm" onClick={() => setOpen(true)}>Add document</Button>
      <FormDialog
        open={open}
        onClose={close}
        heading="Add document"
        submitLabel={mutation.isPending ? "Adding…" : "Add document"}
        cancelLabel="Close"
        busy={mutation.isPending}
        onSubmit={() => void form.handleSubmit((input) => mutation.mutate(input))()}
      >
        <DocumentFields form={form} idPrefix="add-document" />
        <div className="modal-feedback" aria-live="polite">
          {mutation.data ? (
            <p className="success-copy">
              Version {mutation.data.version_number} added — {statusLabel(mutation.data.indexing_status).toLocaleLowerCase()}.
            </p>
          ) : null}
          {mutation.isError ? <p className="form-error" role="alert">{mutation.error.message}</p> : null}
        </div>
      </FormDialog>
    </>
  );
}

function EditDocument({ documentId, open, onClose }: {
  documentId: string;
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const editable = useQuery({
    queryKey: ["document-edit", documentId],
    queryFn: () => api.documentEdit(documentId),
    enabled: open,
  });
  const form = useForm<DocumentInput>({
    resolver: zodResolver(documentSchema),
    defaultValues: { title: "", content: "" },
    values: editable.data ? { title: editable.data.title, content: editable.data.content } : undefined,
  });
  const mutation = useMutation({
    mutationFn: (input: DocumentInput) => api.reviseDocument(documentId, input),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["documents"] }),
        queryClient.invalidateQueries({ queryKey: ["versions", documentId] }),
        queryClient.invalidateQueries({ queryKey: ["document-edit", documentId] }),
      ]);
      onClose();
    },
  });

  return (
    <FormDialog
      open={open}
      onClose={onClose}
      heading="Edit document"
      submitLabel={mutation.isPending ? "Saving…" : "Save new version"}
      busy={mutation.isPending || editable.isPending}
      onSubmit={() => void form.handleSubmit((input) => mutation.mutate(input))()}
    >
      {editable.isPending ? <Spinner label="Loading document…" /> : null}
      {editable.isError ? <p className="form-error" role="alert">{editable.error.message}</p> : null}
      {editable.data ? <DocumentFields form={form} idPrefix="edit-document" /> : null}
      {mutation.isError ? <p className="form-error" role="alert">{mutation.error.message}</p> : null}
    </FormDialog>
  );
}

function DocumentFields({ form, idPrefix }: { form: UseFormReturn<DocumentInput>; idPrefix: string }) {
  const errors = form.formState.errors;
  return (
    <div className="form-stack">
      <TextField id={`${idPrefix}-title`} label="Document title" autoComplete="off" error={errors.title?.message} {...form.register("title")} />
      <TextAreaField id={`${idPrefix}-content`} label="Plain-text content" rows={9} error={errors.content?.message} {...form.register("content")} />
    </div>
  );
}
