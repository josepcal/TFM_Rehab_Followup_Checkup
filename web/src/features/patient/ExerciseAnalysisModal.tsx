/**
 * ExerciseAnalysisModal — Exercise Analysis Results dialog
 *
 * Visual design matches the v0 healthcare-ui-design MetricsModal.
 * Adapted for the dysarthria_analysis_v1 metrics returned by the API:
 *   phonation_duration_sec, jitter_local_pct, shimmer_local_pct,
 *   hnr_db, volume_std_db
 *
 * API:
 *   POST /recordings/{id}/run  — trigger analysis
 *   GET  /recordings/{id}/metrics — fetch results (404 = not ready yet)
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { AnalysisApi } from "../../api/recordings";

// ── Types ────────────────────────────────────────────────────────────────────

export type AnalysisState =
  | { phase: "idle" }
  | { phase: "loading" }           // fetching / waiting for worker
  | { phase: "ready"; metrics: Record<string, number>; functionName: string }
  | { phase: "unauthorized" }      // 403 on POST /run
  | { phase: "error"; message: string };

interface Props {
  recordingId: string | null;       // null = closed
  recordingDate?: string | null;
  api: AnalysisApi;
  onClose: () => void;
}

const POLL_INTERVAL_MS = 2500;
const POLL_MAX_ATTEMPTS = 20;       // ~50 s before giving up

// ── Component ────────────────────────────────────────────────────────────────

export function ExerciseAnalysisModal({ recordingId, recordingDate, api, onClose }: Props) {
  const [state, setState] = useState<AnalysisState>({ phase: "idle" });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const attemptsRef = useRef(0);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (id: string) => {
      attemptsRef.current = 0;
      pollRef.current = setInterval(async () => {
        attemptsRef.current += 1;
        if (attemptsRef.current > POLL_MAX_ATTEMPTS) {
          stopPolling();
          setState({ phase: "error", message: "Analysis is taking longer than expected. Try again later." });
          return;
        }
        try {
          const result = await api.getRecordingMetrics(id);
          const handled = applyMetricsResult(result, (nextState) => {
            stopPolling();
            setState(nextState);
          });
          if (handled) return;
        } catch {
          // 404 = still processing, keep polling; other errors fall through to timeout
        }
      }, POLL_INTERVAL_MS);
    },
    [api, stopPolling],
  );

  // When a recordingId appears, start the flow
  useEffect(() => {
    if (!recordingId) {
      stopPolling();
      setState({ phase: "idle" });
      return;
    }

    setState({ phase: "loading" });

    (async () => {
      // 1. Try GET first — metrics may already exist
      try {
        const result = await api.getRecordingMetrics(recordingId);
        if (applyMetricsResult(result, setState)) {
          return;
        }
      } catch {
        // 404 = no metrics yet, fall through to POST /run
      }

      // 2. Trigger analysis
      try {
        await api.runAnalysis(recordingId);
      } catch (err: unknown) {
        const status = (err as { status?: number })?.status;
        if (status === 403) {
          setState({ phase: "unauthorized" });
          return;
        }
        setState({ phase: "error", message: "Failed to start analysis. Please try again." });
        return;
      }

      // 3. Poll until the worker finishes
      startPolling(recordingId);
    })();

    return stopPolling;
  }, [recordingId, api, startPolling, stopPolling]);

  // Close on backdrop click
  function handleBackdropClick(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget) onClose();
  }

  if (!recordingId) return null;

  return (
    <div
      className="metrics-dialog-backdrop"
      role="presentation"
      onClick={handleBackdropClick}
    >
      <section
        className="metrics-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="metrics-dialog-title"
      >
        {/* Header */}
        <div className="metrics-dialog-header">
          <div className="metrics-dialog-title-row">
            <ActivityIcon />
            <h2 id="metrics-dialog-title">Exercise Analysis Results</h2>
          </div>
          {state.phase === "ready" && (
            <p className="metrics-dialog-subtitle">
              Acoustic metrics computed by <code>{state.functionName}</code>
            </p>
          )}
          {recordingDate ? (
            <p className="metrics-dialog-subtitle">
              Recording date: <strong>{formatDisplayDate(recordingDate)}</strong>
            </p>
          ) : null}
          <button
            type="button"
            className="dialog-close-button"
            aria-label="Close analysis dialog"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="metrics-dialog-body">
          {state.phase === "loading" && <LoadingState />}
          {state.phase === "unauthorized" && <UnauthorizedState />}
          {state.phase === "error" && <ErrorState message={state.message} />}
          {state.phase === "ready" && <MetricsContent metrics={state.metrics} />}
        </div>
      </section>
    </div>
  );
}

function applyMetricsResult(
  result: Awaited<ReturnType<AnalysisApi["getRecordingMetrics"]>>,
  setNextState: (state: AnalysisState) => void,
) {
  if (result.status === "error") {
    setNextState({
      phase: "error",
      message: formatAnalysisError(result.error_detail),
    });
    return true;
  }

  if (result.metrics) {
    setNextState({
      phase: "ready",
      metrics: result.metrics,
      functionName: result.function_name ?? "analysis function",
    });
    return true;
  }

  return false;
}

function formatAnalysisError(errorDetail?: string | null) {
  if (!errorDetail) {
    return "Analysis failed. Please try recording again.";
  }

  const message = errorDetail.replace(/^[A-Za-z0-9_]+Error:\s*/, "");
  if (/voiced signal too short/i.test(message)) {
    return `${message}. Try recording a longer sustained vowel.`;
  }
  if (/silence|non-voiced|insufficient signal/i.test(message)) {
    return `${message}. Try again in a quiet place with a clear voice signal.`;
  }
  return message;
}

function formatDisplayDate(value: string) {
  const date = parseDateOnlyAsLocal(value) ?? new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}

function parseDateOnlyAsLocal(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) {
    return null;
  }
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

// ── Inner states ──────────────────────────────────────────────────────────────

function LoadingState() {
  return (
    <div className="metrics-loading-state">
      <div className="metrics-spinner" aria-hidden="true" />
      <p>Analysing your exercise recording…</p>
    </div>
  );
}

function UnauthorizedState() {
  return (
    <div className="metrics-info-state">
      <InfoIcon />
      <p>Analysis for this recording hasn't been run yet.</p>
      <p className="metrics-info-sub">Ask your medical team to trigger the analysis.</p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="metrics-error-state" role="alert">
      <AlertIcon />
      <p>{message}</p>
    </div>
  );
}

// ── Metrics display (matches v0 MetricsModal layout) ─────────────────────────

function MetricsContent({ metrics }: { metrics: Record<string, number> }) {
  const dur   = metrics.phonation_duration_sec ?? null;
  const jitr  = metrics.jitter_local_pct       ?? null;
  const shim  = metrics.shimmer_local_pct      ?? null;
  const hnr   = metrics.hnr_db                 ?? null;
  const vStd  = metrics.volume_std_db          ?? null;

  // Derive a 0–100 quality score from each metric (higher = better)
  const jitterScore  = jitr  != null ? Math.max(0, Math.min(100, 100 - jitr  * 10)) : null;
  const shimmerScore = shim  != null ? Math.max(0, Math.min(100, 100 - shim  * 5))  : null;
  const hnrScore     = hnr   != null ? Math.max(0, Math.min(100, (hnr / 30) * 100)) : null;

  const recommendations = buildRecommendations({ dur, jitr, shim, hnr, vStd });

  return (
    <div className="metrics-content">
      {/* Quick stats grid — mirrors v0's 4-column grid */}
      <div className="metrics-stats-grid">
        <StatCard label="Phonation duration" value={dur != null ? `${dur.toFixed(1)}s` : "—"} />
        <StatCard label="Jitter" value={jitr != null ? `${jitr.toFixed(2)}%` : "—"} />
        <StatCard label="Shimmer" value={shim != null ? `${shim.toFixed(2)}%` : "—"} />
        <StatCard label="HNR" value={hnr  != null ? `${hnr.toFixed(1)} dB` : "—"} />
      </div>

      <div className="metrics-separator" />

      {/* Performance bars — mirrors v0's symmetry/range-of-motion bars */}
      <div className="metrics-performance">
        <h3 className="metrics-section-title">Voice quality metrics</h3>

        <div className="metrics-bars">
          <MetricBar
            icon={<WaveIcon />}
            label="Pitch stability (jitter)"
            score={jitterScore}
            note="Lower jitter = more stable pitch"
          />
          <MetricBar
            icon={<ZapIcon />}
            label="Amplitude stability (shimmer)"
            score={shimmerScore}
            note="Lower shimmer = more stable volume"
          />
          <MetricBar
            icon={<EyeIcon />}
            label="Harmonic-to-noise ratio"
            score={hnrScore}
            note="Higher HNR = cleaner voice signal"
          />
        </div>
      </div>

      {vStd != null && (
        <>
          <div className="metrics-separator" />
          <div className="metrics-volume-row">
            <span className="metrics-volume-label">Volume stability (std dev)</span>
            <span className={`metrics-quality-badge ${vStd < 2 ? "good" : vStd < 5 ? "medium" : "poor"}`}>
              {vStd.toFixed(2)} dB — {vStd < 2 ? "Stable" : vStd < 5 ? "Moderate" : "Variable"}
            </span>
          </div>
        </>
      )}

      <div className="metrics-separator" />

      {/* Recommendations — mirrors v0's TrendingUp + CheckCircle rows */}
      <div className="metrics-recommendations">
        <div className="metrics-rec-title-row">
          <TrendingUpIcon />
          <h3 className="metrics-section-title">Recommendations</h3>
        </div>
        <div className="metrics-rec-list">
          {recommendations.map((rec, i) => (
            <div key={i} className="metrics-rec-item">
              <CheckCircleIcon />
              <p>{rec}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Status footer — mirrors v0's green success banner */}
      <div className="metrics-status-footer">
        <CheckCircleIcon />
        <p>Analysis completed successfully.</p>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="metrics-stat-card">
      <span className="metrics-stat-label">{label}</span>
      <span className="metrics-stat-value">{value}</span>
    </div>
  );
}

function MetricBar({ icon, label, score, note }: {
  icon: React.ReactNode;
  label: string;
  score: number | null;
  note: string;
}) {
  const pct = score ?? 0;
  const colorClass = pct >= 70 ? "good" : pct >= 40 ? "medium" : "poor";

  return (
    <div className="metrics-bar-row">
      <div className="metrics-bar-label-group">
        {icon}
        <div>
          <span className="metrics-bar-label">{label}</span>
          <span className="metrics-bar-note">{note}</span>
        </div>
      </div>
      <div className="metrics-bar-right">
        <div className="metrics-bar-track">
          <div
            className={`metrics-bar-fill ${colorClass}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className={`metrics-bar-pct ${colorClass}`}>
          {score != null ? `${Math.round(pct)}` : "—"}
        </span>
      </div>
    </div>
  );
}

// ── Clinical recommendations ─────────────────────────────────────────────────

function buildRecommendations({
  dur, jitr, shim, hnr, vStd,
}: {
  dur: number | null;
  jitr: number | null;
  shim: number | null;
  hnr: number | null;
  vStd: number | null;
}): string[] {
  const recs: string[] = [];

  if (dur != null && dur < 5)
    recs.push("Try to sustain the vowel for longer. Aim for at least 10 seconds.");
  if (jitr != null && jitr > 2)
    recs.push("Pitch variation (jitter) is elevated. Focus on maintaining a steady tone.");
  if (shim != null && shim > 5)
    recs.push("Amplitude variation (shimmer) is elevated. Try to keep a consistent volume.");
  if (hnr != null && hnr < 10)
    recs.push("Noise in the voice signal is high. Reduce background noise and try again in a quieter environment.");
  if (vStd != null && vStd > 5)
    recs.push("Volume is unstable during the recording. Try to maintain even breath support.");

  if (recs.length === 0)
    recs.push("Great performance! All acoustic metrics are within acceptable ranges. Keep up the work.");

  return recs;
}

// ── Inline SVG icons (mirrors v0's lucide-react icons, no extra dependency) ──

function ActivityIcon() {
  return (
    <svg className="metrics-icon" viewBox="0 0 24 24" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}
function WaveIcon() {
  return (
    <svg className="metrics-icon-sm blue" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2 12h3l3-8 4 16 3-8h3" />
    </svg>
  );
}
function ZapIcon() {
  return (
    <svg className="metrics-icon-sm amber" viewBox="0 0 24 24" aria-hidden="true">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  );
}
function EyeIcon() {
  return (
    <svg className="metrics-icon-sm blue" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}
function TrendingUpIcon() {
  return (
    <svg className="metrics-icon-sm" viewBox="0 0 24 24" aria-hidden="true">
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
      <polyline points="17 6 23 6 23 12" />
    </svg>
  );
}
function CheckCircleIcon() {
  return (
    <svg className="metrics-check-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}
function AlertIcon() {
  return (
    <svg className="metrics-alert-icon" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}
function InfoIcon() {
  return (
    <svg className="metrics-info-icon" viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}
