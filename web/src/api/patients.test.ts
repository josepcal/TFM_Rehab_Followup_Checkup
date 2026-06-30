import { describe, expect, it, vi } from "vitest";

import type { RequestOptions } from "./http";
import { createPatientsApi } from "./patients";

function makeHttp(response: unknown = []) {
  const request = vi.fn(async () => response) as unknown as (<T>(
    path: string,
    options?: RequestOptions,
  ) => Promise<T>) &
    ReturnType<typeof vi.fn>;
  return { http: { request }, request };
}

describe("patients API", () => {
  it("listPatients calls GET /patients", async () => {
    const { http, request } = makeHttp([]);
    const api = createPatientsApi(http);

    await api.listPatients();

    expect(request).toHaveBeenCalledWith("/patients");
  });

  it("listPatients returns patient list", async () => {
    const patients = [
      { id: "p-1", nombre: "Ana", apellidos: "García", birth_date: null, sex: null, last_assessment: null },
      { id: "p-2", nombre: "Juan", apellidos: "López", birth_date: "1985-03-12", sex: "male", last_assessment: "2026-05-01T10:00:00Z" },
    ];
    const { http } = makeHttp(patients);
    const api = createPatientsApi(http);

    const result = await api.listPatients();

    expect(result).toEqual(patients);
  });

  it("listPatients returns empty array when no patients", async () => {
    const { http } = makeHttp([]);
    const api = createPatientsApi(http);

    const result = await api.listPatients();

    expect(result).toEqual([]);
  });
});
