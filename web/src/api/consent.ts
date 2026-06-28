import type { RequestOptions } from "./http";

export type ConsentStatus = {
  consent_id: string | null;
  program_id: string;
  granted: boolean;
  granted_at: string | null;
  withdrawn_at: string | null;
  consent_text: string | null;
};

export type ConsentApi = {
  getConsentStatus(programId: string): Promise<ConsentStatus>;
  grantConsent(programId: string, consentText: string): Promise<ConsentStatus>;
  withdrawConsent(programId: string): Promise<ConsentStatus>;
};

type HttpClient = {
  request: <T>(path: string, options?: RequestOptions) => Promise<T>;
};

export function createConsentApi(http: HttpClient): ConsentApi {
  return {
    getConsentStatus(programId) {
      return http.request<ConsentStatus>(`/programs/${programId}/consent`);
    },
    grantConsent(programId, consentText) {
      return http.request<ConsentStatus>(`/programs/${programId}/consent/grant`, {
        method: "POST",
        body: { consent_text: consentText },
      });
    },
    withdrawConsent(programId) {
      return http.request<ConsentStatus>(`/programs/${programId}/consent/withdraw`, {
        method: "POST",
      });
    },
  };
}
