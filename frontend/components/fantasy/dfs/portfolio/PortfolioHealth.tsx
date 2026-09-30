"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type { DfsPortfolioSignal } from "@/services/api";

interface Props {
  signals: DfsPortfolioSignal[];
  alerts: DfsPortfolioSignal[];
  onViewExposure: () => void;
}

export default function PortfolioHealth({
  signals,
  alerts,
  onViewExposure,
}: Props) {
  const headline =
    alerts[0] ||
    signals.find((item) => item.severity !== "info") ||
    signals[0];

  if (!headline) {
    return null;
  }

  const isAlert = Boolean(
    alerts[0] || headline.severity === "high"
  );

  return (
    <section
      className="rounded-[10px] border px-4 py-3"
      style={{
        borderColor: isAlert
          ? snapshotTokens.warning
          : snapshotTokens.border,
        background: isAlert
          ? "rgba(217, 119, 6, 0.06)"
          : snapshotTokens.blueLight,
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Portfolio Health
          </p>
          <p
            className="mt-1 max-w-3xl text-sm"
            style={{ color: snapshotTokens.textPrimary }}
          >
            {headline.explanation}
          </p>
        </div>
        <button
          type="button"
          onClick={onViewExposure}
          className="text-sm font-semibold"
          style={{ color: snapshotTokens.blue }}
        >
          View Exposure →
        </button>
      </div>
    </section>
  );
}
