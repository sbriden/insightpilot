"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { PlayerGameMetrics } from "@/services/api";

import {
  formatMetricValue,
  snapshotTokens,
} from "./tokens";

interface Props {
  games: PlayerGameMetrics[];
  trendScore?: number | null;
}

export default function TrendChart({
  games,
  trendScore,
}: Props) {
  const data = games.map((game) => ({
    label: game.label || `W${game.week}`,
    fantasy_points: game.production?.fantasy_points ?? null,
  }));

  const values = data
    .map((row) => row.fantasy_points)
    .filter((value): value is number => value != null);

  const latest = values.length
    ? values[values.length - 1]
    : null;
  const prior = values.length > 1
    ? values[values.length - 2]
    : null;
  const delta =
    latest != null && prior != null && prior !== 0
      ? ((latest - prior) / Math.abs(prior)) * 100
      : null;

  return (
    <section
      className="rounded-[10px] border bg-white p-4 sm:p-5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3
            className="text-[15px] font-semibold"
            style={{ color: snapshotTokens.navy }}
          >
            Fantasy Points Trend
          </h3>
          <p
            className="mt-1 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Recent game PPR production
          </p>
        </div>
        <div className="text-right">
          <p
            className="text-[22px] font-bold tabular-nums leading-none"
            style={{ color: snapshotTokens.textPrimary }}
          >
            {formatMetricValue(latest)}
          </p>
          {delta != null && (
            <p
              className="mt-1 text-xs font-semibold tabular-nums"
              style={{
                color:
                  delta >= 0
                    ? snapshotTokens.success
                    : snapshotTokens.negative,
              }}
            >
              {delta >= 0 ? "↑" : "↓"}{" "}
              {Math.abs(delta).toFixed(1)}% vs prior game
            </p>
          )}
          {trendScore != null && (
            <p
              className="mt-1 text-[11px]"
              style={{ color: snapshotTokens.textMuted }}
            >
              Trend score {Math.round(trendScore)}
            </p>
          )}
        </div>
      </div>

      {data.length === 0 ? (
        <p
          className="mt-6 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          No recent game trend data available yet.
        </p>
      ) : (
        <div className="mt-4 h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid
                stroke={snapshotTokens.divider}
                strokeDasharray="3 3"
                vertical={false}
              />
              <XAxis
                dataKey="label"
                tick={{
                  fill: snapshotTokens.textMuted,
                  fontSize: 11,
                }}
                axisLine={{ stroke: snapshotTokens.border }}
                tickLine={false}
              />
              <YAxis
                tick={{
                  fill: snapshotTokens.textMuted,
                  fontSize: 11,
                }}
                axisLine={false}
                tickLine={false}
                width={32}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 8,
                  borderColor: snapshotTokens.border,
                  fontSize: 12,
                }}
              />
              <Line
                type="monotone"
                dataKey="fantasy_points"
                stroke={snapshotTokens.blue}
                strokeWidth={2.5}
                dot={{
                  r: 3.5,
                  fill: snapshotTokens.blue,
                  strokeWidth: 0,
                }}
                activeDot={{ r: 5 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
