import { describe, expect, it, vi } from "vitest";

import type { RequestOptions } from "./http";
import { createProgramsApi } from "./programs";

function makeHttp(response: unknown = { data: [], total: 0, limit: 20, offset: 0 }) {
  const request = vi.fn(async () => response) as unknown as (<T>(
    path: string,
    options?: RequestOptions,
  ) => Promise<T>) &
    ReturnType<typeof vi.fn>;
  return { http: { request }, request };
}

describe("UC-02 programs API", () => {
  it("builds doctor-wide program search query without requiring diagnostic id", async () => {
    const { http, request } = makeHttp({ data: [{ id: "program-1" }], total: 1, limit: 10, offset: 5 });
    const api = createProgramsApi(http);

    const page = await api.listPrograms({ limit: 10, offset: 5 });

    expect(request).toHaveBeenCalledWith("/programs/?limit=10&offset=5");
    expect(page.items).toEqual([{ id: "program-1" }]);
  });

  it("builds diagnostic and patient filters for program search", async () => {
    const { http, request } = makeHttp();
    const api = createProgramsApi(http);

    await api.listPrograms({ diagnosticId: "diag-1", patientId: "patient-1" });

    expect(request).toHaveBeenCalledWith(
      "/programs/?limit=20&offset=0&diagnostic_id=diag-1&patient_id=patient-1",
    );
  });

  it("sends program create payload", async () => {
    const { http, request } = makeHttp({ id: "program-1", diagnostic_id: "diag-1", estado: "active" });
    const api = createProgramsApi(http);

    await api.createProgram({ diagnostic_id: "diag-1", name: "Plan de movilidad" });

    expect(request).toHaveBeenCalledWith("/programs/", {
      method: "POST",
      body: { diagnostic_id: "diag-1", name: "Plan de movilidad" },
    });
  });

  it("lists and assigns program exercises", async () => {
    const { http, request } = makeHttp({ data: [{ id: "assignment-1" }], total: 1, limit: 20, offset: 0 });
    const api = createProgramsApi(http);

    await api.listProgramExercises("program-1");
    await api.assignProgramExercise("program-1", { exercise_id: "exercise-1", pauta: "2 series" });

    expect(request).toHaveBeenNthCalledWith(1, "/programs/program-1/exercises?limit=20&offset=0");
    expect(request).toHaveBeenNthCalledWith(2, "/programs/program-1/exercises", {
      method: "POST",
      body: { exercise_id: "exercise-1", pauta: "2 series" },
    });
  });
});
