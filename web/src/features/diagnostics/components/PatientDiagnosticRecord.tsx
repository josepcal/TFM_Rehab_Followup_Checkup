import { ApiError } from "../../../api/http";
import type { DiagnosticOut } from "../../../api/diagnostics";
import type { PatientOut } from "../../../api/patients";

type PatientDiagnosticRecordProps = {
  patient?: PatientOut;
  diagnostics: DiagnosticOut[];
  selectedDiagnosticId?: string;
  onSelectDiagnostic: (diagnosticId: string) => void;
  onBackToPatients: () => void;
  onStartNewDiagnostic: () => void;
  isLoading: boolean;
  error?: unknown;
  hasSelectedPatient: boolean;
};

export function PatientDiagnosticRecord({
  patient,
  diagnostics,
  selectedDiagnosticId,
  onSelectDiagnostic,
  onBackToPatients,
  onStartNewDiagnostic,
  isLoading,
  error,
  hasSelectedPatient,
}: PatientDiagnosticRecordProps) {
  if (!hasSelectedPatient || !patient) {
    return <p className="state-card">Select a patient to view diagnostic history.</p>;
  }

  const signedCount = diagnostics.filter((diagnostic) => Boolean(diagnostic.signed_at)).length;
  const latestDiagnostic = diagnostics[0]?.signed_at ?? diagnostics[0]?.created_at ?? null;

  return (
    <section className="patient-record-screen" aria-label="Patient diagnostic record">
      <button type="button" className="back-link-button" onClick={onBackToPatients}>
        ← Patients
      </button>

      <article className="patient-record-card" aria-label="Selected patient">
        <header className="patient-record-header">
          <div className="patient-identity">
            <span className="patient-avatar" aria-hidden="true">
              {getInitials(patient)}
            </span>
            <div>
              <p className="eyebrow">Patient record</p>
              <h3 className="card-title">
                {patient.nombre} {patient.apellidos}
              </h3>
              <p className="patient-id">{patient.id}</p>
            </div>
          </div>
          <button type="button" className="secondary-button" onClick={onStartNewDiagnostic}>
            + New diagnostic
          </button>
        </header>

        <dl className="patient-record-stats" aria-label="Patient diagnostic summary">
          <div>
            <dt>Diagnostics</dt>
            <dd>{diagnostics.length}</dd>
          </div>
          <div>
            <dt>Signed</dt>
            <dd>{signedCount}</dd>
          </div>
          <div>
            <dt>Last assessment</dt>
            <dd>{latestDiagnostic ? formatDateTime(latestDiagnostic) : "—"}</dd>
          </div>
        </dl>
      </article>

      <div className="section-heading">
        <h3>Diagnostic history</h3>
        <p>Assessments recorded for this patient, most recent first.</p>
      </div>

      <DiagnosticHistoryState
        diagnostics={diagnostics}
        selectedDiagnosticId={selectedDiagnosticId}
        onSelectDiagnostic={onSelectDiagnostic}
        isLoading={isLoading}
        error={error}
        onStartNewDiagnostic={onStartNewDiagnostic}
      />
    </section>
  );
}

type DiagnosticHistoryStateProps = {
  diagnostics: DiagnosticOut[];
  selectedDiagnosticId?: string;
  onSelectDiagnostic: (diagnosticId: string) => void;
  onStartNewDiagnostic: () => void;
  isLoading: boolean;
  error?: unknown;
};

function DiagnosticHistoryState({
  diagnostics,
  selectedDiagnosticId,
  onSelectDiagnostic,
  isLoading,
  error,
  onStartNewDiagnostic,
}: DiagnosticHistoryStateProps) {
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
      <section className="empty-record-card" aria-label="Diagnostic history empty state">
        <p>No diagnostics exist for this patient yet.</p>
        <button type="button" className="secondary-button" onClick={onStartNewDiagnostic}>
          Create first diagnostic
        </button>
      </section>
    );
  }

  return (
    <div aria-label="Diagnostic history" className="diagnostic-card-list">
      {diagnostics.map((diagnostic) => (
        <article
          key={diagnostic.id}
          className={
            diagnostic.id === selectedDiagnosticId
              ? "diagnostic-record-card diagnostic-record-card-selected"
              : "diagnostic-record-card"
          }
        >
          <div className="diagnostic-card-head">
            <button
              type="button"
              className="diagnostic-title-button"
              aria-pressed={diagnostic.id === selectedDiagnosticId}
              onClick={() => onSelectDiagnostic(diagnostic.id)}
            >
              {diagnostic.dolencia}
            </button>
            <span className={diagnostic.signed_at ? "status-badge status-signed" : "status-badge"}>
              {diagnostic.signed_at ? "✓ Signed" : "Draft"}
            </span>
          </div>
          {diagnostic.descripcion ? <p>{diagnostic.descripcion}</p> : <p>No description provided.</p>}
          <small>
            {diagnostic.signed_at
              ? `Signed ${formatDateTime(diagnostic.signed_at)}`
              : diagnostic.created_at
                ? `Created ${formatDateTime(diagnostic.created_at)}`
                : "No timestamp available"}
          </small>
        </article>
      ))}
    </div>
  );
}

function getInitials(patient: PatientOut) {
  return [patient.nombre, patient.apellidos]
    .filter(Boolean)
    .map((part) => part.trim().charAt(0).toUpperCase())
    .join("")
    .slice(0, 2);
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}
