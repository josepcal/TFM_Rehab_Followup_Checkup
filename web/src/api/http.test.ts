import { describe, expect, it, vi } from "vitest";

import { createHttpClient, ApiError } from "./http";

function makeAuthClient(token = "test-token") {
  return { getToken: vi.fn(async () => token) };
}

function makeHttpClient(fetchImpl: typeof fetch, token = "test-token") {
  return createHttpClient({
    baseUrl: "/api",
    authClient: makeAuthClient(token),
    fetchImpl,
  });
}

describe("ApiError", () => {
  it("extracts string detail from FastAPI error payload", () => {
    const error = new ApiError("Not found", 404, { detail: "recording not found" });
    expect(error.message).toBe("Not found");
    expect(error.status).toBe(404);
  });

  it("exposes payload for downstream inspection", () => {
    const payload = { detail: "Forbidden" };
    const error = new ApiError("Forbidden", 403, payload);
    expect(error.payload).toBe(payload);
  });
});

describe("getErrorMessage — validation error arrays", () => {
  it("extracts first msg from FastAPI array detail", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(
        JSON.stringify({ detail: [{ loc: ["body", "dolencia"], msg: "field required", type: "missing" }] }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const http = makeHttpClient(fetchImpl);

    await expect(http.request("/patients", { method: "POST", body: {} })).rejects.toMatchObject({
      status: 422,
      message: "field required",
    });
  });

  it("falls back to generic message when detail is an unrecognised shape", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ detail: { code: "weird" } }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    const http = makeHttpClient(fetchImpl);

    await expect(http.request("/patients")).rejects.toMatchObject({
      status: 500,
      message: "API request failed with status 500",
    });
  });
});

describe("request", () => {
  it("sets Authorization header with bearer token", async () => {
    let capturedHeaders: Headers | undefined;
    const fetchImpl = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
      capturedHeaders = init?.headers as Headers;
      return new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } });
    }) as unknown as typeof fetch;

    const http = makeHttpClient(fetchImpl, "my-jwt");
    await http.request("/patients");

    expect(capturedHeaders?.get("Authorization")).toBe("Bearer my-jwt");
  });

  it("sets Content-Type application/json when body is present", async () => {
    let capturedHeaders: Headers | undefined;
    const fetchImpl = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
      capturedHeaders = init?.headers as Headers;
      return new Response(JSON.stringify({ id: "p-1" }), { status: 200, headers: { "Content-Type": "application/json" } });
    }) as unknown as typeof fetch;

    const http = makeHttpClient(fetchImpl);
    await http.request("/patients", { method: "POST", body: { nombre: "Ana" } });

    expect(capturedHeaders?.get("Content-Type")).toBe("application/json");
  });

  it("handles 204 No Content response without throwing", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(null, { status: 204 }),
    ) as unknown as typeof fetch;

    const http = makeHttpClient(fetchImpl);
    const result = await http.request("/patients/p-1", { method: "DELETE" });

    expect(result).toBeUndefined();
  });

  it("throws ApiError with correct status on non-ok response", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ detail: "Not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;

    const http = makeHttpClient(fetchImpl);

    await expect(http.request("/patients/unknown")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      message: "Not found",
    });
  });

  it("omits Authorization header when token is null", async () => {
    let capturedHeaders: Headers | undefined;
    const fetchImpl = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
      capturedHeaders = init?.headers as Headers;
      return new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } });
    }) as unknown as typeof fetch;

    const http = makeHttpClient(fetchImpl, null as unknown as string);
    await http.request("/patients");

    expect(capturedHeaders?.get("Authorization")).toBeNull();
  });
});
