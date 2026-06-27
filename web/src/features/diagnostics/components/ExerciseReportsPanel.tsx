import { useState } from "react";

import type { ReportListItem } from "../../../api/reports";
import type { DiagnosticFeatureApi } from "../api";
import {
  useCreateReport,
  useProgramExercises,
  useProgramReports,
  useReportDetail,
} from "../hooks";

type Props = {
  api: DiagnosticFeatureApi;
  programId: string;
};

export function ExerciseReportsPanel({ api, programId }: Props) {
  const reportsQuery = useProgramReports(api, programId);
  const exercisesQuery = useProgramExercises(api, programId);
  const createReport = useCreateReport(api, programId);

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [selectedProgramExerciseId, setSelectedProgramExerciseId] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [summary, setSummary] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const [editingReportId, setEditingReportId] = useState<string | null>(null);
  const [editingSummary, setEditingSummary] = useState("");

  const [expandedReportId, setExpandedReportId] = useState<string | null>(null);
  const [localSummaries, setLocalSummaries] = useState<Record<string, string>>({});

  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const reports = reportsQuery.data ?? [];
  const exercises = exercisesQuery.data?.items ?? [];

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);

    if (!selectedProgramExerciseId) {
      setFormError("Please select an exercise.");
      return;
    }
    if (!periodStart || !periodEnd) {
      setFormError("Please fill in both period dates.");
      return;
    }
    if (periodEnd < periodStart) {
      setFormError("End date must be on or after start date.");
      return;
    }

    const recordings = await api.listExerciseRecordings(selectedProgramExerciseId);
    if (recordings.length === 0) {
      setFormError("No recordings found for this exercise.");
      return;
    }

    createReport.mutate(
      {
        program_exercise_id: selectedProgramExerciseId,
        recording_ids: recordings.map((r) => r.recording_id),
        period_start: periodStart,
        period_end: periodEnd,
        summary: summary || null,
      },
      {
        onSuccess: () => {
          setShowCreateForm(false);
          setSelectedProgramExerciseId("");
          setPeriodStart("");
          setPeriodEnd("");
          setSummary("");
          setFormError(null);
        },
        onError: (err) => {
          setFormError(err instanceof Error ? err.message : "Failed to create report.");
        },
      },
    );
  }

  async function handleDelete(reportId: string) {
    if (!window.confirm("Delete this report?")) return;
    setDeleteError(null);
    try {
      await api.deleteReport(reportId);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete report.");
    }
  }

  return (
    <div className="rehab-program-panel">
      <div className="section-heading section-heading-row">
        <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem", margin: 0 }}>
          <CalendarIcon />
          Exercise Reports
        </h3>
        {!showCreateForm ? (
          <button
            type="button"
            className="v0-outline-button"
            onClick={() => setShowCreateForm(true)}
          >
            <PlusIcon />
            New Report
          </button>
        ) : null}
      </div>

      {showCreateForm ? (
        <form className="detail-card" onSubmit={handleSubmit} aria-label="Create report form">
          <div className="card-header">
            <h4 className="card-title">New Exercise Report</h4>
          </div>

          <label className="field">
            <span>Exercise</span>
            <select
              value={selectedProgramExerciseId}
              onChange={(e) => setSelectedProgramExerciseId(e.target.value)}
              disabled={createReport.isPending}
            >
              <option value="">— select an exercise —</option>
              {exercises.map((ex) => (
                <option key={ex.id} value={ex.id}>
                  {ex.exercise_description ?? ex.exercise_id ?? ex.id}
                </option>
              ))}
            </select>
          </label>

          <div className="form-grid-2">
            <label className="field">
              <span>Period start</span>
              <input
                type="date"
                value={periodStart}
                onChange={(e) => setPeriodStart(e.target.value)}
                disabled={createReport.isPending}
              />
            </label>
            <label className="field">
              <span>Period end</span>
              <input
                type="date"
                value={periodEnd}
                onChange={(e) => setPeriodEnd(e.target.value)}
                disabled={createReport.isPending}
              />
            </label>
          </div>

          <label className="field">
            <span>Summary (optional)</span>
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={3}
              disabled={createReport.isPending}
            />
          </label>

          {formError ? (
            <p role="alert" className="form-help">
              {formError}
            </p>
          ) : null}

          <div className="form-actions diagnostic-form-actions-v0">
            <button type="button" className="ghost-button v0-program-action" onClick={() => { setShowCreateForm(false); setFormError(null); }} disabled={createReport.isPending}>
              Cancel
            </button>
            <button type="submit" className="v0-outline-button" disabled={createReport.isPending}>
              <PlusIcon />
              {createReport.isPending ? "Creating…" : "Create Report"}
            </button>
          </div>
        </form>
      ) : null}

      {reportsQuery.isLoading ? (
        <p className="state-card" role="status">
          Loading reports…
        </p>
      ) : reportsQuery.error ? (
        <p className="state-card" role="alert">
          Unable to load exercise reports.
        </p>
      ) : reports.length === 0 ? (
        <p className="state-card">No exercise reports yet.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {deleteError ? (
            <p role="alert" className="state-card">
              {deleteError}
            </p>
          ) : null}
          {reports.map((report) => (
            <ReportCard
              key={report.exercise_report_id}
              report={report}
              api={api}
              editingReportId={editingReportId}
              editingSummary={editingSummary}
              expandedReportId={expandedReportId}
              localSummaries={localSummaries}
              onStartEdit={(id, current) => {
                setEditingReportId(id);
                setEditingSummary(current);
              }}
              saveError={saveError}
              onSaveEdit={async (id, value) => {
                setSaveError(null);
                try {
                  await api.updateReport(id, value);
                  setLocalSummaries((prev) => ({ ...prev, [id]: value }));
                  setEditingReportId(null);
                } catch (err) {
                  setSaveError(err instanceof Error ? err.message : "Failed to save summary.");
                }
              }}
              onCancelEdit={() => setEditingReportId(null)}
              onEditingSummaryChange={setEditingSummary}
              onToggleExpand={(id) =>
                setExpandedReportId((prev) => (prev === id ? null : id))
              }
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}

type ReportCardProps = {
  report: ReportListItem;
  api: DiagnosticFeatureApi;
  editingReportId: string | null;
  editingSummary: string;
  expandedReportId: string | null;
  localSummaries: Record<string, string>;
  saveError: string | null;
  onStartEdit: (id: string, current: string) => void;
  onSaveEdit: (id: string, value: string) => Promise<void>;
  onCancelEdit: () => void;
  onEditingSummaryChange: (value: string) => void;
  onToggleExpand: (id: string) => void;
  onDelete: (id: string) => void;
};

function ReportCard({
  report,
  api,
  editingReportId,
  editingSummary,
  expandedReportId,
  localSummaries,
  saveError,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onEditingSummaryChange,
  onToggleExpand,
  onDelete,
}: ReportCardProps) {
  const id = report.exercise_report_id;
  const isEditing = editingReportId === id;
  const isExpanded = expandedReportId === id;
  const displaySummary = localSummaries[id] ?? report.summary ?? "—";
  const currentForEdit = localSummaries[id] ?? report.summary ?? "";

  return (
    <article className="detail-card">
      <div className="exercise-table-header">
        <h4 style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
          <CalendarIcon size="small" />
          {formatDate(report.period_start)} – {formatDate(report.period_end)}
        </h4>
        <span className="status-badge">{report.recording_count} recording{report.recording_count === 1 ? "" : "s"}</span>
      </div>

      <dl style={{ display: "grid", gridTemplateColumns: "max-content 1fr", gap: "0.25rem 0.75rem", margin: 0, fontSize: "0.875rem" }}>
        <dt style={{ color: "oklch(0.52 0.015 240)", fontWeight: 500 }}>Created by</dt>
        <dd style={{ margin: 0, color: "oklch(0.24 0.02 240)" }}>
          {report.created_by_name ?? report.created_by}
        </dd>
        <dt style={{ color: "oklch(0.52 0.015 240)", fontWeight: 500 }}>Exercise</dt>
        <dd style={{ margin: 0, color: "oklch(0.24 0.02 240)" }}>
          {report.exercise_name ?? "—"}
          {report.exercise_id ? (
            <span className="muted-cell" style={{ marginLeft: "0.4rem" }}>({report.exercise_id})</span>
          ) : null}
        </dd>
      </dl>

      {isEditing ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <textarea
            value={editingSummary}
            onChange={(e) => onEditingSummaryChange(e.target.value)}
            rows={3}
            style={{ width: "100%", boxSizing: "border-box" }}
          />
          {saveError && editingReportId === id ? (
            <p role="alert" className="form-help">{saveError}</p>
          ) : null}
          <div className="form-actions diagnostic-form-actions-v0">
            <button type="button" className="ghost-button v0-program-action" onClick={onCancelEdit}>
              Cancel
            </button>
            <button
              type="button"
              className="v0-outline-button"
              onClick={() => onSaveEdit(id, editingSummary)}
            >
              <SaveIcon />
              Save
            </button>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <p style={{ margin: 0, fontSize: "0.875rem", color: "oklch(0.24 0.02 240)" }}>{displaySummary}</p>
          <button
            type="button"
            className="v0-outline-button"
            style={{ alignSelf: "flex-start" }}
            onClick={() => onStartEdit(id, currentForEdit)}
          >
            <EditIcon />
            Edit Summary
          </button>
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
        <button
          type="button"
          className="v0-outline-button"
          onClick={() => onToggleExpand(id)}
        >
          {isExpanded ? <ChevronUpIcon /> : <ChevronDownIcon />}
          {isExpanded ? "Hide Details" : "Show Details"}
        </button>

        <button
          type="button"
          className="v0-outline-button"
          style={{ color: "#b42318", borderColor: "#fecdca" }}
          onClick={() => onDelete(id)}
        >
          <TrashIcon />
          Delete Report
        </button>
      </div>

      {isExpanded ? (
        <ReportDetailSection api={api} reportId={id} />
      ) : null}
    </article>
  );
}

function ReportDetailSection({
  api,
  reportId,
}: {
  api: DiagnosticFeatureApi;
  reportId: string;
}) {
  const detailQuery = useReportDetail(api, reportId);
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);

  if (detailQuery.isLoading) {
    return (
      <p className="state-card compact" role="status">
        Loading details…
      </p>
    );
  }

  if (detailQuery.error) {
    return (
      <p className="state-card compact" role="alert">
        Unable to load report details.
      </p>
    );
  }

  const detail = detailQuery.data;
  if (!detail) return null;

  return (
    <div className="exercise-table-card">
      <div className="exercise-table-header">
        <h4>Recordings</h4>
        <span className="status-badge">{detail.recordings.length} linked</span>
      </div>
      <div className="table-scroll">
        <table className="exercise-table">
          <thead>
            <tr>
              <th scope="col">Recording date</th>
              <th scope="col">Duration</th>
              <th scope="col">Media status</th>
              <th scope="col">Insight</th>
              <th scope="col"></th>
            </tr>
          </thead>
          <tbody>
            {detail.recordings.map((rec) => {
              const isRowExpanded = expandedRowId === rec.recording_id;
              return (
                <>
                  <tr key={rec.recording_id}>
                    <td>{formatDate(rec.recording_date)}</td>
                    <td>{rec.duration_seconds != null ? `${rec.duration_seconds}s` : "—"}</td>
                    <td>{rec.media_status ?? "—"}</td>
                    <td className="muted-cell">
                      {rec.insight_text
                        ? rec.insight_text.slice(0, 60) + (rec.insight_text.length > 60 ? "…" : "")
                        : "—"}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="v0-outline-button"
                        onClick={() =>
                          setExpandedRowId((prev) =>
                            prev === rec.recording_id ? null : rec.recording_id,
                          )
                        }
                      >
                        {isRowExpanded ? <ChevronUpIcon /> : <PlayIcon />}
                        {isRowExpanded ? "Hide" : "View"}
                      </button>
                    </td>
                  </tr>
                  {isRowExpanded ? (
                    <tr key={`${rec.recording_id}-detail`}>
                      <td colSpan={5} style={{ background: "oklch(0.98 0.004 220)", padding: "1rem" }}>
                        {rec.insight_text ? (
                          <p style={{ margin: "0 0 0.75rem", fontSize: "0.875rem", color: "oklch(0.24 0.02 240)" }}>
                            {rec.insight_text}
                          </p>
                        ) : (
                          <p className="muted-cell" style={{ margin: "0 0 0.75rem" }}>No insight available.</p>
                        )}
                        {rec.raw_json ? (
                          <pre style={{ fontSize: "0.78rem", overflowX: "auto", margin: 0, color: "oklch(0.32 0.02 240)" }}>
                            {JSON.stringify(rec.raw_json, null, 2)}
                          </pre>
                        ) : (
                          <p className="muted-cell" style={{ margin: 0 }}>No metrics available.</p>
                        )}
                      </td>
                    </tr>
                  ) : null}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatDate(value?: string | null) {
  if (!value) return "—";
  const d = new Date(value);
  if (isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(d);
}

function CalendarIcon({ size }: { size?: "small" }) {
  const dim = size === "small" ? "1rem" : "1.125rem";
  return (
    <svg
      viewBox="0 0 24 24"
      focusable="false"
      aria-hidden="true"
      style={{ fill: "none", height: dim, width: dim, stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, flexShrink: 0 }}
    >
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      focusable="false"
      aria-hidden="true"
      style={{ fill: "none", height: "1rem", width: "1rem", stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, flexShrink: 0 }}
    >
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function EditIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      focusable="false"
      aria-hidden="true"
      style={{ fill: "none", height: "1rem", width: "1rem", stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, flexShrink: 0 }}
    >
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

function SaveIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      focusable="false"
      aria-hidden="true"
      style={{ fill: "none", height: "1rem", width: "1rem", stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, flexShrink: 0 }}
    >
      <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2Z" />
      <path d="M17 21v-8H7v8" />
      <path d="M7 3v5h8" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      focusable="false"
      aria-hidden="true"
      style={{ fill: "none", height: "1rem", width: "1rem", stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, flexShrink: 0 }}
    >
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
      <path d="M10 11v6" />
      <path d="M14 11v6" />
      <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      focusable="false"
      aria-hidden="true"
      style={{ fill: "none", height: "1rem", width: "1rem", stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, flexShrink: 0 }}
    >
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      focusable="false"
      aria-hidden="true"
      style={{ fill: "none", height: "1rem", width: "1rem", stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, flexShrink: 0 }}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function ChevronUpIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      focusable="false"
      aria-hidden="true"
      style={{ fill: "none", height: "1rem", width: "1rem", stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, flexShrink: 0 }}
    >
      <polyline points="18 15 12 9 6 15" />
    </svg>
  );
}
