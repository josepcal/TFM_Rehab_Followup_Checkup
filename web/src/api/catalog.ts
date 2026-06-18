import type { RequestOptions } from "./http";

export type RehabExerciseOut = {
  id: string;
  nombre: string;
  tipo?: string | null;
};

export type CatalogApi = {
  listExercises: () => Promise<RehabExerciseOut[]>;
};

type HttpClient = {
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
};

export function createCatalogApi(http: HttpClient): CatalogApi {
  return {
    listExercises() {
      return http.request<RehabExerciseOut[]>("/exercises");
    },
  };
}
