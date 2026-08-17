import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { api, type ConsoleContext } from "./api";
import { ClientDirectory, ClientRecord } from "./features/clients";
import { GlobalSearch } from "./features/global-search";
import { selectionFromUrl, selectionInUrl, type Selection } from "./lib";
import { NevisWordmark } from "./nevis-wordmark";
import { Button, Spinner } from "./ui/primitives";
import { SessionMenu } from "./ui/session-menu";

const NO_SELECTION: Selection = { clientId: null, documentId: null };

export function App() {
  const [signedOut, setSignedOut] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const context = useQuery({ queryKey: ["context"], queryFn: api.context, retry: false, enabled: !signedOut });
  const [selection, setSelection] = useState(selectionFromUrl);

  useEffect(() => {
    const update = () => setSelection(selectionFromUrl());
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);

  const select = (next: Selection) => {
    selectionInUrl(next);
    setSelection(next);
  };

  const logout = async () => {
    setSigningOut(true);
    setLogoutError(null);
    try {
      await api.logout();
      setSignedOut(true);
    } catch (error) {
      setLogoutError(error instanceof Error ? error.message : "Sign out failed. Try again.");
    } finally {
      setSigningOut(false);
    }
  };

  if (signedOut)
    return (
      <AuthShell>
        <p className="product-label">Session ended</p>
        <h1>Signed out</h1>
        <p className="login-copy muted">Your Nevis workspace session has been cleared.</p>
        <Button onClick={() => window.location.reload()}>Return to workspace</Button>
      </AuthShell>
    );

  if (context.isPending)
    return (
      <AuthShell>
        <Spinner label="Preparing workspace…" />
      </AuthShell>
    );
  if (context.isError)
    return (
      <AuthShell>
        <p className="form-error" role="alert">
          {context.error.message}
        </p>
      </AuthShell>
    );

  return (
    <AdvisorConsole
      context={context.data}
      selection={selection}
      onSelect={select}
      signingOut={signingOut}
      logoutError={logoutError}
      onLogout={() => void logout()}
    />
  );
}

function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="login-shell">
      <a className="login-wordmark" href="/" aria-label="Nevis home">
        <NevisWordmark />
      </a>
      <section className="login-stage">
        <div className="login-card">{children}</div>
      </section>
      <footer className="login-footer">
        <span>Nevis</span>
        <span>Advisor workspace</span>
      </footer>
    </main>
  );
}

function AdvisorConsole({
  context,
  selection,
  onSelect,
  signingOut,
  logoutError,
  onLogout,
}: {
  context: ConsoleContext;
  selection: Selection;
  onSelect: (selection: Selection) => void;
  signingOut: boolean;
  logoutError: string | null;
  onLogout: () => void;
}) {
  const workspace = context.workspace;

  return (
    <div className="app-shell">
      <header className="app-header">
        <button
          className="header-wordmark"
          type="button"
          onClick={() => onSelect(NO_SELECTION)}
          aria-label="Open clients"
        >
          <NevisWordmark />
        </button>
        <div className="header-workspace">
          <span className="workspace-mark" aria-hidden="true">
            {workspace.name.charAt(0)}
          </span>
          <span className="header-workspace__copy">
            <strong>{workspace.name}</strong>
          </span>
        </div>
        <GlobalSearch onSelect={onSelect} />
        <div className="header-user">
          <SessionMenu
            advisor={context.advisor}
            workspace={workspace.name}
            busy={signingOut}
            onLogout={onLogout}
          />
        </div>
      </header>

      {logoutError ? <p className="session-error" role="alert">{logoutError}</p> : null}

      <main className="workspace-content">
        <div className={`workspace-layout${selection.clientId ? " workspace-layout--detail-open" : ""}`}>
          <aside className="workspace-sidebar" aria-label="Client directory">
            <ClientDirectory
              selectedClientId={selection.clientId}
              onSelect={(clientId) => onSelect({ clientId, documentId: null })}
            />
          </aside>
          <section className="workspace-detail">
            {selection.clientId ? (
              <ClientRecord
                clientId={selection.clientId}
                selectedDocumentId={selection.documentId}
                onBack={() => onSelect(NO_SELECTION)}
                onOpenDocument={(documentId) =>
                  onSelect({ clientId: selection.clientId, documentId })
                }
                onCloseDocument={() =>
                  onSelect({ clientId: selection.clientId, documentId: null })
                }
              />
            ) : (
              <div className="detail-empty-state">
                <h2>Select a client</h2>
                <p>Choose a relationship from the list to review context, documents, and actions.</p>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
