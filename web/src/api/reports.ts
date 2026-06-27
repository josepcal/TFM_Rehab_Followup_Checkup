import type { RequestOptions } from "./http";

export type ReportIn = {
  program_exercise_id: string;
  recording_ids: string[];
  period_start: string;
  period_end: string;
  summary?: string | null;
};

export type ReportListItem = {
  exercise_report_id: string;
  program_exercise_id: string;
  period_start: string;
  period_end: string;
  summary?: string | null;
  created_by: string;
  created_by_name?: string | null;
  attested_at?: string | null;
  recording_count: number;
  exercise_id?: string | null;
  exercise_name?: string | null;
};

export type RecordingInsightEntry = {
  recording_id: string;
  recording_date?: string | null;
  duration_seconds?: number | null;
  media_status?: string | null;
  metrics_status?: string | null;
  raw_json?: Record<string, unknown> | null;
  insight_text?: string | null;
  model_used?: string | null;
};

export type ReportDetailOut = Omit<ReportListItem, "recording_count"> & {
  recordings: RecordingInsightEntry[];
};

export type ReportsApi = {
  createReport: (body: ReportIn) => Promise<{ exercise_report_id: string }>;
  listProgramReports: (programId: string) => Promise<ReportListItem[]>;
  getReportDetail: (reportId: string) => Promise<ReportDetailOut>;
  updateReport: (reportId: string, summary: string) => Promise<void>;
  deleteReport: (reportId: string) => Promise<void>;
};

type HttpClient = {
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
};

export function createReportsApi(http: HttpClient): ReportsApi {
  return {
    createReport(body) {
      return http.request<{ exercise_report_id: string }>("/reports", {
        method: "POST",
        body,
      });
    },
    listProgramReports(programId) {
      return http.request<ReportListItem[]>(`/programs/${programId}/reports`);
    },
    getReportDetail(reportId) {
      return http.request<ReportDetailOut>(`/reports/${reportId}`);
    },
    updateReport(reportId, summary) {
      return http.request<void>(`/reports/${reportId}`, {
        method: "PATCH",
        body: { summary },
      });
    },
    deleteReport(reportId) {
      return http.request<void>(`/reports/${reportId}`, { method: "DELETE" });
    },
  };
}
