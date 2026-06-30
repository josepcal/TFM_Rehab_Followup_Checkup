import { useState, useEffect, useRef } from "react";
import type { AuditLogApi, AuditLogFilters, EventLogEntry } from "../../api/auditLog";

const ITEMS_PER_PAGE = 10;

type AdminEventsDashboardProps = {
  api: AuditLogApi;
};

export function AdminEventsDashboard({ api }: AdminEventsDashboardProps) {
  const [entries, setEntries] = useState<EventLogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [searchText, setSearchText] = useState("");
  const [entityTypeFilter, setEntityTypeFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [offset, setOffset] = useState(0);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function buildFilters(overrides: Partial<AuditLogFilters> = {}): AuditLogFilters {
    const filters: AuditLogFilters = {
      limit: ITEMS_PER_PAGE,
      offset,
    };
    if (entityTypeFilter) filters.entity_type = entityTypeFilter;
    if (dateFrom) filters.from_ts = new Date(dateFrom).toISOString();
    if (dateTo) filters.to_ts = new Date(dateTo).toISOString();
    if (searchText) filters.actor_id = searchText;
    return { ...filters, ...overrides };
  }

  function fetchData(filters: AuditLogFilters, localActionFilter: string) {
    setIsLoading(true);
    setError(null);
    api
      .getAuditLog(filters)
      .then((data) => {
        const filtered = localActionFilter
          ? data.filter((e) => e.action === localActionFilter)
          : data;
        setEntries(filtered);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load audit log");
        setIsLoading(false);
      });
  }

  // Debounce text search; immediate for other filters
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      fetchData(buildFilters({ offset }), actionFilter);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchText, entityTypeFilter, actionFilter, dateFrom, dateTo, offset]);

  function handleReset() {
    setSearchText("");
    setEntityTypeFilter("");
    setActionFilter("");
    setDateFrom("");
    setDateTo("");
    setOffset(0);
  }

  const hasActiveFilters = searchText || entityTypeFilter || actionFilter || dateFrom || dateTo;
  const currentPage = Math.floor(offset / ITEMS_PER_PAGE) + 1;
  const hasNextPage = entries.length === ITEMS_PER_PAGE;
  const hasPrevPage = offset > 0;

  return (
    <div className="audit-log-dashboard">
      <div className="audit-log-header">
        <h2>Event Log</h2>
        <p className="muted">{isLoading ? "Loading…" : `${entries.length} events on this page`}</p>
      </div>

      {/* Filters */}
      <div className="audit-log-filters">
        <div className="audit-log-filters-header">
          <span className="audit-log-filters-title">Filters</span>
          <span className="muted">Search and filter events by multiple criteria</span>
        </div>

        <input
          type="search"
          placeholder="Search by actor ID…"
          value={searchText}
          onChange={(e) => {
            setSearchText(e.target.value);
            setOffset(0);
          }}
          className="audit-log-search"
          aria-label="Search by actor ID"
        />

        <div className="audit-log-filter-grid">
          <div className="audit-log-filter-field">
            <label htmlFor="audit-entity-type">Entity Type</label>
            <select
              id="audit-entity-type"
              value={entityTypeFilter}
              onChange={(e) => {
                setEntityTypeFilter(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All entity types</option>
              <option value="patient">patient</option>
              <option value="diagnostic">diagnostic</option>
              <option value="program">program</option>
              <option value="doctor">doctor</option>
              <option value="recording">recording</option>
              <option value="consent">consent</option>
            </select>
          </div>

          <div className="audit-log-filter-field">
            <label htmlFor="audit-action">Action</label>
            <select
              id="audit-action"
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All actions</option>
              <option value="create">create</option>
              <option value="update">update</option>
              <option value="delete">delete</option>
              <option value="view">view</option>
              <option value="login">login</option>
              <option value="upload">upload</option>
              <option value="sign">sign</option>
              <option value="analyze">analyze</option>
              <option value="consent_granted">consent_granted</option>
            </select>
          </div>

          <div className="audit-log-filter-field">
            <label htmlFor="audit-date-from">From</label>
            <input
              id="audit-date-from"
              type="datetime-local"
              step="1"
              value={dateFrom}
              onChange={(e) => {
                setDateFrom(e.target.value);
                setOffset(0);
              }}
            />
          </div>

          <div className="audit-log-filter-field">
            <label htmlFor="audit-date-to">To</label>
            <input
              id="audit-date-to"
              type="datetime-local"
              step="1"
              value={dateTo}
              onChange={(e) => {
                setDateTo(e.target.value);
                setOffset(0);
              }}
            />
          </div>
        </div>

        {hasActiveFilters ? (
          <button type="button" className="secondary-button" onClick={handleReset}>
            Reset Filters
          </button>
        ) : null}
      </div>

      {/* Error state */}
      {error ? (
        <div className="audit-log-error" role="alert">
          <span>{error}</span>
          <button
            type="button"
            className="secondary-button"
            onClick={() => fetchData(buildFilters({ offset }), actionFilter)}
          >
            Retry
          </button>
        </div>
      ) : null}

      {/* Table */}
      <div className="audit-log-table-wrapper">
        {!isLoading && entries.length === 0 ? (
          <p className="audit-log-empty muted">No events found matching your filters</p>
        ) : (
          <table className="audit-log-table" aria-label="Audit event log">
            <thead>
              <tr>
                <th scope="col">Timestamp</th>
                <th scope="col">Entity</th>
                <th scope="col">Entity ID</th>
                <th scope="col">Action</th>
                <th scope="col">Actor</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.event_id}>
                  <td className="audit-log-mono audit-log-muted">
                    {new Date(entry.occurred_at).toLocaleString()}
                  </td>
                  <td>
                    <span className="audit-badge audit-badge--entity">{entry.entity_type}</span>
                  </td>
                  <td className="audit-log-mono audit-log-muted">
                    {entry.entity_id ? entry.entity_id.slice(0, 8) : "—"}
                  </td>
                  <td>
                    <span className={`audit-badge ${getActionBadgeClass(entry.action)}`}>
                      {entry.action}
                    </span>
                  </td>
                  <td className="audit-log-mono audit-log-muted">
                    {entry.actor_id ? entry.actor_id.slice(0, 8) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {(hasPrevPage || hasNextPage) ? (
        <div className="audit-log-pagination">
          <span className="muted">Page {currentPage}</span>
          <div className="audit-log-pagination-actions">
            <button
              type="button"
              className="secondary-button"
              disabled={!hasPrevPage}
              onClick={() => setOffset((prev) => Math.max(0, prev - ITEMS_PER_PAGE))}
            >
              ← Previous
            </button>
            <button
              type="button"
              className="secondary-button"
              disabled={!hasNextPage}
              onClick={() => setOffset((prev) => prev + ITEMS_PER_PAGE)}
            >
              Next →
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function getActionBadgeClass(action: string): string {
  const map: Record<string, string> = {
    create: "audit-badge--create",
    update: "audit-badge--update",
    delete: "audit-badge--delete",
    upload: "audit-badge--upload",
    view: "audit-badge--view",
    login: "audit-badge--login",
    sign: "audit-badge--sign",
    analyze: "audit-badge--analyze",
    consent_granted: "audit-badge--consent",
  };
  return map[action] ?? "audit-badge--default";
}
