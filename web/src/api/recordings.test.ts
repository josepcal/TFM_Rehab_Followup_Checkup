import { describe, expect, it, vi } from "vitest";

import type { RequestOptions } from "./http";
import { createRecordingsApi, createAnalysisApi } from "./recordings";

function makeHttp(response: unknown = undefined) {
  const request = vi.fn(async () => response) as unknown as (<T>(
    path: string,
    options?: RequestOptions,
  ) => Promise<T>) &
    ReturnType<typeof vi.fn>;
  return { http: { request }, request };
}

describe("recordings API", () => {
  it("createRecordingUploadUrl calls POST /recordings/upload-url with body", async () => {
    const { http, request } = makeHttp({ key: "k", url: "https://bucket/k", content_type: "audio/wav" });
    const api = createRecordingsApi(http);

    await api.createRecordingUploadUrl({ program_exercise_id: "pe-1", content_type: "audio/wav" });

    expect(request).toHaveBeenCalledWith("/recordings/upload-url", {
      method: "POST",
      body: { program_exercise_id: "pe-1", content_type: "audio/wav" },
    });
  });

  it("uploadRecordingBlob calls http.upload with signed url and blob", async () => {
    const upload = vi.fn(async () => undefined);
    const request = vi.fn() as unknown as (<T>(path: string, options?: RequestOptions) => Promise<T>) & ReturnType<typeof vi.fn>;
    const api = createRecordingsApi({ request, upload });

    const blob = new Blob(["audio"], { type: "audio/wav" });
    await api.uploadRecordingBlob("https://bucket/signed", blob, "audio/wav");

    expect(upload).toHaveBeenCalledWith("https://bucket/signed", blob, "audio/wav");
  });

  it("uploadRecordingBlob throws when http.upload is not configured", async () => {
    const { http } = makeHttp();
    const api = createRecordingsApi(http);

    await expect(
      api.uploadRecordingBlob("https://bucket/signed", new Blob(), "audio/wav"),
    ).rejects.toThrow("Recording upload is not configured");
  });

  it("registerRecording calls POST /recordings with body", async () => {
    const { http, request } = makeHttp({ recording_id: "rec-1" });
    const api = createRecordingsApi(http);

    const body = {
      program_exercise_id: "pe-1",
      storage_uri: "recordings/pe-1/audio.wav",
      content_type: "audio/wav",
      duration_seconds: 12.5,
      sha256: "a".repeat(64),
    };
    await api.registerRecording(body);

    expect(request).toHaveBeenCalledWith("/recordings", { method: "POST", body });
  });

  it("listExerciseRecordings calls GET /program-exercises/{id}/recordings", async () => {
    const { http, request } = makeHttp([]);
    const api = createRecordingsApi(http);

    await api.listExerciseRecordings("pe-1");

    expect(request).toHaveBeenCalledWith("/program-exercises/pe-1/recordings");
  });

  it("deleteRecording calls DELETE /recordings/{id}", async () => {
    const { http, request } = makeHttp();
    const api = createRecordingsApi(http);

    await api.deleteRecording("rec-1");

    expect(request).toHaveBeenCalledWith("/recordings/rec-1", { method: "DELETE" });
  });

  it("getRecordingDownloadUrl calls GET /recordings/{id}/download-url and extracts url", async () => {
    const { http, request } = makeHttp({ url: "https://bucket/signed-download" });
    const api = createRecordingsApi(http);

    const url = await api.getRecordingDownloadUrl("rec-1");

    expect(request).toHaveBeenCalledWith("/recordings/rec-1/download-url");
    expect(url).toBe("https://bucket/signed-download");
  });
});

describe("analysis API", () => {
  it("runAnalysis calls POST /recordings/{id}/run with function_name", async () => {
    const { http, request } = makeHttp({ job_id: "job-1", status: "queued" });
    const api = createAnalysisApi(http);

    await api.runAnalysis("rec-1", "sustained_phonation_v1");

    expect(request).toHaveBeenCalledWith("/recordings/rec-1/run", {
      method: "POST",
      body: { function_name: "sustained_phonation_v1" },
    });
  });

  it("runAnalysis uses default function name when not provided", async () => {
    const { http, request } = makeHttp({ job_id: "job-2", status: "queued" });
    const api = createAnalysisApi(http);

    await api.runAnalysis("rec-1");

    expect(request).toHaveBeenCalledWith("/recordings/rec-1/run", {
      method: "POST",
      body: { function_name: "dysarthria_analysis_v1" },
    });
  });

  it("getRecordingMetrics returns metrics from raw_json when metrics field is null", async () => {
    const { http } = makeHttp({
      function_name: "sustained_phonation_v1",
      status: "done",
      metrics: null,
      raw_json: { phonation_seconds: 12.4, f0_stability: 0.91, label: "good" },
    });
    const api = createAnalysisApi(http);

    const result = await api.getRecordingMetrics("rec-1");

    expect(result.metrics).toEqual({ phonation_seconds: 12.4, f0_stability: 0.91 });
  });

  it("getRecordingMetrics prefers metrics field over raw_json when both present", async () => {
    const { http } = makeHttp({
      function_name: "sustained_phonation_v1",
      status: "done",
      metrics: { phonation_seconds: 10.0 },
      raw_json: { phonation_seconds: 12.4 },
    });
    const api = createAnalysisApi(http);

    const result = await api.getRecordingMetrics("rec-1");

    expect(result.metrics).toEqual({ phonation_seconds: 10.0 });
  });

  it("getRecordingMetrics extracts recommendations from raw_json.recommendations", async () => {
    const { http } = makeHttp({
      function_name: "sustained_phonation_v1",
      status: "done",
      metrics: null,
      raw_json: { recommendations: ["Keep practising", "Breathe deeper"] },
    });
    const api = createAnalysisApi(http);

    const result = await api.getRecordingMetrics("rec-1");

    expect(result.recommendations).toEqual(["Keep practising", "Breathe deeper"]);
  });

  it("getRecordingMetrics extracts recommendations from note lines when raw_json has none", async () => {
    const { http } = makeHttp({
      function_name: "sustained_phonation_v1",
      status: "done",
      metrics: { phonation_seconds: 8.0 },
      raw_json: null,
      note: "Try to hold longer\nBreath support is key",
    });
    const api = createAnalysisApi(http);

    const result = await api.getRecordingMetrics("rec-1");

    expect(result.recommendations).toEqual(["Try to hold longer", "Breath support is key"]);
  });

  it("getRecordingMetrics returns null metrics and recommendations when raw_json is empty object", async () => {
    const { http } = makeHttp({
      function_name: "sustained_phonation_v1",
      status: "pending",
      metrics: null,
      raw_json: {},
    });
    const api = createAnalysisApi(http);

    const result = await api.getRecordingMetrics("rec-1");

    expect(result.metrics).toBeNull();
    expect(result.recommendations).toBeNull();
  });
});
