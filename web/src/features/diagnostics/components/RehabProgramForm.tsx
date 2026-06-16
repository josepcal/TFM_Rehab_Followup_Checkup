import { useState } from "react";

import { ApiError } from "../../../api/http";
import type { ProgramIn } from "../../../api/programs";

type RehabProgramFormValues = Omit<ProgramIn, "diagnostic_id" | "physiotherapist_id">;

type RehabProgramFormProps = {
  title?: string;
  submitLabel?: string;
  isSubmitting: boolean;
  error?: unknown;
  onSubmit: (values: RehabProgramFormValues) => void;
};

export function RehabProgramForm({
  title = "Create rehab program",
  submitLabel = "Create rehab program",
  isSubmitting,
  error,
  onSubmit,
}: RehabProgramFormProps) {
  const [name, setName] = useState("");
  const [estado, setEstado] = useState("active");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  return (
    <form
      className="diagnostic-form rehab-program-form"
      aria-label={title}
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({
          name: name.trim() || null,
          estado,
          start_date: toApiDate(startDate),
          end_date: toApiDate(endDate),
        });
      }}
    >
      <div className="card-header">
        <h3 className="card-title">{title}</h3>
        <p className="card-description">
          Set up the rehabilitation plan metadata. Exercise assignment is handled from the program detail.
        </p>
      </div>

      <label className="field">
        <span>Program name</span>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="e.g. Mobility and speech rehabilitation"
        />
      </label>

      <label className="field">
        <span>Status</span>
        <select value={estado} onChange={(event) => setEstado(event.target.value)}>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </label>

      <div className="form-grid-2">
        <label className="field">
          <span>Start date</span>
          <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
        </label>
        <label className="field">
          <span>End date</span>
          <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
        </label>
      </div>

      {error ? <p role="alert">{getErrorMessage(error)}</p> : null}

      <div className="form-actions">
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}

function toApiDate(value: string) {
  return value ? `${value}T00:00:00Z` : null;
}

function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "Unable to save rehab program.";
}
