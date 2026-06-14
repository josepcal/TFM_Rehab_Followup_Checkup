import { describe, expect, it } from "vitest";

import { ApiError } from "./http";
import { normalizePage } from "./diagnostics";

describe("diagnostics API DTO normalization", () => {
  it("normalizes backend data envelope", () => {
    const page = normalizePage({ data: [{ id: "d1" }], total: 1, limit: 20, offset: 0 });

    expect(page.items).toEqual([{ id: "d1" }]);
  });

  it("normalizes alternate items envelope", () => {
    const page = normalizePage({ items: [{ id: "d2" }], total: 1, limit: 20, offset: 0 });

    expect(page.items).toEqual([{ id: "d2" }]);
  });
});

describe("typed API errors", () => {
  it("exposes status for authorization states", () => {
    const error = new ApiError("Forbidden", 403, { detail: "Forbidden" });

    expect(error.status).toBe(403);
  });
});
