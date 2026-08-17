export type Selection = { clientId: string | null; documentId: string | null };

export function selectionFromUrl(): Selection {
  const params = new URL(window.location.href).searchParams;
  return { clientId: params.get("client"), documentId: params.get("document") };
}

export function selectionInUrl(selection: Selection): void {
  const url = new URL(window.location.href);
  if (selection.clientId) url.searchParams.set("client", selection.clientId);
  else url.searchParams.delete("client");
  if (selection.documentId) url.searchParams.set("document", selection.documentId);
  else url.searchParams.delete("document");
  window.history.pushState({}, "", url);
}

const dateFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

export function formatDate(value: string): string {
  return dateFormat.format(new Date(value));
}

export function statusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1).replaceAll("_", " ");
}

export function statusTone(status: string): "positive" | "negative" | "neutral" {
  if (status === "completed") return "positive";
  if (status === "failed") return "negative";
  return "neutral";
}

export function countLabel(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}
