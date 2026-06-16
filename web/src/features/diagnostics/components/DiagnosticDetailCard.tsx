import { ApiError } from "../../../api/http";
import type { DiagnosticOut } from "../../../api/diagnostics";

type DiagnosticDetailCardProps = {
  diagnostic?: DiagnosticOut;
  isLoading: boolean;
  error?: unknown;
};

export function DiagnosticDetailCard({ diagnostic, isLoading, error }: DiagnosticDetailCardProps) {
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

  return (
    <article className="detail-card" aria-label="Diagnostic detail">
      <header className="card-header">
        <p className="eyebrow">Attested diagnostic</p>
        <h3 className="card-title">{diagnostic.dolencia}</h3>
      </header>
      {diagnostic.descripcion ? <p>{diagnostic.descripcion}</p> : <p>No description provided.</p>}
      <dl>
        <DetailTerm label="Created" value={diagnostic.created_at} />
        <DetailTerm label="Updated" value={diagnostic.updated_at} />
        <DetailTerm label="Signature" value={diagnostic.signature} />
        <DetailTerm label="Signed at" value={diagnostic.signed_at} />
        <DetailTerm label="Content hash" value={diagnostic.content_hash} />
      </dl>
    </article>
  );
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
