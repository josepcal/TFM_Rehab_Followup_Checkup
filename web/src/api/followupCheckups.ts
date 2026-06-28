import type { RequestOptions } from "./http";

export type CheckupIn = {
  rehab_program_id: string;
  exercise_report_ids: string[];
  period_start: string;
  period_end: string;
  summary?: string | null;
};

export type CheckupListItem = {
  followup_checkup_id: string;
  rehab_program_id: string;
  patient_id: string;
  period_start: string;
  period_end: string;
  summary?: string | null;
  created_by?: string | null;
  created_by_name?: string | null;
  report_count: number;
};

export type LinkedReportItem = {
  exercise_report_id: string;
  period_start: string;
  period_end: string;
  summary?: string | null;
};

export type CheckupDetailOut = Omit<CheckupListItem, "report_count"> & {
  reports: LinkedReportItem[];
};

export type FollowupCheckupsApi = {
  createCheckup: (body: CheckupIn) => Promise<{ followup_checkup_id: string }>;
  listProgramCheckups: (programId: string) => Promise<CheckupListItem[]>;
  getCheckupDetail: (checkupId: string) => Promise<CheckupDetailOut>;
  updateCheckup: (checkupId: string, summary: string | null) => Promise<void>;
  deleteCheckup: (checkupId: string) => Promise<void>;
};

type HttpClient = {
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
};

export function createFollowupCheckupsApi(http: HttpClient): FollowupCheckupsApi {
  return {
    createCheckup(body) {
      return http.request<{ followup_checkup_id: string }>("/followup-checkups", {
        method: "POST",
        body,
      });
    },
    listProgramCheckups(programId) {
      return http.request<CheckupListItem[]>(`/programs/${programId}/followup-checkups`);
    },
    getCheckupDetail(checkupId) {
      return http.request<CheckupDetailOut>(`/followup-checkups/${checkupId}`);
    },
    updateCheckup(checkupId, summary) {
      return http.request<void>(`/followup-checkups/${checkupId}`, {
        method: "PATCH",
        body: { summary },
      });
    },
    deleteCheckup(checkupId) {
      return http.request<void>(`/followup-checkups/${checkupId}`, { method: "DELETE" });
    },
  };
}
