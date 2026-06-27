import { describe, expect, it, vi } from "vitest";

import type { RequestOptions } from "./http";
import { createReportsApi } from "./reports";
import type { ReportIn } from "./reports";

function makeHttp(response: unknown = []) {
  const request = vi.fn(async () => response) as unknown as (<T>(
    path: string,
    options?: RequestOptions,
  ) => Promise<T>) &
    ReturnType<typeof vi.fn>;
  return { http: { request }, request };
}

describe("UC-08 reports API", () => {
  it("listProgramReports calls GET /programs/{id}/reports", async () => {
    const { http, request } = makeHttp([]);
    const api = createReportsApi(http);

    await api.listProgramReports("pid");

    expect(request).toHaveBeenCalledWith("/programs/pid/reports");
  });

  it("createReport calls POST /reports with body", async () => {
    const { http, request } = makeHttp({ exercise_report_id: "rep-1" });
    const api = createReportsApi(http);

    const body: ReportIn = {
      program_exercise_id: "pe-1",
      recording_ids: ["rec-1", "rec-2"],
      period_start: "2026-01-01",
      period_end: "2026-01-31",
      summary: "Test summary",
    };

    await api.createReport(body);

    expect(request).toHaveBeenCalledWith("/reports", {
      method: "POST",
      body,
    });
  });

  it("getReportDetail calls GET /reports/{id}", async () => {
    const { http, request } = makeHttp({ exercise_report_id: "rid", recordings: [] });
    const api = createReportsApi(http);

    await api.getReportDetail("rid");

    expect(request).toHaveBeenCalledWith("/reports/rid");
  });

  it("deleteReport throws Error without calling http", async () => {
    const { http, request } = makeHttp();
    const api = createReportsApi(http);

    await expect(api.deleteReport("rid")).rejects.toThrow(
      "Delete is not yet supported by the API.",
    );
    expect(request).not.toHaveBeenCalled();
  });
});
