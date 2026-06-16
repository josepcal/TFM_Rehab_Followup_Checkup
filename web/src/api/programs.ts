import type { NormalizedPage, PaginatedResponse } from "./diagnostics";
import { normalizePage } from "./diagnostics";
import type { RequestOptions } from "./http";

export type ProgramIn = {
  diagnostic_id: string;
  estado?: string | null;
  name?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  physiotherapist_id?: string | null;
};

export type ProgramOut = {
  id: string;
  diagnostic_id: string;
  estado: string;
  name?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  physiotherapist_id?: string | null;
  created_at?: string | null;
};

export type ProgramExerciseIn = {
  exercise_id: string;
  pauta?: string | null;
};

export type ProgramExerciseOut = {
  id: string;
  program_id: string;
  exercise_id: string;
  pauta?: string | null;
  estado?: string | null;
  created_at?: string | null;
};

export type ListProgramsParams = {
  diagnosticId?: string;
  patientId?: string;
  limit?: number;
  offset?: number;
};

export type ListProgramExercisesParams = {
  limit?: number;
  offset?: number;
};

export type ProgramsApi = {
  listPrograms: (params?: ListProgramsParams) => Promise<NormalizedPage<ProgramOut>>;
  getProgram: (programId: string) => Promise<ProgramOut>;
  createProgram: (body: ProgramIn) => Promise<ProgramOut>;
  listProgramExercises: (
    programId: string,
    params?: ListProgramExercisesParams,
  ) => Promise<NormalizedPage<ProgramExerciseOut>>;
  assignProgramExercise: (programId: string, body: ProgramExerciseIn) => Promise<ProgramExerciseOut>;
};

type HttpClient = {
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
};

export function createProgramsApi(http: HttpClient): ProgramsApi {
  return {
    async listPrograms(params = {}) {
      const query = buildPaginationQuery(params.limit, params.offset);
      if (params.diagnosticId) {
        query.set("diagnostic_id", params.diagnosticId);
      }
      if (params.patientId) {
        query.set("patient_id", params.patientId);
      }

      const page = await http.request<PaginatedResponse<ProgramOut>>(
        `/programs/?${query.toString()}`,
      );
      return normalizePage(page);
    },
    getProgram(programId) {
      return http.request<ProgramOut>(`/programs/${programId}`);
    },
    createProgram(body) {
      return http.request<ProgramOut>("/programs/", {
        method: "POST",
        body,
      });
    },
    async listProgramExercises(programId, params = {}) {
      const query = buildPaginationQuery(params.limit, params.offset);
      const page = await http.request<PaginatedResponse<ProgramExerciseOut>>(
        `/programs/${programId}/exercises?${query.toString()}`,
      );
      return normalizePage(page);
    },
    assignProgramExercise(programId, body) {
      return http.request<ProgramExerciseOut>(`/programs/${programId}/exercises`, {
        method: "POST",
        body,
      });
    },
  };
}

function buildPaginationQuery(limit = 20, offset = 0) {
  const query = new URLSearchParams();
  query.set("limit", String(limit));
  query.set("offset", String(offset));
  return query;
}
