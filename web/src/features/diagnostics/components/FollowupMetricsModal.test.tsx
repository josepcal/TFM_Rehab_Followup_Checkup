import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { DiagnosticFeatureApi } from "../api";
import { FollowupMetricsModal } from "./FollowupMetricsModal";

vi.mock("../hooks", () => ({
  useCheckupMetrics: vi.fn(),
  useMetricNorms: vi.fn(),
}));

import { useCheckupMetrics, useMetricNorms } from "../hooks";

const mockUseCheckupMetrics = useCheckupMetrics as ReturnType<typeof vi.fn>;
const mockUseMetricNorms = useMetricNorms as ReturnType<typeof vi.fn>;

const fakeApi = {} as DiagnosticFeatureApi;

function defaultNormsReturn() {
  mockUseMetricNorms.mockReturnValue({
    data: new Map(),
    isLoading: false,
    isError: false,
  });
}

describe("FollowupMetricsModal", () => {
  it("renders loading state when isLoading=true", () => {
    mockUseCheckupMetrics.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    defaultNormsReturn();
    render(<FollowupMetricsModal api={fakeApi} checkupId="chk-1" onClose={vi.fn()} />);
    expect(document.querySelector(".loading-spinner")).toBeInTheDocument();
  });

  it("renders empty state when data is empty and not loading", () => {
    mockUseCheckupMetrics.mockReturnValue({
      data: { data: [], metricKeys: [] },
      isLoading: false,
      isError: false,
    });
    defaultNormsReturn();
    render(<FollowupMetricsModal api={fakeApi} checkupId="chk-1" onClose={vi.fn()} />);
    expect(
      screen.getByText("No metrics available yet for this check-up."),
    ).toBeInTheDocument();
  });

  it("calls onClose when × button is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    mockUseCheckupMetrics.mockReturnValue({
      data: { data: [], metricKeys: [] },
      isLoading: false,
      isError: false,
    });
    defaultNormsReturn();
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
    defaultNormsReturn();
    const { container } = render(
      <FollowupMetricsModal api={fakeApi} checkupId="chk-1" onClose={onClose} />,
    );
    const overlay = container.querySelector(".modal-overlay") as HTMLElement;
    await user.click(overlay);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders one chart section per metric key", () => {
    mockUseCheckupMetrics.mockReturnValue({
      data: {
        data: [
          { date: "2026-01-01", jitter_local_pct: 0.8, hnr_db: 18 },
        ],
        metricKeys: ["jitter_local_pct", "hnr_db"],
      },
      isLoading: false,
      isError: false,
    });
    defaultNormsReturn();
    render(<FollowupMetricsModal api={fakeApi} checkupId="chk-1" onClose={vi.fn()} />);
    // Each metric section has an h4 heading with the metric key (no norm label in this case)
    expect(screen.getByText("jitter_local_pct")).toBeInTheDocument();
    expect(screen.getByText("hnr_db")).toBeInTheDocument();
  });

  it("renders metric label from norm when norm is present", () => {
    mockUseCheckupMetrics.mockReturnValue({
      data: {
        data: [{ date: "2026-01-01", jitter_local_pct: 0.8 }],
        metricKeys: ["jitter_local_pct"],
      },
      isLoading: false,
      isError: false,
    });
    mockUseMetricNorms.mockReturnValue({
      data: new Map([
        [
          "jitter_local_pct",
          {
            norm_id: "norm-1",
            metric_code: "jitter_local_pct",
            label: "Jitter (local)",
            unit: "%",
            direction: "lower_better",
            sex: null,
            age_min: null,
            age_max: null,
            good_min: null,
            good_max: 1.04,
            poor_min: 3.0,
            poor_max: null,
            source: "dysarthria_analysis_v1",
            version: 1,
          },
        ],
      ]),
      isLoading: false,
      isError: false,
    });
    render(<FollowupMetricsModal api={fakeApi} checkupId="chk-1" onClose={vi.fn()} />);
    expect(screen.getByText("Jitter (local)")).toBeInTheDocument();
    expect(screen.getByText("↓ lower is better")).toBeInTheDocument();
  });

  it("renders without error when norms map is empty (graceful degradation)", () => {
    mockUseCheckupMetrics.mockReturnValue({
      data: {
        data: [{ date: "2026-01-01", hnr_db: 18 }],
        metricKeys: ["hnr_db"],
      },
      isLoading: false,
      isError: false,
    });
    defaultNormsReturn();
    expect(() =>
      render(<FollowupMetricsModal api={fakeApi} checkupId="chk-1" onClose={vi.fn()} />),
    ).not.toThrow();
    expect(screen.getByText("hnr_db")).toBeInTheDocument();
  });
});
