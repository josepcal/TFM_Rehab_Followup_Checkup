import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DiagnosticFeatureApi } from "../api";
import { FollowupCheckupPanel } from "./FollowupCheckupPanel";

function makeApi(overrides: Partial<DiagnosticFeatureApi> = {}): DiagnosticFeatureApi {
  return {
    listPatients: vi.fn(async () => []),
    listDiagnostics: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
    getDiagnostic: vi.fn(async () => { throw new Error("not implemented"); }),
    createDiagnostic: vi.fn(async () => { throw new Error("not implemented"); }),
    updateDiagnostic: vi.fn(async () => { throw new Error("not implemented"); }),
    listPrograms: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
    getProgram: vi.fn(async () => { throw new Error("not implemented"); }),
    createProgram: vi.fn(async () => { throw new Error("not implemented"); }),
    updateProgram: vi.fn(async () => { throw new Error("not implemented"); }),
    listProgramExercises: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
    assignProgramExercise: vi.fn(async () => { throw new Error("not implemented"); }),
    listExercises: vi.fn(async () => []),
    listDoctors: vi.fn(async () => []),
    getMyPatient: vi.fn(async () => { throw new Error("not implemented"); }),
    listMyDiagnostics: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
    listMyPrograms: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
    getMyProgram: vi.fn(async () => { throw new Error("not implemented"); }),
    listMyProgramExercises: vi.fn(async () => ({ items: [], total: 0, limit: 20, offset: 0 })),
    createRecordingUploadUrl: vi.fn(async () => ({ key: "k", url: "/u" })),
    uploadRecordingBlob: vi.fn(async () => undefined),
    registerRecording: vi.fn(async () => ({ recording_id: "r-1" })),
    listExerciseRecordings: vi.fn(async () => []),
    deleteRecording: vi.fn(async () => undefined),
    runAnalysis: vi.fn(async () => ({ job_id: "j-1", status: "pending" })),
    getRecordingMetrics: vi.fn(async () => ({ function_name: "f", metrics: null })),
    getRecordingDownloadUrl: vi.fn(async () => "/url"),
    listProgramReports: vi.fn(async () => []),
    createReport: vi.fn(async () => ({ exercise_report_id: "rep-1" })),
    getReportDetail: vi.fn(async () => { throw new Error("not implemented"); }),
    updateReport: vi.fn(async () => undefined),
    deleteReport: vi.fn(async () => undefined),
    listProgramCheckups: vi.fn(async () => []),
    createCheckup: vi.fn(async () => ({ followup_checkup_id: "chk-1" })),
    getCheckupDetail: vi.fn(async () => { throw new Error("not implemented"); }),
    updateCheckup: vi.fn(async () => undefined),
    deleteCheckup: vi.fn(async () => undefined),
    ...overrides,
  } as DiagnosticFeatureApi;
}

function renderPanel(api: DiagnosticFeatureApi, programId = "prog-1") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <FollowupCheckupPanel api={api} programId={programId} />
    </QueryClientProvider>,
  );
}

describe("FollowupCheckupPanel", () => {
  it("shows loading state while check-ups are fetching", () => {
    const api = makeApi({
      listProgramCheckups: vi.fn((): Promise<never> => new Promise(() => {})),
    });
    renderPanel(api);
    expect(screen.getByRole("status")).toHaveTextContent("Loading check-ups…");
  });

  it("shows empty state when check-up list is empty", async () => {
    const api = makeApi({
      listProgramCheckups: vi.fn(async () => []),
    });
    renderPanel(api);
    expect(await screen.findByText("No follow-up check-ups yet.")).toBeInTheDocument();
  });

  it("shows check-up cards when list returns data", async () => {
    const api = makeApi({
      listProgramCheckups: vi.fn(async () => [
        {
          followup_checkup_id: "chk-1",
          rehab_program_id: "prog-1",
          patient_id: "pat-1",
          period_start: "2026-01-01",
          period_end: "2026-01-31",
          summary: "Patient progress good",
          report_count: 2,
        },
      ]),
    });
    renderPanel(api);
    expect(await screen.findByText(/Jan 1, 2026/)).toBeInTheDocument();
    expect(screen.getByText("2 reports")).toBeInTheDocument();
    expect(screen.getByText("Patient progress good")).toBeInTheDocument();
  });

  it("clicking New Check-up shows the create form", async () => {
    const user = userEvent.setup();
    const api = makeApi({
      listProgramCheckups: vi.fn(async () => []),
    });
    renderPanel(api);
    await user.click(await screen.findByRole("button", { name: /New Check-up/i }));
    expect(screen.getByRole("form", { name: "Create check-up form" })).toBeInTheDocument();
  });

  it("form with period_end before period_start shows a validation error without calling createCheckup", async () => {
    const user = userEvent.setup();
    const createCheckup = vi.fn(async () => ({ followup_checkup_id: "chk-new" }));
    const api = makeApi({
      listProgramCheckups: vi.fn(async () => []),
      createCheckup,
    });
    renderPanel(api);

    await user.click(await screen.findByRole("button", { name: /New Check-up/i }));

    const dateInputs = screen.getAllByDisplayValue("");
    const dateFields = screen
      .getByRole("form", { name: "Create check-up form" })
      .querySelectorAll("input[type='date']");

    await user.type(dateFields[0] as HTMLInputElement, "2026-02-01");
    await user.type(dateFields[1] as HTMLInputElement, "2026-01-01");

    await user.click(screen.getByRole("button", { name: /Create Check-up/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("End date must be on or after start date."),
    );
    expect(createCheckup).not.toHaveBeenCalled();
  });

  it("form with no reports selected shows inline error without calling createCheckup", async () => {
    const user = userEvent.setup();
    const createCheckup = vi.fn(async () => ({ followup_checkup_id: "chk-new" }));
    const api = makeApi({
      listProgramCheckups: vi.fn(async () => []),
      listProgramReports: vi.fn(async () => []),
      createCheckup,
    });
    renderPanel(api);

    await user.click(await screen.findByRole("button", { name: /New Check-up/i }));

    const form = screen.getByRole("form", { name: "Create check-up form" });
    const dateFields = form.querySelectorAll("input[type='date']");
    await user.type(dateFields[0] as HTMLInputElement, "2026-01-01");
    await user.type(dateFields[1] as HTMLInputElement, "2026-01-31");

    await user.click(screen.getByRole("button", { name: /Create Check-up/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Select at least one report."),
    );
    expect(createCheckup).not.toHaveBeenCalled();
  });

  it("period auto-selection pre-checks reports within range", async () => {
    const user = userEvent.setup();
    const api = makeApi({
      listProgramCheckups: vi.fn(async () => []),
      listProgramReports: vi.fn(async () => [
        {
          exercise_report_id: "rep-in",
          program_exercise_id: "pe-1",
          period_start: "2026-01-05",
          period_end: "2026-01-20",
          recording_count: 1,
          created_by: "dr-1",
        },
        {
          exercise_report_id: "rep-out",
          program_exercise_id: "pe-2",
          period_start: "2026-02-01",
          period_end: "2026-02-28",
          recording_count: 1,
          created_by: "dr-1",
        },
      ]),
    });
    renderPanel(api);

    await user.click(await screen.findByRole("button", { name: /New Check-up/i }));

    const form = screen.getByRole("form", { name: "Create check-up form" });
    const dateFields = form.querySelectorAll("input[type='date']");

    await user.type(dateFields[0] as HTMLInputElement, "2026-01-01");
    await user.type(dateFields[1] as HTMLInputElement, "2026-01-31");

    await waitFor(() => {
      const checkboxes = form.querySelectorAll("input[type='checkbox']");
      const repIn = Array.from(checkboxes).find(
        (cb) => (cb as HTMLInputElement).checked,
      );
      expect(repIn).toBeTruthy();
    });
  });
});
