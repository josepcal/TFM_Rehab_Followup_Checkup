import type { RequestOptions } from "./http";

export type UploadUrlIn = {
  program_exercise_id: string;
  content_type?: string;
};

export type UploadUrlOut = {
  key: string;
  url: string;
  content_type?: string;
};

export type RecordingIn = {
  program_exercise_id: string;
  storage_uri: string;
  content_type?: string;
  duration_seconds?: number;
  sample_rate?: number;
  size_bytes?: number;
  sha256?: string;
};

export type RecordingOut = {
  recording_id: string;
};

export type ExerciseRecordingListItem = {
  recording_id: string;
  program_exercise_id: string;
  recorded_by?: string | null;
  storage_uri?: string | null;
  content_type?: string | null;
  media_kind?: "audio" | "video" | string | null;
  media_status?: string | null;
  recording_date?: string | null;
  duration_seconds?: number | null;
  sample_rate?: number | null;
  size_bytes?: number | null;
  sha256?: string | null;
  notes?: string | null;
  created_at?: string | null;
};

export type RecordingsApi = {
  createRecordingUploadUrl: (body: UploadUrlIn) => Promise<UploadUrlOut>;
  uploadRecordingBlob: (url: string, blob: Blob, contentType: string) => Promise<void>;
  registerRecording: (body: RecordingIn) => Promise<RecordingOut>;
  listExerciseRecordings: (programExerciseId: string) => Promise<ExerciseRecordingListItem[]>;
};

type HttpClient = {
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
  upload?: (url: string, blob: Blob, contentType: string) => Promise<void>;
};

export function createRecordingsApi(http: HttpClient): RecordingsApi {
  return {
    createRecordingUploadUrl(body) {
      return http.request<UploadUrlOut>("/recordings/upload-url", {
        method: "POST",
        body,
      });
    },
    async uploadRecordingBlob(url, blob, contentType) {
      if (!http.upload) {
        throw new Error("Recording upload is not configured");
      }
      await http.upload(url, blob, contentType);
    },
    registerRecording(body) {
      return http.request<RecordingOut>("/recordings", {
        method: "POST",
        body,
      });
    },
    listExerciseRecordings(programExerciseId) {
      return http.request<ExerciseRecordingListItem[]>(`/program-exercises/${programExerciseId}/recordings`);
    },
  };
}

// ── Analysis / Metrics ─────────────────────────────────────────────────────

export type RunAnalysisOut = {
  job_id: string;
  status: string;
};

export type MetricsOut = {
  result_id?: string;
  recording_id?: string;
  function_name: string | null;
  function_version?: string | null;
  code_sha?: string | null;
  status?: string;
  error_detail?: string | null;
  raw_json?: Record<string, unknown> | null;
  extracted_at?: string;
  metrics: Record<string, number> | null;
};

export type AnalysisApi = {
  runAnalysis: (recordingId: string, functionName?: string) => Promise<RunAnalysisOut>;
  getRecordingMetrics: (recordingId: string) => Promise<MetricsOut>;
};

export function createAnalysisApi(http: HttpClient): AnalysisApi {
  return {
    runAnalysis(recordingId, functionName = "dysarthria_analysis_v1") {
      return http.request<RunAnalysisOut>(`/recordings/${recordingId}/run`, {
        method: "POST",
        body: { function_name: functionName },
      });
    },
    async getRecordingMetrics(recordingId) {
      const result = await http.request<MetricsOut>(`/recordings/${recordingId}/metrics`);
      return {
        ...result,
        metrics: result.metrics ?? numericMetricsFromRawJson(result.raw_json),
      };
    },
  };
}

function numericMetricsFromRawJson(rawJson?: Record<string, unknown> | null): Record<string, number> | null {
  if (!rawJson) {
    return null;
  }
  const metrics = Object.fromEntries(
    Object.entries(rawJson).filter((entry): entry is [string, number] => (
      typeof entry[1] === "number" && Number.isFinite(entry[1])
    )),
  );
  return Object.keys(metrics).length > 0 ? metrics : null;
}
