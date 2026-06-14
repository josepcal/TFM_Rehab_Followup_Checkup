import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { createMockAuthClient } from "./auth/authClient";

describe("UC-01 medical access shell", () => {
  it("GIVEN a medical user WHEN opening the UI THEN shows the diagnostic workspace", () => {
    render(<App authClient={createMockAuthClient()} />);

    expect(screen.getByRole("heading", { name: /doctor diagnostic workspace/i })).toBeInTheDocument();
  });

  it("GIVEN a non-medical user WHEN opening the UI THEN shows access denied", () => {
    render(
      <App
        authClient={createMockAuthClient({
          authenticated: true,
          roles: ["patient"],
        })}
      />,
    );

    expect(screen.getByRole("heading", { name: /access denied/i })).toBeInTheDocument();
  });
});
