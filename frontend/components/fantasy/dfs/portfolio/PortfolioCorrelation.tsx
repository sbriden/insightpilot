"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type { DfsPortfolioCorrelationSummary } from "@/services/api";

interface Props {
  correlation?: DfsPortfolioCorrelationSummary | null;
  /** When true, omit outer card chrome (parent tabs own it). */
  embedded?: boolean;
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
            className="flex items-start justify-between gap-3 text-sm"
            style={{ color: snapshotTokens.textPrimary }}
          >
            <span className="min-w-0">
              <span style={{ color: accent }}>
                {row.correlation_score > 0 ? "+" : ""}
                {row.correlation_score.toFixed(2)}
              </span>{" "}
              {row.player_name} + {row.correlated_player_name}
              <span
                className="mt-0.5 block text-xs"
                style={{ color: snapshotTokens.textMuted }}
              >
                {formatLineupIndexes(row.lineup_indexes)}
              </span>
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

function formatLineupIndexes(
  indexes?: number[] | null
): string {
  const values = (indexes ?? [])
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value) && value > 0)
    .sort((a, b) => a - b);
  if (values.length === 0) {
    return "Regenerate to see lineup numbers";
  }
  const shown = values.slice(0, 8);
  const label = shown.join(", ");
  const remaining = values.length - shown.length;
  if (values.length === 1) {
    return `Lineup ${label}`;
  }
  if (remaining > 0) {
    return `Lineups ${label} +${remaining} more`;
  }
  return `Lineups ${label}`;
}

export default function PortfolioCorrelation({
  correlation,
  embedded = false,
}: Props) {
  const positive = correlation?.positive_correlation_exposure ?? [];
  const negative = correlation?.negative_correlation_exposure ?? [];

  const body = (
    <>
      {!correlation ? (
        <p
          className="text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          Generate a portfolio to see correlation exposure.
        </p>
      ) : (
        <>
          {correlation.narrative && (
            <p
              className="text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              {correlation.narrative}
            </p>
          )}
          <div
            className={
              correlation.narrative
                ? "mt-3 grid gap-4 lg:grid-cols-2"
                : "grid gap-4 lg:grid-cols-2"
            }
          >
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
        </>
      )}
    </>
  );

  if (embedded) {
    return <div>{body}</div>;
  }

  if (!correlation) {
    return null;
  }

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
      <div className="mt-2">{body}</div>
    </section>
  );
}
