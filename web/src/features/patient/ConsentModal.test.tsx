import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConsentModal } from "./ConsentModal";
import type { ConsentApi, ConsentStatus } from "../../api/consent";

function makeConsentApi(overrides: Partial<ConsentApi> = {}): ConsentApi {
  const defaultStatus: ConsentStatus = {
    consent_id: "c-1",
    program_id: "prog-1",
    granted: true,
    granted_at: new Date().toISOString(),
    withdrawn_at: null,
    consent_text: "test",
  };
  return {
    getConsentStatus: vi.fn(async () => ({
      consent_id: null,
      program_id: "prog-1",
      granted: false,
      granted_at: null,
      withdrawn_at: null,
      consent_text: null,
    })),
    grantConsent: vi.fn(async () => defaultStatus),
    withdrawConsent: vi.fn(async () => defaultStatus),
    ...overrides,
  };
}

describe("ConsentModal", () => {
  it("renders RGPD text and two buttons", () => {
    render(
      <ConsentModal
        programId="prog-1"
        api={makeConsentApi()}
        onGranted={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByText(/dato biométrico/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /acepto/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancelar/i })).toBeInTheDocument();
  });

  it("calls grantConsent and fires onGranted on Accept", async () => {
    const user = userEvent.setup();
    const grantConsent = vi.fn(async () => ({
      consent_id: "c-1",
      program_id: "prog-1",
      granted: true,
      granted_at: new Date().toISOString(),
      withdrawn_at: null,
      consent_text: "test",
    }));
    const onGranted = vi.fn();
    render(
      <ConsentModal
        programId="prog-1"
        api={makeConsentApi({ grantConsent })}
        onGranted={onGranted}
        onCancel={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /acepto/i }));

    await waitFor(() => expect(onGranted).toHaveBeenCalledTimes(1));
    expect(grantConsent).toHaveBeenCalledWith("prog-1", expect.any(String));
  });

  it("disables buttons while grantConsent is in-flight", async () => {
    const user = userEvent.setup();
    let resolve!: () => void;
    const grantConsent = vi.fn(
      () =>
        new Promise<ConsentStatus>((res) => {
          resolve = () =>
            res({
              consent_id: "c-1",
              program_id: "prog-1",
              granted: true,
              granted_at: new Date().toISOString(),
              withdrawn_at: null,
              consent_text: "test",
            });
        }),
    );
    render(
      <ConsentModal
        programId="prog-1"
        api={makeConsentApi({ grantConsent })}
        onGranted={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /acepto/i }));

    expect(screen.getByRole("button", { name: /acepto/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /cancelar/i })).toBeDisabled();

    resolve();
  });

  it("fires onCancel without API call on Cancel", async () => {
    const user = userEvent.setup();
    const api = makeConsentApi();
    const onCancel = vi.fn();
    render(
      <ConsentModal
        programId="prog-1"
        api={api}
        onGranted={vi.fn()}
        onCancel={onCancel}
      />,
    );

    await user.click(screen.getByRole("button", { name: /cancelar/i }));

    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(api.grantConsent).not.toHaveBeenCalled();
  });
});
