import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PatientPortal, RecordingDialog } from "./PatientPortal";
import { ExerciseAnalysisModal } from "./ExerciseAnalysisModal";

type DialogApi = Parameters<typeof RecordingDialog>[0]["api"];
type PortalApi = Parameters<typeof PatientPortal>[0]["api"];

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function makeDialogApi(overrides: Partial<DialogApi> = {}): DialogApi {
  return {
    createRecordingUploadUrl: vi.fn(async () => ({
      key: "recordings/program-exercise-1/11111111-1111-1111-1111-111111111111.webm",
      url: "/api/recordings/_local-upload/recordings/program-exercise-1/11111111-1111-1111-1111-111111111111.webm",
      content_type: "audio/webm",
    })),
    uploadRecordingBlob: vi.fn(async () => undefined),
    registerRecording: vi.fn(async () => ({ recording_id: "recording-uploaded" })),
    listExerciseRecordings: vi.fn(async () => []),
    getMyPatient: vi.fn(),
    listMyDiagnostics: vi.fn(),
    listMyPrograms: vi.fn(),
    getMyProgram: vi.fn(),
    listMyProgramExercises: vi.fn(),
    listDoctors: vi.fn(),
    ...overrides,
  } as DialogApi;
}

function renderDialog(api: DialogApi) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <RecordingDialog
        api={api}
        exercise={{ id: "program-exercise-1", program_id: "program-1", exercise_id: "exercise-1" }}
        onClose={vi.fn()}
      />
    </QueryClientProvider>,
  );
}

function installMediaBlobMocks() {
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:preview") });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
  Object.defineProperty(Blob.prototype, "arrayBuffer", { configurable: true, value: vi.fn(async () => new ArrayBuffer(4)) });
  vi.spyOn(crypto.subtle, "digest").mockResolvedValue(new Uint8Array(32).buffer);
}

describe("UC-05 patient recording navigation", () => {
  it("opens the recording workspace from a rehabilitation program", async () => {
    const user = userEvent.setup();
    const api = {
      getMyPatient: vi.fn(async () => ({ id: "patient-1", nombre: "Ana", apellidos: "Garcia" })),
      listMyDiagnostics: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
      listMyPrograms: vi.fn(async () => ({
        items: [{ id: "program-1", diagnostic_id: "diagnostic-1", estado: "active", name: "Speech plan" }],
        total: 1,
        limit: 20,
        offset: 0,
      })),
      getMyProgram: vi.fn(async () => ({ id: "program-1", diagnostic_id: "diagnostic-1", estado: "active", name: "Speech plan" })),
      listMyProgramExercises: vi.fn(async () => ({
        items: [{
          id: "program-exercise-1",
          program_id: "program-1",
          exercise_id: "exercise-1",
          estado: "active",
          exercise_description: "Fonación sostenida de la vocal /a/",
        }],
        total: 1,
        limit: 20,
        offset: 0,
      })),
      listDoctors: vi.fn(async () => []),
      createRecordingUploadUrl: vi.fn(),
      uploadRecordingBlob: vi.fn(),
      registerRecording: vi.fn(),
      listExerciseRecordings: vi.fn(async () => []),
      runAnalysis: vi.fn(),
      getRecordingMetrics: vi.fn(),
    } as PortalApi;
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <PatientPortal api={api} />
      </QueryClientProvider>,
    );

    await user.click(await screen.findByRole("link", { name: /speech plan: view exercises/i }));

    expect(await screen.findByRole("heading", { level: 2, name: "Speech plan" })).toBeInTheDocument();
    expect(screen.getAllByText("Fonación sostenida de la vocal /a/").length).toBeGreaterThan(0);
    expect(screen.getByText("View exercises and record progress")).toBeInTheDocument();
  });

  it("shows each recording creation time instead of the date-only clinical field", async () => {
    const user = userEvent.setup();
    const createdAt = "2026-06-20T14:35:00Z";
    const api = {
      getMyPatient: vi.fn(async () => ({ id: "patient-1", nombre: "Ana", apellidos: "Garcia" })),
      listMyDiagnostics: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
      listMyPrograms: vi.fn(async () => ({
        items: [{ id: "program-1", diagnostic_id: "diagnostic-1", estado: "active", name: "Speech plan" }],
        total: 1,
        limit: 20,
        offset: 0,
      })),
      getMyProgram: vi.fn(async () => ({ id: "program-1", diagnostic_id: "diagnostic-1", estado: "active", name: "Speech plan" })),
      listMyProgramExercises: vi.fn(async () => ({
        items: [{ id: "program-exercise-1", program_id: "program-1", exercise_id: "exercise-1", estado: "active" }],
        total: 1,
        limit: 20,
        offset: 0,
      })),
      listDoctors: vi.fn(async () => []),
      createRecordingUploadUrl: vi.fn(),
      uploadRecordingBlob: vi.fn(),
      registerRecording: vi.fn(),
      listExerciseRecordings: vi.fn(async () => [{
        recording_id: "recording-1",
        program_exercise_id: "program-exercise-1",
        recording_date: "2026-06-20",
        created_at: createdAt,
        media_kind: "audio",
      }]),
      runAnalysis: vi.fn(),
      getRecordingMetrics: vi.fn(),
    } as PortalApi;
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <PatientPortal api={api} />
      </QueryClientProvider>,
    );

    await user.click(await screen.findByRole("link", { name: /speech plan: view exercises/i }));

    const expectedDateTime = new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(createdAt));
    expect(await screen.findByText(expectedDateTime)).toBeInTheDocument();
  });
});

describe("UC-05 patient live recording", () => {
  it("gates capture on consent and reports unsupported browsers", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("MediaRecorder", undefined);
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: undefined });
    renderDialog(makeDialogApi());
    const recordButton = screen.getByRole("button", { name: /^record$/i });

    expect(recordButton).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /consent/i }));
    await user.click(recordButton);

    expect(screen.getByRole("alert")).toHaveTextContent(/not supported/i);
  });

  it("captures and saves a MediaRecorder blob through upload and registration", async () => {
    const user = userEvent.setup();
    installMediaBlobMocks();
    const stopTrack = vi.fn();
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: vi.fn(async () => ({
          getAudioTracks: () => [{ getSettings: () => ({ sampleRate: 48_000 }) }],
          getTracks: () => [{ stop: stopTrack }],
        })),
      },
    });
    class MockMediaRecorder {
      static isTypeSupported() { return true; }
      mimeType = "audio/webm";
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      start() {}
      stop() {
        this.ondataavailable?.({ data: new Blob(["recorded"], { type: this.mimeType }) });
        this.onstop?.();
      }
    }
    vi.stubGlobal("MediaRecorder", MockMediaRecorder);
    const uploadRecordingBlob = vi.fn(async () => undefined);
    const registerRecording = vi.fn(async () => ({ recording_id: "live-recording" }));
    renderDialog(makeDialogApi({ uploadRecordingBlob, registerRecording }));

    await user.click(screen.getByRole("checkbox", { name: /consent/i }));
    await user.click(screen.getByRole("button", { name: /^record$/i }));
    await user.click(await screen.findByRole("button", { name: /stop/i }));
    await user.click(await screen.findByRole("button", { name: /save recording/i }));

    await waitFor(() => expect(registerRecording).toHaveBeenCalledTimes(1));
    expect(uploadRecordingBlob).toHaveBeenCalledTimes(1);
    expect(registerRecording).toHaveBeenCalledWith(expect.objectContaining({
      program_exercise_id: "program-exercise-1",
      sample_rate: 48_000,
      sha256: "0".repeat(64),
    }));
    expect(stopTrack).toHaveBeenCalled();
  });
});

describe("UC-05 patient recording file upload", () => {
  it("selects, previews and saves an existing audio file through the recording API", async () => {
    const user = userEvent.setup();
    const uploadRecordingBlob = vi.fn(async () => undefined);
    const registerRecording = vi.fn(async () => ({ recording_id: "recording-uploaded" }));
    const api = makeDialogApi({ uploadRecordingBlob, registerRecording });
    installMediaBlobMocks();
    renderDialog(api);

    await user.click(screen.getByRole("checkbox", { name: /consent/i }));
    const file = new File(["recording"], "session.webm", { type: "audio/webm" });
    await user.upload(screen.getByLabelText(/upload audio or video file/i), file);

    expect(screen.getByText("File uploaded")).toBeInTheDocument();
    expect(screen.getByText(/session\.webm/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /save recording/i }));

    await waitFor(() => expect(registerRecording).toHaveBeenCalledTimes(1));
    expect(uploadRecordingBlob).toHaveBeenCalledWith(
      "/api/recordings/_local-upload/recordings/program-exercise-1/11111111-1111-1111-1111-111111111111.webm",
      file,
      "audio/webm",
    );
    expect(registerRecording).toHaveBeenCalledWith(expect.objectContaining({
      program_exercise_id: "program-exercise-1",
      size_bytes: file.size,
      sha256: "0".repeat(64),
    }));
  });
});


describe("ExerciseAnalysisModal", () => {
  it("shows worker error details instead of polling forever", async () => {
    const api = makeDialogApi({
      getRecordingMetrics: vi.fn(async () => ({
        result_id: "result-1",
        recording_id: "recording-1",
        function_name: "dysarthria_analysis_v1",
        status: "error",
        error_detail: "InsufficientSignalError: Voiced signal too short (0.18s < 1.0s minimum)",
        raw_json: null,
        metrics: null,
      })),
      runAnalysis: vi.fn(),
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <ExerciseAnalysisModal
          recordingId="recording-1"
          recordingDate="2026-06-25"
          api={api}
          onClose={vi.fn()}
        />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(/voiced signal too short/i);
    expect(screen.queryByText(/analysing your exercise recording/i)).not.toBeInTheDocument();
    expect(api.runAnalysis).not.toHaveBeenCalled();
  });
});
