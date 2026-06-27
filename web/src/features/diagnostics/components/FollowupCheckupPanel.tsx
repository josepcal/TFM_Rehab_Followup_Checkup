import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import type { CheckupListItem } from "../../../api/followupCheckups";
import type { DiagnosticFeatureApi } from "../api";
import {
  useCheckupDetail,
  useCreateCheckup,
  useProgramCheckups,
  useProgramReports,
} from "../hooks";

type Props = {
  api: DiagnosticFeatureApi;
  programId: string;
};

export function FollowupCheckupPanel({ api, programId }: Props) {
  const checkupsQuery = useProgramCheckups(api, programId);
  const reportsQuery = useProgramReports(api, programId);
  const createCheckup = useCreateCheckup(api, programId);
  const queryClient = useQueryClient();

  const [showCreateForm, setShowCreateForm] = useState(false);
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [selectedReportIds, setSelectedReportIds] = useState<string[]>([]);
  const [summary, setSummary] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const [editingCheckupId, setEditingCheckupId] = useState<string | null>(null);
  const [editingSummary, setEditingSummary] = useState("");
  const [expandedCheckupId, setExpandedCheckupId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const checkups = checkupsQuery.data ?? [];
  const availableReports = reportsQuery.data ?? [];

  function getAutoSelectedIds(start: string, end: string): string[] {
    if (!start || !end) return [];
    return availableReports
      .filter((r) => r.period_start <= end && r.period_end >= start)
      .map((r) => r.exercise_report_id);
  }

  function handlePeriodStartChange(value: string) {
    setPeriodStart(value);
    setSelectedReportIds(getAutoSelectedIds(value, periodEnd));
  }

  function handlePeriodEndChange(value: string) {
    setPeriodEnd(value);
    setSelectedReportIds(getAutoSelectedIds(periodStart, value));
  }

  function toggleReport(reportId: string) {
    setSelectedReportIds((prev) =>
      prev.includes(reportId) ? prev.filter((id) => id !== reportId) : [...prev, reportId],
    );
  }

  function handleCancelForm() {
    setShowCreateForm(false);
    setPeriodStart("");
    setPeriodEnd("");
    setSelectedReportIds([]);
    setSummary("");
    setFormError(null);
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);

    if (!periodStart || !periodEnd) {
      setFormError("Please fill in both period dates.");
      return;
    }
    if (periodEnd < periodStart) {
      setFormError("End date must be on or after start date.");
      return;
    }
    if (selectedReportIds.length === 0) {
      setFormError("Select at least one report.");
      return;
    }

    createCheckup.mutate(
      {
        rehab_program_id: programId,
        exercise_report_ids: selectedReportIds,
        period_start: periodStart,
        period_end: periodEnd,
        summary: summary || null,
      },
      {
        onSuccess: () => {
          handleCancelForm();
        },
        onError: (err) => {
          setFormError(err instanceof Error ? err.message : "Failed to create check-up.");
        },
      },
    );
  }

  async function handleDelete(checkupId: string) {
    if (!window.confirm("Delete this check-up? This cannot be undone.")) return;
    setDeleteError(null);
    try {
      await api.deleteCheckup(checkupId);
      queryClient.invalidateQueries({ queryKey: ["followup-checkups", programId] });
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete check-up.");
    }
  }

  return (
    <div className="rehab-program-panel">
      <div className="section-heading section-heading-row">
        <h3 style={{ display: "flex", alignItems: "center", gap: "0.5rem", margin: 0 }}>
          <CalendarIcon />
          Follow-up Check-ups
        </h3>
        {!showCreateForm ? (
          <button
            type="button"
            className="v0-outline-button"
            onClick={() => setShowCreateForm(true)}
          >
            <PlusIcon />
            New Check-up
          </button>
        ) : null}
      </div>

      {showCreateForm ? (
        <form className="detail-card" onSubmit={handleSubmit} aria-label="Create check-up form">
          <div className="card-header">
            <h4 className="card-title">New Follow-up Check-up</h4>
          </div>

          <div className="form-grid-2">
            <label className="field">
              <span>Period start</span>
              <input
                type="date"
                value={periodStart}
                onChange={(e) => handlePeriodStartChange(e.target.value)}
                disabled={createCheckup.isPending}
              />
            </label>
            <label className="field">
              <span>Period end</span>
              <input
                type="date"
                value={periodEnd}
                onChange={(e) => handlePeriodEndChange(e.target.value)}
                disabled={createCheckup.isPending}
              />
            </label>
          </div>

          <fieldset style={{ border: "1px solid oklch(0.88 0.01 240)", borderRadius: "0.5rem", padding: "0.75rem" }}>
            <legend style={{ fontSize: "0.875rem", fontWeight: 500, padding: "0 0.25rem" }}>
              Reports to include
            </legend>
            {availableReports.length === 0 ? (
              <p style={{ margin: 0, fontSize: "0.875rem", color: "oklch(0.52 0.015 240)" }}>
                No reports available for this program.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", maxHeight: "12rem", overflowY: "auto" }}>
                {availableReports.map((report) => (
                  <label
                    key={report.exercise_report_id}
                    style={{ display: "flex", alignItems: "center", gap: "0.625rem", cursor: "pointer", fontSize: "0.875rem" }}
                  >
                    <input
                      type="checkbox"
                      checked={selectedReportIds.includes(report.exercise_report_id)}
                      onChange={() => toggleReport(report.exercise_report_id)}
                      disabled={createCheckup.isPending}
                    />
                    <span>
                      {formatDate(report.period_start)} – {formatDate(report.period_end)}
                      <span className="muted-cell" style={{ marginLeft: "0.5rem" }}>
                        {report.recording_count} recording{report.recording_count === 1 ? "" : "s"}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            )}
            {selectedReportIds.length > 0 ? (
              <p style={{ margin: "0.5rem 0 0", fontSize: "0.75rem", color: "oklch(0.52 0.015 240)" }}>
                {selectedReportIds.length} report{selectedReportIds.length === 1 ? "" : "s"} selected
              </p>
            ) : null}
          </fieldset>

          <label className="field">
            <span>Summary (optional)</span>
            <textarea
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              rows={3}
              disabled={createCheckup.isPending}
            />
          </label>

          {formError ? (
            <p role="alert" className="form-help">
              {formError}
            </p>
          ) : null}

          <div className="form-actions diagnostic-form-actions-v0">
            <button
              type="button"
              className="ghost-button v0-program-action"
              onClick={handleCancelForm}
              disabled={createCheckup.isPending}
            >
              Cancel
            </button>
            <button type="submit" className="v0-outline-button" disabled={createCheckup.isPending}>
              <PlusIcon />
              {createCheckup.isPending ? "Creating…" : "Create Check-up"}
            </button>
          </div>
        </form>
      ) : null}

      {checkupsQuery.isLoading ? (
        <p className="state-card" role="status">
          Loading check-ups…
        </p>
      ) : checkupsQuery.error ? (
        <p className="state-card" role="alert">
          Unable to load follow-up check-ups.
        </p>
      ) : checkups.length === 0 ? (
        <p className="state-card">No follow-up check-ups yet.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {deleteError ? (
            <p role="alert" className="state-card">
              {deleteError}
            </p>
          ) : null}
          {checkups.map((checkup) => (
            <CheckupCard
              key={checkup.followup_checkup_id}
              checkup={checkup}
              api={api}
              programId={programId}
              editingCheckupId={editingCheckupId}
              editingSummary={editingSummary}
              expandedCheckupId={expandedCheckupId}
              saveError={saveError}
              onStartEdit={(id, current) => {
                setEditingCheckupId(id);
                setEditingSummary(current);
              }}
              onSaveEdit={async (id, value) => {
                setSaveError(null);
                try {
                  await api.updateCheckup(id, value);
                  queryClient.invalidateQueries({ queryKey: ["followup-checkups", programId] });
                  setEditingCheckupId(null);
                } catch (err) {
                  setSaveError(err instanceof Error ? err.message : "Failed to save summary.");
                }
              }}
              onCancelEdit={() => setEditingCheckupId(null)}
              onEditingSummaryChange={setEditingSummary}
              onToggleExpand={(id) =>
                setExpandedCheckupId((prev) => (prev === id ? null : id))
              }
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}

type CheckupCardProps = {
  checkup: CheckupListItem;
  api: DiagnosticFeatureApi;
  programId: string;
  editingCheckupId: string | null;
  editingSummary: string;
  expandedCheckupId: string | null;
  saveError: string | null;
  onStartEdit: (id: string, current: string) => void;
  onSaveEdit: (id: string, value: string) => Promise<void>;
  onCancelEdit: () => void;
  onEditingSummaryChange: (value: string) => void;
  onToggleExpand: (id: string) => void;
  onDelete: (id: string) => void;
};

function CheckupCard({
  checkup,
  api,
  editingCheckupId,
  editingSummary,
  expandedCheckupId,
  saveError,
  onStartEdit,
  onSaveEdit,
  onCancelEdit,
  onEditingSummaryChange,
  onToggleExpand,
  onDelete,
}: CheckupCardProps) {
  const id = checkup.followup_checkup_id;
  const isEditing = editingCheckupId === id;
  const isExpanded = expandedCheckupId === id;
  const displaySummary = checkup.summary ?? "—";
  const currentForEdit = checkup.summary ?? "";

  return (
    <article className="detail-card">
      <div className="exercise-table-header">
        <h4 style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
          <CalendarIcon size="small" />
          {formatDate(checkup.period_start)} – {formatDate(checkup.period_end)}
        </h4>
        <span className="status-badge">
          {checkup.report_count} report{checkup.report_count === 1 ? "" : "s"}
        </span>
      </div>

      {isEditing ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
          <textarea
            value={editingSummary}
            onChange={(e) => onEditingSummaryChange(e.target.value)}
            rows={3}
            style={{ width: "100%", boxSizing: "border-box" }}
          />
          {saveError && editingCheckupId === id ? (
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
          <p style={{ margin: 0, fontSize: "0.875rem", color: "oklch(0.24 0.02 240)" }}>
            {displaySummary}
          </p>
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
          {isExpanded ? "Hide Reports" : "Show Reports"}
        </button>

        <button
          type="button"
          className="v0-outline-button"
          style={{ color: "#b42318", borderColor: "#fecdca" }}
          onClick={() => onDelete(id)}
        >
          <TrashIcon />
          Delete
        </button>
      </div>

      {isExpanded ? (
        <CheckupDetailSection api={api} checkupId={id} />
      ) : null}
    </article>
  );
}

function CheckupDetailSection({
  api,
  checkupId,
}: {
  api: DiagnosticFeatureApi;
  checkupId: string;
}) {
  const detailQuery = useCheckupDetail(api, checkupId);

  if (detailQuery.isLoading) {
    return (
      <p className="state-card compact" role="status">
        Loading reports…
      </p>
    );
  }

  if (detailQuery.error) {
    return (
      <p className="state-card compact" role="alert">
        Unable to load check-up details.
      </p>
    );
  }

  const detail = detailQuery.data;
  if (!detail) return null;

  return (
    <div className="exercise-table-card">
      <div className="exercise-table-header">
        <h4>Included Reports</h4>
        <span className="status-badge">{detail.reports.length} linked</span>
      </div>
      <div className="table-scroll">
        <table className="exercise-table">
          <thead>
            <tr>
              <th scope="col">Period start</th>
              <th scope="col">Period end</th>
              <th scope="col">Summary</th>
            </tr>
          </thead>
          <tbody>
            {detail.reports.map((rep) => (
              <tr key={rep.exercise_report_id}>
                <td>{formatDate(rep.period_start)}</td>
                <td>{formatDate(rep.period_end)}</td>
                <td className="muted-cell">
                  {rep.summary
                    ? rep.summary.slice(0, 60) + (rep.summary.length > 60 ? "…" : "")
                    : "—"}
                </td>
              </tr>
            ))}
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
