import { FormEvent, KeyboardEvent, useState } from "react";

import { ApiError } from "../../../api/http";

type DiagnosticFormValues = {
  dolencia: string;
  descripcion: string;
  history: string;
  symptoms: string;
};

type DiagnosticFormProps = {
  title: string;
  submitLabel: string;
  initialValues?: Partial<DiagnosticFormValues>;
  isSubmitting: boolean;
  error?: unknown;
  disabled?: boolean;
  useV0Actions?: boolean;
  onCancel?: () => void;
  onSubmit: (values: DiagnosticFormValues) => void;
};

export function DiagnosticForm({
  title,
  submitLabel,
  initialValues,
  isSubmitting,
  error,
  disabled = false,
  useV0Actions = false,
  onCancel,
  onSubmit,
}: DiagnosticFormProps) {
  const [dolencia, setDolencia] = useState(initialValues?.dolencia ?? "");
  const [descripcion, setDescripcion] = useState(initialValues?.descripcion ?? "");
  const [history, setHistory] = useState(initialValues?.history ?? "");
  const [symptoms, setSymptoms] = useState<string[]>(parseSymptoms(initialValues?.symptoms));
  const [symptomInput, setSymptomInput] = useState("");
  const validationError = validateDolencia(dolencia);
  const visibleValidationError = dolencia.length > 0 ? validationError : undefined;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitCurrentValues();
  }

  function submitCurrentValues() {
    if (validationError || disabled || isSubmitting) {
      return;
    }
    onSubmit({
      dolencia: dolencia.trim(),
      descripcion: descripcion.trim(),
      history: history.trim(),
      symptoms: getSubmittedSymptoms().join(", "),
    });
  }

  function getSubmittedSymptoms() {
    const pendingSymptom = symptomInput.trim();
    if (!pendingSymptom || symptoms.includes(pendingSymptom)) {
      return symptoms;
    }
    return [...symptoms, pendingSymptom];
  }

  function addSymptom() {
    const value = symptomInput.trim();
    if (!value) {
      return;
    }
    setSymptoms((current) => (current.includes(value) ? current : [...current, value]));
    setSymptomInput("");
  }

  function handleSymptomKey(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addSymptom();
    }
  }

  function removeSymptom(symptom: string) {
    setSymptoms((current) => current.filter((item) => item !== symptom));
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
        <span>Description</span>
        <textarea
          value={descripcion}
          maxLength={5000}
          disabled={disabled || isSubmitting}
          placeholder="Clinical notes and relevant context"
          onChange={(event) => setDescripcion(event.target.value)}
        />
      </label>

      <label className="field">
        <span>History</span>
        <textarea
          value={history}
          maxLength={5000}
          disabled={disabled || isSubmitting}
          placeholder="Relevant clinical history"
          onChange={(event) => setHistory(event.target.value)}
        />
      </label>

      <div className="field diagnostic-symptoms-field">
        <label htmlFor="diagnostic-symptoms-input">Symptoms</label>
        <div className="symptom-editor-row">
          <input
            id="diagnostic-symptoms-input"
            value={symptomInput}
            maxLength={2000}
            disabled={disabled || isSubmitting}
            placeholder="Add a symptom and press Enter"
            onChange={(event) => setSymptomInput(event.target.value)}
            onKeyDown={handleSymptomKey}
          />
          <button
            type="button"
            className="v0-outline-button symptom-add-button"
            aria-label="Add symptom"
            disabled={disabled || isSubmitting}
            onClick={addSymptom}
          >
            <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
              <path d="M5 12h14" />
              <path d="M12 5v14" />
            </svg>
          </button>
        </div>
        {symptoms.length > 0 ? (
          <div className="symptom-badge-list symptom-edit-list">
            {symptoms.map((symptom) => (
              <span key={symptom} className="status-badge symptom-badge symptom-edit-badge">
                {symptom}
                <button
                  type="button"
                  aria-label={`Remove ${symptom}`}
                  disabled={disabled || isSubmitting}
                  onClick={() => removeSymptom(symptom)}
                >
                  <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
                    <path d="M18 6 6 18" />
                    <path d="m6 6 12 12" />
                  </svg>
                </button>
              </span>
            ))}
          </div>
        ) : null}
      </div>

      {error ? <p role="alert">{formatFormError(error)}</p> : null}

      {useV0Actions ? (
        <div className="form-actions diagnostic-form-actions-v0">
          <button type="button" className="ghost-button" disabled={disabled || isSubmitting} onClick={onCancel}>
            Cancel
          </button>
          <button type="submit" className="v0-outline-button" disabled={disabled || isSubmitting || Boolean(validationError)}>
            <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
              <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z" />
              <path d="M17 21v-8H7v8" />
              <path d="M7 3v5h8" />
            </svg>
            {isSubmitting ? "Saving…" : "Save draft"}
          </button>
          <button
            type="button"
            className="v0-primary-button"
            disabled={disabled || isSubmitting || Boolean(validationError)}
            onClick={submitCurrentValues}
          >
            <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <path d="m9 11 3 3L22 4" />
            </svg>
            {isSubmitting ? "Saving…" : "Sign & save"}
          </button>
        </div>
      ) : (
        <div className="form-actions">
          <p className="form-help">The backend derives doctor identity from the authenticated session.</p>
          <button type="submit" disabled={disabled || isSubmitting || Boolean(validationError)}>
            {isSubmitting ? "Saving…" : submitLabel}
          </button>
        </div>
      )}
    </form>
  );
}

function parseSymptoms(value?: string) {
  return (value ?? "")
    .split(/[\n,]+/)
    .map((symptom) => symptom.trim())
    .filter(Boolean);
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
