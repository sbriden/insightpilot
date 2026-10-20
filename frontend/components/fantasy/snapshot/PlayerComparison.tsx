"use client";

import {
  ArrowLeft,
  Sparkles,
  User,
} from "lucide-react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";

import TeamLogo, {
  canonicalTeamAbbreviation,
} from "@/components/teams/TeamLogo";
import {
  FantasyPlayerSnapshot,
} from "@/services/api";

import {
  assessmentStyles,
  formatMetricValue,
  formatScore,
  snapshotTokens,
} from "./tokens";

const PLAYER_B_COLOR = "#F97316";

function playerAColor(): string {
  return snapshotTokens.blue;
}

interface Props {
  base: FantasyPlayerSnapshot;
  compare: FantasyPlayerSnapshot;
  baseOwnership?: number | null;
  compareOwnership?: number | null;
  onBack?: () => void;
  onOpenPlayer?: (playerId: string) => void;
}

function scoreOrZero(
  value: number | null | undefined
): number {
  return value == null || !Number.isFinite(value) ? 0 : value;
}

function OverlayRadar({
  base,
  compare,
}: {
  base: FantasyPlayerSnapshot;
  compare: FantasyPlayerSnapshot;
}) {
  const data = [
    {
      metric: "Value",
      base: scoreOrZero(base.fantasy_value_score),
      compare: scoreOrZero(compare.fantasy_value_score),
    },
    {
      metric: "Opportunity",
      base: scoreOrZero(base.opportunity_score),
      compare: scoreOrZero(compare.opportunity_score),
    },
    {
      metric: "Production",
      base: scoreOrZero(base.production_score),
      compare: scoreOrZero(compare.production_score),
    },
  ];
  const baseName = base.name || "Player A";
  const compareName = compare.name || "Player B";

  return (
    <div
      className="mx-auto h-[188px] w-full max-w-[280px]"
      aria-label={
        `${baseName} in blue and ${compareName} in orange. `
        + "Value, opportunity, and production."
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart
          data={data}
          cx="50%"
          cy="50%"
          outerRadius="68%"
          margin={{ top: 16, right: 44, bottom: 16, left: 44 }}
        >
          <PolarGrid stroke={snapshotTokens.divider} />
          <PolarAngleAxis
            dataKey="metric"
            tick={{
              fill: snapshotTokens.textMuted,
              fontSize: 11,
            }}
          />
          <PolarRadiusAxis
            type="number"
            domain={[0, 100]}
            allowDataOverflow
            tick={false}
            axisLine={false}
          />
          <Radar
            dataKey="compare"
            stroke={PLAYER_B_COLOR}
            fill={PLAYER_B_COLOR}
            fillOpacity={0.28}
            strokeWidth={2}
            isAnimationActive={false}
          />
          <Radar
            dataKey="base"
            stroke={playerAColor()}
            fill={playerAColor()}
            fillOpacity={0.22}
            strokeWidth={2}
            isAnimationActive={false}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}

function LegendSwatch({ color }: { color: string }) {
  return (
    <span
      className="inline-block h-2.5 w-2.5 shrink-0 rounded-[3px]"
      style={{ background: color }}
      aria-hidden
    />
  );
}

function PlayerIdentity({
  player,
  side,
  onOpen,
}: {
  player: FantasyPlayerSnapshot;
  side: "left" | "right";
  onOpen?: () => void;
}) {
  const tone = assessmentStyles(player.overall_assessment);
  const reversed = side === "right";
  const color = reversed ? PLAYER_B_COLOR : playerAColor();
  const name = player.name || player.player_id;
  const className = `flex min-w-0 items-center gap-3 rounded-xl text-left ${
    reversed ? "flex-row-reverse" : ""
  } ${
    onOpen
      ? "cursor-pointer transition hover:opacity-80"
      : ""
  }`;
  const content = (
    <>
      <div
        className="relative h-16 w-16 shrink-0 sm:h-20 sm:w-20"
      >
        <div
          className="h-full w-full overflow-hidden rounded-xl border bg-white"
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
        {canonicalTeamAbbreviation(player.team) ? (
          <span
            className="absolute -bottom-1 -right-1 rounded-full border bg-white p-0.5"
            style={{ borderColor: snapshotTokens.border }}
          >
            <TeamLogo abbreviation={player.team} size={22} />
          </span>
        ) : null}
      </div>
      <div className={`min-w-0 ${reversed ? "text-right" : ""}`}>
        <span
          className={`flex items-center gap-2 ${
            reversed ? "justify-end" : ""
          }`}
        >
          {!reversed && <LegendSwatch color={color} />}
          <span
            className="truncate text-lg font-bold leading-tight"
            style={{ color: snapshotTokens.navy }}
          >
            {name}
          </span>
          {reversed && <LegendSwatch color={color} />}
        </span>
        <span
          className="mt-0.5 block text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {[player.position, player.team]
            .filter(Boolean)
            .join(" · ") || "—"}
        </span>
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
    </>
  );

  if (!onOpen) {
    return <div className={className}>{content}</div>;
  }

  return (
    <button
      type="button"
      onClick={onOpen}
      className={className}
      aria-label={`Open ${name} snapshot`}
    >
      {content}
    </button>
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
  const shift = advantageShift(left, right, higherIsBetter);
  const favoredColor = shift < 0 ? playerAColor() : PLAYER_B_COLOR;
  const reach = Math.abs(shift) * 50;

  return (
    <div
      className="border-b py-3 last:border-0"
      style={{ borderColor: snapshotTokens.divider }}
    >
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <p
          className="text-left text-base font-bold tabular-nums"
          style={{ color: leftColor }}
        >
          {display(left)}
        </p>
        <p
          className="w-[5.75rem] text-center text-[10px] font-medium uppercase leading-tight tracking-wide"
          style={{ color: snapshotTokens.textMuted }}
        >
          {label}
        </p>
        <p
          className="text-right text-base font-bold tabular-nums"
          style={{ color: rightColor }}
        >
          {display(right)}
        </p>
      </div>
      <div className="relative mt-2 h-3">
        <div
          className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full"
          style={{ background: snapshotTokens.divider }}
        />
        {shift !== 0 && (
          <div
            className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full"
            style={{
              width: `${reach}%`,
              left: shift < 0 ? `${50 - reach}%` : "50%",
              background: favoredColor,
            }}
          />
        )}
        <div
          className="absolute left-1/2 top-0 h-full w-0.5 -translate-x-1/2 rounded-full"
          style={{ background: snapshotTokens.navy }}
          aria-hidden
        />
      </div>
    </div>
  );
}

function advantageShift(
  left: number | null | undefined,
  right: number | null | undefined,
  higherIsBetter: boolean
): number {
  const finite = (value: number | null | undefined) =>
    value != null && Number.isFinite(value) ? Math.abs(value) : null;
  const leftValue = finite(left);
  const rightValue = finite(right);
  if (leftValue == null && rightValue == null) {
    return 0;
  }
  if (leftValue == null) {
    return higherIsBetter ? 1 : -1;
  }
  if (rightValue == null) {
    return higherIsBetter ? -1 : 1;
  }
  if (leftValue === rightValue) {
    return 0;
  }
  const rightFavored = higherIsBetter
    ? rightValue > leftValue
    : rightValue < leftValue;
  const other = rightFavored ? leftValue : rightValue;
  const gap = Math.abs(leftValue - rightValue);
  const magnitude = other === 0 ? 1 : Math.min(1, gap / other);
  return rightFavored ? magnitude : -magnitude;
}

function CompareHeaders({
  leftName,
  rightName,
}: {
  leftName: string;
  rightName: string;
}) {
  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 pt-3">
      <p
        className="line-clamp-2 text-left text-xs font-semibold leading-tight"
        style={{ color: snapshotTokens.navy }}
        title={leftName}
      >
        {leftName}
      </p>
      <span className="w-[5.75rem]" aria-hidden />
      <p
        className="line-clamp-2 text-right text-xs font-semibold leading-tight"
        style={{ color: snapshotTokens.navy }}
        title={rightName}
      >
        {rightName}
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
      "Use the assessment score with opportunity and season "
      + "production. Ownership is listed on its own.",
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

  const baseName = base.name || "Player A";
  const compareName = compare.name || "Player B";

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
        <div className="grid items-center gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(220px,280px)_minmax(0,1fr)]">
          <div className="min-w-0 justify-self-start">
            <PlayerIdentity
              player={base}
              side="left"
              onOpen={
                onOpenPlayer
                  ? () => onOpenPlayer(base.player_id)
                  : undefined
              }
            />
          </div>
          <OverlayRadar base={base} compare={compare} />
          <div className="min-w-0 justify-self-end">
            <PlayerIdentity
              player={compare}
              side="right"
              onOpen={
                onOpenPlayer
                  ? () => onOpenPlayer(compare.player_id)
                  : undefined
              }
            />
          </div>
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

      <div
        className={`grid items-start gap-4 ${
          [
            true,
            hasOpportunityMetrics,
            metricKeys.size > 0,
          ].filter(Boolean).length >= 3
            ? "lg:grid-cols-3"
            : "lg:grid-cols-2"
        }`}
      >
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
        <CompareHeaders
          leftName={baseName}
          rightName={compareName}
        />
        <div>
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
          <CompareHeaders
            leftName={baseName}
            rightName={compareName}
          />
          <div>
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
          <CompareHeaders
            leftName={baseName}
            rightName={compareName}
          />
          <div>
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
      </div>

      {onBack && (
        <div className="flex flex-wrap gap-2">
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
        </div>
      )}
    </div>
  );
}
