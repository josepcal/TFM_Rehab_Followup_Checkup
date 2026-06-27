import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { MetricNorm } from "../../../api/norms";
import type { DiagnosticFeatureApi } from "../api";
import type { ChartPoint } from "../hooks";
import { useCheckupMetrics, useMetricNorms } from "../hooks";

type Props = {
  api: DiagnosticFeatureApi;
  checkupId: string;
  onClose: () => void;
};

function directionLabel(d: MetricNorm["direction"]): string {
  if (d === "higher_better") return "↑ higher is better";
  if (d === "lower_better") return "↓ lower is better";
  return "↔ target range";
}

type MetricChartProps = {
  metricKey: string;
  data: ChartPoint[];
  norm: MetricNorm | null;
};

function MetricChart({ metricKey, data, norm }: MetricChartProps) {
  const values = data
    .map((d) => d[metricKey] as number)
    .filter((v) => v != null && isFinite(v));

  if (values.length === 0) return null;

  const dataMin = Math.min(...values);
  const dataMax = Math.max(...values);

  const candidates = [dataMin, dataMax];
  if (norm?.good_min != null) candidates.push(norm.good_min);
  if (norm?.good_max != null) candidates.push(norm.good_max);
  if (norm?.poor_min != null) candidates.push(norm.poor_min);
  if (norm?.poor_max != null) candidates.push(norm.poor_max);

  const yMin = Math.min(...candidates) * 0.85;
  const yMax = Math.max(...candidates) * 1.15;

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis domain={[yMin, yMax]} tick={{ fontSize: 11 }} />
        <Tooltip />

        {norm && norm.direction === "higher_better" && (
          <>
            <ReferenceArea y1={norm.good_min ?? undefined} y2={yMax} fill="#dcfce7" fillOpacity={0.5} />
            <ReferenceArea y1={yMin} y2={norm.poor_max ?? undefined} fill="#fee2e2" fillOpacity={0.5} />
          </>
        )}

        {norm && norm.direction === "lower_better" && (
          <>
            <ReferenceArea y1={yMin} y2={norm.good_max ?? undefined} fill="#dcfce7" fillOpacity={0.5} />
            <ReferenceArea y1={norm.poor_min ?? undefined} y2={yMax} fill="#fee2e2" fillOpacity={0.5} />
          </>
        )}

        {norm && norm.direction === "in_range" && (
          <>
            <ReferenceArea y1={norm.good_min ?? undefined} y2={norm.good_max ?? undefined} fill="#dcfce7" fillOpacity={0.5} />
            <ReferenceArea y1={yMin} y2={norm.poor_min ?? undefined} fill="#fee2e2" fillOpacity={0.5} />
            <ReferenceArea y1={norm.poor_max ?? undefined} y2={yMax} fill="#fee2e2" fillOpacity={0.5} />
          </>
        )}

        <Line
          type="monotone"
          dataKey={metricKey}
          stroke="#8b5cf6"
          strokeWidth={2}
          dot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function FollowupMetricsModal({ api, checkupId, onClose }: Props) {
  const metricsQuery = useCheckupMetrics(api, checkupId);
  const isLoading = metricsQuery.isLoading;
  const data = metricsQuery.data?.data ?? [];
  const metricKeys = metricsQuery.data?.metricKeys ?? [];

  const normsQuery = useMetricNorms(api, metricKeys);
  const normsMap = normsQuery.data ?? new Map<string, MetricNorm>();

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content detail-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Metrics Evolution</h3>
          <button type="button" className="ghost-button" onClick={onClose}>
            ×
          </button>
        </div>

        {isLoading ? (
          <div className="loading-spinner" />
        ) : data.length === 0 ? (
          <p>No metrics available yet for this check-up.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            {metricKeys.map((key) => {
              const norm = normsMap.get(key) ?? null;
              return (
                <div key={key}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: "0.5rem",
                      marginBottom: "0.25rem",
                    }}
                  >
                    <h4 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600 }}>
                      {norm?.label ?? key}
                    </h4>
                    {norm && (
                      <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                        {directionLabel(norm.direction)}
                      </span>
                    )}
                  </div>
                  <MetricChart metricKey={key} data={data} norm={norm} />
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
