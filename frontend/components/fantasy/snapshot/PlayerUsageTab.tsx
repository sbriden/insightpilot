"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import {
  FantasyPlayerUsage,
  FantasyScoringFormat,
  FantasyUsageDirection,
  FantasyUsageMetricCard,
  FantasyUsagePeriod,
  getFantasyPlayerUsage,
} from "@/services/api";

import {
  formatMetricValue,
  snapshotTokens,
} from "./tokens";

interface Props {
  playerId: string;
  defaultSeason?: number | null;
}

const PERIOD_OPTIONS: Array<{
  value: FantasyUsagePeriod;
  label: string;
}> = [
  { value: "full_season", label: "Full Season" },
  { value: "last_8", label: "Last 8 Games" },
  { value: "last_6", label: "Last 6 Games" },
  { value: "last_4", label: "Last 4 Games" },
  { value: "last_3", label: "Last 3 Games" },
];

const SCORING_OPTIONS: Array<{
  value: FantasyScoringFormat;
  label: string;
}> = [
  { value: "ppr", label: "PPR" },
  { value: "half_ppr", label: "Half PPR" },
  { value: "standard", label: "Standard" },
];

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className="rounded-[10px] border bg-white p-4 sm:p-5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-[15px] font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        {title}
      </h3>
      {subtitle && (
        <p
          className="mt-1 text-xs"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {subtitle}
        </p>
      )}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function CompactSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="inline-flex items-center gap-2 text-sm">
      <span
        className="text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-full border bg-white px-3 py-1.5 text-sm outline-none"
        style={{
          borderColor: snapshotTokens.border,
          color: snapshotTokens.textPrimary,
        }}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function directionMeta(direction: FantasyUsageDirection | string) {
  switch (direction) {
    case "increasing":
      return {
        arrow: "↑",
        label: "Increasing",
        color: snapshotTokens.success,
      };
    case "decreasing":
      return {
        arrow: "↓",
        label: "Decreasing",
        color: snapshotTokens.negative,
      };
    case "volatile":
      return {
        arrow: "↕",
        label: "Volatile",
        color: snapshotTokens.warning,
      };
    case "insufficient":
      return {
        arrow: "—",
        label: "Limited sample",
        color: snapshotTokens.textMuted,
      };
    default:
      return {
        arrow: "→",
        label: "Stable",
        color: snapshotTokens.blue,
      };
  }
}

function formatUsageValue(
  value: number | null | undefined,
  format?: string | null
): string {
  if (value == null) {
    return "—";
  }
  if (format === "percent") {
    return `${formatMetricValue(value, 1)}%`;
  }
  return formatMetricValue(value, 1);
}

function UsageMetricCard({
  card,
}: {
  card: FantasyUsageMetricCard;
}) {
  const meta = directionMeta(card.direction);
  return (
    <div
      className="rounded-[10px] border p-3.5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <p
        className="text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {card.label}
      </p>
      <p
        className="mt-2 text-[26px] font-bold tabular-nums leading-none"
        style={{ color: snapshotTokens.textPrimary }}
      >
        {formatUsageValue(card.value, card.format)}
      </p>
      <p
        className="mt-2 text-xs font-semibold"
        style={{ color: meta.color }}
      >
        {card.change_label || `${meta.arrow} ${meta.label}`}
      </p>
    </div>
  );
}

export default function PlayerUsageTab({
  playerId,
  defaultSeason,
}: Props) {
  const [season, setSeason] = useState<number | null>(
    defaultSeason ?? null
  );
  const [period, setPeriod] =
    useState<FantasyUsagePeriod>("last_8");
  const [scoring, setScoring] =
    useState<FantasyScoringFormat>("ppr");
  const [usage, setUsage] = useState<FantasyPlayerUsage | null>(
    null
  );
  const [chartMetric, setChartMetric] = useState<string | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await getFantasyPlayerUsage(playerId, {
          season,
          period,
          scoring,
        });
        if (cancelled) {
          return;
        }
        setUsage(result.usage);
        if (season == null && result.usage.season != null) {
          setSeason(result.usage.season);
        }
        const firstMetric =
          result.usage.chart_metrics?.[0]?.key ?? null;
        setChartMetric((current) => {
          if (
            current
            && result.usage.chart_metrics.some(
              (metric) => metric.key === current
            )
          ) {
            return current;
          }
          return firstMetric;
        });
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        setUsage(null);
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load usage trends."
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [playerId, season, period, scoring]);

  const chartData = useMemo(() => {
    if (!usage || !chartMetric) {
      return [];
    }
    return usage.weekly_usage.map((game) => {
      const opportunity = game.opportunity || {};
      const production = game.production || {};
      const raw =
        opportunity[chartMetric] ?? production[chartMetric] ?? null;
      return {
        label: game.label || `W${game.week}`,
        value: typeof raw === "number" ? raw : null,
        fantasy_points:
          typeof production.fantasy_points === "number"
            ? production.fantasy_points
            : null,
      };
    });
  }, [usage, chartMetric]);

  const scatterData = useMemo(() => {
    return (
      usage?.opportunity_vs_production?.points.map((point) => ({
        ...point,
        name: point.label || `W${point.week}`,
      })) ?? []
    );
  }, [usage]);

  if (loading && !usage) {
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap gap-3">
          {[1, 2, 3].map((item) => (
            <div
              key={item}
              className="h-9 w-36 animate-pulse rounded-full"
              style={{ background: snapshotTokens.divider }}
            />
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <div
              key={item}
              className="h-28 animate-pulse rounded-[10px]"
              style={{ background: snapshotTokens.divider }}
            />
          ))}
        </div>
        <div
          className="h-64 animate-pulse rounded-[10px]"
          style={{ background: snapshotTokens.divider }}
        />
      </div>
    );
  }

  if (error) {
    return (
      <p
        className="rounded-[10px] border px-4 py-6 text-sm"
        style={{
          borderColor: snapshotTokens.border,
          color: snapshotTokens.negative,
        }}
      >
        {error}
      </p>
    );
  }

  if (!usage) {
    return null;
  }

  if (usage.empty_message) {
    return (
      <div className="space-y-4">
        <Controls
          usage={usage}
          season={season}
          period={period}
          scoring={scoring}
          onSeason={setSeason}
          onPeriod={setPeriod}
          onScoring={setScoring}
        />
        <p
          className="rounded-[10px] border px-4 py-8 text-center text-sm"
          style={{
            borderColor: snapshotTokens.border,
            color: snapshotTokens.textSecondary,
          }}
        >
          {usage.empty_message}
        </p>
      </div>
    );
  }

  const activeChart =
    usage.chart_metrics.find(
      (metric) => metric.key === chartMetric
    ) || usage.chart_metrics[0];

  return (
    <div className="space-y-4">
      <Controls
        usage={usage}
        season={season}
        period={period}
        scoring={scoring}
        onSeason={setSeason}
        onPeriod={setPeriod}
        onScoring={setScoring}
      />

      <Section
        title="Role & Opportunity"
        subtitle={`Current period averages · ${usage.sample_size} games`}
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {usage.role_opportunity.map((card) => (
            <UsageMetricCard key={card.key} card={card} />
          ))}
        </div>
      </Section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.9fr)]">
        <Section
          title="Usage Trend"
          subtitle={
            activeChart
              ? `${activeChart.label} by week`
              : "Weekly usage"
          }
        >
          <div className="mb-4 flex flex-wrap gap-2">
            {usage.chart_metrics.map((metric) => {
              const selected = metric.key === chartMetric;
              return (
                <button
                  key={metric.key}
                  type="button"
                  onClick={() => setChartMetric(metric.key)}
                  className="rounded-full border px-3 py-1 text-xs font-semibold transition"
                  style={{
                    borderColor: selected
                      ? snapshotTokens.blue
                      : snapshotTokens.border,
                    background: selected
                      ? snapshotTokens.blueLight
                      : snapshotTokens.white,
                    color: selected
                      ? snapshotTokens.blue
                      : snapshotTokens.textSecondary,
                  }}
                >
                  {metric.label}
                </button>
              );
            })}
          </div>
          {chartData.length === 0 ? (
            <p
              className="text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              No weekly usage points available yet.
            </p>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid
                    stroke={snapshotTokens.divider}
                    vertical={false}
                  />
                  <XAxis
                    dataKey="label"
                    tick={{
                      fill: snapshotTokens.textMuted,
                      fontSize: 11,
                    }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{
                      fill: snapshotTokens.textMuted,
                      fontSize: 11,
                    }}
                    axisLine={false}
                    tickLine={false}
                    width={40}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: 8,
                      borderColor: snapshotTokens.border,
                    }}
                    formatter={(value: number | null) => [
                      formatUsageValue(
                        value,
                        chartMetric
                          && [
                              "snap_pct",
                              "target_share",
                              "rush_share",
                              "qb_rush_share",
                              "route_participation",
                            ].includes(chartMetric)
                          ? "percent"
                          : "number"
                      ),
                      activeChart?.label || "Value",
                    ]}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke={snapshotTokens.blue}
                    strokeWidth={2.5}
                    dot={{
                      r: 3.5,
                      fill: snapshotTokens.blue,
                    }}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Section>

        <Section
          title="InsightPilot Signals"
          subtitle="Automatically generated from recent usage"
        >
          <div className="space-y-3">
            {usage.signals.length === 0 ? (
              <p
                className="text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                No clear signals yet for this sample.
              </p>
            ) : (
              usage.signals.map((signal) => {
                const meta = directionMeta(signal.direction);
                return (
                  <div
                    key={`${signal.signal_type}-${signal.metric}`}
                    className="rounded-[10px] border p-3"
                    style={{
                      borderColor: snapshotTokens.border,
                      background: snapshotTokens.purpleLight,
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p
                        className="text-sm font-semibold"
                        style={{ color: snapshotTokens.purple }}
                      >
                        <span style={{ color: meta.color }}>
                          {meta.arrow}
                        </span>{" "}
                        {signal.headline}
                      </p>
                      {signal.confidence && (
                        <span
                          className="shrink-0 text-[10px] font-semibold uppercase tracking-wide"
                          style={{
                            color: snapshotTokens.textMuted,
                          }}
                        >
                          {signal.confidence}
                        </span>
                      )}
                    </div>
                    {signal.body && (
                      <p
                        className="mt-1.5 text-xs leading-5"
                        style={{
                          color: snapshotTokens.textSecondary,
                        }}
                      >
                        {signal.body}
                      </p>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </Section>
      </div>

      {usage.recent_role_change && (
        <Section
          title="Recent Role Change"
          subtitle={`${usage.recent_role_change.current_label} vs ${usage.recent_role_change.previous_label}`}
        >
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr
                  className="border-b text-[11px] uppercase tracking-wide"
                  style={{
                    borderColor: snapshotTokens.divider,
                    color: snapshotTokens.textMuted,
                  }}
                >
                  <th className="py-2 pr-3 font-medium">Metric</th>
                  <th className="px-2 py-2 text-right font-medium">
                    Previous
                  </th>
                  <th className="px-2 py-2 text-right font-medium">
                    Current
                  </th>
                  <th className="px-2 py-2 text-right font-medium">
                    Change
                  </th>
                </tr>
              </thead>
              <tbody>
                {usage.recent_role_change.metrics.map((metric) => {
                  const meta = directionMeta(metric.direction);
                  const changeText =
                    metric.format === "percent"
                      && metric.change_pts != null
                      ? `${metric.change_pts > 0 ? "+" : ""}${formatMetricValue(metric.change_pts, 1)} pts`
                      : metric.change_pct != null
                        ? `${metric.change_pct > 0 ? "+" : ""}${formatMetricValue(metric.change_pct, 0)}%`
                        : "—";
                  return (
                    <tr
                      key={metric.key}
                      className="border-b last:border-0"
                      style={{
                        borderColor: snapshotTokens.divider,
                      }}
                    >
                      <td
                        className="py-2.5 pr-3 font-medium"
                        style={{
                          color: snapshotTokens.textPrimary,
                        }}
                      >
                        {metric.label}
                      </td>
                      <td
                        className="px-2 py-2.5 text-right tabular-nums"
                        style={{
                          color: snapshotTokens.textSecondary,
                        }}
                      >
                        {formatUsageValue(
                          metric.previous,
                          metric.format
                        )}
                      </td>
                      <td
                        className="px-2 py-2.5 text-right tabular-nums font-semibold"
                        style={{
                          color: snapshotTokens.textPrimary,
                        }}
                      >
                        {formatUsageValue(
                          metric.current,
                          metric.format
                        )}
                      </td>
                      <td
                        className="px-2 py-2.5 text-right text-xs font-semibold tabular-nums"
                        style={{ color: meta.color }}
                      >
                        {meta.arrow} {changeText}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {usage.recent_role_change.interpretation && (
            <p
              className="mt-4 rounded-[10px] border px-3 py-2.5 text-sm"
              style={{
                borderColor: snapshotTokens.border,
                background: snapshotTokens.background,
                color: snapshotTokens.textPrimary,
              }}
            >
              <span
                className="font-semibold"
                style={{ color: snapshotTokens.purple }}
              >
                ✦ Why it matters
              </span>
              <span className="mt-1 block text-xs leading-5"
                style={{ color: snapshotTokens.textSecondary }}
              >
                {usage.recent_role_change.interpretation}
              </span>
            </p>
          )}
        </Section>
      )}

      <div className="grid gap-4 xl:grid-cols-2">
        {usage.opportunity_vs_production && (
          <Section
            title="Opportunity vs. Production"
            subtitle={
              usage.opportunity_vs_production.opportunity_metric.label
              + " vs "
              + usage.opportunity_vs_production.production_metric.label
            }
          >
            {scatterData.length < 3 ? (
              <p
                className="text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                {usage.opportunity_vs_production.interpretation
                  || "Not enough paired games yet."}
              </p>
            ) : (
              <>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ScatterChart>
                      <CartesianGrid
                        stroke={snapshotTokens.divider}
                      />
                      <XAxis
                        type="number"
                        dataKey="opportunity"
                        name="Opportunity"
                        tick={{
                          fill: snapshotTokens.textMuted,
                          fontSize: 11,
                        }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        type="number"
                        dataKey="production"
                        name="Production"
                        tick={{
                          fill: snapshotTokens.textMuted,
                          fontSize: 11,
                        }}
                        axisLine={false}
                        tickLine={false}
                        width={36}
                      />
                      <ZAxis range={[60, 60]} />
                      <Tooltip
                        cursor={{
                          strokeDasharray: "3 3",
                        }}
                        contentStyle={{
                          borderRadius: 8,
                          borderColor: snapshotTokens.border,
                        }}
                        formatter={(
                          value: number,
                          name: string
                        ) => [
                          formatMetricValue(value, 1),
                          name === "opportunity"
                            ? usage.opportunity_vs_production
                                ?.opportunity_metric.label
                            : usage.opportunity_vs_production
                                ?.production_metric.label,
                        ]}
                        labelFormatter={(_, payload) => {
                          const point = payload?.[0]?.payload as
                            | { name?: string }
                            | undefined;
                          return point?.name || "";
                        }}
                      />
                      <Scatter
                        data={scatterData}
                        fill={snapshotTokens.blue}
                      />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
                {usage.opportunity_vs_production.interpretation && (
                  <p
                    className="mt-3 text-xs leading-5"
                    style={{
                      color: snapshotTokens.textSecondary,
                    }}
                  >
                    <span
                      className="font-semibold"
                      style={{ color: snapshotTokens.purple }}
                    >
                      ✦{" "}
                    </span>
                    {usage.opportunity_vs_production.interpretation}
                  </p>
                )}
              </>
            )}
          </Section>
        )}

        {usage.consistency && (
          <Section
            title="Usage Consistency"
            subtitle={usage.consistency.metric_label}
          >
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                ["Median", usage.consistency.median],
                ["Average", usage.consistency.average],
                ["Low", usage.consistency.low],
                ["High", usage.consistency.high],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <p
                    className="text-[11px] font-semibold uppercase tracking-wide"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    {label}
                  </p>
                  <p
                    className="mt-1 text-lg font-bold tabular-nums"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {formatUsageValue(
                      value as number | null,
                      usage.consistency?.format
                    )}
                  </p>
                </div>
              ))}
            </div>
            {usage.consistency.threshold_counts
              && usage.consistency.threshold_counts.length > 0 && (
              <div className="mt-4 space-y-2">
                {usage.consistency.threshold_counts.map((row) => (
                  <div
                    key={row.label}
                    className="flex items-center justify-between text-sm"
                  >
                    <span
                      style={{
                        color: snapshotTokens.textSecondary,
                      }}
                    >
                      {row.label}
                    </span>
                    <span
                      className="font-semibold tabular-nums"
                      style={{
                        color: snapshotTokens.textPrimary,
                      }}
                    >
                      {row.count} / {row.total}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Section>
        )}
      </div>

      {usage.position_context && (
        <Section
          title="Position Context"
          subtitle={`Player vs ${usage.position_context.position_group} season average`}
        >
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr
                  className="border-b text-[11px] uppercase tracking-wide"
                  style={{
                    borderColor: snapshotTokens.divider,
                    color: snapshotTokens.textMuted,
                  }}
                >
                  <th className="py-2 pr-3 font-medium">Metric</th>
                  <th className="px-2 py-2 text-right font-medium">
                    Player
                  </th>
                  <th className="px-2 py-2 text-right font-medium">
                    {usage.position_context.position_group} Avg
                  </th>
                </tr>
              </thead>
              <tbody>
                {usage.position_context.metrics.map((metric) => (
                  <tr
                    key={metric.key}
                    className="border-b last:border-0"
                    style={{
                      borderColor: snapshotTokens.divider,
                    }}
                  >
                    <td
                      className="py-2.5 pr-3 font-medium"
                      style={{
                        color: snapshotTokens.textPrimary,
                      }}
                    >
                      {metric.label}
                    </td>
                    <td
                      className="px-2 py-2.5 text-right tabular-nums font-semibold"
                      style={{
                        color: snapshotTokens.textPrimary,
                      }}
                    >
                      {formatUsageValue(
                        metric.player,
                        metric.format
                      )}
                    </td>
                    <td
                      className="px-2 py-2.5 text-right tabular-nums"
                      style={{
                        color: snapshotTokens.textSecondary,
                      }}
                    >
                      {formatUsageValue(
                        metric.position_avg,
                        metric.format
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      <Section
        title="Weekly Usage"
        subtitle="Selected period detail"
      >
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr
                className="border-b text-[11px] uppercase tracking-wide"
                style={{
                  borderColor: snapshotTokens.divider,
                  color: snapshotTokens.textMuted,
                }}
              >
                <th className="py-2 pr-3 font-medium">Week</th>
                <th className="px-2 py-2 font-medium">Opp</th>
                {usage.chart_metrics.map((metric) => (
                  <th
                    key={metric.key}
                    className="px-2 py-2 text-right font-medium"
                  >
                    {metric.label}
                  </th>
                ))}
                <th className="px-2 py-2 text-right font-medium">
                  FPTS
                </th>
              </tr>
            </thead>
            <tbody>
              {[...usage.weekly_usage].reverse().map((game) => (
                <tr
                  key={`${game.season}-${game.week}`}
                  className="border-b last:border-0"
                  style={{ borderColor: snapshotTokens.divider }}
                >
                  <td
                    className="py-2.5 pr-3 font-medium"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {game.label || `W${game.week}`}
                  </td>
                  <td
                    className="px-2 py-2.5"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    {game.opponent_label || game.opponent || "—"}
                  </td>
                  {usage.chart_metrics.map((metric) => {
                    const value =
                      game.opportunity?.[metric.key]
                      ?? game.production?.[metric.key]
                      ?? null;
                    const isPercent = [
                      "snap_pct",
                      "target_share",
                      "rush_share",
                      "qb_rush_share",
                      "route_participation",
                    ].includes(metric.key);
                    return (
                      <td
                        key={metric.key}
                        className="px-2 py-2.5 text-right tabular-nums"
                        style={{
                          color: snapshotTokens.textPrimary,
                        }}
                      >
                        {formatUsageValue(
                          typeof value === "number" ? value : null,
                          isPercent ? "percent" : "number"
                        )}
                      </td>
                    );
                  })}
                  <td
                    className="px-2 py-2.5 text-right tabular-nums font-semibold"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {formatMetricValue(
                      game.production?.fantasy_points
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {usage.data_note && (
        <p
          className="text-[11px] leading-4"
          style={{ color: snapshotTokens.textMuted }}
        >
          {usage.data_note}
        </p>
      )}
    </div>
  );
}

function Controls({
  usage,
  season,
  period,
  scoring,
  onSeason,
  onPeriod,
  onScoring,
}: {
  usage: FantasyPlayerUsage;
  season: number | null;
  period: FantasyUsagePeriod;
  scoring: FantasyScoringFormat;
  onSeason: (value: number | null) => void;
  onPeriod: (value: FantasyUsagePeriod) => void;
  onScoring: (value: FantasyScoringFormat) => void;
}) {
  const seasons = (
    usage.available_seasons.length > 0
      ? usage.available_seasons
      : usage.season != null
        ? [usage.season]
        : []
  ).map((value) => ({
    value: String(value),
    label: String(value),
  }));

  return (
    <div className="flex flex-wrap items-center gap-3">
      <CompactSelect
        label="Season"
        value={String(season ?? usage.season)}
        options={seasons}
        onChange={(value) => onSeason(Number(value))}
      />
      <CompactSelect
        label="Period"
        value={period}
        options={PERIOD_OPTIONS}
        onChange={(value) =>
          onPeriod(value as FantasyUsagePeriod)
        }
      />
      <CompactSelect
        label="Scoring"
        value={scoring}
        options={SCORING_OPTIONS}
        onChange={(value) =>
          onScoring(value as FantasyScoringFormat)
        }
      />
    </div>
  );
}
