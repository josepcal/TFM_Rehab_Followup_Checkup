import { describe, expect, it, vi } from "vitest";

import type { RequestOptions } from "./http";
import { createPatientPortalApi } from "./patientPortal";

function makeHttp(response: unknown = { data: [], total: 0, limit: 20, offset: 0 }) {
  const request = vi.fn(async () => response) as unknown as (<T>(
    path: string,
    options?: RequestOptions,
  ) => Promise<T>) &
    ReturnType<typeof vi.fn>;
  return { http: { request }, request };
}

describe("patient portal API", () => {
  it("loads patient profile, diagnostics and programs", async () => {
    const { http, request } = makeHttp({ data: [], total: 0, limit: 20, offset: 0 });
    const api = createPatientPortalApi(http);

    await api.getMyPatient();
    await api.listMyDiagnostics();
    await api.listMyPrograms();
    await api.getMyProgram("program-1");
    await api.listMyProgramExercises("program-1");

    expect(request).toHaveBeenNthCalledWith(1, "/patients/me");
    expect(request).toHaveBeenNthCalledWith(2, "/patients/me/diagnostics?limit=20&offset=0");
    expect(request).toHaveBeenNthCalledWith(3, "/patients/me/programs?limit=20&offset=0");
    expect(request).toHaveBeenNthCalledWith(4, "/patients/me/programs/program-1");
    expect(request).toHaveBeenNthCalledWith(5, "/patients/me/programs/program-1/exercises?limit=20&offset=0");
  });
});
