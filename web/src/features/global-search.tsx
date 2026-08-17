import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { api, type SearchResult } from "../api";
import type { Selection } from "../lib";
import { Dialog } from "../ui/dialog";
import { ClientsIcon, DocumentIcon, SearchIcon } from "../ui/icons";
import { Button, SearchField, Spinner, Tag } from "../ui/primitives";

const RECENTS_KEY = "nevis:recent-searches:v1";
const RECENTS_LIMIT = 6;
const CLIENT_SUGGESTION_LIMIT = 5;
type SearchType = "all" | "client" | "document";

function readRecents(): string[] {
  try {
    const stored: unknown = JSON.parse(window.localStorage.getItem(RECENTS_KEY) ?? "[]");
    return Array.isArray(stored) ? stored.filter((entry): entry is string => typeof entry === "string") : [];
  } catch {
    return [];
  }
}

function storeRecent(query: string): string[] {
  const next = [query, ...readRecents().filter((entry) => entry !== query)].slice(0, RECENTS_LIMIT);
  try {
    window.localStorage.setItem(RECENTS_KEY, JSON.stringify(next));
  } catch {
    return next;
  }
  return next;
}

type Suggestion =
  | { kind: "recent"; key: string; query: string }
  | { kind: "client"; key: string; clientId: string; name: string; email: string }
  | { kind: "query"; key: string; query: string };

type SuggestionGroup = { label: string; items: number[] };

const LISTBOX_ID = "global-search-listbox";
const optionId = (index: number) => `global-search-option-${index}`;

export function GlobalSearch({ onSelect }: { onSelect: (selection: Selection) => void }) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [searchType, setSearchType] = useState<SearchType>("all");
  const [activeIndex, setActiveIndex] = useState(-1);
  const [searchLatencyMs, setSearchLatencyMs] = useState<number | null>(null);
  const [recents, setRecents] = useState(readRecents);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const searchStartedAtRef = useRef<number | null>(null);
  const normalizedInput = input.trim();

  const search = useInfiniteQuery({
    queryKey: ["workspace-search", submittedQuery],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => api.search(submittedQuery, pageParam),
    getNextPageParam: (page) => page.next_cursor || undefined,
    enabled: open && submittedQuery.length > 0,
  });
  const clientPool = useQuery({
    queryKey: ["client-suggestions"],
    queryFn: () => api.clients(),
    enabled: open,
    staleTime: 60_000,
  });

  const results = useMemo(
    () => search.data?.pages.flatMap((page) => page.results) ?? [],
    [search.data]
  );
  const filteredResults = useMemo(
    () => searchType === "all" ? results : results.filter((result) => result.type === searchType),
    [results, searchType]
  );
  const mode = search.data?.pages[0]?.mode;
  const showingResults = normalizedInput === submittedQuery && submittedQuery.length > 0;

  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      const editable = event.target instanceof HTMLElement
        && event.target.matches("input, textarea, select, [contenteditable='true']");
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k" && !editable) {
        event.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);

  const { rows: suggestions, groups: suggestionGroups, partialClients } = useMemo(() => {
    if (showingResults) {
      return { rows: [] as Suggestion[], groups: [] as SuggestionGroup[], partialClients: false };
    }
    const needle = normalizedInput.toLocaleLowerCase();
    const rows: Suggestion[] = [];
    const groups: SuggestionGroup[] = [];

    const recentItems: number[] = [];
    for (const query of recents) {
      if (needle && !query.toLocaleLowerCase().includes(needle)) continue;
      recentItems.push(rows.length);
      rows.push({ kind: "recent", key: `recent-${query}`, query });
    }
    if (recentItems.length > 0) groups.push({ label: "Recent searches", items: recentItems });

    if (searchType !== "document") {
      const clientItems: number[] = [];
      for (const client of clientPool.data?.clients ?? []) {
        if (clientItems.length >= CLIENT_SUGGESTION_LIMIT) break;
        const haystack = `${client.first_name} ${client.last_name} ${client.email}`.toLocaleLowerCase();
        if (needle && !haystack.includes(needle)) continue;
        clientItems.push(rows.length);
        rows.push({
          kind: "client",
          key: `client-${client.id}`,
          clientId: client.id,
          name: `${client.first_name} ${client.last_name}`,
          email: client.email,
        });
      }
      if (clientItems.length > 0) {
        groups.push({ label: needle ? "Clients" : "Jump to a client", items: clientItems });
      }
    }

    if (normalizedInput) {
      const scopeLabel = searchType === "all" ? "Search everything" : `Search ${searchType}s`;
      groups.push({ label: scopeLabel, items: [rows.length] });
      rows.push({ kind: "query", key: "query", query: normalizedInput });
    }
    return { rows, groups, partialClients: Boolean(needle && clientPool.data?.next_cursor) };
  }, [showingResults, normalizedInput, recents, clientPool.data, searchType]);

  const close = () => {
    setOpen(false);
    setSearchType("all");
  };

  const submit = (query = normalizedInput) => {
    if (!query) return;
    setInput(query);
    setRecents(storeRecent(query));
    setActiveIndex(0);
    setSearchLatencyMs(null);
    searchStartedAtRef.current = performance.now();
    setSubmittedQuery(query);
  };

  const activateResult = (result: SearchResult) => {
    close();
    onSelect({
      clientId: result.provenance.client_id,
      documentId: result.type === "document" ? result.provenance.document_id : null,
    });
  };

  const activateSuggestion = (suggestion: Suggestion) => {
    if (suggestion.kind === "client") {
      close();
      onSelect({ clientId: suggestion.clientId, documentId: null });
    } else {
      submit(suggestion.query);
    }
  };

  const rowCount = showingResults ? filteredResults.length : suggestions.length;

  useEffect(() => {
    if (!submittedQuery || !search.isFetched) return;
    if (searchStartedAtRef.current === null) return;

    const elapsedMs = Math.max(0, Math.round(performance.now() - searchStartedAtRef.current));
    setSearchLatencyMs(elapsedMs);
    searchStartedAtRef.current = null;
  }, [search.isFetched, submittedQuery, search.data]);

  const navigate = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((value) => Math.min(value + 1, rowCount - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((value) => Math.max(value - 1, showingResults ? 0 : -1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (showingResults && filteredResults[activeIndex]) activateResult(filteredResults[activeIndex]);
      else if (!showingResults && activeIndex >= 0 && suggestions[activeIndex]) activateSuggestion(suggestions[activeIndex]);
      else submit();
    }
  };

  return (
    <>
      <button
        ref={launcherRef}
        className="global-search-trigger"
        type="button"
        aria-label="Search clients and documents"
        onClick={() => setOpen(true)}
      >
        <SearchIcon size={16} />
        <span>Search clients and documents</span>
        <kbd>⌘ K</kbd>
      </button>
      <Dialog
        open={open}
        onClose={close}
        heading="Search workspace"
        size="lg"
        align="top"
        className="search-dialog"
        initialFocus={inputRef}
        finalFocus={launcherRef}
      >
        <form className="search-form" onSubmit={(event) => { event.preventDefault(); submit(); }}>
          <SearchField
            ref={inputRef}
            label="Search clients and documents"
            placeholder="Search clients and documents"
            role="combobox"
            aria-expanded={rowCount > 0}
            aria-controls={LISTBOX_ID}
            aria-activedescendant={activeIndex >= 0 && activeIndex < rowCount ? optionId(activeIndex) : undefined}
            aria-autocomplete="list"
            value={input}
            onChange={(event) => {
              setInput(event.target.value);
              setActiveIndex(-1);
              if (event.target.value === "") setSubmittedQuery("");
            }}
            onKeyDown={navigate}
          />
        </form>

        <SearchTypeFilter
          value={searchType}
          results={showingResults ? results : undefined}
          onChange={(next) => {
            setSearchType(next);
            setActiveIndex(showingResults && (next === "all" ? results.length : results.some((result) => result.type === next)) ? 0 : -1);
          }}
        />

        {showingResults ? (
          <ResultList
            results={filteredResults}
            resultType={searchType}
            activeIndex={activeIndex}
            query={submittedQuery}
            mode={mode}
            pending={search.isPending}
            error={search.isError ? search.error.message : null}
            latencyMs={searchLatencyMs}
            hasNextPage={search.hasNextPage}
            isFetchingNextPage={search.isFetchingNextPage}
            onHover={setActiveIndex}
            onActivate={activateResult}
            onLoadMore={() => search.fetchNextPage()}
          />
        ) : (
          <SuggestionList
            suggestions={suggestions}
            groups={suggestionGroups}
            activeIndex={activeIndex}
            partialClients={partialClients}
            onHover={setActiveIndex}
            onActivate={activateSuggestion}
          />
        )}

        <p className="search-shortcuts" aria-hidden="true">
          <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
          <span><kbd>↵</kbd> open</span>
          <span><kbd>esc</kbd> close</span>
        </p>
      </Dialog>
    </>
  );
}

function SearchTypeFilter({ value, results, onChange }: {
  value: SearchType;
  results?: SearchResult[];
  onChange: (value: SearchType) => void;
}) {
  const counts = results?.reduce(
    (total, result) => ({ ...total, [result.type]: total[result.type] + 1 }),
    { client: 0, document: 0 }
  );
  const options: { value: SearchType; label: string; count?: number }[] = [
    { value: "all", label: "All", count: results?.length },
    { value: "client", label: "Clients", count: counts?.client },
    { value: "document", label: "Documents", count: counts?.document },
  ];

  return (
    <div className="search-type-filter" role="group" aria-label="Filter search results by type">
      {options.map((option) => (
        <button
          type="button"
          key={option.value}
          className="search-type-filter__option"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          <span>{option.label}</span>
          {option.count === undefined ? null : <small>{option.count}</small>}
        </button>
      ))}
    </div>
  );
}

function SuggestionList({ suggestions, groups, activeIndex, partialClients, onHover, onActivate }: {
  suggestions: Suggestion[];
  groups: SuggestionGroup[];
  activeIndex: number;
  partialClients: boolean;
  onHover: (index: number) => void;
  onActivate: (suggestion: Suggestion) => void;
}) {
  if (suggestions.length === 0) {
    return (
      <div className="search-feedback">
        <p className="search-hint">Search names, emails, titles, and indexed content.</p>
      </div>
    );
  }

  return (
    <div className="search-results" role="listbox" id={LISTBOX_ID} aria-label="Suggestions">
      {groups.map((group) => (
        <div className="search-group" role="group" aria-label={group.label} key={group.label}>
          <p className="search-group__label">{group.label}</p>
          {group.items.map((index) => {
            const suggestion = suggestions[index];
            return (
              <button
                key={suggestion.key}
                id={optionId(index)}
                type="button"
                role="option"
                aria-selected={activeIndex === index}
                className={activeIndex === index ? "search-result search-result--active" : "search-result"}
                onMouseEnter={() => onHover(index)}
                onClick={() => onActivate(suggestion)}
              >
                <span className="result-icon">
                  {suggestion.kind === "client" ? <ClientsIcon size={18} /> : <SearchIcon size={18} />}
                </span>
                <span className="result-copy">
                  <strong>
                    {suggestion.kind === "client" ? suggestion.name : null}
                    {suggestion.kind === "recent" ? suggestion.query : null}
                    {suggestion.kind === "query" ? `Search for “${suggestion.query}”` : null}
                  </strong>
                  {suggestion.kind === "client" ? <small>{suggestion.email}</small> : null}
                  {suggestion.kind === "query" ? <small>Includes document content</small> : null}
                </span>
              </button>
            );
          })}
          {partialClients && group.label === "Clients" ? (
            <p className="loaded-scope">Matching loaded clients only — press Enter to search all.</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function ResultList({ results, resultType, activeIndex, query, mode, pending, error, latencyMs, hasNextPage, isFetchingNextPage, onHover, onActivate, onLoadMore }: {
  results: SearchResult[];
  resultType: SearchType;
  activeIndex: number;
  query: string;
  mode: string | undefined;
  pending: boolean;
  error: string | null;
  latencyMs: number | null;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;
  onHover: (index: number) => void;
  onActivate: (result: SearchResult) => void;
  onLoadMore: () => void;
}) {
  return (
    <>
      <div className="search-feedback" aria-live="polite">
        {pending ? <Spinner label="Searching workspace…" /> : null}
        {error ? <p className="form-error" role="alert">{error}</p> : null}
        {latencyMs !== null && !pending ? (
          <p className="search-speed">Search finished in {latencyMs} ms</p>
        ) : null}
        {mode === "lexical_degraded" ? (
          <p className="degraded-note">Semantic search unavailable — showing text matches.</p>
        ) : null}
        {!pending && !error && results.length === 0 ? (
          <p className="empty-copy">
            No {resultType === "all" ? "matches" : `${resultType}s`} for “{query}”.
            {hasNextPage && resultType !== "all" ? " Load more to check additional results." : null}
          </p>
        ) : null}
      </div>
      {results.length > 0 || hasNextPage ? (
        <div className="search-results" role="listbox" id={LISTBOX_ID} aria-label="Search results">
          {results.map((result, index) => (
            <SearchHit
              key={`${result.type}-${result.type === "document" ? result.provenance.document_id : result.provenance.client_id}`}
              id={optionId(index)}
              result={result}
              active={activeIndex === index}
              onHover={() => onHover(index)}
              onActivate={() => onActivate(result)}
            />
          ))}
          {hasNextPage ? (
            <Button kind="ghost" size="sm" onClick={onLoadMore} disabled={isFetchingNextPage}>
              {isFetchingNextPage ? "Loading…" : "Load more results"}
            </Button>
          ) : null}
        </div>
      ) : null}
    </>
  );
}

function SearchHit({ id, result, active, onHover, onActivate }: {
  id: string;
  result: SearchResult;
  active: boolean;
  onHover: () => void;
  onActivate: () => void;
}) {
  return (
    <button
      id={id}
      type="button"
      role="option"
      aria-selected={active}
      className={active ? "search-result search-result--active" : "search-result"}
      onMouseEnter={onHover}
      onClick={onActivate}
    >
      <span className="result-icon">
        {result.type === "client" ? <ClientsIcon size={18} /> : <DocumentIcon size={18} />}
      </span>
      <span className="result-copy">
        {result.type === "document" ? <em className="result-parent">{result.client_name}</em> : null}
        <strong>{result.title}</strong>
        <small>{result.type === "client" ? result.email : result.snippet}</small>
      </span>
      <span className="result-tags">
        {result.match_band === 3 ? <Tag tone="info">suggestion</Tag> : null}
        <Tag tone={result.type === "client" ? "info" : "accent"}>{result.type}</Tag>
      </span>
    </button>
  );
}
