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
};

export type RecordingOut = {
  recording_id: string;
};

export type ExerciseRecordingListItem = {
  recording_id: string;
  program_exercise_id: string;
  storage_uri?: string | null;
  media_kind?: "audio" | "video" | string | null;
  media_status?: string | null;
  recording_date?: string | null;
  duration_seconds?: number | null;
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
