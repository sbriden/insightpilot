"use client";

import { useMemo, useState } from "react";
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ZAxis,
  Legend,
} from "recharts";

import {
  FantasyPlayerSearchHit,
} from "@/services/api";

import {
  formatScore,
  snapshotTokens,
} from "@/components/fantasy/snapshot/tokens";

interface Props {
  players: FantasyPlayerSearchHit[];
  onSelectPlayer: (playerId: string) => void;
}

type ScatterPoint = {
  player_id: string;
  name: string;
  position: string;
  team: string;
  opportunity: number;
  production: number;
  total: number;
  fantasy_points: number | null;
  ownership: number | null;
};

const POSITION_COLORS: Record<string, string> = {
  QB: "#7C3AED",
  RB: "#16A34A",
  WR: "#1677FF",
  TE: "#F59E0B",
  K: "#5B6B7F",
  PK: "#5B6B7F",
  FB: "#0F766E",
  HB: "#15803D",
};

const POSITION_ORDER = [
  "QB",
  "RB",
  "WR",
  "TE",
  "K",
  "FB",
  "HB",
];

function colorForPosition(position: string): string {
  return (
    POSITION_COLORS[position.toUpperCase()]
    || snapshotTokens.textMuted
  );
}

function ownershipValue(
  raw: unknown
): number | null {
  if (raw == null || raw === "") {
    return null;
  }
  const numeric =
    typeof raw === "number" ? raw : Number(raw);
  if (!Number.isFinite(numeric)) {
    return null;
  }
  return numeric;
}

function ScatterTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ScatterPoint }>;
}) {
  if (!active || !payload?.[0]?.payload) {
    return null;
  }
  const point = payload[0].payload;
  return (
    <div
      className="rounded-lg border bg-white px-3 py-2 text-xs shadow-md"
      style={{ borderColor: snapshotTokens.border }}
    >
      <p
        className="font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        {point.name}
      </p>
      <p style={{ color: snapshotTokens.textSecondary }}>
        {[point.position, point.team]
          .filter(Boolean)
          .join(" · ")}
      </p>
      <p
        className="mt-1 tabular-nums"
        style={{ color: snapshotTokens.textPrimary }}
      >
        Opp {Math.round(point.opportunity)} · Prod{" "}
        {Math.round(point.production)} · Total{" "}
        {Math.round(point.total)}
        {point.fantasy_points != null
          && ` · ${point.fantasy_points.toFixed(1)} pts`}
        {point.ownership != null
          && ` · ${point.ownership.toFixed(1)}% owned`}
      </p>
    </div>
  );
}

function OwnershipRangeSlider({
  min,
  max,
  onChange,
}: {
  min: number;
  max: number;
  onChange: (next: { min: number; max: number }) => void;
}) {
  const spanLeft = Math.min(min, max);
  const spanRight = Math.max(min, max);

  return (
    <div className="relative h-5 w-full">
      <div
        className="absolute left-0 right-0 top-1/2 h-1 -translate-y-1/2 rounded-full"
        style={{ background: snapshotTokens.divider }}
      />
      <div
        className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full"
        style={{
          left: `${spanLeft}%`,
          width: `${Math.max(spanRight - spanLeft, 0)}%`,
          background: snapshotTokens.blue,
        }}
      />
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={min}
        aria-label="Minimum ownership"
        onChange={(event) => {
          const nextMin = Number(event.target.value);
          onChange({
            min: Math.min(nextMin, max),
            max,
          });
        }}
        className="ownership-range-thumb absolute inset-0 w-full appearance-none bg-transparent"
        style={{ zIndex: min > 100 - max ? 5 : 3 }}
      />
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={max}
        aria-label="Maximum ownership"
        onChange={(event) => {
          const nextMax = Number(event.target.value);
          onChange({
            min,
            max: Math.max(nextMax, min),
          });
        }}
        className="ownership-range-thumb absolute inset-0 w-full appearance-none bg-transparent"
        style={{ zIndex: 4 }}
      />
      <style>{`
        .ownership-range-thumb {
          pointer-events: none;
          height: 1.25rem;
          margin: 0;
        }
        .ownership-range-thumb::-webkit-slider-thumb {
          pointer-events: auto;
          -webkit-appearance: none;
          appearance: none;
          width: 0.7rem;
          height: 0.7rem;
          border-radius: 9999px;
          background: #1677FF;
          border: 1.5px solid #FFFFFF;
          box-shadow: 0 0 0 1px #DCE3EC;
          cursor: pointer;
        }
        .ownership-range-thumb::-moz-range-thumb {
          pointer-events: auto;
          width: 0.7rem;
          height: 0.7rem;
          border: 1.5px solid #FFFFFF;
          border-radius: 9999px;
          background: #1677FF;
          box-shadow: 0 0 0 1px #DCE3EC;
          cursor: pointer;
        }
        .ownership-range-thumb::-webkit-slider-runnable-track {
          background: transparent;
          height: 1.25rem;
        }
        .ownership-range-thumb::-moz-range-track {
          background: transparent;
          height: 1.25rem;
          border: none;
        }
      `}</style>
    </div>
  );
}

function ScatterDot({
  cx,
  cy,
  fill,
  payload,
  hoveredPlayerId,
}: {
  cx?: number;
  cy?: number;
  fill?: string;
  payload?: ScatterPoint;
  hoveredPlayerId: string | null;
}) {
  if (
    cx == null
    || cy == null
    || !payload
  ) {
    return null;
  }

  const highlighted =
    hoveredPlayerId != null
    && payload.player_id === hoveredPlayerId;
  const dimmed =
    hoveredPlayerId != null && !highlighted;

  return (
    <circle
      cx={cx}
      cy={cy}
      r={highlighted ? 9 : 5}
      fill={fill}
      fillOpacity={dimmed ? 0.22 : highlighted ? 1 : 0.8}
      stroke={
        highlighted ? snapshotTokens.navy : "transparent"
      }
      strokeWidth={highlighted ? 2.5 : 0}
      style={{
        transition: "r 120ms ease, fill-opacity 120ms ease",
      }}
    />
  );
}

export default function PlayerOverviewScatter({
  players,
  onSelectPlayer,
}: Props) {
  const [ownershipMin, setOwnershipMin] = useState(0);
  const [ownershipMax, setOwnershipMax] = useState(100);
  const [hoveredPlayerId, setHoveredPlayerId] = useState<
    string | null
  >(null);

  const scoredPlayers = useMemo(
    () =>
      players.filter(
        (player) =>
          player.opportunity_score != null
          && player.production_score != null
          && Number.isFinite(player.opportunity_score)
          && Number.isFinite(player.production_score)
      ),
    [players]
  );

  const hasOwnershipData = useMemo(
    () =>
      scoredPlayers.some(
        (player) => ownershipValue(player.ownership) != null
      ),
    [scoredPlayers]
  );

  const filterActive =
    hasOwnershipData
    && (ownershipMin > 0 || ownershipMax < 100);

  const data: ScatterPoint[] = useMemo(
    () =>
      scoredPlayers
        .filter((player) => {
          if (!filterActive) {
            return true;
          }
          const ownership = ownershipValue(player.ownership);
          if (ownership == null) {
            return false;
          }
          return (
            ownership >= ownershipMin
            && ownership <= ownershipMax
          );
        })
        .map((player) => {
          const opportunity = Number(player.opportunity_score);
          const production = Number(player.production_score);
          return {
            player_id: player.player_id,
            name: player.name,
            position: (player.position || "").toUpperCase(),
            team: player.team || "",
            opportunity,
            production,
            total: opportunity + production,
            fantasy_points: player.fantasy_points ?? null,
            ownership: ownershipValue(player.ownership),
          };
        }),
    [
      scoredPlayers,
      filterActive,
      ownershipMin,
      ownershipMax,
    ]
  );

  const rankedRows = useMemo(
    () =>
      [...data].sort((left, right) => {
        const byTotal = right.total - left.total;
        if (byTotal !== 0) {
          return byTotal;
        }
        return left.name.localeCompare(
          right.name,
          undefined,
          { sensitivity: "base" }
        );
      }),
    [data]
  );

  const byPosition = new Map<string, ScatterPoint[]>();
  for (const point of data) {
    const key = point.position || "Other";
    const bucket = byPosition.get(key) ?? [];
    bucket.push(point);
    byPosition.set(key, bucket);
  }

  const series = [
    ...POSITION_ORDER.filter((position) =>
      byPosition.has(position)
    ),
    ...[...byPosition.keys()]
      .filter((position) => !POSITION_ORDER.includes(position))
      .sort(),
  ];

  function handleClick(point: unknown) {
    const record = point as ScatterPoint & {
      payload?: ScatterPoint;
    };
    const id =
      record?.player_id
      || record?.payload?.player_id;
    if (id) {
      onSelectPlayer(id);
    }
  }

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
            Opportunity vs Production
          </h3>
          <p
            className="mt-1 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Each dot is a player, colored by position. Hover a
            name in the table to highlight the bubble; click
            either to open the snapshot.
          </p>
        </div>
        <p
          className="text-xs"
          style={{ color: snapshotTokens.textMuted }}
        >
          {data.length} plotted
        </p>
      </div>

      <div className="mt-3 flex max-w-xs flex-wrap items-center gap-x-3 gap-y-1">
        <p
          className="text-[10px] font-semibold uppercase tracking-wide"
          style={{ color: snapshotTokens.textMuted }}
        >
          Ownership
        </p>
        <p
          className="text-[11px] tabular-nums"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {ownershipMin}%–{ownershipMax}%
        </p>
        {filterActive && (
          <button
            type="button"
            onClick={() => {
              setOwnershipMin(0);
              setOwnershipMax(100);
            }}
            className="text-[11px] font-medium"
            style={{ color: snapshotTokens.blue }}
          >
            Reset
          </button>
        )}
        <div className="w-full">
          <OwnershipRangeSlider
            min={ownershipMin}
            max={ownershipMax}
            onChange={({ min, max }) => {
              setOwnershipMin(min);
              setOwnershipMax(max);
            }}
          />
        </div>
        {!hasOwnershipData && (
          <p
            className="text-[11px]"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Ownership is not on the current player list yet.
          </p>
        )}
      </div>

      {data.length === 0 ? (
        <p
          className="mt-8 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          No players match the current ownership range with
          both opportunity and production scores.
        </p>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(17rem,0.85fr)]">
          <div className="h-[28rem] min-w-0 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart
                margin={{
                  top: 12,
                  right: 16,
                  bottom: 28,
                  left: 8,
                }}
              >
                <CartesianGrid
                  stroke={snapshotTokens.divider}
                  strokeDasharray="3 3"
                />
                <XAxis
                  type="number"
                  dataKey="opportunity"
                  name="Opportunity"
                  domain={[0, 100]}
                  tick={{
                    fill: snapshotTokens.textMuted,
                    fontSize: 11,
                  }}
                  axisLine={{ stroke: snapshotTokens.border }}
                  tickLine={false}
                  label={{
                    value: "Opportunity score",
                    position: "insideBottom",
                    offset: -16,
                    fill: snapshotTokens.textSecondary,
                    fontSize: 12,
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="production"
                  name="Production"
                  domain={[0, 100]}
                  tick={{
                    fill: snapshotTokens.textMuted,
                    fontSize: 11,
                  }}
                  axisLine={false}
                  tickLine={false}
                  label={{
                    value: "Production score",
                    angle: -90,
                    position: "insideLeft",
                    offset: 8,
                    fill: snapshotTokens.textSecondary,
                    fontSize: 12,
                  }}
                />
                <ZAxis
                  type="number"
                  dataKey="fantasy_points"
                  range={[40, 160]}
                />
                <Tooltip
                  cursor={{
                    strokeDasharray: "3 3",
                    stroke: snapshotTokens.border,
                  }}
                  content={<ScatterTooltip />}
                />
                <Legend
                  verticalAlign="top"
                  height={28}
                  wrapperStyle={{
                    fontSize: 12,
                    color: snapshotTokens.textSecondary,
                  }}
                />
                {series.map((position) => (
                  <Scatter
                    key={position}
                    name={position}
                    data={byPosition.get(position) ?? []}
                    fill={colorForPosition(position)}
                    cursor="pointer"
                    onClick={handleClick}
                    shape={(props) => (
                      <ScatterDot
                        {...props}
                        hoveredPlayerId={hoveredPlayerId}
                      />
                    )}
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          <div
            className="flex max-h-[28rem] min-w-0 flex-col overflow-hidden rounded-[10px] border"
            style={{ borderColor: snapshotTokens.border }}
          >
            <div
              className="border-b px-3 py-2.5"
              style={{
                borderColor: snapshotTokens.divider,
                background: snapshotTokens.background,
              }}
            >
              <p
                className="text-[13px] font-semibold"
                style={{ color: snapshotTokens.navy }}
              >
                Ranked players
              </p>
              <p
                className="mt-0.5 text-[11px]"
                style={{ color: snapshotTokens.textMuted }}
              >
                Sorted by production + opportunity
              </p>
            </div>
            <div className="min-h-0 flex-1 overflow-auto">
              <table className="min-w-full text-left text-sm">
                <thead
                  className="sticky top-0"
                  style={{ background: snapshotTokens.background }}
                >
                  <tr
                    className="border-b text-[11px] uppercase tracking-wide"
                    style={{
                      borderColor: snapshotTokens.divider,
                      color: snapshotTokens.textMuted,
                    }}
                  >
                    <th className="px-3 py-2 font-medium">
                      Player
                    </th>
                    <th className="px-2 py-2 text-right font-medium">
                      Prod
                    </th>
                    <th className="px-3 py-2 text-right font-medium">
                      Opp
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rankedRows.map((player) => {
                    const hovered =
                      hoveredPlayerId === player.player_id;
                    return (
                      <tr
                        key={player.player_id}
                        className="border-b last:border-0"
                        style={{
                          borderColor: snapshotTokens.divider,
                          background: hovered
                            ? snapshotTokens.blueLight
                            : "transparent",
                        }}
                        onMouseEnter={() =>
                          setHoveredPlayerId(player.player_id)
                        }
                        onMouseLeave={() =>
                          setHoveredPlayerId(null)
                        }
                      >
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            className="text-left font-medium"
                            style={{
                              color: snapshotTokens.textPrimary,
                            }}
                            onClick={() =>
                              onSelectPlayer(player.player_id)
                            }
                            onFocus={() =>
                              setHoveredPlayerId(
                                player.player_id
                              )
                            }
                            onBlur={() =>
                              setHoveredPlayerId(null)
                            }
                          >
                            {player.name}
                            <span
                              className="ml-1.5 text-[11px] font-normal"
                              style={{
                                color: snapshotTokens.textMuted,
                              }}
                            >
                              {[player.position, player.team]
                                .filter(Boolean)
                                .join(" · ")}
                            </span>
                          </button>
                        </td>
                        <td
                          className="px-2 py-2 text-right tabular-nums"
                          style={{
                            color: snapshotTokens.textPrimary,
                          }}
                        >
                          {formatScore(player.production)}
                        </td>
                        <td
                          className="px-3 py-2 text-right tabular-nums"
                          style={{
                            color: snapshotTokens.textPrimary,
                          }}
                        >
                          {formatScore(player.opportunity)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
