import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DiagnosticFeatureApi } from "../api";
import { FollowupMetricsModal } from "./FollowupMetricsModal";

vi.mock("../hooks", () => ({
  useCheckupMetrics: vi.fn(),
}));

import { useCheckupMetrics } from "../hooks";

const mockUseCheckupMetrics = useCheckupMetrics as ReturnType<typeof vi.fn>;

const fakeApi = {} as DiagnosticFeatureApi;

describe("FollowupMetricsModal", () => {
  it("renders loading state when isLoading=true", () => {
    mockUseCheckupMetrics.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    render(<FollowupMetricsModal api={fakeApi} checkupId="chk-1" onClose={vi.fn()} />);
    expect(document.querySelector(".loading-spinner")).toBeInTheDocument();
  });

  it("renders empty state when data is empty and not loading", () => {
    mockUseCheckupMetrics.mockReturnValue({
      data: { data: [], metricKeys: [] },
      isLoading: false,
      isError: false,
    });
    render(<FollowupMetricsModal api={fakeApi} checkupId="chk-1" onClose={vi.fn()} />);
    expect(
      screen.getByText("No metrics available yet for this check-up."),
    ).toBeInTheDocument();
  });

  it("renders chart container when data has entries", () => {
    mockUseCheckupMetrics.mockReturnValue({
      data: { data: [{ date: "2026-01-01", pitch: 120 }], metricKeys: ["pitch"] },
      isLoading: false,
      isError: false,
    });
    render(<FollowupMetricsModal api={fakeApi} checkupId="chk-1" onClose={vi.fn()} />);
    expect(screen.getByTestId("metrics-chart")).toBeInTheDocument();
  });

  it("calls onClose when × button is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockUseCheckupMetrics.mockReturnValue({
      data: { data: [], metricKeys: [] },
      isLoading: false,
      isError: false,
    });
    render(<FollowupMetricsModal api={fakeApi} checkupId="chk-1" onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: "×" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when overlay is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockUseCheckupMetrics.mockReturnValue({
      data: { data: [], metricKeys: [] },
      isLoading: false,
      isError: false,
    });
    const { container } = render(
      <FollowupMetricsModal api={fakeApi} checkupId="chk-1" onClose={onClose} />,
    );
    const overlay = container.querySelector(".modal-overlay") as HTMLElement;
    await user.click(overlay);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
