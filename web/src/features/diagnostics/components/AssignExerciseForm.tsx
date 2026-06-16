import { FormEvent, useState } from "react";

import { ApiError } from "../../../api/http";
import type { RehabExerciseOut } from "../../../api/catalog";
import type { ProgramExerciseIn } from "../../../api/programs";

type AssignExerciseFormProps = {
  exercises: RehabExerciseOut[];
  isLoadingCatalog: boolean;
  isSubmitting: boolean;
  error?: unknown;
  catalogError?: unknown;
  onSubmit: (values: ProgramExerciseIn) => void;
};

export function AssignExerciseForm({
  exercises,
  isLoadingCatalog,
  isSubmitting,
  error,
  catalogError,
  onSubmit,
}: AssignExerciseFormProps) {
  const [exerciseId, setExerciseId] = useState("");
  const [pauta, setPauta] = useState("");

  const canSubmit = Boolean(exerciseId) && !isLoadingCatalog && !isSubmitting && !catalogError;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    onSubmit({
      exercise_id: exerciseId,
      pauta: pauta.trim() || null,
    });
  }

  return (
    <form className="assign-exercise-form" aria-label="Assign exercise" onSubmit={handleSubmit}>
      <div className="card-header">
        <p className="eyebrow">Exercise catalog</p>
        <h4 className="card-title">Assign exercise</h4>
        <p className="form-help">Select a catalog exercise and add optional pauta instructions.</p>
      </div>

      {isLoadingCatalog ? (
        <p className="state-card compact" role="status">
          Loading exercise catalog…
        </p>
      ) : null}

      {catalogError ? (
        <p className="state-card compact" role="alert">
          {formatCatalogError(catalogError)}
        </p>
      ) : null}

      {!isLoadingCatalog && !catalogError && exercises.length === 0 ? (
        <p className="state-card compact">No catalog exercises available.</p>
      ) : null}

      <label>
        Exercise
        <select
          value={exerciseId}
          onChange={(event) => setExerciseId(event.target.value)}
          disabled={isLoadingCatalog || Boolean(catalogError) || exercises.length === 0 || isSubmitting}
        >
          <option value="">Select exercise</option>
          {exercises.map((exercise) => (
            <option key={exercise.id} value={exercise.id}>
              {exercise.nombre}{exercise.tipo ? ` · ${exercise.tipo}` : ""}
            </option>
          ))}
        </select>
      </label>

      <label>
        Pauta
        <textarea
          value={pauta}
          onChange={(event) => setPauta(event.target.value)}
          placeholder="e.g. 2 series of 10 repetitions, daily"
          disabled={isSubmitting}
        />
      </label>

      {error ? <p role="alert">{formatAssignmentError(error)}</p> : null}

      <button type="submit" disabled={!canSubmit}>
        {isSubmitting ? "Assigning…" : "Assign exercise"}
      </button>
    </form>
  );
}

function formatCatalogError(error: unknown) {
  if (error instanceof ApiError && error.status === 403) {
    return "You are not authorized to view the exercise catalog.";
  }
  if (error instanceof ApiError && error.status === 404) {
    return "Exercise catalog not found.";
  }
  return "Unable to load the exercise catalog.";
}

function formatAssignmentError(error: unknown) {
  if (error instanceof ApiError && error.status === 403) {
    return "You are not authorized to assign exercises to this program.";
  }
  if (error instanceof ApiError && error.status === 404) {
    return "Program or exercise not found. Review the selection and try again.";
  }
  return "Unable to assign exercise. Please try again.";
}
