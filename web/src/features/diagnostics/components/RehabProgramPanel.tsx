import { ApiError } from "../../../api/http";
import type { ProgramOut } from "../../../api/programs";
import type { DiagnosticFeatureApi } from "../api";
import { useProgramDetail, usePrograms } from "../hooks";

type RehabProgramPanelProps = {
  api: DiagnosticFeatureApi;
  diagnosticId?: string;
  patientId?: string;
  selectedProgramId?: string;
  title?: string;
  description?: string;
  onSelectProgram: (programId: string) => void;
  onCreateProgram?: () => void;
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
}: RehabProgramPanelProps) {
  const programsQuery = usePrograms(api, { diagnosticId, patientId });
  const programs = programsQuery.data?.items ?? [];
  const detailQuery = useProgramDetail(api, selectedProgramId);
  const selectedProgram = detailQuery.data ?? programs.find((program) => program.id === selectedProgramId);

  return (
    <section className="rehab-program-panel" aria-label={title}>
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

      <ProgramListState
        programs={programs}
        isLoading={programsQuery.isLoading}
        error={programsQuery.error}
        selectedProgramId={selectedProgramId}
        onSelectProgram={onSelectProgram}
      />

      {selectedProgramId ? (
        <ProgramDetailState
          program={selectedProgram}
          isLoading={detailQuery.isLoading}
          error={detailQuery.error}
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
          <p className="muted-cell">Diagnostic {program.diagnostic_id}</p>
          <span className="status-badge">{formatStatus(program.estado)}</span>
        </article>
      ))}
    </div>
  );
}

function ProgramDetailState({
  program,
  isLoading,
  error,
}: {
  program?: ProgramOut;
  isLoading: boolean;
  error?: unknown;
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

  return (
    <article className="detail-card rehab-program-detail" aria-label="Rehab program detail">
      <div className="card-header">
        <p className="eyebrow">Rehab program</p>
        <h3 className="card-title">{program.name || "Untitled rehab program"}</h3>
      </div>
      <dl>
        <dt>Status</dt>
        <dd>{formatStatus(program.estado)}</dd>
        <dt>Diagnostic</dt>
        <dd>{program.diagnostic_id}</dd>
        <dt>Start date</dt>
        <dd>{program.start_date ? formatDate(program.start_date) : "—"}</dd>
        <dt>End date</dt>
        <dd>{program.end_date ? formatDate(program.end_date) : "—"}</dd>
        <dt>Exercise table</dt>
        <dd>Exercise assignment is available from the next UC-02 slice.</dd>
      </dl>
    </article>
  );
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
