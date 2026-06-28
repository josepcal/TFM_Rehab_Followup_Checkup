import { describe, expect, it, vi } from "vitest";

import type { RequestOptions } from "./http";
import { createFollowupCheckupsApi } from "./followupCheckups";
import type { CheckupIn } from "./followupCheckups";

function makeHttp(response: unknown = []) {
  const request = vi.fn(async () => response) as unknown as (<T>(
    path: string,
    options?: RequestOptions,
  ) => Promise<T>) &
    ReturnType<typeof vi.fn>;
  return { http: { request }, request };
}

describe("UC-09 followup checkups API", () => {
  it("listProgramCheckups calls GET /programs/{id}/followup-checkups", async () => {
    const { http, request } = makeHttp([]);
    const api = createFollowupCheckupsApi(http);

    await api.listProgramCheckups("prog-1");

    expect(request).toHaveBeenCalledWith("/programs/prog-1/followup-checkups");
  });

  it("createCheckup calls POST /followup-checkups with correct body", async () => {
    const { http, request } = makeHttp({ followup_checkup_id: "chk-1" });
    const api = createFollowupCheckupsApi(http);

    const body: CheckupIn = {
      rehab_program_id: "prog-1",
      exercise_report_ids: ["rep-1", "rep-2"],
      period_start: "2026-01-01",
      period_end: "2026-01-31",
      summary: "Test summary",
    };

    await api.createCheckup(body);

    expect(request).toHaveBeenCalledWith("/followup-checkups", {
      method: "POST",
      body,
    });
  });

  it("getCheckupDetail calls GET /followup-checkups/{id}", async () => {
    const { http, request } = makeHttp({ followup_checkup_id: "chk-1", reports: [] });
    const api = createFollowupCheckupsApi(http);

    await api.getCheckupDetail("chk-1");

    expect(request).toHaveBeenCalledWith("/followup-checkups/chk-1");
  });

  it("updateCheckup calls PATCH /followup-checkups/{id} with { summary }", async () => {
    const { http, request } = makeHttp();
    const api = createFollowupCheckupsApi(http);

    await api.updateCheckup("chk-1", "Updated summary");

    expect(request).toHaveBeenCalledWith("/followup-checkups/chk-1", {
      method: "PATCH",
      body: { summary: "Updated summary" },
    });
  });

  it("deleteCheckup calls DELETE /followup-checkups/{id}", async () => {
    const { http, request } = makeHttp();
    const api = createFollowupCheckupsApi(http);

    await api.deleteCheckup("chk-1");

    expect(request).toHaveBeenCalledWith("/followup-checkups/chk-1", { method: "DELETE" });
  });
});
