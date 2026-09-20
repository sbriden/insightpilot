"use client";

import {
  ArrowLeft,
  ArrowRight,
  Sparkles,
  User,
} from "lucide-react";

import {
  FantasyPlayerSnapshot,
} from "@/services/api";

import {
  assessmentStyles,
  formatMetricValue,
  formatScore,
  snapshotTokens,
} from "./tokens";

interface Props {
  base: FantasyPlayerSnapshot;
  compare: FantasyPlayerSnapshot;
  baseOwnership?: number | null;
  compareOwnership?: number | null;
  onBack?: () => void;
  onOpenPlayer?: (playerId: string) => void;
}

function PlayerIdentity({
  player,
  badge,
}: {
  player: FantasyPlayerSnapshot;
  badge: string;
}) {
  const tone = assessmentStyles(player.overall_assessment);

  return (
    <div className="flex min-w-0 items-start gap-3">
      <div
        className="h-16 w-16 shrink-0 overflow-hidden rounded-xl border bg-white sm:h-20 sm:w-20"
        style={{ borderColor: snapshotTokens.border }}
      >
        {player.headshot_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={player.headshot_url}
            alt=""
            className="h-full w-full object-cover object-top"
          />
        ) : (
          <div
            className="flex h-full w-full items-center justify-center"
            style={{ background: snapshotTokens.background }}
          >
            <User
              className="h-7 w-7"
              style={{ color: snapshotTokens.textMuted }}
            />
          </div>
        )}
      </div>
      <div className="min-w-0">
        <p
          className="text-[11px] font-semibold uppercase tracking-wide"
          style={{ color: snapshotTokens.textMuted }}
        >
          {badge}
        </p>
        <p
          className="mt-0.5 truncate text-lg font-bold leading-tight"
          style={{ color: snapshotTokens.navy }}
        >
          {player.name || player.player_id}
        </p>
        <p
          className="mt-0.5 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {[player.position, player.team]
            .filter(Boolean)
            .join(" · ") || "—"}
        </p>
        <span
          className="mt-2 inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-semibold tabular-nums"
          style={{
            background: tone.bg,
            color: tone.text,
          }}
        >
          {formatScore(player.fantasy_value_score)}
          {player.overall_assessment
            ? ` · ${player.overall_assessment}`
            : ""}
        </span>
      </div>
    </div>
  );
}

function deltaTone(
  left: number | null | undefined,
  right: number | null | undefined,
  higherIsBetter = true
): string {
  if (left == null || right == null) {
    return snapshotTokens.textMuted;
  }
  if (left === right) {
    return snapshotTokens.textMuted;
  }
  const leftWins = higherIsBetter ? left > right : left < right;
  return leftWins
    ? snapshotTokens.success
    : snapshotTokens.negative;
}

function CompareRow({
  label,
  left,
  right,
  format = "score",
  higherIsBetter = true,
}: {
  label: string;
  left: number | null | undefined;
  right: number | null | undefined;
  format?: "score" | "points" | "rank" | "percent";
  higherIsBetter?: boolean;
}) {
  const display = (value: number | null | undefined) => {
    if (value == null) {
      return "—";
    }
    if (format === "rank") {
      return `#${Math.round(value)}`;
    }
    if (format === "percent") {
      return `${value.toFixed(1)}%`;
    }
    if (format === "points") {
      return formatMetricValue(value);
    }
    return formatScore(value);
  };

  const leftColor = deltaTone(left, right, higherIsBetter);
  const rightColor = deltaTone(right, left, higherIsBetter);

  return (
    <div
      className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 border-b py-3 last:border-0"
      style={{ borderColor: snapshotTokens.divider }}
    >
      <p
        className="text-right text-base font-bold tabular-nums"
        style={{ color: leftColor }}
      >
        {display(left)}
      </p>
      <p
        className="min-w-[7.5rem] text-center text-[11px] font-medium uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {label}
      </p>
      <p
        className="text-left text-base font-bold tabular-nums"
        style={{ color: rightColor }}
      >
        {display(right)}
      </p>
    </div>
  );
}

function buildComparisonInsight(
  base: FantasyPlayerSnapshot,
  compare: FantasyPlayerSnapshot,
  baseOwnership?: number | null,
  compareOwnership?: number | null
): { headline: string; body: string } {
  const baseValue = base.fantasy_value_score;
  const compareValue = compare.fantasy_value_score;
  const basePts = base.season_stats?.fantasy_points;
  const comparePts = compare.season_stats?.fantasy_points;
  const baseOpp = base.opportunity_score;
  const compareOpp = compare.opportunity_score;

  if (
    compareValue != null
    && baseValue != null
    && compareValue >= baseValue - 5
    && (compareOwnership == null || compareOwnership < 50)
  ) {
    return {
      headline: "Viable free-agent alternative",
      body:
        `${compare.name || "This player"} posts a similar `
        + `InsightPilot value profile`
        + (compareOwnership != null
          ? ` at ${compareOwnership.toFixed(1)}% ownership`
          : "")
        + (baseOwnership != null
          ? ` versus ${baseOwnership.toFixed(1)}% for ${base.name || "the current player"}`
          : "")
        + `, making them a practical replacement candidate.`,
    };
  }

  if (
    compareOpp != null
    && baseOpp != null
    && compareOpp > baseOpp + 8
  ) {
    return {
      headline: "Higher opportunity profile",
      body:
        `${compare.name || "The free agent"} currently shows `
        + `stronger opportunity (${Math.round(compareOpp)} vs `
        + `${Math.round(baseOpp)}), which can matter more than `
        + `recent production when evaluating replacements.`,
    };
  }

  if (
    basePts != null
    && comparePts != null
    && basePts > comparePts * 1.25
  ) {
    return {
      headline: "Production gap favors the current player",
      body:
        `${base.name || "Your player"} has materially higher `
        + `season fantasy points (${formatMetricValue(basePts)} vs `
        + `${formatMetricValue(comparePts)}). Only pivot if `
        + `opportunity or availability has clearly shifted.`,
    };
  }

  return {
    headline: "Compare value, opportunity, and availability",
    body:
      "Use assessment score, opportunity, and ownership together — "
      + "not fantasy points alone — when deciding on a replacement.",
  };
}

export default function PlayerComparison({
  base,
  compare,
  baseOwnership,
  compareOwnership,
  onBack,
  onOpenPlayer,
}: Props) {
  const resolvedBaseOwnership =
    baseOwnership ?? base.ownership ?? null;
  const resolvedCompareOwnership =
    compareOwnership ?? compare.ownership ?? null;

  const insight = buildComparisonInsight(
    base,
    compare,
    resolvedBaseOwnership,
    resolvedCompareOwnership
  );

  const metricKeys = new Map<string, string>();
  for (const metric of base.season_stats?.metrics ?? []) {
    metricKeys.set(metric.key, metric.label);
  }
  for (const metric of compare.season_stats?.metrics ?? []) {
    if (!metricKeys.has(metric.key)) {
      metricKeys.set(metric.key, metric.label);
    }
  }

  const metricValue = (
    player: FantasyPlayerSnapshot,
    key: string
  ) =>
    player.season_stats?.metrics?.find(
      (metric) => metric.key === key
    )?.value ?? null;

  const opportunityFields = new Map<string, string>();
  for (const field of base.performance?.opportunity_fields ?? []) {
    opportunityFields.set(field.key, field.label);
  }
  for (const field of compare.performance?.opportunity_fields ?? []) {
    if (!opportunityFields.has(field.key)) {
      opportunityFields.set(field.key, field.label);
    }
  }

  function averageOpportunity(
    player: FantasyPlayerSnapshot,
    key: string
  ): number | null {
    const games = player.performance?.recent_games ?? [];
    const values = games
      .map((game) => game.opportunity?.[key])
      .filter(
        (value): value is number =>
          typeof value === "number"
          && Number.isFinite(value)
      );
    if (values.length === 0) {
      return null;
    }
    const sum = values.reduce(
      (total, value) => total + value,
      0
    );
    return sum / values.length;
  }

  const percentKeys = new Set([
    "snap_pct",
    "route_participation",
    "target_share",
    "rush_share",
    "qb_rush_share",
  ]);

  const opportunityRows = [...opportunityFields.entries()]
    .map(([key, label]) => ({
      key,
      label,
      left: averageOpportunity(base, key),
      right: averageOpportunity(compare, key),
    }))
    .filter(
      (row) => row.left != null || row.right != null
    );

  const snapRow = opportunityRows.find(
    (row) => row.key === "snap_pct"
  );
  const routeRow = opportunityRows.find(
    (row) => row.key === "route_participation"
  );

  function routeDuplicatesSnap(
    snap: number | null | undefined,
    route: number | null | undefined
  ): boolean {
    if (route == null) {
      return true;
    }
    if (snap == null) {
      return false;
    }
    return Math.abs(snap - route) < 0.05;
  }

  const dedupedOpportunityRows =
    snapRow
    && routeRow
    && routeDuplicatesSnap(snapRow.left, routeRow.left)
    && routeDuplicatesSnap(snapRow.right, routeRow.right)
      ? opportunityRows.filter(
          (row) => row.key !== "route_participation"
        )
      : opportunityRows;

  const hasOpportunityMetrics =
    base.opportunity_score != null
    || compare.opportunity_score != null
    || dedupedOpportunityRows.length > 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {onBack ? (
          <button
            type="button"
            onClick={onBack}
            className="inline-flex items-center gap-1.5 rounded-lg border bg-white px-3 py-1.5 text-sm font-medium transition hover:opacity-90"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textSecondary,
            }}
          >
            <ArrowLeft className="h-4 w-4" />
            Back to snapshot
          </button>
        ) : (
          <span />
        )}
        <p
          className="text-xs font-medium uppercase tracking-wide"
          style={{ color: snapshotTokens.textMuted }}
        >
          Player comparison
        </p>
      </div>

      <section
        className="rounded-[10px] border bg-white p-4 sm:p-5"
        style={{ borderColor: snapshotTokens.border }}
      >
        <div className="grid gap-4 sm:grid-cols-[1fr_auto_1fr] sm:items-center">
          <PlayerIdentity
            player={base}
            badge="Current player"
          />
          <div
            className="hidden h-10 w-10 items-center justify-center rounded-full border sm:flex"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textMuted,
            }}
          >
            <ArrowRight className="h-4 w-4" />
          </div>
          <PlayerIdentity
            player={compare}
            badge="Free-agent replacement"
          />
        </div>
      </section>

      <section
        className="rounded-[10px] border p-4 sm:p-5"
        style={{
          borderColor: "#DDD6FE",
          background: snapshotTokens.purpleLight,
        }}
      >
        <p
          className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide"
          style={{ color: snapshotTokens.purple }}
        >
          <Sparkles className="h-3.5 w-3.5" />
          InsightPilot Analysis
        </p>
        <h3
          className="mt-2 text-[16px] font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          {insight.headline}
        </h3>
        <p
          className="mt-2 text-sm leading-6"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {insight.body}
        </p>
      </section>

      <section
        className="rounded-[10px] border bg-white p-4 sm:p-5"
        style={{ borderColor: snapshotTokens.border }}
      >
        <h3
          className="text-[15px] font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          Value Summary
        </h3>
        <p
          className="mt-1 text-xs"
          style={{ color: snapshotTokens.textSecondary }}
        >
          Green favors that side of the comparison
        </p>
        <div className="mt-2">
          <CompareRow
            label="Assessment"
            left={base.fantasy_value_score}
            right={compare.fantasy_value_score}
          />
          <CompareRow
            label="Production"
            left={base.production_score}
            right={compare.production_score}
          />
          <CompareRow
            label="Fantasy Pts"
            left={base.season_stats?.fantasy_points}
            right={compare.season_stats?.fantasy_points}
            format="points"
          />
          <CompareRow
            label="Pos Rank"
            left={base.position_rank}
            right={compare.position_rank}
            format="rank"
            higherIsBetter={false}
          />
          <CompareRow
            label="Overall Rank"
            left={base.overall_rank}
            right={compare.overall_rank}
            format="rank"
            higherIsBetter={false}
          />
          {resolvedCompareOwnership != null
            || resolvedBaseOwnership != null ? (
            <CompareRow
              label="Ownership"
              left={resolvedBaseOwnership}
              right={resolvedCompareOwnership}
              format="percent"
              higherIsBetter={false}
            />
          ) : null}
        </div>
      </section>

      {hasOpportunityMetrics && (
        <section
          className="rounded-[10px] border bg-white p-4 sm:p-5"
          style={{ borderColor: snapshotTokens.border }}
        >
          <h3
            className="text-[15px] font-semibold"
            style={{ color: snapshotTokens.navy }}
          >
            Opportunity
          </h3>
          <p
            className="mt-1 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Average of recent games — snaps, shares, and
            high-leverage chances
          </p>
          <div className="mt-2">
            <CompareRow
              label="Opp Score"
              left={base.opportunity_score}
              right={compare.opportunity_score}
            />
            {dedupedOpportunityRows.map((row) => (
              <CompareRow
                key={row.key}
                label={row.label}
                left={row.left}
                right={row.right}
                format={
                  percentKeys.has(row.key)
                    ? "percent"
                    : "points"
                }
              />
            ))}
          </div>
        </section>
      )}

      {metricKeys.size > 0 && (
        <section
          className="rounded-[10px] border bg-white p-4 sm:p-5"
          style={{ borderColor: snapshotTokens.border }}
        >
          <h3
            className="text-[15px] font-semibold"
            style={{ color: snapshotTokens.navy }}
          >
            Season Production
          </h3>
          <p
            className="mt-1 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Factual box-score totals (PPR)
          </p>
          <div className="mt-2">
            {[...metricKeys.entries()].map(([key, label]) => (
              <CompareRow
                key={key}
                label={label}
                left={metricValue(base, key)}
                right={metricValue(compare, key)}
                format="points"
                higherIsBetter={key !== "interceptions"}
              />
            ))}
          </div>
        </section>
      )}

      <div className="flex flex-wrap gap-2">
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="rounded-lg border bg-white px-3 py-2 text-sm font-medium"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textSecondary,
            }}
          >
            Keep viewing {base.name || "current player"}
          </button>
        )}
        {onOpenPlayer && (
          <button
            type="button"
            onClick={() =>
              onOpenPlayer(compare.player_id)
            }
            className="rounded-lg px-3 py-2 text-sm font-semibold text-white"
            style={{ background: snapshotTokens.blue }}
          >
            Open {compare.name || "replacement"} snapshot
          </button>
        )}
        {onOpenPlayer && (
          <button
            type="button"
            onClick={() =>
              onOpenPlayer(base.player_id)
            }
            className="rounded-lg border bg-white px-3 py-2 text-sm font-medium"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textSecondary,
            }}
          >
            Open {base.name || "player"} snapshot
          </button>
        )}
      </div>
    </div>
  );
}
