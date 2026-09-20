"use client";

import {
  useEffect,
  useState,
  type ReactNode,
} from "react";

import {
  FantasyPlayerStats,
  FantasyScoringFormat,
  FantasyStatsGameRow,
  FantasyStatsMetric,
  getFantasyPlayerStats,
} from "@/services/api";

import {
  formatMetricValue,
  snapshotTokens,
} from "./tokens";

interface Props {
  playerId: string;
  defaultSeason?: number | null;
}

const SCORING_OPTIONS: Array<{
  id: FantasyScoringFormat;
  label: string;
}> = [
  { id: "ppr", label: "PPR" },
  { id: "half_ppr", label: "Half PPR" },
  { id: "standard", label: "Standard" },
];

function formatStatValue(
  metric: Pick<FantasyStatsMetric, "value" | "format">
): string {
  const format = metric.format || "number";
  if (format === "integer") {
    return formatMetricValue(metric.value, 0);
  }
  if (format === "percent") {
    return `${formatMetricValue(metric.value, 1)}%`;
  }
  return formatMetricValue(metric.value, 1);
}

function Section({
  title,
  children,
  note,
}: {
  title: string;
  children: ReactNode;
  note?: string | null;
}) {
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
          {title}
        </h3>
        {note && (
          <p
            className="text-[11px]"
            style={{ color: snapshotTokens.textMuted }}
          >
            {note}
          </p>
        )}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function MetricCard({
  label,
  value,
  context,
}: {
  label: string;
  value: string;
  context?: string | null;
}) {
  return (
    <div
      className="rounded-lg border px-3 py-3"
      style={{
        borderColor: snapshotTokens.divider,
        background: snapshotTokens.background,
      }}
    >
      <p
        className="text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {label}
      </p>
      <p
        className="mt-1.5 text-[22px] font-bold tabular-nums leading-none"
        style={{ color: snapshotTokens.textPrimary }}
      >
        {value}
      </p>
      {context && (
        <p
          className="mt-1.5 text-xs"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {context}
        </p>
      )}
    </div>
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

function gameLogColumns(positionGroup?: string | null) {
  const group = (positionGroup || "WR").toUpperCase();
  if (group === "QB") {
    return [
      { key: "pass_completions", label: "Cmp" },
      { key: "pass_attempts", label: "Att" },
      { key: "pass_yards", label: "Yds" },
      { key: "pass_tds", label: "TD" },
      { key: "interceptions", label: "INT" },
      { key: "rush_yards", label: "Rush" },
      { key: "fantasy_points", label: "FPTS" },
    ] as const;
  }
  if (group === "RB") {
    return [
      { key: "rush_attempts", label: "Att" },
      { key: "rush_yards", label: "Rush Yds" },
      { key: "receptions", label: "Rec" },
      { key: "receiving_yards", label: "Rec Yds" },
      { key: "touchdowns", label: "TD" },
      { key: "fantasy_points", label: "FPTS" },
    ] as const;
  }
  if (group === "K") {
    return [
      { key: "fg_made", label: "FG" },
      { key: "fg_att", label: "FGA" },
      { key: "fg_made_50_plus", label: "50+" },
      { key: "pat_made", label: "XP" },
      { key: "fantasy_points", label: "FPTS" },
    ] as const;
  }
  if (group === "DEF") {
    return [
      { key: "points_allowed", label: "PA" },
      { key: "sacks", label: "Sack" },
      { key: "interceptions", label: "INT" },
      { key: "fantasy_points", label: "FPTS" },
    ] as const;
  }
  return [
    { key: "targets", label: "Tgt" },
    { key: "receptions", label: "Rec" },
    { key: "receiving_yards", label: "Rec Yds" },
    { key: "touchdowns", label: "TD" },
    { key: "fantasy_points", label: "FPTS" },
  ] as const;
}

function gameCell(
  game: FantasyStatsGameRow,
  key: string
): string {
  const value = game[key as keyof FantasyStatsGameRow];
  if (typeof value !== "number") {
    return "—";
  }
  if (key === "fantasy_points") {
    return formatMetricValue(value, 1);
  }
  return formatMetricValue(value, 0);
}

function fptsTone(points: number | null | undefined): string {
  if (points == null) {
    return "transparent";
  }
  if (points >= 30) {
    return snapshotTokens.successLight;
  }
  if (points >= 20) {
    return snapshotTokens.blueLight;
  }
  if (points <= 0) {
    return snapshotTokens.negativeLight;
  }
  return "transparent";
}

export default function PlayerStatsTab({
  playerId,
  defaultSeason,
}: Props) {
  const [season, setSeason] = useState<number | null>(
    defaultSeason ?? null
  );
  const [scoring, setScoring] =
    useState<FantasyScoringFormat>("ppr");
  const [stats, setStats] = useState<FantasyPlayerStats | null>(
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
        const result = await getFantasyPlayerStats(playerId, {
          season,
          scoring,
        });
        if (cancelled) {
          return;
        }
        setStats(result.stats);
        if (
          season == null
          && result.stats.season != null
        ) {
          setSeason(result.stats.season);
        }
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        setStats(null);
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load player stats."
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
  }, [playerId, season, scoring]);

  if (loading && !stats) {
    return (
      <div className="space-y-3 animate-pulse">
        <div
          className="h-10 rounded-[10px]"
          style={{ background: snapshotTokens.divider }}
        />
        <div
          className="h-36 rounded-[10px]"
          style={{ background: snapshotTokens.divider }}
        />
        <div
          className="h-56 rounded-[10px]"
          style={{ background: snapshotTokens.divider }}
        />
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="rounded-[10px] border bg-white px-4 py-8 text-sm"
        style={{
          borderColor: snapshotTokens.border,
          color: snapshotTokens.textSecondary,
        }}
      >
        {error}
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  const production = stats.fantasy_production;
  const consistency = stats.consistency;
  const seasons = stats.available_seasons?.length
    ? stats.available_seasons
    : stats.season
      ? [stats.season]
      : [];
  const columns = gameLogColumns(stats.position_group);
  const historyIsQb = stats.position_group === "QB";
  const historyIsRb = stats.position_group === "RB";
  const historyIsK = stats.position_group === "K";

  return (
    <div className="space-y-4">
      <div
        className="flex flex-wrap items-center gap-3 rounded-[10px] border bg-white px-4 py-3"
        style={{ borderColor: snapshotTokens.border }}
      >
        <CompactSelect
          label="Season"
          value={String(season ?? stats.season)}
          options={seasons.map((value) => ({
            value: String(value),
            label: String(value),
          }))}
          onChange={(value) => setSeason(Number(value))}
        />
        <CompactSelect
          label="Scoring"
          value={scoring}
          options={SCORING_OPTIONS.map((option) => ({
            value: option.id,
            label: option.label,
          }))}
          onChange={(value) =>
            setScoring(value as FantasyScoringFormat)
          }
        />
        {loading && (
          <p
            className="text-xs"
            style={{ color: snapshotTokens.textMuted }}
          >
            Updating…
          </p>
        )}
      </div>

      {stats.empty_message ? (
        <Section title="Fantasy Production">
          <p
            className="text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {stats.empty_message}
          </p>
        </Section>
      ) : (
        <>
          <Section
            title="Fantasy Production"
            note={stats.data_note}
          >
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <MetricCard
                label="Fantasy Points"
                value={formatMetricValue(production?.fantasy_points)}
                context={production?.position_rank_label}
              />
              <MetricCard
                label="FPPG"
                value={formatMetricValue(production?.fppg)}
                context={
                  production?.position_rank_label
                    ? `${production.position_rank_label} pace`
                    : null
                }
              />
              <MetricCard
                label="Games"
                value={formatMetricValue(production?.games, 0)}
                context={production?.games_context}
              />
              <MetricCard
                label="Weekly Ceiling"
                value={formatMetricValue(production?.weekly_ceiling)}
                context={
                  production?.ceiling_week != null
                    ? `Week ${production.ceiling_week}`
                    : null
                }
              />
              <MetricCard
                label="Weekly Floor"
                value={formatMetricValue(production?.weekly_floor)}
                context={
                  production?.floor_week != null
                    ? `Week ${production.floor_week}`
                    : null
                }
              />
              <MetricCard
                label="15+ Point Games"
                value={formatMetricValue(
                  production?.top_12_finishes,
                  0
                )}
                context={
                  production?.top_12_rate != null
                    ? `${production.top_12_rate}% of games`
                    : null
                }
              />
            </div>
          </Section>

          {stats.production_breakdown.length > 0 && (
            <Section title="Production Breakdown">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {stats.production_breakdown.map((group) => (
                  <div key={group.title}>
                    <p
                      className="text-[12px] font-semibold uppercase tracking-wide"
                      style={{ color: snapshotTokens.textMuted }}
                    >
                      {group.title}
                    </p>
                    <dl className="mt-2 space-y-1.5">
                      {group.metrics.map((metric) => (
                        <div
                          key={metric.key}
                          className="flex items-baseline justify-between gap-3 border-b pb-1.5 last:border-0"
                          style={{ borderColor: snapshotTokens.divider }}
                        >
                          <dt
                            className="text-sm"
                            style={{
                              color: snapshotTokens.textSecondary,
                            }}
                          >
                            {metric.label}
                          </dt>
                          <dd
                            className="text-sm font-semibold tabular-nums"
                            style={{
                              color: snapshotTokens.textPrimary,
                            }}
                          >
                            {formatStatValue(metric)}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {stats.season_history.length > 0 && (
            <Section title="Season History">
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
                      <th className="py-2 pr-3 font-medium">Season</th>
                      <th className="px-2 py-2 text-right font-medium">GP</th>
                      <th className="px-2 py-2 text-right font-medium">FPTS</th>
                      <th className="px-2 py-2 text-right font-medium">FPPG</th>
                      {historyIsQb ? (
                        <>
                          <th className="px-2 py-2 text-right font-medium">Pass Yds</th>
                          <th className="px-2 py-2 text-right font-medium">Pass TD</th>
                          <th className="px-2 py-2 text-right font-medium">INT</th>
                        </>
                      ) : historyIsRb ? (
                        <>
                          <th className="px-2 py-2 text-right font-medium">Rush Yds</th>
                          <th className="px-2 py-2 text-right font-medium">Rec</th>
                          <th className="px-2 py-2 text-right font-medium">Rec Yds</th>
                          <th className="px-2 py-2 text-right font-medium">TD</th>
                        </>
                      ) : historyIsK ? (
                        <>
                          <th className="px-2 py-2 text-right font-medium">FG</th>
                          <th className="px-2 py-2 text-right font-medium">FGA</th>
                          <th className="px-2 py-2 text-right font-medium">50+</th>
                          <th className="px-2 py-2 text-right font-medium">XP</th>
                        </>
                      ) : (
                        <>
                          <th className="px-2 py-2 text-right font-medium">Tgt</th>
                          <th className="px-2 py-2 text-right font-medium">Rec</th>
                          <th className="px-2 py-2 text-right font-medium">Rec Yds</th>
                          <th className="px-2 py-2 text-right font-medium">TD</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {stats.season_history.map((row) => (
                      <tr
                        key={row.season}
                        className="border-b last:border-0"
                        style={{
                          borderColor: snapshotTokens.divider,
                          background:
                            row.season === stats.season
                              ? snapshotTokens.blueLight
                              : "transparent",
                        }}
                      >
                        <td
                          className="py-2 pr-3 font-medium"
                          style={{ color: snapshotTokens.textPrimary }}
                        >
                          {row.season}
                        </td>
                        <td className="px-2 py-2 text-right tabular-nums">
                          {formatMetricValue(row.games, 0)}
                        </td>
                        <td className="px-2 py-2 text-right tabular-nums font-semibold">
                          {formatMetricValue(row.fantasy_points)}
                        </td>
                        <td className="px-2 py-2 text-right tabular-nums">
                          {formatMetricValue(row.fppg)}
                        </td>
                        {historyIsQb ? (
                          <>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.pass_yards, 0)}
                            </td>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.pass_tds, 0)}
                            </td>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.interceptions, 0)}
                            </td>
                          </>
                        ) : historyIsRb ? (
                          <>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.rush_yards, 0)}
                            </td>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.receptions, 0)}
                            </td>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.receiving_yards, 0)}
                            </td>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.touchdowns, 0)}
                            </td>
                          </>
                        ) : historyIsK ? (
                          <>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.fg_made, 0)}
                            </td>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.fg_att, 0)}
                            </td>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.fg_made_50_plus, 0)}
                            </td>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.pat_made, 0)}
                            </td>
                          </>
                        ) : (
                          <>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.targets, 0)}
                            </td>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.receptions, 0)}
                            </td>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.receiving_yards, 0)}
                            </td>
                            <td className="px-2 py-2 text-right tabular-nums">
                              {formatMetricValue(row.touchdowns, 0)}
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            {stats.volume.length > 0 && (
              <Section title="Volume & Opportunity">
                <dl className="space-y-1.5">
                  {stats.volume.map((metric) => (
                    <div
                      key={metric.key}
                      className="flex items-baseline justify-between gap-3 border-b pb-1.5 last:border-0"
                      style={{ borderColor: snapshotTokens.divider }}
                    >
                      <dt
                        className="text-sm"
                        style={{ color: snapshotTokens.textSecondary }}
                      >
                        {metric.label}
                      </dt>
                      <dd
                        className="text-sm font-semibold tabular-nums"
                        style={{ color: snapshotTokens.textPrimary }}
                      >
                        {formatStatValue(metric)}
                      </dd>
                    </div>
                  ))}
                </dl>
              </Section>
            )}

            {stats.efficiency.length > 0 && (
              <Section title="Efficiency">
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
                          Value
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.efficiency.map((metric) => (
                        <tr
                          key={metric.key}
                          className="border-b last:border-0"
                          style={{ borderColor: snapshotTokens.divider }}
                        >
                          <td
                            className="py-2 pr-3"
                            style={{
                              color: snapshotTokens.textSecondary,
                            }}
                          >
                            {metric.label}
                          </td>
                          <td
                            className="px-2 py-2 text-right tabular-nums font-semibold"
                            style={{
                              color: snapshotTokens.textPrimary,
                            }}
                          >
                            {formatStatValue(metric)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Section>
            )}
          </div>

          {consistency && (
            <Section title="Consistency">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <MetricCard
                  label="Ceiling"
                  value={formatMetricValue(consistency.ceiling)}
                />
                <MetricCard
                  label="Median"
                  value={formatMetricValue(consistency.median)}
                />
                <MetricCard
                  label="Floor"
                  value={formatMetricValue(consistency.floor)}
                />
                <MetricCard
                  label="Std Dev"
                  value={formatMetricValue(consistency.stdev)}
                />
              </div>
              <div
                className="mt-4 grid grid-cols-3 gap-3 rounded-lg border px-3 py-3 text-sm"
                style={{
                  borderColor: snapshotTokens.divider,
                  background: snapshotTokens.background,
                }}
              >
                <div>
                  <p
                    className="text-[11px] uppercase tracking-wide"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    15+ pts
                  </p>
                  <p
                    className="mt-1 font-semibold tabular-nums"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {consistency.top_12_finishes} / {consistency.games}
                  </p>
                </div>
                <div>
                  <p
                    className="text-[11px] uppercase tracking-wide"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    10+ pts
                  </p>
                  <p
                    className="mt-1 font-semibold tabular-nums"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {consistency.top_24_finishes} / {consistency.games}
                  </p>
                </div>
                <div>
                  <p
                    className="text-[11px] uppercase tracking-wide"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    FPPG
                  </p>
                  <p
                    className="mt-1 font-semibold tabular-nums"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {formatMetricValue(consistency.fppg)}
                  </p>
                </div>
              </div>
              {consistency.weekly_points
                && consistency.weekly_points.length > 0 && (
                <div className="mt-4">
                  <p
                    className="mb-2 text-[11px] font-semibold uppercase tracking-wide"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    Weekly fantasy points
                  </p>
                  <div className="flex h-16 items-end gap-1">
                    {consistency.weekly_points.map((points, index) => {
                      const max = Math.max(
                        ...consistency.weekly_points!,
                        1
                      );
                      const height = Math.max(
                        8,
                        Math.round((points / max) * 100)
                      );
                      return (
                        <div
                          key={`${index}-${points}`}
                          className="flex-1 rounded-t"
                          title={`W${index + 1}: ${points}`}
                          style={{
                            height: `${height}%`,
                            background:
                              points >= 20
                                ? snapshotTokens.blue
                                : snapshotTokens.border,
                          }}
                        />
                      );
                    })}
                  </div>
                </div>
              )}
            </Section>
          )}

          {stats.game_log.length > 0 && (
            <Section title="Game Log">
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
                      <th className="sticky left-0 bg-white py-2 pr-3 font-medium">
                        Week
                      </th>
                      <th className="sticky left-12 bg-white px-2 py-2 font-medium">
                        Opp
                      </th>
                      {columns.map((column) => (
                        <th
                          key={column.key}
                          className="px-2 py-2 text-right font-medium"
                        >
                          {column.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {stats.game_log.map((game) => (
                      <tr
                        key={`${game.season}-${game.week}`}
                        className="border-b last:border-0"
                        style={{
                          borderColor: snapshotTokens.divider,
                          background: fptsTone(game.fantasy_points),
                        }}
                      >
                        <td
                          className="sticky left-0 py-2 pr-3 font-medium"
                          style={{
                            color: snapshotTokens.textPrimary,
                            background: fptsTone(game.fantasy_points),
                          }}
                        >
                          {game.week ?? "—"}
                        </td>
                        <td
                          className="sticky left-12 px-2 py-2"
                          style={{
                            color: snapshotTokens.textSecondary,
                            background: fptsTone(game.fantasy_points),
                          }}
                        >
                          {game.opponent_label || game.opponent || "—"}
                        </td>
                        {columns.map((column) => (
                          <td
                            key={column.key}
                            className="px-2 py-2 text-right tabular-nums"
                            style={{
                              color: snapshotTokens.textPrimary,
                              fontWeight:
                                column.key === "fantasy_points"
                                  ? 600
                                  : 400,
                            }}
                          >
                            {gameCell(game, column.key)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Section>
          )}
        </>
      )}
    </div>
  );
}
