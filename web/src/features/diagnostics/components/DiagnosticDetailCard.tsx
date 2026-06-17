import { ApiError } from "../../../api/http";
import type { DiagnosticOut } from "../../../api/diagnostics";
import type { ReactNode } from "react";

type DiagnosticDetailCardProps = {
  diagnostic?: DiagnosticOut;
  isLoading: boolean;
  error?: unknown;
  onEdit?: () => void;
};

export function DiagnosticDetailCard({ diagnostic, isLoading, error, onEdit }: DiagnosticDetailCardProps) {
  if (isLoading) {
    return (
      <p className="state-card" role="status">
        Loading diagnostic detail…
      </p>
    );
  }

  if (error instanceof ApiError && error.status === 403) {
    return (
      <p className="state-card" role="alert">
        You are not authorized to view this diagnostic.
      </p>
    );
  }

  if (error instanceof ApiError && error.status === 404) {
    return (
      <p className="state-card" role="alert">
        Diagnostic was not found.
      </p>
    );
  }

  if (error) {
    return (
      <p className="state-card" role="alert">
        Unable to load diagnostic detail.
      </p>
    );
  }

  if (!diagnostic) {
    return <p className="state-card">Select or create a diagnostic to see details.</p>;
  }

  const isSigned = Boolean(diagnostic.signed_at);
  const timestamp = diagnostic.signed_at
    ? `Signed ${formatDateTime(diagnostic.signed_at)}`
    : diagnostic.created_at
      ? `Created ${formatDateTime(diagnostic.created_at)}`
      : "No timestamp available";

  return (
    <div className="diagnostic-detail-v0" aria-label="Diagnostic detail">
      <div className="v0-page-title-row">
        <div className="v0-page-title-stack">
          <div className="v0-title-with-badge">
            <h1>{diagnostic.dolencia}</h1>
            <span className={isSigned ? "status-badge status-signed" : "status-badge"}>
              {isSigned ? "✓ Signed" : "Draft"}
            </span>
          </div>
          <p>{timestamp}</p>
        </div>
        {onEdit ? (
          <button type="button" className="v0-outline-button" aria-label="Edit diagnostic" onClick={onEdit}>
            <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
            </svg>
            Edit
          </button>
        ) : null}
      </div>

      <article className="detail-card diagnostic-assessment-card" aria-label="Diagnostic assessment">
        <header className="card-header">
          <h3 className="card-title">Assessment</h3>
        </header>
        <div className="assessment-fields">
          <section className="assessment-box">
            <AssessmentHeading
              label="Description"
              icon={
                <>
                  <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" x2="8" y1="13" y2="13" />
                  <line x1="16" x2="8" y1="17" y2="17" />
                  <line x1="10" x2="8" y1="9" y2="9" />
                </>
              }
            />
            <p>{diagnostic.descripcion || <span className="muted-cell">Not documented.</span>}</p>
          </section>
          <section className="assessment-box">
            <AssessmentHeading
              label="History"
              icon={
                <>
                  <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
                  <path d="M3 3v5h5" />
                  <path d="M12 7v5l4 2" />
                </>
              }
            />
            <p>{diagnostic.history || <span className="muted-cell">Not documented.</span>}</p>
          </section>
          <section className="assessment-box">
            <AssessmentHeading
              label="Symptoms"
              icon={<polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />}
            />
            {diagnostic.symptoms ? (
              <div className="symptom-badge-list">
                {splitSymptoms(diagnostic.symptoms).map((symptom) => (
                  <span key={symptom} className="status-badge symptom-badge">
                    {symptom}
                  </span>
                ))}
              </div>
            ) : (
              <p><span className="muted-cell">No symptoms recorded.</span></p>
            )}
          </section>
          <details className="assessment-box assessment-box-attestation" aria-label="Attestation">
            <summary>
              <AssessmentHeading
                label="Attestation"
                icon={
                  <>
                    <path d="M9 12l2 2 4-4" />
                    <path d="M21 12c.552 0 1-.448 1-1V5a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v6c0 .552.448 1 1 1" />
                    <path d="M3 12v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  </>
                }
              />
              <span className="details-caret" aria-hidden="true">▾</span>
            </summary>
            <dl>
              <DetailTerm label="Created" value={diagnostic.created_at} />
              <DetailTerm label="Updated" value={diagnostic.updated_at} />
              <DetailTerm label="Signature" value={diagnostic.signature} />
              <DetailTerm label="Signed at" value={diagnostic.signed_at} />
              <DetailTerm label="Content hash" value={diagnostic.content_hash} />
            </dl>
          </details>
        </div>
      </article>
    </div>
  );
}

function AssessmentHeading({ label, icon }: { label: string; icon: ReactNode }) {
  return (
    <h4 className="assessment-heading">
      <span className="assessment-heading-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" focusable="false">
          {icon}
        </svg>
      </span>
      {label}
    </h4>
  );
}

function splitSymptoms(value: string) {
  return value
    .split(/[\n,]+/)
    .map((symptom) => symptom.trim())
    .filter(Boolean);
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

function DetailTerm({ label, value }: { label: string; value?: string | null }) {
  if (!value) {
    return null;
  }

  return (
    <>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </>
  );
}
