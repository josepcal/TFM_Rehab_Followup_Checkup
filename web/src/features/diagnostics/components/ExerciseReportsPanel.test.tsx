import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DiagnosticFeatureApi } from "../api";
import { ExerciseReportsPanel } from "./ExerciseReportsPanel";

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
    listProgramReports: vi.fn(async () => []),
    createReport: vi.fn(async () => ({ exercise_report_id: "rep-1" })),
    getReportDetail: vi.fn(async () => { throw new Error("not implemented"); }),
    updateReport: vi.fn(async () => undefined),
    deleteReport: vi.fn(async () => { throw new Error("Delete is not yet supported by the API."); }),
    ...overrides,
  } as DiagnosticFeatureApi;
}

function renderPanel(api: DiagnosticFeatureApi, programId = "prog-1") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ExerciseReportsPanel api={api} programId={programId} />
    </QueryClientProvider>,
  );
}

describe("ExerciseReportsPanel", () => {
  it("shows loading state while reports are fetching", () => {
    const api = makeApi({
      listProgramReports: vi.fn((): Promise<never> => new Promise(() => {})),
    });
    renderPanel(api);
    expect(screen.getByRole("status")).toHaveTextContent("Loading reports…");
  });

  it("shows empty state when report list is empty", async () => {
    const api = makeApi({
      listProgramReports: vi.fn(async () => []),
    });
    renderPanel(api);
    expect(await screen.findByText("No exercise reports yet.")).toBeInTheDocument();
  });

  it("shows report cards when list returns data", async () => {
    const api = makeApi({
      listProgramReports: vi.fn(async () => [
        {
          exercise_report_id: "rep-1",
          program_exercise_id: "pe-1",
          period_start: "2026-01-01",
          period_end: "2026-01-31",
          summary: "Monthly check",
          created_by: "dr-smith",
          recording_count: 3,
        },
      ]),
    });
    renderPanel(api);
    expect(await screen.findByText(/Jan 1, 2026/)).toBeInTheDocument();
    expect(screen.getByText("3 recordings")).toBeInTheDocument();
    expect(screen.getByText("dr-smith")).toBeInTheDocument();
    expect(screen.getByText("Monthly check")).toBeInTheDocument();
  });

  it("clicking New Report shows the create form", async () => {
    const user = userEvent.setup();
    const api = makeApi({
      listProgramReports: vi.fn(async () => []),
    });
    renderPanel(api);
    await user.click(await screen.findByRole("button", { name: "New Report" }));
    expect(screen.getByRole("form", { name: "Create report form" })).toBeInTheDocument();
  });

  it("form with period_end before period_start shows a validation error without calling createReport", async () => {
    const user = userEvent.setup();
    const createReport = vi.fn(async () => ({ exercise_report_id: "rep-new" }));
    const api = makeApi({
      listProgramReports: vi.fn(async () => []),
      listProgramExercises: vi.fn(async () => ({
        items: [{ id: "pe-1", program_id: "prog-1", exercise_id: "ex-1" }],
        total: 1,
        limit: 20,
        offset: 0,
      })),
      createReport,
    });
    renderPanel(api);

    await user.click(await screen.findByRole("button", { name: "New Report" }));
    const form = screen.getByRole("form", { name: "Create report form" });

    const selects = form.querySelectorAll("select");
    await user.selectOptions(selects[0] as HTMLSelectElement, "pe-1");

    const dateInputs = form.querySelectorAll("input[type='date']");
    await user.type(dateInputs[0] as HTMLInputElement, "2026-02-01");
    await user.type(dateInputs[1] as HTMLInputElement, "2026-01-01");

    await user.click(screen.getByRole("button", { name: "Create Report" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("End date must be on or after start date."),
    );
    expect(createReport).not.toHaveBeenCalled();
  });
});
