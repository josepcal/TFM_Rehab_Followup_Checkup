import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { DiagnosticFeatureApi } from "../api";
import { useCheckupMetrics } from "../hooks";

const COLORS = ["#8b5cf6", "#06b6d4", "#f59e0b", "#10b981", "#ef4444"];

type Props = {
  api: DiagnosticFeatureApi;
  checkupId: string;
  onClose: () => void;
};

export function FollowupMetricsModal({ api, checkupId, onClose }: Props) {
  const query = useCheckupMetrics(api, checkupId);
  const isLoading = query.isLoading;
  const data = query.data?.data ?? [];
  const metricKeys = query.data?.metricKeys ?? [];

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
          <div data-testid="metrics-chart">
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={data} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                {metricKeys.map((key, i) => (
                  <Line
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={COLORS[i % COLORS.length]}
                    strokeWidth={2}
                    dot={{ r: 4 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
