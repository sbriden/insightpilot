"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type { DfsPortfolioCorrelationSummary } from "@/services/api";

interface Props {
  correlation?: DfsPortfolioCorrelationSummary | null;
}

function PairList({
  title,
  rows,
  tone,
}: {
  title: string;
  rows: NonNullable<
    DfsPortfolioCorrelationSummary["positive_correlation_exposure"]
  >;
  tone: "positive" | "negative";
}) {
  const accent =
    tone === "positive" ? snapshotTokens.success : snapshotTokens.warning;

  return (
    <div>
      <p
        className="text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {title}
      </p>
      <ul className="mt-2 space-y-1.5">
        {rows.length === 0 && (
          <li
            className="text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            None material.
          </li>
        )}
        {rows.map((row) => (
          <li
            key={`${row.player_id}-${row.correlated_player_id}`}
            className="flex items-baseline justify-between gap-3 text-sm"
            style={{ color: snapshotTokens.textPrimary }}
          >
            <span>
              <span style={{ color: accent }}>
                {row.correlation_score > 0 ? "+" : ""}
                {row.correlation_score.toFixed(2)}
              </span>{" "}
              {row.player_name} + {row.correlated_player_name}
            </span>
            <span
              className="shrink-0 tabular-nums"
              style={{ color: snapshotTokens.textMuted }}
            >
              {row.exposure_pct.toFixed(0)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function PortfolioCorrelation({ correlation }: Props) {
  if (!correlation) {
    return null;
  }

  const positive = correlation.positive_correlation_exposure ?? [];
  const negative = correlation.negative_correlation_exposure ?? [];

  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-sm font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Correlation Exposure
      </h3>
      {correlation.narrative && (
        <p
          className="mt-2 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {correlation.narrative}
        </p>
      )}
      <div className="mt-3 grid gap-4 lg:grid-cols-2">
        <PairList
          title="Positive Correlation Exposure"
          rows={positive}
          tone="positive"
        />
        <PairList
          title="Negative Correlation Exposure"
          rows={negative}
          tone="negative"
        />
      </div>
    </section>
  );
}
