import { FormEvent, useState } from "react";

import { ApiError } from "../../../api/http";

type DiagnosticFormValues = {
  dolencia: string;
  descripcion: string;
};

type DiagnosticFormProps = {
  title: string;
  submitLabel: string;
  initialValues?: Partial<DiagnosticFormValues>;
  isSubmitting: boolean;
  error?: unknown;
  disabled?: boolean;
  onSubmit: (values: DiagnosticFormValues) => void;
};

export function DiagnosticForm({
  title,
  submitLabel,
  initialValues,
  isSubmitting,
  error,
  disabled = false,
  onSubmit,
}: DiagnosticFormProps) {
  const [dolencia, setDolencia] = useState(initialValues?.dolencia ?? "");
  const [descripcion, setDescripcion] = useState(initialValues?.descripcion ?? "");
  const validationError = validateDolencia(dolencia);
  const visibleValidationError = dolencia.length > 0 ? validationError : undefined;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (validationError || disabled) {
      return;
    }
    onSubmit({ dolencia: dolencia.trim(), descripcion: descripcion.trim() });
  }

  return (
    <form className="diagnostic-form" onSubmit={handleSubmit} aria-label={title}>
      <header className="card-header">
        <p className="eyebrow">Assessment details</p>
        <h3 className="card-title">{title}</h3>
        <p className="card-description">
          Record the clinical condition and supporting description for the selected patient.
        </p>
      </header>

      <label className="field">
        <span>Dolencia</span>
        <input
          value={dolencia}
          maxLength={500}
          disabled={disabled || isSubmitting}
          placeholder="e.g. Shoulder pain"
          onChange={(event) => setDolencia(event.target.value)}
        />
      </label>
      {visibleValidationError ? <p role="alert">{visibleValidationError}</p> : null}

      <label className="field">
        <span>Descripcion</span>
        <textarea
          value={descripcion}
          maxLength={5000}
          disabled={disabled || isSubmitting}
          placeholder="Clinical notes, symptoms and relevant context"
          onChange={(event) => setDescripcion(event.target.value)}
        />
      </label>

      {error ? <p role="alert">{formatFormError(error)}</p> : null}

      <div className="form-actions">
        <p className="form-help">The backend derives doctor identity from the authenticated session.</p>
        <button type="submit" disabled={disabled || isSubmitting || Boolean(validationError)}>
          {isSubmitting ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}

function validateDolencia(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return "Dolencia is required.";
  }
  if (trimmed.length > 500) {
    return "Dolencia must be 500 characters or fewer.";
  }
  return undefined;
}

function formatFormError(error: unknown) {
  if (error instanceof ApiError && error.status === 404) {
    return "Selected patient or diagnostic was not found.";
  }
  if (error instanceof ApiError && error.status === 403) {
    return "You are not authorized to save this diagnostic.";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unable to save diagnostic.";
}
