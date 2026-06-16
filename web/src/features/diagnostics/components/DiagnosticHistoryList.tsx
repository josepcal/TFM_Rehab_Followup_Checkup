import { ApiError } from "../../../api/http";
import type { DiagnosticOut } from "../../../api/diagnostics";

type DiagnosticHistoryListProps = {
  diagnostics: DiagnosticOut[];
  selectedDiagnosticId?: string;
  onSelectDiagnostic: (diagnosticId: string) => void;
  isLoading: boolean;
  error?: unknown;
  hasSelectedPatient: boolean;
};

export function DiagnosticHistoryList({
  diagnostics,
  selectedDiagnosticId,
  onSelectDiagnostic,
  isLoading,
  error,
  hasSelectedPatient,
}: DiagnosticHistoryListProps) {
  if (!hasSelectedPatient) {
    return <p className="state-card">Select a patient to view diagnostic history.</p>;
  }

  if (isLoading) {
    return (
      <p className="state-card" role="status">
        Loading diagnostic history…
      </p>
    );
  }

  if (error instanceof ApiError && error.status === 403) {
    return (
      <p className="state-card" role="alert">
        You are not authorized to view this patient's diagnostics.
      </p>
    );
  }

  if (error) {
    return (
      <p className="state-card" role="alert">
        Unable to load diagnostic history.
      </p>
    );
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
          <button
            type="button"
            className="link-button"
            aria-pressed={diagnostic.id === selectedDiagnosticId}
            onClick={() => onSelectDiagnostic(diagnostic.id)}
          >
            <strong>{diagnostic.dolencia}</strong>
          </button>
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
