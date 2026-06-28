import type { RequestOptions } from "./http";

export type EventLogEntry = {
  event_id: string;
  entity_type: string;
  entity_id: string | null;
  action: string;
  actor_id: string | null;
  payload: Record<string, unknown> | null;
  occurred_at: string;
};

export type AuditLogFilters = {
  actor_id?: string;
  entity_type?: string;
  from_ts?: string;
  to_ts?: string;
  limit?: number;
  offset?: number;
};

export type AuditLogApi = {
  getAuditLog(filters?: AuditLogFilters): Promise<EventLogEntry[]>;
};

type HttpClient = {
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
};

export function createAuditLogApi(http: HttpClient): AuditLogApi {
  return {
    getAuditLog(filters = {}) {
      const query = new URLSearchParams();
      if (filters.actor_id) query.set("actor_id", filters.actor_id);
      if (filters.entity_type) query.set("entity_type", filters.entity_type);
      if (filters.from_ts) query.set("from_ts", filters.from_ts);
      if (filters.to_ts) query.set("to_ts", filters.to_ts);
      if (filters.limit !== undefined) query.set("limit", String(filters.limit));
      if (filters.offset !== undefined) query.set("offset", String(filters.offset));

      const qs = query.toString();
      return http.request<EventLogEntry[]>(`/iam/audit-log${qs ? `?${qs}` : ""}`);
    },
  };
}
