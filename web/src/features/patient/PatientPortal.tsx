import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import type { PatientPortalApi } from "../../api/patientPortal";

export function PatientPortal({ api }: { api: PatientPortalApi }) {
  const [selectedProgramId, setSelectedProgramId] = useState<string>();
  const patientQuery = useQuery({ queryKey: ["patient-portal", "me"], queryFn: () => api.getMyPatient() });
  const diagnosticsQuery = useQuery({ queryKey: ["patient-portal", "diagnostics"], queryFn: () => api.listMyDiagnostics() });
  const programsQuery = useQuery({ queryKey: ["patient-portal", "programs"], queryFn: () => api.listMyPrograms() });
  const programDetailQuery = useQuery({
    queryKey: ["patient-portal", "program", selectedProgramId],
    queryFn: () => api.getMyProgram(selectedProgramId ?? ""),
    enabled: Boolean(selectedProgramId),
  });
  const programExercisesQuery = useQuery({
    queryKey: ["patient-portal", "program-exercises", selectedProgramId],
    queryFn: () => api.listMyProgramExercises(selectedProgramId ?? ""),
    enabled: Boolean(selectedProgramId),
  });

  if (patientQuery.isLoading) {
    return <p className="state-card" role="status">Loading patient portal…</p>;
  }

  if (patientQuery.error) {
    return <p className="state-card" role="alert">Unable to load your patient profile.</p>;
  }

  const patient = patientQuery.data;
  const diagnostics = diagnosticsQuery.data?.items ?? [];
  const programs = programsQuery.data?.items ?? [];
  const selectedProgram = programDetailQuery.data ?? programs.find((program) => program.id === selectedProgramId);
  const exercises = programExercisesQuery.data?.items ?? [];

  return (
    <section className="patient-portal" aria-label="Patient portal">
      <section className="patient-record-card patient-portal-hero" aria-label="Patient summary">
        <div className="patient-identity">
          <span className="patient-avatar" aria-hidden="true">
            {getInitials(`${patient?.nombre ?? ""} ${patient?.apellidos ?? ""}`)}
          </span>
          <div>
            <p className="eyebrow">Patient view</p>
            <h1>{patient ? `${patient.nombre} ${patient.apellidos}` : "Patient"}</h1>
            <p className="patient-id">Your rehabilitation follow-up workspace.</p>
          </div>
        </div>
      </section>

      <section className="detail-card" aria-label="My diagnostic history">
        <div className="section-heading section-heading-row">
          <div>
            <h3>Diagnostic history</h3>
            <p>Read-only diagnostics shared with your patient account.</p>
          </div>
          <span className="status-badge">{diagnostics.length} diagnostics</span>
        </div>
        {diagnosticsQuery.isLoading ? <p className="state-card compact" role="status">Loading diagnostics…</p> : null}
        {diagnostics.length === 0 && !diagnosticsQuery.isLoading ? <p className="state-card compact">No diagnostics available yet.</p> : null}
        <div className="diagnostic-card-list">
          {diagnostics.map((diagnostic) => (
            <article key={diagnostic.id} className="diagnostic-record-card">
              <div className="diagnostic-card-head">
                <strong>{diagnostic.dolencia}</strong>
                <span className={diagnostic.signed_at ? "status-badge status-signed" : "status-badge"}>
                  {diagnostic.signed_at ? "Signed" : "Draft"}
                </span>
              </div>
              <p>{diagnostic.descripcion || "No description documented."}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="detail-card" aria-label="My rehabilitation programs">
        <div className="section-heading section-heading-row">
          <div>
            <h3>Rehabilitation programs</h3>
            <p>Programs linked to your diagnostics.</p>
          </div>
          <span className="status-badge">{programs.length} programs</span>
        </div>
        {programsQuery.isLoading ? <p className="state-card compact" role="status">Loading programs…</p> : null}
        {programs.length === 0 && !programsQuery.isLoading ? <p className="state-card compact">No rehabilitation programs available yet.</p> : null}
        <div className="rehab-program-list">
          {programs.map((program) => (
            <article key={program.id} className={program.id === selectedProgramId ? "rehab-program-card selected" : "rehab-program-card"}>
              <button
                type="button"
                className="diagnostic-title-button"
                aria-pressed={program.id === selectedProgramId}
                onClick={() => setSelectedProgramId(program.id)}
              >
                {program.name || "Untitled rehab program"}
              </button>
              <p className="muted-cell">Linked diagnostic {program.diagnostic_id}</p>
              <span className="status-badge">{program.estado}</span>
            </article>
          ))}
        </div>
      </section>

      {selectedProgramId ? (
        <section className="detail-card patient-program-detail" aria-label="Selected rehabilitation program">
          {programDetailQuery.isLoading ? <p className="state-card compact" role="status">Loading rehabilitation program…</p> : null}
          {programDetailQuery.error ? <p className="state-card compact" role="alert">Unable to load this rehabilitation program.</p> : null}
          {selectedProgram ? (
            <>
              <div className="section-heading section-heading-row">
                <div>
                  <h3>{selectedProgram.name || "Untitled rehab program"}</h3>
                  <p>Linked diagnostic {selectedProgram.diagnostic_id}</p>
                </div>
                <span className="status-badge">{selectedProgram.estado}</span>
              </div>
              <dl>
                <dt>Start date</dt>
                <dd>{selectedProgram.start_date ? formatDate(selectedProgram.start_date) : "—"}</dd>
                <dt>End date</dt>
                <dd>{selectedProgram.end_date ? formatDate(selectedProgram.end_date) : "—"}</dd>
                <dt>Physiotherapist</dt>
                <dd>{selectedProgram.physiotherapist_id || "Not assigned"}</dd>
              </dl>
              <div className="exercise-table-card">
                <div className="exercise-table-header">
                  <h4>Exercise table</h4>
                  <span className="status-badge">{exercises.length === 1 ? "1 exercise" : `${exercises.length} exercises`}</span>
                </div>
                {programExercisesQuery.isLoading ? <p className="state-card compact" role="status">Loading exercises…</p> : null}
                {exercises.length === 0 && !programExercisesQuery.isLoading ? <p className="exercise-table-empty">No exercises assigned yet.</p> : null}
                {exercises.length > 0 ? (
                  <div className="table-scroll" aria-label="Patient program exercises">
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
                        {exercises.map((exercise) => (
                          <tr key={exercise.id}>
                            <td>{exercise.exercise_id}</td>
                            <td>{exercise.pauta || "—"}</td>
                            <td>{exercise.estado || "—"}</td>
                            <td>{exercise.created_at ? formatDate(exercise.created_at) : "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
              </div>
            </>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}

function getInitials(label: string) {
  return label
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase())
    .slice(0, 2)
    .join("") || "P";
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(date);
}
