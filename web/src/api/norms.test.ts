import { describe, expect, it, vi } from "vitest";

import type { RequestOptions } from "./http";
import { createNormsApi } from "./norms";

function makeHttp(response: unknown = undefined) {
  const request = vi.fn(async () => response) as unknown as (<T>(
    path: string,
    options?: RequestOptions,
  ) => Promise<T>) &
    ReturnType<typeof vi.fn>;
  return { http: { request }, request };
}

const NORM = {
  norm_id: "norm-1",
  metric_code: "phonation_seconds",
  label: "Maximum phonation time",
  unit: "s",
  direction: "higher_better" as const,
  sex: null,
  age_min: null,
  age_max: null,
  good_min: 15,
  good_max: null,
  poor_min: null,
  poor_max: 8,
  source: "clinical-reference-2023",
  version: 1,
};

describe("norms API", () => {
  it("listNorms calls GET /norms", async () => {
    const { http, request } = makeHttp([NORM]);
    const api = createNormsApi(http);

    await api.listNorms();

    expect(request).toHaveBeenCalledWith("/norms");
  });

  it("listNorms returns the full norm list", async () => {
    const { http } = makeHttp([NORM]);
    const api = createNormsApi(http);

    const result = await api.listNorms();

    expect(result).toEqual([NORM]);
  });

  it("getNorm calls GET /norms/{metricCode}", async () => {
    const { http, request } = makeHttp(NORM);
    const api = createNormsApi(http);

    await api.getNorm("phonation_seconds");

    expect(request).toHaveBeenCalledWith("/norms/phonation_seconds");
  });

  it("getNorm returns the norm object", async () => {
    const { http } = makeHttp(NORM);
    const api = createNormsApi(http);

    const result = await api.getNorm("phonation_seconds");

    expect(result).toEqual(NORM);
  });
});
