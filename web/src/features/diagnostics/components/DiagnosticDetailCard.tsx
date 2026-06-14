import { ApiError } from "../../../api/http";
import type { DiagnosticOut } from "../../../api/diagnostics";

type DiagnosticDetailCardProps = {
  diagnostic?: DiagnosticOut;
  isLoading: boolean;
  error?: unknown;
};

export function DiagnosticDetailCard({ diagnostic, isLoading, error }: DiagnosticDetailCardProps) {
  if (isLoading) {
    return <p role="status">Loading diagnostic detail…</p>;
  }

  if (error instanceof ApiError && error.status === 403) {
    return <p role="alert">You are not authorized to view this diagnostic.</p>;
  }

  if (error instanceof ApiError && error.status === 404) {
    return <p role="alert">Diagnostic was not found.</p>;
  }

  if (error) {
    return <p role="alert">Unable to load diagnostic detail.</p>;
  }

  if (!diagnostic) {
    return <p>Select or create a diagnostic to see details.</p>;
  }

  return (
    <article className="detail-card" aria-label="Diagnostic detail">
      <h3>{diagnostic.dolencia}</h3>
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
