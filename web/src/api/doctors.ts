import type { RequestOptions } from "./http";

export type DoctorOut = {
  id: string;
  nombre: string;
  apellidos: string;
  doctor_type: string;
  colegiado_id?: string | null;
};

export type DoctorsApi = {
  listDoctors: () => Promise<DoctorOut[]>;
};

type HttpClient = {
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
};

export function createDoctorsApi(http: HttpClient): DoctorsApi {
  return {
    listDoctors() {
      return http.request<DoctorOut[]>("/doctors");
    },
  };
}
