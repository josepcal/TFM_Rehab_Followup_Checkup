import type { RequestOptions } from "./http";

export type MetricNorm = {
  norm_id: string;
  metric_code: string;
  label: string | null;
  unit: string | null;
  direction: "higher_better" | "lower_better" | "in_range";
  sex: string | null;
  age_min: number | null;
  age_max: number | null;
  good_min: number | null;
  good_max: number | null;
  poor_min: number | null;
  poor_max: number | null;
  source: string | null;
  version: number;
};

export type NormsApi = {
  listNorms(): Promise<MetricNorm[]>;
  getNorm(metricCode: string): Promise<MetricNorm>;
};

type HttpClient = {
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
};

export function createNormsApi(http: HttpClient): NormsApi {
  return {
    listNorms() {
      return http.request<MetricNorm[]>("/norms");
    },
    getNorm(metricCode) {
      return http.request<MetricNorm>(`/norms/${metricCode}`);
    },
  };
}
