import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";


import type { DiagnosticIn, DiagnosticPatchIn } from "../../api/diagnostics";
import type { CheckupIn } from "../../api/followupCheckups";
import type { ProgramExerciseIn, ProgramIn, ProgramPatchIn } from "../../api/programs";
import type { ReportIn } from "../../api/reports";
import type { MetricsOut } from "../../api/recordings";
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

export function usePrograms(
  api: DiagnosticFeatureApi,
  filters: { diagnosticId?: string; patientId?: string } = {},
) {
  return useQuery({
    queryKey: ["programs", filters],
    queryFn: () => api.listPrograms(filters),
  });
}

export function useProgramDetail(api: DiagnosticFeatureApi, programId?: string) {
  return useQuery({
    queryKey: ["programs", "detail", programId],
    queryFn: () => api.getProgram(programId ?? ""),
    enabled: Boolean(programId),
    retry: false,
  });
}

export function useCreateProgram(api: DiagnosticFeatureApi) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: ProgramIn) => api.createProgram(body),
    onSuccess: (program) => {
      queryClient.invalidateQueries({ queryKey: ["programs"] });
      queryClient.setQueryData(["programs", "detail", program.id], program);
    },
  });
}

export function useUpdateProgram(api: DiagnosticFeatureApi) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ programId, body }: { programId: string; body: ProgramPatchIn }) =>
      api.updateProgram(programId, body),
    onSuccess: (program) => {
      queryClient.invalidateQueries({ queryKey: ["programs"] });
      queryClient.setQueryData(["programs", "detail", program.id], program);
    },
  });
}

export function useProgramExercises(api: DiagnosticFeatureApi, programId?: string) {
  return useQuery({
    queryKey: ["programs", "exercises", programId],
    queryFn: () => api.listProgramExercises(programId ?? ""),
    enabled: Boolean(programId),
    retry: false,
  });
}

export function useExerciseCatalog(api: DiagnosticFeatureApi) {
  return useQuery({
    queryKey: ["catalog", "exercises"],
    queryFn: () => api.listExercises(),
  });
}

export function useDoctors(api: DiagnosticFeatureApi, enabled = true) {
  return useQuery({
    queryKey: ["doctors"],
    queryFn: () => api.listDoctors(),
    enabled,
  });
}

export function useAssignExercise(api: DiagnosticFeatureApi) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ programId, body }: { programId: string; body: ProgramExerciseIn }) =>
      api.assignProgramExercise(programId, body),
    onSuccess: (assignment) => {
      queryClient.invalidateQueries({ queryKey: ["programs", "exercises", assignment.program_id] });
    },
  });
}

export function useProgramReports(api: DiagnosticFeatureApi, programId?: string) {
  return useQuery({
    queryKey: ["reports", programId],
    queryFn: () => api.listProgramReports(programId ?? ""),
    enabled: Boolean(programId),
    retry: false,
  });
}

export function useReportDetail(api: DiagnosticFeatureApi, reportId?: string) {
  return useQuery({
    queryKey: ["reports", "detail", reportId],
    queryFn: () => api.getReportDetail(reportId ?? ""),
    enabled: Boolean(reportId),
    retry: false,
  });
}

export function useCreateReport(api: DiagnosticFeatureApi, programId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: ReportIn) => api.createReport(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reports", programId] });
    },
  });
}

export function useProgramCheckups(api: DiagnosticFeatureApi, programId?: string) {
  return useQuery({
    queryKey: ["followup-checkups", programId],
    queryFn: () => api.listProgramCheckups(programId!),
    enabled: Boolean(programId),
    retry: false,
  });
}

export function useCheckupDetail(api: DiagnosticFeatureApi, checkupId?: string) {
  return useQuery({
    queryKey: ["followup-checkups", "detail", checkupId],
    queryFn: () => api.getCheckupDetail(checkupId!),
    enabled: Boolean(checkupId),
    retry: false,
  });
}

export type ChartPoint = { date: string; [key: string]: string | number };

export function useCheckupMetrics(api: DiagnosticFeatureApi, checkupId: string | null) {
  return useQuery({
    queryKey: ["checkup-metrics", checkupId],
    enabled: checkupId !== null,
    queryFn: async () => {
      const checkup = await api.getCheckupDetail(checkupId!);
      const reportIds = checkup.reports.map((r) => r.exercise_report_id);

      const reports = await Promise.all(reportIds.map((id) => api.getReportDetail(id)));
      const recordingEntries = reports.flatMap((rep) => rep.recordings);

      const metricsResults: MetricsOut[] = await Promise.all(
        recordingEntries.map((rec) => api.getRecordingMetrics(rec.recording_id)),
      );

      const points: ChartPoint[] = [];
      const keySet = new Set<string>();

      recordingEntries.forEach((rec, i) => {
        const m = metricsResults[i];
        if (!m.metrics) return;

        const date = rec.recording_date
          ? rec.recording_date.slice(0, 10)
          : "";

        const point: ChartPoint = { date };
        for (const [k, v] of Object.entries(m.metrics)) {
          point[k] = v;
          keySet.add(k);
        }
        points.push(point);
      });

      points.sort((a, b) => a.date.localeCompare(b.date));

      return { data: points, metricKeys: Array.from(keySet) };
    },
    select: (result) => result,
  });
}

export function useCreateCheckup(api: DiagnosticFeatureApi, programId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: CheckupIn) => api.createCheckup(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["followup-checkups", programId] });
    },
  });
}
