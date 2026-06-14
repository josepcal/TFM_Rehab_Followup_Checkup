import { ApiError } from "../../../api/http";
import type { DiagnosticOut } from "../../../api/diagnostics";

type DiagnosticHistoryListProps = {
  diagnostics: DiagnosticOut[];
  isLoading: boolean;
  error?: unknown;
  hasSelectedPatient: boolean;
};

export function DiagnosticHistoryList({
  diagnostics,
  isLoading,
  error,
  hasSelectedPatient,
}: DiagnosticHistoryListProps) {
  if (!hasSelectedPatient) {
    return <p>Select a patient to view diagnostic history.</p>;
  }

  if (isLoading) {
    return <p role="status">Loading diagnostic history…</p>;
  }

  if (error instanceof ApiError && error.status === 403) {
    return <p role="alert">You are not authorized to view this patient's diagnostics.</p>;
  }

  if (error) {
    return <p role="alert">Unable to load diagnostic history.</p>;
  }

  if (diagnostics.length === 0) {
    return (
      <section aria-label="Diagnostic history empty state">
        <p>No diagnostics exist for this patient yet.</p>
        <p>The create diagnostic action will be available in the next PR slice.</p>
      </section>
    );
  }

  return (
    <ul aria-label="Diagnostic history" className="history-list">
      {diagnostics.map((diagnostic) => (
        <li key={diagnostic.id}>
          <strong>{diagnostic.dolencia}</strong>
          {diagnostic.descripcion ? <p>{diagnostic.descripcion}</p> : null}
          {diagnostic.created_at ? <small>{formatDate(diagnostic.created_at)}</small> : null}
        </li>
      ))}
    </ul>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
