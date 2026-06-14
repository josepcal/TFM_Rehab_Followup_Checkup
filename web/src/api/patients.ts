import type { RequestOptions } from "./http";

export type PatientOut = {
  id: string;
  nombre: string;
  apellidos: string;
};

export type PatientsApi = {
  listPatients: () => Promise<PatientOut[]>;
};

type HttpClient = {
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
};

export function createPatientsApi(http: HttpClient): PatientsApi {
  return {
    listPatients() {
      return http.request<PatientOut[]>("/patients");
    },
  };
}
