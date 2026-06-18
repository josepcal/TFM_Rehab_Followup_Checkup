import type { DiagnosticOut, NormalizedPage, PaginatedResponse } from "./diagnostics";
import { normalizePage } from "./diagnostics";
import type { PatientOut } from "./patients";
import type { ProgramExerciseOut, ProgramOut } from "./programs";
import type { RequestOptions } from "./http";

export type PatientPortalApi = {
  getMyPatient: () => Promise<PatientOut>;
  listMyDiagnostics: () => Promise<NormalizedPage<DiagnosticOut>>;
  listMyPrograms: () => Promise<NormalizedPage<ProgramOut>>;
  getMyProgram: (programId: string) => Promise<ProgramOut>;
  listMyProgramExercises: (programId: string) => Promise<NormalizedPage<ProgramExerciseOut>>;
};

type HttpClient = {
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
};

export function createPatientPortalApi(http: HttpClient): PatientPortalApi {
  return {
    getMyPatient() {
      return http.request<PatientOut>("/patients/me");
    },
    async listMyDiagnostics() {
      const page = await http.request<PaginatedResponse<DiagnosticOut>>("/patients/me/diagnostics?limit=20&offset=0");
      return normalizePage(page);
    },
    async listMyPrograms() {
      const page = await http.request<PaginatedResponse<ProgramOut>>("/patients/me/programs?limit=20&offset=0");
      return normalizePage(page);
    },
    getMyProgram(programId) {
      return http.request<ProgramOut>(`/patients/me/programs/${programId}`);
    },
    async listMyProgramExercises(programId) {
      const page = await http.request<PaginatedResponse<ProgramExerciseOut>>(
        `/patients/me/programs/${programId}/exercises?limit=20&offset=0`,
      );
      return normalizePage(page);
    },
  };
}
