import { describe, expect, it, vi } from "vitest";

import type { RequestOptions } from "./http";
import { createCatalogApi } from "./catalog";

describe("UC-02 catalog API", () => {
  it("lists rehab exercises from catalog endpoint", async () => {
    const response = [{ id: "exercise-1", nombre: "Fonación", tipo: "phonation" }];
    const request = vi.fn(async () => response) as unknown as (<T>(
      path: string,
      options?: RequestOptions,
    ) => Promise<T>) &
      ReturnType<typeof vi.fn>;
    const api = createCatalogApi({ request });

    const exercises = await api.listExercises();

    expect(request).toHaveBeenCalledWith("/exercises");
    expect(exercises).toEqual([{ id: "exercise-1", nombre: "Fonación", tipo: "phonation" }]);
  });
});
