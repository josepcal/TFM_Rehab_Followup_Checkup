import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DiagnosticOut } from "../../api/diagnostics";
import { ApiError } from "../../api/http";
import type { DiagnosticFeatureApi } from "./api";
import { DiagnosticWorkspace } from "./DiagnosticWorkspace";

const patients = [
  {
    id: "patient-1",
    nombre: "Ana",
    apellidos: "Garcia",
    birth_date: "1980-01-15",
    sex: "female",
    last_assessment: "2026-06-14T10:01:00Z",
  },
  { id: "patient-2", nombre: "Luis", apellidos: "Perez", birth_date: "1975-09-10", sex: "male" },
];

const diagnostic: DiagnosticOut = {
  id: "diag-1",
  patient_id: "patient-1",
  dolencia: "Shoulder pain",
  descripcion: "Limited range of motion",
  history: "Prior rotator cuff repair",
  symptoms: "Pain, Reduced mobility",
  created_at: "2026-06-14T10:00:00Z",
  signature: "attested:diag-1",
  signed_at: "2026-06-14T10:01:00Z",
  content_hash: "abc123",
};

function renderWorkspace(api: DiagnosticFeatureApi, mode: "diagnostics" | "programs" = "diagnostics") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <DiagnosticWorkspace api={api} mode={mode} />
    </QueryClientProvider>,
  );
}

function makeApi(overrides: Partial<DiagnosticFeatureApi> = {}): DiagnosticFeatureApi {
  return {
    listPatients: async () => patients,
    listDiagnostics: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    getDiagnostic: async () => diagnostic,
    createDiagnostic: async (body) => ({
      id: "diag-created",
      patient_id: body.patient_id,
      dolencia: body.dolencia,
      descripcion: body.descripcion,
      history: body.history,
      symptoms: body.symptoms,
      signature: "attested:diag-created",
      signed_at: "2026-06-14T11:00:00Z",
      content_hash: "created-hash",
    }),
    updateDiagnostic: async (_diagnosticId, body) => ({
      ...diagnostic,
      ...body,
    }),
    listPrograms: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    getProgram: async () => {
      throw new Error("Not implemented in diagnostic tests");
    },
    createProgram: async (body) => ({
      id: "program-created",
      diagnostic_id: body.diagnostic_id,
      estado: body.estado ?? "active",
      name: body.name,
      start_date: body.start_date,
      end_date: body.end_date,
      physiotherapist_id: body.physiotherapist_id,
    }),
    updateProgram: async (programId, body) => ({
      id: programId,
      diagnostic_id: "diag-1",
      estado: body.estado ?? "active",
      name: body.name,
      start_date: body.start_date,
      end_date: body.end_date,
      physiotherapist_id: body.physiotherapist_id,
    }),
    listProgramExercises: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    assignProgramExercise: async (programId, body) => ({
      id: "assignment-created",
      program_id: programId,
      exercise_id: body.exercise_id,
      pauta: body.pauta,
      estado: "active",
    }),
    listExercises: async () => [],
    listDoctors: async () => [
      {
        id: "22222222-2222-4222-8222-222222222222",
        nombre: "Elena",
        apellidos: "Marsh",
        doctor_type: "physiotherapist",
        colegiado_id: "COL-22",
      },
    ],
    getMyPatient: async () => ({ id: "patient-1", nombre: "Ana", apellidos: "Garcia" }),
    listMyDiagnostics: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    listMyPrograms: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    getMyProgram: async (programId) => ({ id: programId, diagnostic_id: "diag-1", estado: "active", name: "Mobility plan" }),
    listMyProgramExercises: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
    createRecordingUploadUrl: async () => ({ key: "recording.wav", url: "/api/recordings/_local-upload/recording.wav" }),
    uploadRecordingBlob: async () => undefined,
    registerRecording: async () => ({ recording_id: "recording-1" }),
    listExerciseRecordings: async () => [],
    runAnalysis: async () => ({ job_id: "job-1", status: "pending" }),
    getRecordingMetrics: async () => ({ function_name: "dysarthria_analysis_v1", metrics: null }),
    ...overrides,
  };
}

describe("UC-01 AC-01 diagnostic history UI", () => {
  it("GIVEN a medical user WHEN selecting a patient THEN displays diagnostic history", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        listDiagnostics: async (params) => ({
          items: [{ ...diagnostic, patient_id: params?.patientId ?? "patient-1" }],
          total: 1,
          limit: 20,
          offset: 0,
        }),
      }),
    );

    await openPatient(user, /ana garcia clinical record/i);

    expect(await screen.findAllByText("Shoulder pain")).toHaveLength(1);
    expect(screen.getByText("Limited range of motion")).toBeInTheDocument();
  });

  it("GIVEN a selected patient with no diagnostics WHEN history loads THEN displays empty state", async () => {
    const user = userEvent.setup();
    renderWorkspace(makeApi());

    await openPatient(user, /luis perez clinical record/i);

    expect(await screen.findByText(/no diagnostics exist/i)).toBeInTheDocument();
  });

  it("GIVEN forbidden history WHEN API returns 403 THEN clears stale records and shows auth error", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        listDiagnostics: async () => {
          throw new ApiError("Forbidden", 403);
        },
      }),
    );

    await openPatient(user, /ana garcia clinical record/i);

    expect(await screen.findByText(/not authorized/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByLabelText("Diagnostic history")).not.toBeInTheDocument());
  });
});


  it("GIVEN accented patient names WHEN searching without accents or punctuation THEN matches the patient", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        listPatients: async () => [
          { id: "patient-acentos", nombre: "José", apellidos: "García-López" },
          { id: "patient-plain", nombre: "Luis", apellidos: "Perez" },
        ],
      }),
    );

    await user.type(await screen.findByLabelText(/search by name or patient id/i), "jose garcia lopez");

    expect(screen.getByRole("button", { name: /josé garcía-lópez clinical record/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /luis perez clinical record/i })).not.toBeInTheDocument();
  });

  it("GIVEN patients with demographics WHEN listing patients THEN displays age, sex and last assessment columns", async () => {
    renderWorkspace(makeApi());

    expect(await screen.findByRole("columnheader", { name: /age/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /sex/i })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /last assessment/i })).toBeInTheDocument();
    expect(screen.getByText("Female")).toBeInTheDocument();
    expect(screen.getByText("Male")).toBeInTheDocument();
    expect(screen.getByText("Jun 14, 2026")).toBeInTheDocument();
  });

describe("UC-01 AC-03 diagnostic create/detail/edit UI", () => {
  it("GIVEN selected patient WHEN creating diagnostic THEN sends patient_id without doctor_id", async () => {
    const user = userEvent.setup();
    const createDiagnostic = vi.fn(makeApi().createDiagnostic);
    renderWorkspace(makeApi({ createDiagnostic }));

    await openPatient(user, /ana garcia clinical record/i);
    await startNewDiagnostic(user);
    await user.type(screen.getByLabelText(/^dolencia$/i), "Knee pain");
    await user.type(screen.getByLabelText(/description/i), "Pain when walking");
    await user.type(screen.getByLabelText(/history/i), "Sports injury two years ago");
    const symptomsInput = screen.getByLabelText(/symptoms/i);
    await user.type(symptomsInput, "Pain{enter}");
    await user.type(symptomsInput, "Instability{enter}");
    await user.click(screen.getByRole("button", { name: /create diagnostic/i }));

    await waitFor(() => expect(createDiagnostic).toHaveBeenCalled());
    expect(createDiagnostic).toHaveBeenCalledWith({
      patient_id: "patient-1",
      dolencia: "Knee pain",
      descripcion: "Pain when walking",
      history: "Sports injury two years ago",
      symptoms: "Pain, Instability",
    });
    expect(JSON.stringify(createDiagnostic.mock.calls[0][0])).not.toContain("doctor_id");
  });

  it("GIVEN empty dolencia WHEN creating diagnostic THEN prevents submission", async () => {
    const user = userEvent.setup();
    const createDiagnostic = vi.fn(makeApi().createDiagnostic);
    renderWorkspace(makeApi({ createDiagnostic }));

    await openPatient(user, /ana garcia clinical record/i);
    await startNewDiagnostic(user);
    expect(screen.getByRole("button", { name: /create diagnostic/i })).toBeDisabled();

    expect(createDiagnostic).not.toHaveBeenCalled();
  });

  it("GIVEN selected diagnostic WHEN opening detail THEN displays attestation metadata", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        listDiagnostics: async () => ({ items: [diagnostic], total: 1, limit: 20, offset: 0 }),
      }),
    );

    await openPatient(user, /ana garcia clinical record/i);
    await user.click(await screen.findByRole("button", { name: /shoulder pain/i }));

    expect(await screen.findByText("Description")).toBeInTheDocument();
    expect(screen.getByText("History")).toBeInTheDocument();
    expect(screen.getByText("Symptoms")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /attestation/i })).toBeInTheDocument();
    expect((await screen.findAllByLabelText(/diagnostic detail/i)).at(-1)).toHaveTextContent("attested:diag-1");
    expect(screen.getByText("abc123")).toBeInTheDocument();
  });

  it("GIVEN selected diagnostic WHEN editing THEN sends PATCH body and shows updated diagnostic", async () => {
    const user = userEvent.setup();
    const updateDiagnostic = vi.fn(makeApi().updateDiagnostic);
    renderWorkspace(
      makeApi({
        listDiagnostics: async () => ({ items: [diagnostic], total: 1, limit: 20, offset: 0 }),
        updateDiagnostic,
      }),
    );

    await openPatient(user, /ana garcia clinical record/i);
    await user.click(await screen.findByRole("button", { name: /shoulder pain/i }));
    await user.click(await screen.findByRole("button", { name: /edit diagnostic/i }));
    const editForm = await screen.findByRole("form", { name: /edit diagnostic/i });
    const dolenciaInput = withinForm(editForm, /^dolencia$/i);
    await user.clear(dolenciaInput);
    await user.type(dolenciaInput, "Updated shoulder pain");
    await user.click(screen.getByRole("button", { name: /save draft/i }));

    await waitFor(() => expect(updateDiagnostic).toHaveBeenCalled());
    expect(updateDiagnostic).toHaveBeenCalledWith("diag-1", {
      dolencia: "Updated shoulder pain",
      descripcion: "Limited range of motion",
      history: "Prior rotator cuff repair",
      symptoms: "Pain, Reduced mobility",
    });
  });

  it("GIVEN missing patient WHEN create returns 404 THEN displays recoverable error", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        createDiagnostic: async () => {
          throw new ApiError("Not found", 404);
        },
      }),
    );

    await openPatient(user, /ana garcia clinical record/i);
    await startNewDiagnostic(user);
    await user.type(screen.getByLabelText(/^dolencia$/i), "Back pain");
    await user.click(screen.getByRole("button", { name: /create diagnostic/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/not found/i);
    expect(screen.getByDisplayValue("Back pain")).toBeInTheDocument();
  });

  it("GIVEN forbidden edit WHEN API returns 403 THEN does not show save success", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        listDiagnostics: async () => ({ items: [diagnostic], total: 1, limit: 20, offset: 0 }),
        updateDiagnostic: async () => {
          throw new ApiError("Forbidden", 403);
        },
      }),
    );

    await openPatient(user, /ana garcia clinical record/i);
    await user.click(await screen.findByRole("button", { name: /shoulder pain/i }));
    await user.click(await screen.findByRole("button", { name: /edit diagnostic/i }));
    await user.click(await screen.findByRole("button", { name: /save draft/i }));

    expect(await screen.findByText(/not authorized/i)).toBeInTheDocument();
  });
});

describe("UC-02 rehab program setup UI", () => {
  it("GIVEN a diagnostic detail WHEN creating a rehab program THEN sends diagnostic_id and metadata", async () => {
    const user = userEvent.setup();
    const createProgram = vi.fn(makeApi().createProgram);
    renderWorkspace(
      makeApi({
        listDiagnostics: async () => ({ items: [diagnostic], total: 1, limit: 20, offset: 0 }),
        listPrograms: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
        createProgram,
      }),
    );

    await openPatient(user, /ana garcia clinical record/i);
    await user.click(await screen.findByRole("button", { name: /shoulder pain/i }));
    await user.click(await screen.findByRole("button", { name: /setup rehab program/i }));
    await user.type(screen.getByLabelText(/program name/i), "Plan de movilidad");
    await user.click(screen.getByRole("button", { name: /^create rehab program$/i }));

    await waitFor(() => expect(createProgram).toHaveBeenCalled());
    expect(createProgram).toHaveBeenCalledWith({
      diagnostic_id: "diag-1",
      estado: "active",
      name: "Plan de movilidad",
      start_date: null,
      end_date: null,
    });
  });

  it("GIVEN a selected rehab program WHEN editing metadata THEN patches program setup", async () => {
    const user = userEvent.setup();
    const updateProgram = vi.fn(makeApi().updateProgram);
    renderWorkspace(
      makeApi({
        updateProgram,
        listPrograms: async () => ({
          items: [
            {
              id: "program-1",
              diagnostic_id: "diag-1",
              estado: "active",
              name: "Plan de movilidad",
              physiotherapist_id: "11111111-1111-4111-8111-111111111111",
              start_date: "2026-06-16T00:00:00Z",
            },
          ],
          total: 1,
          limit: 20,
          offset: 0,
        }),
        getProgram: async () => ({
          id: "program-1",
          diagnostic_id: "diag-1",
          estado: "active",
          name: "Plan de movilidad",
          physiotherapist_id: "11111111-1111-4111-8111-111111111111",
          start_date: "2026-06-16T00:00:00Z",
        }),
      }),
      "programs",
    );

    await user.click(await screen.findByRole("button", { name: /plan de movilidad/i }));
    await user.click(screen.getByRole("button", { name: /edit program/i }));
    const editForm = await screen.findByRole("form", { name: /edit program form/i });
    const programName = withinForm(editForm, /program name/i) as HTMLInputElement;
    await user.clear(programName);
    await user.type(programName, "Updated mobility plan");
    await user.click(screen.getByRole("button", { name: /assign from doctor list/i }));
    await user.click(await screen.findByRole("button", { name: /dr\. elena marsh/i }));
    await user.click(screen.getByRole("button", { name: /save draft/i }));

    await waitFor(() => expect(updateProgram).toHaveBeenCalled());
    expect(updateProgram).toHaveBeenCalledWith("program-1", {
      name: "Updated mobility plan",
      estado: "active",
      physiotherapist_id: "22222222-2222-4222-8222-222222222222",
      start_date: "2026-06-16T00:00:00Z",
      end_date: null,
    });
  });

  it("GIVEN a selected rehab program WHEN assigning an exercise THEN posts assignment and refreshes the table", async () => {
    const user = userEvent.setup();
    const assignments = [
      {
        id: "assignment-existing",
        program_id: "program-1",
        exercise_id: "exercise-existing",
        pauta: "Warm-up daily",
        estado: "active",
        created_at: "2026-06-15T00:00:00Z",
      },
    ];
    const assignProgramExercise = vi.fn(async (programId, body) => {
      const assignment = {
        id: "assignment-created",
        program_id: programId,
        exercise_id: body.exercise_id,
        pauta: body.pauta,
        estado: "active",
        created_at: "2026-06-16T00:00:00Z",
      };
      assignments.push(assignment);
      return assignment;
    });
    const listProgramExercises = vi.fn(async () => ({
      items: assignments,
      total: assignments.length,
      limit: 20,
      offset: 0,
    }));

    renderWorkspace(
      makeApi({
        listPrograms: async () => ({
          items: [
            {
              id: "program-1",
              diagnostic_id: "diag-1",
              estado: "active",
              name: "Plan de movilidad",
              physiotherapist_id: "11111111-1111-4111-8111-111111111111",
            },
          ],
          total: 1,
          limit: 20,
          offset: 0,
        }),
        getProgram: async () => ({
          id: "program-1",
          diagnostic_id: "diag-1",
          estado: "active",
          name: "Plan de movilidad",
          physiotherapist_id: "11111111-1111-4111-8111-111111111111",
        }),
        listExercises: async () => [
          { id: "exercise-existing", nombre: "Movilidad cervical", tipo: "mobility" },
          { id: "exercise-1", nombre: "Fonación sostenida", tipo: "voice" },
        ],
        listProgramExercises,
        assignProgramExercise,
      }),
      "programs",
    );

    await user.click(await screen.findByRole("button", { name: /plan de movilidad/i }));

    expect(await screen.findByText("Movilidad cervical")).toBeInTheDocument();
    expect(screen.getByText("1 exercise")).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: /assign exercise/i })).not.toBeInTheDocument();
    expect(screen.getByText("11111111-1111-4111-8111-111111111111")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /edit program/i }));
    await user.selectOptions(await screen.findByRole("combobox", { name: /^exercise$/i }), "exercise-1");
    await user.type(screen.getByLabelText(/pauta/i), "2 series diarias");
    await user.click(screen.getByRole("button", { name: /^assign exercise$/i }));

    await waitFor(() => expect(assignProgramExercise).toHaveBeenCalled());
    expect(assignProgramExercise).toHaveBeenCalledWith("program-1", {
      exercise_id: "exercise-1",
      pauta: "2 series diarias",
    });
    await waitFor(() => expect(listProgramExercises).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Fonación sostenida")).toBeInTheDocument();
    expect(screen.getAllByText("2 series diarias").length).toBeGreaterThan(0);
  });

  it("GIVEN a selected rehab program without exercises WHEN exercise list loads THEN shows empty assignment state", async () => {
    const user = userEvent.setup();
    renderWorkspace(
      makeApi({
        listPrograms: async () => ({
          items: [
            {
              id: "program-1",
              diagnostic_id: "diag-1",
              estado: "active",
              name: "Plan de movilidad",
              physiotherapist_id: "11111111-1111-4111-8111-111111111111",
            },
          ],
          total: 1,
          limit: 20,
          offset: 0,
        }),
        getProgram: async () => ({
          id: "program-1",
          diagnostic_id: "diag-1",
          estado: "active",
          name: "Plan de movilidad",
          physiotherapist_id: "11111111-1111-4111-8111-111111111111",
        }),
        listExercises: async () => [{ id: "exercise-1", nombre: "Fonación sostenida", tipo: "voice" }],
        listProgramExercises: async () => ({ items: [], total: 0, limit: 20, offset: 0 }),
      }),
      "programs",
    );

    await user.click(await screen.findByRole("button", { name: /plan de movilidad/i }));

    expect(await screen.findByText(/no exercises assigned yet/i)).toBeInTheDocument();
    expect(screen.getByText("0 exercises")).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: /assign exercise/i })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /edit program/i }));
    expect(screen.getByRole("form", { name: /assign exercise/i })).toBeInTheDocument();
  });

  it("GIVEN top-level rehab programs mode WHEN programs load THEN lists and opens owned programs", async () => {
    const user = userEvent.setup();
    const listPrograms = vi.fn(async () => ({
      items: [
        {
          id: "program-1",
          diagnostic_id: "diag-1",
          estado: "active",
          name: "Plan de movilidad",
          start_date: "2026-06-16T00:00:00Z",
          physiotherapist_id: "11111111-1111-4111-8111-111111111111",
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    }));
    renderWorkspace(
      makeApi({
        listPrograms,
        getProgram: async () => ({
          id: "program-1",
          diagnostic_id: "diag-1",
          estado: "active",
          name: "Plan de movilidad",
          start_date: "2026-06-16T00:00:00Z",
          physiotherapist_id: "11111111-1111-4111-8111-111111111111",
        }),
      }),
      "programs",
    );

    expect(await screen.findByText("Plan de movilidad")).toBeInTheDocument();
    expect(listPrograms).toHaveBeenCalledWith({});
    await user.click(screen.getByRole("button", { name: /plan de movilidad/i }));

    const detail = await screen.findByLabelText(/rehab program detail/i);
    expect(detail).toHaveTextContent("Linked diagnostic");
    expect(detail).toHaveTextContent("11111111-1111-4111-8111-111111111111");
    expect(detail).toHaveTextContent("Jun 16, 2026");
  });
});

function withinForm(form: HTMLElement, label: RegExp) {
  return Array.from(form.querySelectorAll("input, textarea")).find((input) => {
    const id = input.getAttribute("id");
    if (!id) {
      return input.previousElementSibling?.textContent?.match(label);
    }
    return form.querySelector(`label[for="${id}"]`)?.textContent?.match(label);
  }) as HTMLInputElement | HTMLTextAreaElement;
}


async function openPatient(user: ReturnType<typeof userEvent.setup>, name: RegExp) {
  await user.click(await screen.findByRole("button", { name }));
}

async function startNewDiagnostic(user: ReturnType<typeof userEvent.setup>) {
  await user.click((await screen.findAllByRole("button", { name: /new diagnostic|create first diagnostic/i }))[0]);
}
