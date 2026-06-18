import type { RequestOptions } from "./http";

export type DiagnosticIn = {
  patient_id: string;
  dolencia: string;
  descripcion?: string | null;
  history?: string | null;
  symptoms?: string | null;
};

export type DiagnosticPatchIn = {
  dolencia?: string;
  descripcion?: string | null;
  history?: string | null;
  symptoms?: string | null;
};

export type DiagnosticOut = {
  id: string;
  patient_id: string;
  doctor_id?: string | null;
  dolencia: string;
  descripcion?: string | null;
  history?: string | null;
  symptoms?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  signature?: string | null;
  signed_at?: string | null;
  content_hash?: string | null;
};

export type PaginatedResponse<T> = {
  data?: T[];
  items?: T[];
  total: number;
  limit: number;
  offset: number;
};

export type NormalizedPage<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type DiagnosticsApi = {
  listDiagnostics: (params?: ListDiagnosticsParams) => Promise<NormalizedPage<DiagnosticOut>>;
  getDiagnostic: (diagnosticId: string) => Promise<DiagnosticOut>;
  createDiagnostic: (body: DiagnosticIn) => Promise<DiagnosticOut>;
  updateDiagnostic: (diagnosticId: string, body: DiagnosticPatchIn) => Promise<DiagnosticOut>;
};

export type ListDiagnosticsParams = {
  patientId?: string;
  limit?: number;
  offset?: number;
};

type HttpClient = {
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
};

export function createDiagnosticsApi(http: HttpClient): DiagnosticsApi {
  return {
    async listDiagnostics(params = {}) {
      const query = new URLSearchParams();
      query.set("limit", String(params.limit ?? 20));
      query.set("offset", String(params.offset ?? 0));
      if (params.patientId) {
        query.set("patient_id", params.patientId);
      }

      const page = await http.request<PaginatedResponse<DiagnosticOut>>(
        `/diagnostics/?${query.toString()}`,
      );
      const normalized = normalizePage(page);

      // Backend currently accepts the patient_id query as a compatibility filter
      // in the UI contract; keep a defensive client-side filter until the API
      // envelope/filter behavior is hardened.
      if (!params.patientId) {
        return normalized;
      }

      return {
        ...normalized,
        items: normalized.items.filter((diagnostic) => diagnostic.patient_id === params.patientId),
      };
    },
    getDiagnostic(diagnosticId) {
      return http.request<DiagnosticOut>(`/diagnostics/${diagnosticId}`);
    },
    createDiagnostic(body) {
      return http.request<DiagnosticOut>("/diagnostics/", {
        method: "POST",
        body,
      });
    },
    updateDiagnostic(diagnosticId, body) {
      return http.request<DiagnosticOut>(`/diagnostics/${diagnosticId}`, {
        method: "PATCH",
        body,
      });
    },
  };
}

export function normalizePage<T>(page: PaginatedResponse<T>): NormalizedPage<T> {
  return {
    items: page.items ?? page.data ?? [],
    total: page.total,
    limit: page.limit,
    offset: page.offset,
  };
}
