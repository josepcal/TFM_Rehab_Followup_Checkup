import { describe, expect, it, vi } from "vitest";

import type { RequestOptions } from "./http";
import { createAuditLogApi } from "./auditLog";

function makeHttp(response: unknown = []) {
  const request = vi.fn(async () => response) as unknown as (<T>(
    path: string,
    options?: RequestOptions,
  ) => Promise<T>) &
    ReturnType<typeof vi.fn>;
  return { http: { request }, request };
}

describe("audit log API", () => {
  it("getAuditLog calls GET /iam/audit-log with no query string when no filters", async () => {
    const { http, request } = makeHttp([]);
    const api = createAuditLogApi(http);

    await api.getAuditLog();

    expect(request).toHaveBeenCalledWith("/iam/audit-log");
  });

  it("getAuditLog appends actor_id filter to query string", async () => {
    const { http, request } = makeHttp([]);
    const api = createAuditLogApi(http);

    await api.getAuditLog({ actor_id: "user-123" });

    expect(request).toHaveBeenCalledWith("/iam/audit-log?actor_id=user-123");
  });

  it("getAuditLog appends entity_type filter to query string", async () => {
    const { http, request } = makeHttp([]);
    const api = createAuditLogApi(http);

    await api.getAuditLog({ entity_type: "recording.exercise_recording" });

    expect(request).toHaveBeenCalledWith("/iam/audit-log?entity_type=recording.exercise_recording");
  });

  it("getAuditLog appends pagination params to query string", async () => {
    const { http, request } = makeHttp([]);
    const api = createAuditLogApi(http);

    await api.getAuditLog({ limit: 50, offset: 100 });

    expect(request).toHaveBeenCalledWith("/iam/audit-log?limit=50&offset=100");
  });

  it("getAuditLog appends multiple filters combined", async () => {
    const { http, request } = makeHttp([]);
    const api = createAuditLogApi(http);

    await api.getAuditLog({
      actor_id: "user-1",
      entity_type: "clinical.patient",
      from_ts: "2026-01-01T00:00:00Z",
      to_ts: "2026-06-30T23:59:59Z",
      limit: 25,
      offset: 0,
    });

    const [[calledPath]] = request.mock.calls;
    expect(calledPath).toContain("actor_id=user-1");
    expect(calledPath).toContain("entity_type=clinical.patient");
    expect(calledPath).toContain("from_ts=2026-01-01T00%3A00%3A00Z");
    expect(calledPath).toContain("limit=25");
    expect(calledPath).toContain("offset=0");
  });

  it("getAuditLog returns the entries list", async () => {
    const entries = [
      {
        event_id: "evt-1",
        entity_type: "recording.exercise_recording",
        entity_id: "rec-1",
        action: "create",
        actor_id: "user-1",
        payload: null,
        occurred_at: "2026-05-01T10:00:00Z",
      },
    ];
    const { http } = makeHttp(entries);
    const api = createAuditLogApi(http);

    const result = await api.getAuditLog();

    expect(result).toEqual(entries);
  });
});
