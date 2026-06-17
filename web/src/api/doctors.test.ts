import { describe, expect, it, vi } from "vitest";

import type { RequestOptions } from "./http";
import { createDoctorsApi } from "./doctors";

function makeHttp(response: unknown = []) {
  const request = vi.fn(async () => response) as unknown as (<T>(
    path: string,
    options?: RequestOptions,
  ) => Promise<T>) &
    ReturnType<typeof vi.fn>;
  return { http: { request }, request };
}

describe("doctors API", () => {
  it("lists doctors for physiotherapist assignment", async () => {
    const { http, request } = makeHttp([{ id: "doctor-1", nombre: "Ana", apellidos: "Marsh", doctor_type: "physio" }]);
    const api = createDoctorsApi(http);

    const doctors = await api.listDoctors();

    expect(request).toHaveBeenCalledWith("/doctors");
    expect(doctors).toHaveLength(1);
  });
});
