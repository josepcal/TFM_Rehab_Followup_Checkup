import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RecordingDialog } from "./PatientPortal";

type DialogApi = Parameters<typeof RecordingDialog>[0]["api"];

afterEach(() => {
  vi.restoreAllMocks();
});

describe("UC-05 patient recording file upload", () => {
  it("selects, previews and saves an existing audio file through the recording API", async () => {
    const user = userEvent.setup();
    const uploadRecordingBlob = vi.fn(async () => undefined);
    const registerRecording = vi.fn(async () => ({ recording_id: "recording-uploaded" }));
    const api = {
      createRecordingUploadUrl: vi.fn(async () => ({
        key: "exercise/uploaded.webm",
        url: "/api/recordings/_local-upload/exercise/uploaded.webm",
        content_type: "audio/webm",
      })),
      uploadRecordingBlob,
      registerRecording,
      listExerciseRecordings: vi.fn(async () => []),
      getMyPatient: vi.fn(),
      listMyDiagnostics: vi.fn(),
      listMyPrograms: vi.fn(),
      getMyProgram: vi.fn(),
      listMyProgramExercises: vi.fn(),
      listDoctors: vi.fn(),
    } as DialogApi;
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:preview") });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() });
    Object.defineProperty(Blob.prototype, "arrayBuffer", { configurable: true, value: vi.fn(async () => new ArrayBuffer(4)) });
    vi.spyOn(crypto.subtle, "digest").mockResolvedValue(new Uint8Array(32).buffer);

    render(
      <QueryClientProvider client={queryClient}>
        <RecordingDialog
          api={api}
          exercise={{ id: "program-exercise-1", program_id: "program-1", exercise_id: "exercise-1" }}
          onClose={vi.fn()}
        />
      </QueryClientProvider>,
    );

    await user.click(screen.getByRole("checkbox", { name: /consent/i }));
    const file = new File(["recording"], "session.webm", { type: "audio/webm" });
    await user.upload(screen.getByLabelText(/upload audio or video file/i), file);

    expect(screen.getByText("File uploaded")).toBeInTheDocument();
    expect(screen.getByText(/session\.webm/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /save recording/i }));

    await waitFor(() => expect(registerRecording).toHaveBeenCalledTimes(1));
    expect(uploadRecordingBlob).toHaveBeenCalledWith(
      "/api/recordings/_local-upload/exercise/uploaded.webm",
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
