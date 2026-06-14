import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { DiagnosticIn, DiagnosticPatchIn } from "../../api/diagnostics";
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

export function useDiagnosticDetail(api: DiagnosticFeatureApi, diagnosticId?: string) {
  return useQuery({
    queryKey: ["diagnostics", "detail", diagnosticId],
    queryFn: () => api.getDiagnostic(diagnosticId ?? ""),
    enabled: Boolean(diagnosticId),
    retry: false,
  });
}

export function useCreateDiagnostic(api: DiagnosticFeatureApi) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: DiagnosticIn) => api.createDiagnostic(body),
    onSuccess: (diagnostic) => {
      queryClient.invalidateQueries({ queryKey: ["diagnostics", "history", diagnostic.patient_id] });
      queryClient.setQueryData(["diagnostics", "detail", diagnostic.id], diagnostic);
    },
  });
}

export function useUpdateDiagnostic(api: DiagnosticFeatureApi) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ diagnosticId, body }: { diagnosticId: string; body: DiagnosticPatchIn }) =>
      api.updateDiagnostic(diagnosticId, body),
    onSuccess: (diagnostic) => {
      queryClient.invalidateQueries({ queryKey: ["diagnostics", "history", diagnostic.patient_id] });
      queryClient.setQueryData(["diagnostics", "detail", diagnostic.id], diagnostic);
    },
  });
}
