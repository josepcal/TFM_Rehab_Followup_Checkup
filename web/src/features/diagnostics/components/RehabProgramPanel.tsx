import { FormEvent, useEffect, useState } from "react";

import { ApiError } from "../../../api/http";
import type { RehabExerciseOut } from "../../../api/catalog";
import type { DoctorOut } from "../../../api/doctors";
import type { ProgramExerciseOut, ProgramOut, ProgramPatchIn } from "../../../api/programs";
import type { DiagnosticFeatureApi } from "../api";
import { ExerciseReportsPanel } from "./ExerciseReportsPanel";
import { FollowupCheckupPanel } from "./FollowupCheckupPanel";
import {
  useAssignExercise,
  useDoctors,
  useExerciseCatalog,
  useProgramDetail,
  useProgramExercises,
  usePrograms,
  useUpdateProgram,
} from "../hooks";
import { AssignExerciseForm } from "./AssignExerciseForm";

type RehabProgramPanelProps = {
  api: DiagnosticFeatureApi;
  diagnosticId?: string;
  patientId?: string;
  selectedProgramId?: string;
  title?: string;
  description?: string;
  onSelectProgram: (programId: string) => void;
  onCreateProgram?: () => void;
  showHeader?: boolean;
  showList?: boolean;
  showDetail?: boolean;
};

export function RehabProgramPanel({
  api,
  diagnosticId,
  patientId,
  selectedProgramId,
  title = "Rehab programs",
  description = "Programs visible to the authenticated doctor.",
  onSelectProgram,
  onCreateProgram,
  showHeader = true,
  showList = true,
  showDetail = true,
}: RehabProgramPanelProps) {
  const [isEditingProgram, setIsEditingProgram] = useState(false);
  const programsQuery = usePrograms(api, { diagnosticId, patientId });
  const programs = programsQuery.data?.items ?? [];
  const detailQuery = useProgramDetail(api, selectedProgramId);
  const exercisesQuery = useProgramExercises(api, selectedProgramId);
  const catalogQuery = useExerciseCatalog(api);
  const doctorsQuery = useDoctors(api, isEditingProgram);
  const assignExercise = useAssignExercise(api);
  const updateProgram = useUpdateProgram(api);
  const selectedProgram = detailQuery.data ?? programs.find((program) => program.id === selectedProgramId);

  useEffect(() => {
    setIsEditingProgram(false);
  }, [selectedProgramId]);

  return (
    <section className="rehab-program-panel" aria-label={title}>
      {showHeader ? (
        <div className="section-heading section-heading-row">
          <div>
            <h3>{title}</h3>
            <p>{description}</p>
          </div>
          {onCreateProgram ? (
            <button type="button" className="secondary-button" onClick={onCreateProgram}>
              + Setup rehab program
            </button>
          ) : null}
        </div>
      ) : null}

      {showList ? (
        <ProgramListState
          programs={programs}
          isLoading={programsQuery.isLoading}
          error={programsQuery.error}
          selectedProgramId={selectedProgramId}
          onSelectProgram={onSelectProgram}
        />
      ) : null}

      {showDetail && selectedProgramId ? (
        <ProgramDetailState
          api={api}
          program={selectedProgram}
          isLoading={detailQuery.isLoading}
          error={detailQuery.error}
          assignedExercises={exercisesQuery.data?.items ?? []}
          isLoadingExercises={exercisesQuery.isLoading}
          exercisesError={exercisesQuery.error}
          catalogExercises={catalogQuery.data ?? []}
          isLoadingCatalog={catalogQuery.isLoading}
          assignError={assignExercise.error}
          catalogError={catalogQuery.error}
          isAssigning={assignExercise.isPending}
          isUpdating={updateProgram.isPending}
          updateError={updateProgram.error}
          doctors={doctorsQuery.data ?? []}
          isLoadingDoctors={doctorsQuery.isLoading}
          doctorsError={doctorsQuery.error}
          isEditing={isEditingProgram}
          onEdit={() => setIsEditingProgram(true)}
          onCancelEdit={() => setIsEditingProgram(false)}
          onUpdateProgram={(values) =>
            updateProgram.mutate(
              { programId: selectedProgramId, body: values },
              { onSuccess: () => setIsEditingProgram(false) },
            )
          }
          onAssignExercise={(values) => assignExercise.mutate({ programId: selectedProgramId, body: values })}
        />
      ) : null}
    </section>
  );
}

type ProgramListStateProps = {
  programs: ProgramOut[];
  isLoading: boolean;
  error?: unknown;
  selectedProgramId?: string;
  onSelectProgram: (programId: string) => void;
};

function ProgramListState({
  programs,
  isLoading,
  error,
  selectedProgramId,
  onSelectProgram,
}: ProgramListStateProps) {
  if (isLoading) {
    return (
      <p className="state-card" role="status">
        Loading rehab programs…
      </p>
    );
  }

  if (error instanceof ApiError && error.status === 403) {
    return (
      <p className="state-card" role="alert">
        You are not authorized to view these rehab programs.
      </p>
    );
  }

  if (error) {
    return (
      <p className="state-card" role="alert">
        Unable to load rehab programs.
      </p>
    );
  }

  if (programs.length === 0) {
    return <p className="state-card">No rehab programs found.</p>;
  }

  return (
    <div className="rehab-program-list" aria-label="Rehab program list">
      {programs.map((program) => (
        <article
          className={program.id === selectedProgramId ? "rehab-program-card selected" : "rehab-program-card"}
          key={program.id}
        >
          <button
            type="button"
            className="diagnostic-title-button"
            aria-pressed={program.id === selectedProgramId}
            onClick={() => onSelectProgram(program.id)}
          >
            {program.name || "Untitled rehab program"}
          </button>
          <p className="muted-cell">Diagnostic {program.diagnostic_id ? `#${program.diagnostic_id.slice(0, 8)}` : "—"}</p>
          <span className="status-badge">{formatStatus(program.estado)}</span>
        </article>
      ))}
    </div>
  );
}

function ProgramDetailState({
  api,
  program,
  isLoading,
  error,
  assignedExercises,
  isLoadingExercises,
  exercisesError,
  catalogExercises,
  isLoadingCatalog,
  assignError,
  catalogError,
  isAssigning,
  isUpdating,
  updateError,
  doctors,
  isLoadingDoctors,
  doctorsError,
  isEditing,
  onEdit,
  onCancelEdit,
  onUpdateProgram,
  onAssignExercise,
}: {
  api: DiagnosticFeatureApi;
  program?: ProgramOut;
  isLoading: boolean;
  error?: unknown;
  assignedExercises: ProgramExerciseOut[];
  isLoadingExercises: boolean;
  exercisesError?: unknown;
  catalogExercises: RehabExerciseOut[];
  isLoadingCatalog: boolean;
  assignError?: unknown;
  catalogError?: unknown;
  isAssigning: boolean;
  isUpdating: boolean;
  updateError?: unknown;
  doctors: DoctorOut[];
  isLoadingDoctors: boolean;
  doctorsError?: unknown;
  isEditing: boolean;
  onEdit: () => void;
  onCancelEdit: () => void;
  onUpdateProgram: (values: ProgramPatchIn) => void;
  onAssignExercise: (values: { exercise_id: string; pauta?: string | null }) => void;
}) {
  if (isLoading) {
    return (
      <p className="state-card" role="status">
        Loading program detail…
      </p>
    );
  }

  if (error instanceof ApiError && error.status === 403) {
    return (
      <p className="state-card" role="alert">
        You are not authorized to view this rehab program.
      </p>
    );
  }

  if (error instanceof ApiError && error.status === 404) {
    return (
      <p className="state-card" role="alert">
        Rehab program not found.
      </p>
    );
  }

  if (error) {
    return (
      <p className="state-card" role="alert">
        Unable to load rehab program detail.
      </p>
    );
  }

  if (!program) {
    return null;
  }

  const [showReports, setShowReports] = useState(false);
  const [showCheckups, setShowCheckups] = useState(false);

  return (
    <article
      className={isEditing ? "rehab-program-detail-screen rehab-program-edit-screen" : "rehab-program-detail-screen"}
      aria-label={isEditing ? "Edit rehab program" : "Rehab program detail"}
    >
      <div className="v0-page-title-row">
        <div className="v0-page-title-stack">
          <div className="v0-title-with-badge">
            <h1>{isEditing ? "Edit program" : program.name || "Untitled rehab program"}</h1>
            <span className="status-badge">{formatStatus(program.estado)}</span>
          </div>
          <p>{isEditing ? program.name || "Untitled rehab program" : `Linked diagnostic ${program.diagnostic_id}`}</p>
        </div>
        {isEditing ? (
          <button type="button" className="ghost-button v0-program-action" onClick={onCancelEdit}>
            Cancel
          </button>
        ) : (
          <button type="button" className="v0-outline-button" aria-label="Edit program" onClick={onEdit}>
            <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
            </svg>
            Edit program
          </button>
        )}
      </div>

      <section className="detail-card rehab-program-detail" aria-label="Rehab program summary">
        {isEditing ? (
          <ProgramEditForm
            program={program}
            isSubmitting={isUpdating}
            error={updateError}
            doctors={doctors}
            isLoadingDoctors={isLoadingDoctors}
            doctorsError={doctorsError}
            onSubmit={onUpdateProgram}
          />
        ) : (
          <>
            <div className="card-header">
              <h3 className="card-title">Program setup</h3>
            </div>
            <dl>
              <dt>Linked diagnostic</dt>
              <dd>{program.diagnostic_id}</dd>
              <dt>Physiotherapist</dt>
              <dd>{program.physiotherapist_id || "Not assigned"}</dd>
              <dt>Status</dt>
              <dd>{formatStatus(program.estado)}</dd>
              <dt>Start date</dt>
              <dd>{program.start_date ? formatDate(program.start_date) : "—"}</dd>
              <dt>End date</dt>
              <dd>{program.end_date ? formatDate(program.end_date) : "—"}</dd>
            </dl>
          </>
        )}
      </section>

      <AssignedExerciseTable
        assignments={assignedExercises}
        catalogExercises={catalogExercises}
        isLoading={isLoadingExercises}
        error={exercisesError}
      />

      {isEditing ? (
        <AssignExerciseForm
          exercises={catalogExercises}
          isLoadingCatalog={isLoadingCatalog}
          isSubmitting={isAssigning}
          error={assignError}
          catalogError={catalogError}
          onSubmit={onAssignExercise}
        />
      ) : null}

      <div className="section-heading section-heading-row">
        <button
          type="button"
          className="secondary-button"
          onClick={() => setShowReports((v) => !v)}
        >
          {showReports ? "Hide Exercise Reports" : "Show Exercise Reports"}
        </button>
        <button
          type="button"
          className="v0-outline-button"
          onClick={() => setShowCheckups((v) => !v)}
        >
          {showCheckups ? "Hide Follow-up Check-ups" : "Show Follow-up Check-ups"}
        </button>
      </div>
      {showReports ? (
        <ExerciseReportsPanel programId={program.id} api={api} />
      ) : null}
      {showCheckups ? (
        <FollowupCheckupPanel programId={program.id} api={api} />
      ) : null}
    </article>
  );
}

function ProgramEditForm({
  program,
  isSubmitting,
  error,
  doctors,
  isLoadingDoctors,
  doctorsError,
  onSubmit,
}: {
  program: ProgramOut;
  isSubmitting: boolean;
  error?: unknown;
  doctors: DoctorOut[];
  isLoadingDoctors: boolean;
  doctorsError?: unknown;
  onSubmit: (values: ProgramPatchIn) => void;
}) {
  const [name, setName] = useState(program.name ?? "");
  const [estado, setEstado] = useState(program.estado ?? "active");
  const [physiotherapistId, setPhysiotherapistId] = useState(program.physiotherapist_id ?? "");
  const [isDoctorListOpen, setIsDoctorListOpen] = useState(false);
  const [localError, setLocalError] = useState<string>();
  const [startDate, setStartDate] = useState(toInputDate(program.start_date));
  const [endDate, setEndDate] = useState(toInputDate(program.end_date));

  const trimmedPhysiotherapistId = physiotherapistId.trim();
  const physiotherapistError = getPhysiotherapistIdError(trimmedPhysiotherapistId);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (physiotherapistError) {
      setLocalError(physiotherapistError);
      return;
    }
    setLocalError(undefined);
    onSubmit({
      name: name.trim() || null,
      estado,
      physiotherapist_id: trimmedPhysiotherapistId || null,
      start_date: toApiDate(startDate),
      end_date: toApiDate(endDate),
    });
  }

  return (
    <form className="program-edit-form" aria-label="Edit program form" onSubmit={handleSubmit}>
      <div className="card-header">
        <p className="eyebrow">Program setup</p>
        <h3 className="card-title">Edit program</h3>
        <p className="card-description">Update the rehabilitation plan metadata for this diagnostic.</p>
      </div>

      <label className="field">
        <span>Program name</span>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="e.g. Mobility and speech rehabilitation"
          disabled={isSubmitting}
        />
      </label>

      <label className="field">
        <span>Linked diagnostic</span>
        <input value={program.diagnostic_id} disabled readOnly />
      </label>

      <label className="field">
        <span>Physiotherapist</span>
        <input
          value={physiotherapistId}
          onChange={(event) => {
            setPhysiotherapistId(event.target.value);
            setLocalError(undefined);
          }}
          placeholder="Physiotherapist UUID"
          disabled={isSubmitting}
          aria-invalid={Boolean(physiotherapistError)}
        />
      </label>
      <button
        type="button"
        className="assign-physio-link"
        onClick={() => setIsDoctorListOpen((open) => !open)}
      >
        Assign from doctor list
      </button>
      {isDoctorListOpen ? (
        <DoctorPicker
          doctors={doctors}
          isLoading={isLoadingDoctors}
          error={doctorsError}
          selectedDoctorId={physiotherapistId}
          onSelect={(doctorId) => {
            setPhysiotherapistId(doctorId);
            setLocalError(undefined);
            setIsDoctorListOpen(false);
          }}
        />
      ) : null}
      {physiotherapistError ? <p className="form-help" role="alert">{physiotherapistError}</p> : null}

      <label className="field">
        <span>Status</span>
        <select value={estado} onChange={(event) => setEstado(event.target.value)} disabled={isSubmitting}>
          <option value="active">Active</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </label>

      <div className="form-grid-2">
        <label className="field">
          <span>Start date</span>
          <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} disabled={isSubmitting} />
        </label>
        <label className="field">
          <span>End date</span>
          <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} disabled={isSubmitting} />
        </label>
      </div>

      {localError ? <p role="alert">{localError}</p> : null}
      {error ? <p role="alert">{formatProgramUpdateError(error)}</p> : null}

      <div className="form-actions diagnostic-form-actions-v0">
        <button type="submit" className="v0-outline-button" disabled={isSubmitting || Boolean(physiotherapistError)}>
          <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z" />
            <path d="M17 21v-8H7v8" />
            <path d="M7 3v5h8" />
          </svg>
          {isSubmitting ? "Saving…" : "Save draft"}
        </button>
        <button type="submit" className="v0-primary-button" disabled={isSubmitting || Boolean(physiotherapistError)}>
          <svg viewBox="0 0 24 24" focusable="false" aria-hidden="true">
            <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
            <path d="m9 11 3 3L22 4" />
          </svg>
          {isSubmitting ? "Saving…" : "Sign & save"}
        </button>
      </div>
    </form>
  );
}

function DoctorPicker({
  doctors,
  isLoading,
  error,
  selectedDoctorId,
  onSelect,
}: {
  doctors: DoctorOut[];
  isLoading: boolean;
  error?: unknown;
  selectedDoctorId?: string;
  onSelect: (doctorId: string) => void;
}) {
  if (isLoading) {
    return <p className="state-card compact" role="status">Loading doctors…</p>;
  }

  if (error) {
    return <p className="state-card compact" role="alert">Unable to load doctors.</p>;
  }

  if (doctors.length === 0) {
    return <p className="state-card compact">No doctors available.</p>;
  }

  return (
    <div className="doctor-picker" aria-label="Doctor list">
      {doctors.map((doctor) => (
        <button
          key={doctor.id}
          type="button"
          className={doctor.id === selectedDoctorId ? "doctor-picker-item selected" : "doctor-picker-item"}
          onClick={() => onSelect(doctor.id)}
        >
          <span>
            Dr. {doctor.nombre} {doctor.apellidos}
          </span>
          <small>{doctor.doctor_type}{doctor.colegiado_id ? ` · ${doctor.colegiado_id}` : ""}</small>
        </button>
      ))}
    </div>
  );
}

function AssignedExerciseTable({
  assignments,
  catalogExercises,
  isLoading,
  error,
}: {
  assignments: ProgramExerciseOut[];
  catalogExercises: RehabExerciseOut[];
  isLoading: boolean;
  error?: unknown;
}) {
  const exerciseById = new Map(catalogExercises.map((exercise) => [exercise.id, exercise]));

  if (isLoading) {
    return (
      <p className="state-card compact" role="status">
        Loading assigned exercises…
      </p>
    );
  }

  if (error instanceof ApiError && error.status === 403) {
    return (
      <p className="state-card compact" role="alert">
        You are not authorized to view this program's exercises.
      </p>
    );
  }

  if (error instanceof ApiError && error.status === 404) {
    return (
      <p className="state-card compact" role="alert">
        Rehab program exercises not found.
      </p>
    );
  }

  if (error) {
    return (
      <p className="state-card compact" role="alert">
        Unable to load assigned exercises.
      </p>
    );
  }

  return (
    <div className="exercise-table-card">
      <div className="exercise-table-header">
        <h4>Exercise table</h4>
        <span className="status-badge">{formatExerciseCount(assignments.length)}</span>
      </div>
      {assignments.length === 0 ? (
        <p className="exercise-table-empty">No exercises assigned yet.</p>
      ) : (
        <div className="table-scroll" aria-label="Assigned exercises">
          <table className="exercise-table">
            <thead>
              <tr>
                <th scope="col">Exercise</th>
                <th scope="col">Pauta</th>
                <th scope="col">Status</th>
                <th scope="col">Assigned</th>
              </tr>
            </thead>
            <tbody>
              {assignments.map((assignment) => {
                const exercise = exerciseById.get(assignment.exercise_id);
                return (
                  <tr key={assignment.id}>
                    <td>
                      <strong>{exercise?.nombre ?? assignment.exercise_id}</strong>
                      {exercise?.tipo ? <span className="muted-cell">{exercise.tipo}</span> : null}
                    </td>
                    <td>{assignment.pauta || "—"}</td>
                    <td>{assignment.estado ? formatStatus(assignment.estado) : "—"}</td>
                    <td>{assignment.created_at ? formatDate(assignment.created_at) : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function formatExerciseCount(count: number) {
  return count === 1 ? "1 exercise" : `${count} exercises`;
}

function toInputDate(value?: string | null) {
  if (!value) {
    return "";
  }
  return value.slice(0, 10);
}

function toApiDate(value: string) {
  return value ? `${value}T00:00:00Z` : null;
}

function getPhysiotherapistIdError(value: string) {
  if (!value || isUuid(value)) {
    return undefined;
  }
  return "Physiotherapist must be a valid UUID. Leave it empty if not assigned.";
}

function isUuid(value: string) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
}

function formatProgramUpdateError(error: unknown) {
  if (error instanceof ApiError && error.status === 422) {
    return "Review the program fields. Dates and physiotherapist must use valid API values.";
  }
  if (error instanceof ApiError && error.status === 403) {
    return "You are not authorized to edit this program.";
  }
  if (error instanceof ApiError && error.status === 404) {
    return "Rehab program not found.";
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unable to save rehab program.";
}

function formatStatus(value: string) {
  const labels: Record<string, string> = {
    active: "Active",
    activo: "Active",
    completed: "Completed",
    cancelled: "Cancelled",
  };
  return labels[value] ?? value;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}
