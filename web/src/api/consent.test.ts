import { describe, expect, it, vi } from "vitest";

import type { RequestOptions } from "./http";
import { createConsentApi } from "./consent";

function makeHttp(response: unknown = undefined) {
  const request = vi.fn(async () => response) as unknown as (<T>(
    path: string,
    options?: RequestOptions,
  ) => Promise<T>) &
    ReturnType<typeof vi.fn>;
  return { http: { request }, request };
}

const STATUS = {
  consent_id: "cons-1",
  program_id: "prog-1",
  granted: true,
  granted_at: "2026-01-01T00:00:00Z",
  withdrawn_at: null,
  consent_text: "I consent to voice recording for rehabilitation purposes.",
};

describe("consent API", () => {
  it("getConsentStatus calls GET /programs/{id}/consent", async () => {
    const { http, request } = makeHttp(STATUS);
    const api = createConsentApi(http);

    await api.getConsentStatus("prog-1");

    expect(request).toHaveBeenCalledWith("/programs/prog-1/consent");
  });

  it("grantConsent calls POST /programs/{id}/consent/grant with consent_text body", async () => {
    const { http, request } = makeHttp(STATUS);
    const api = createConsentApi(http);

    await api.grantConsent("prog-1", "I consent to voice recording for rehabilitation purposes.");

    expect(request).toHaveBeenCalledWith("/programs/prog-1/consent/grant", {
      method: "POST",
      body: { consent_text: "I consent to voice recording for rehabilitation purposes." },
    });
  });

  it("withdrawConsent calls POST /programs/{id}/consent/withdraw with no body", async () => {
    const { http, request } = makeHttp({ ...STATUS, granted: false, withdrawn_at: "2026-06-01T00:00:00Z" });
    const api = createConsentApi(http);

    await api.withdrawConsent("prog-1");

    expect(request).toHaveBeenCalledWith("/programs/prog-1/consent/withdraw", {
      method: "POST",
    });
  });

  it("getConsentStatus returns the full status object", async () => {
    const { http } = makeHttp(STATUS);
    const api = createConsentApi(http);

    const result = await api.getConsentStatus("prog-1");

    expect(result).toEqual(STATUS);
  });
});
