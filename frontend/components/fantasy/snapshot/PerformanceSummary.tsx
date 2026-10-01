"use client";

import {
  FantasySeasonStats,
} from "@/services/api";

import {
  formatMetricValue,
  formatScore,
  snapshotTokens,
} from "./tokens";

interface Props {
  seasonStats?: FantasySeasonStats | null;
  productionScore?: number | null;
  opportunityScore?: number | null;
}

export default function PerformanceSummary({
  seasonStats,
  productionScore,
  opportunityScore,
}: Props) {
  const season = seasonStats?.season;
  const metrics = seasonStats?.metrics?.slice(0, 5) ?? [];

  return (
    <section
      className="rounded-[10px] border bg-white p-4 sm:p-5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3
          className="text-[15px] font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          {season
            ? `${season} Season Performance`
            : "Season Performance"}
        </h3>
        <div
          className="flex gap-3 text-xs font-medium"
          style={{ color: snapshotTokens.textSecondary }}
        >
          <span>
            Prod score {formatScore(productionScore)}
          </span>
          <span>
            Opp score {formatScore(opportunityScore)}
          </span>
        </div>
      </div>

      {metrics.length === 0 ? (
        <p
          className="mt-4 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          No season production totals available for this
          player yet.
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {metrics.map((metric) => (
            <div
              key={metric.key}
              className="flex h-full flex-col rounded-lg border px-3 py-3"
              style={{
                borderColor: snapshotTokens.divider,
                background: snapshotTokens.background,
              }}
            >
              <p
                className="text-[11px] font-medium uppercase leading-4 tracking-wide"
                style={{ color: snapshotTokens.textMuted }}
              >
                {metric.label}
              </p>
              <p
                className="mt-auto pt-2 text-[22px] font-bold tabular-nums leading-none"
                style={{ color: snapshotTokens.textPrimary }}
              >
                {formatMetricValue(metric.value)}
              </p>
            </div>
          ))}
        </div>
      )}

      {seasonStats?.games != null && (
        <p
          className="mt-3 text-xs"
          style={{ color: snapshotTokens.textMuted }}
        >
          Based on {seasonStats.games} game
          {seasonStats.games === 1 ? "" : "s"} · factual
          production (PPR)
        </p>
      )}
    </section>
  );
}
