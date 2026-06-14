import { useQuery } from "@tanstack/react-query";

import type { DiagnosticFeatureApi } from "./api";

export function usePatients(api: DiagnosticFeatureApi) {
  return useQuery({
    queryKey: ["patients"],
    queryFn: () => api.listPatients(),
  });
}

export function useDiagnosticHistory(api: DiagnosticFeatureApi, patientId?: string) {
  return useQuery({
    queryKey: ["diagnostics", "history", patientId],
    queryFn: () => api.listDiagnostics({ patientId }),
    enabled: Boolean(patientId),
    retry: false,
  });
}
