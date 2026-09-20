"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  FantasyMatchupDifficulty,
  FantasyMatchupGame,
  FantasyMatchupView,
  FantasyPlayerMatchups,
  FantasyScoringFormat,
  getFantasyPlayerMatchups,
} from "@/services/api";

import {
  formatMetricValue,
  snapshotTokens,
} from "./tokens";

interface Props {
  playerId: string;
  defaultSeason?: number | null;
}

const VIEW_OPTIONS: Array<{
  value: FantasyMatchupView;
  label: string;
}> = [
  { value: "next_4", label: "Next 4 Games" },
  { value: "next_6", label: "Next 6 Games" },
  { value: "next_8", label: "Next 8 Games" },
  { value: "rest_of_season", label: "Rest of Season" },
  { value: "full_season", label: "Full Season" },
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

function difficultyStyles(
  difficulty: FantasyMatchupDifficulty | string | null | undefined
): { bg: string; text: string; border: string } {
  switch (difficulty) {
    case "very_favorable":
      return {
        bg: snapshotTokens.successLight,
        text: snapshotTokens.success,
        border: "#BBF7D0",
      };
    case "favorable":
      return {
        bg: "#F0FDF4",
        text: "#15803D",
        border: "#BBF7D0",
      };
    case "difficult":
      return {
        bg: snapshotTokens.warningLight,
        text: "#B45309",
        border: "#FDE68A",
      };
    case "very_difficult":
      return {
        bg: snapshotTokens.negativeLight,
        text: snapshotTokens.negative,
        border: "#FECACA",
      };
    default:
      return {
        bg: snapshotTokens.blueLight,
        text: snapshotTokens.blue,
        border: "#BFDBFE",
      };
  }
}

function opponentLabel(game: FantasyMatchupGame): string {
  if (game.is_bye) {
    return "BYE";
  }
  const opp = game.opponent || "TBD";
  if (game.home_away === "@") {
    return `@ ${opp}`;
  }
  if (game.home_away === "vs") {
    return `vs ${opp}`;
  }
  return opp;
}

function DifficultyBadge({
  difficulty,
  label,
}: {
  difficulty?: FantasyMatchupDifficulty | string | null;
  label?: string | null;
}) {
  const styles = difficultyStyles(difficulty);
  return (
    <span
      className="inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold"
      style={{
        background: styles.bg,
        color: styles.text,
        borderColor: styles.border,
      }}
    >
      {label || "Neutral"}
    </span>
  );
}

function OutlookCard({
  eyebrow,
  title,
  subtitle,
  children,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      className="rounded-[10px] border p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <p
        className="text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {eyebrow}
      </p>
      <p
        className="mt-2 text-[22px] font-bold leading-none"
        style={{ color: snapshotTokens.textPrimary }}
      >
        {title}
      </p>
      {subtitle && (
        <p
          className="mt-2 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {subtitle}
        </p>
      )}
      {children}
    </div>
  );
}

export default function PlayerMatchupsTab({
  playerId,
  defaultSeason,
}: Props) {
  const [season, setSeason] = useState<number | null>(
    defaultSeason ?? null
  );
  const [view, setView] =
    useState<FantasyMatchupView>("next_8");
  const [scoring, setScoring] =
    useState<FantasyScoringFormat>("ppr");
  const [matchups, setMatchups] =
    useState<FantasyPlayerMatchups | null>(null);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(
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
        const result = await getFantasyPlayerMatchups(playerId, {
          season,
          view,
          scoring,
        });
        if (cancelled) {
          return;
        }
        setMatchups(result.matchups);
        if (season == null && result.matchups.season != null) {
          setSeason(result.matchups.season);
        }
        const nextWeek =
          result.matchups.next_matchup?.week
          ?? result.matchups.upcoming_matchups.find(
            (game) => !game.is_bye
          )?.week
          ?? null;
        setSelectedWeek(nextWeek);
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        setMatchups(null);
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load matchups."
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
  }, [playerId, season, view, scoring]);

  const selectedGame = useMemo(() => {
    if (!matchups) {
      return null;
    }
    const fromUpcoming = matchups.upcoming_matchups.find(
      (game) => game.week === selectedWeek
    );
    if (fromUpcoming) {
      return fromUpcoming;
    }
    return (
      matchups.timeline.find((game) => game.week === selectedWeek)
      || matchups.next_matchup
      || null
    );
  }, [matchups, selectedWeek]);

  const chartData = useMemo(() => {
    if (!matchups) {
      return [];
    }
    return matchups.upcoming_matchups
      .filter((game) => !game.is_bye)
      .map((game) => ({
        label: `W${game.week}`,
        week: game.week,
        difficulty_10: game.difficulty_10,
        score: game.position_matchup_score,
        opponent: opponentLabel(game),
        difficulty_label: game.difficulty_label,
      }));
  }, [matchups]);

  if (loading && !matchups) {
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
        <div className="grid gap-3 sm:grid-cols-3">
          {[1, 2, 3].map((item) => (
            <div
              key={item}
              className="h-28 animate-pulse rounded-[10px]"
              style={{ background: snapshotTokens.divider }}
            />
          ))}
        </div>
        <div
          className="h-48 animate-pulse rounded-[10px]"
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

  if (!matchups) {
    return null;
  }

  const seasons = (
    matchups.available_seasons.length > 0
      ? matchups.available_seasons
      : [matchups.season]
  ).map((value) => ({
    value: String(value),
    label: String(value),
  }));

  if (matchups.empty_message) {
    return (
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <CompactSelect
            label="Season"
            value={String(season ?? matchups.season)}
            options={seasons}
            onChange={(value) => setSeason(Number(value))}
          />
        </div>
        <p
          className="rounded-[10px] border px-4 py-8 text-center text-sm"
          style={{
            borderColor: snapshotTokens.border,
            color: snapshotTokens.textSecondary,
          }}
        >
          {matchups.empty_message}
        </p>
      </div>
    );
  }

  const summary = matchups.outlook_summary;
  const next = matchups.next_matchup;
  const insight = matchups.insight_outlook;
  const profile = selectedGame?.opponent_profile;
  const positionGroup = matchups.position_group || "WR";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <CompactSelect
          label="Season"
          value={String(season ?? matchups.season)}
          options={seasons}
          onChange={(value) => setSeason(Number(value))}
        />
        <CompactSelect
          label="View"
          value={view}
          options={VIEW_OPTIONS}
          onChange={(value) =>
            setView(value as FantasyMatchupView)
          }
        />
        <CompactSelect
          label="Scoring"
          value={scoring}
          options={SCORING_OPTIONS}
          onChange={(value) =>
            setScoring(value as FantasyScoringFormat)
          }
        />
      </div>

      <Section title="Matchup Outlook">
        <div className="grid gap-3 sm:grid-cols-3">
          <OutlookCard
            eyebrow="Next Game"
            title={
              next
                ? `Week ${next.week}`
                : "—"
            }
            subtitle={next ? opponentLabel(next) : "No upcoming game"}
          >
            {next && !next.is_bye && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span
                  className="text-xs font-semibold"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  {positionGroup} Matchup
                </span>
                <DifficultyBadge
                  difficulty={next.difficulty}
                  label={next.difficulty_label}
                />
              </div>
            )}
          </OutlookCard>

          <OutlookCard
            eyebrow="Schedule Difficulty"
            title={
              summary?.schedule_difficulty_10 != null
                ? `${formatMetricValue(summary.schedule_difficulty_10, 1)} / 10`
                : "—"
            }
            subtitle={summary?.schedule_difficulty_label || "Neutral"}
          />

          <OutlookCard
            eyebrow="InsightPilot Outlook"
            title={summary?.overall_label || "Neutral"}
            subtitle={
              summary
                ? `${summary.favorable_count ?? 0} favorable · ${summary.neutral_count ?? 0} neutral · ${summary.difficult_count ?? 0} difficult`
                : undefined
            }
          />
        </div>
      </Section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(280px,0.9fr)]">
        <Section
          title="Upcoming Matchups"
          subtitle="Select a week for matchup detail"
        >
          <div className="flex gap-2 overflow-x-auto pb-1">
            {matchups.upcoming_matchups.map((game) => {
              const selected = game.week === selectedWeek;
              const styles = difficultyStyles(
                game.is_bye ? "neutral" : game.difficulty
              );
              return (
                <button
                  key={game.week}
                  type="button"
                  onClick={() => setSelectedWeek(game.week)}
                  className="min-w-[7.5rem] shrink-0 rounded-[10px] border px-3 py-3 text-left transition"
                  style={{
                    borderColor: selected
                      ? snapshotTokens.blue
                      : snapshotTokens.border,
                    background: selected
                      ? snapshotTokens.blueLight
                      : snapshotTokens.white,
                  }}
                >
                  <p
                    className="text-[11px] font-semibold uppercase tracking-wide"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    W{game.week}
                  </p>
                  <p
                    className="mt-1 text-sm font-semibold"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {opponentLabel(game)}
                  </p>
                  <p
                    className="mt-2 text-xs font-semibold"
                    style={{
                      color: game.is_bye
                        ? snapshotTokens.textMuted
                        : styles.text,
                    }}
                  >
                    {game.is_bye
                      ? "No game"
                      : game.difficulty_label || "Neutral"}
                  </p>
                </button>
              );
            })}
          </div>

          <div className="mt-4 space-y-2">
            {matchups.upcoming_matchups
              .filter((game) => !game.is_bye)
              .map((game) => {
                const width = Math.max(
                  12,
                  Math.min(
                    100,
                    ((game.difficulty_10 ?? 5) / 10) * 100
                  )
                );
                const styles = difficultyStyles(game.difficulty);
                return (
                  <button
                    key={`bar-${game.week}`}
                    type="button"
                    onClick={() => setSelectedWeek(game.week)}
                    className="flex w-full items-center gap-3 text-left"
                  >
                    <span
                      className="w-10 shrink-0 text-xs font-semibold"
                      style={{ color: snapshotTokens.textMuted }}
                    >
                      W{game.week}
                    </span>
                    <div
                      className="h-2.5 flex-1 overflow-hidden rounded-full"
                      style={{ background: snapshotTokens.divider }}
                    >
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${width}%`,
                          background: styles.text,
                        }}
                      />
                    </div>
                    <span
                      className="w-28 shrink-0 text-right text-xs font-semibold"
                      style={{ color: styles.text }}
                    >
                      {game.difficulty_label}
                    </span>
                  </button>
                );
              })}
          </div>
        </Section>

        <Section
          title="InsightPilot Outlook"
          subtitle="Structured schedule signals"
        >
          {insight && (
            <div
              className="mb-3 rounded-[10px] border p-3"
              style={{
                borderColor: snapshotTokens.border,
                background: snapshotTokens.purpleLight,
              }}
            >
              <p
                className="text-sm font-semibold"
                style={{ color: snapshotTokens.purple }}
              >
                ✦ {insight.headline}
              </p>
              {insight.body && (
                <p
                  className="mt-1.5 text-xs leading-5"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {insight.body}
                </p>
              )}
            </div>
          )}
          <div className="space-y-3">
            {matchups.signals.map((signal) => (
              <div
                key={signal.signal_type}
                className="rounded-[10px] border p-3"
                style={{ borderColor: snapshotTokens.border }}
              >
                <div className="flex items-start justify-between gap-2">
                  <p
                    className="text-sm font-semibold"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {signal.headline}
                  </p>
                  {signal.confidence && (
                    <span
                      className="text-[10px] font-semibold uppercase tracking-wide"
                      style={{ color: snapshotTokens.textMuted }}
                    >
                      {signal.confidence}
                    </span>
                  )}
                </div>
                {signal.body && (
                  <p
                    className="mt-1 text-xs leading-5"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    {signal.body}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Section>
      </div>

      {selectedGame && (
        <Section
          title="Matchup Detail"
          subtitle={
            selectedGame.is_bye
              ? `Week ${selectedGame.week} · Bye`
              : `Week ${selectedGame.week} · ${opponentLabel(selectedGame)}`
          }
        >
          {selectedGame.is_bye ? (
            <p
              className="text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              No game this week.
            </p>
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <DifficultyBadge
                    difficulty={selectedGame.difficulty}
                    label={selectedGame.difficulty_label}
                  />
                  <span
                    className="text-xs font-semibold"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    {positionGroup} Matchup
                  </span>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt
                      style={{ color: snapshotTokens.textMuted }}
                      className="text-[11px] font-semibold uppercase tracking-wide"
                    >
                      Opponent Rank
                    </dt>
                    <dd
                      className="mt-1 font-semibold tabular-nums"
                      style={{ color: snapshotTokens.textPrimary }}
                    >
                      {selectedGame.opponent_rank != null
                        ? `${selectedGame.opponent_rank}${ordinal(selectedGame.opponent_rank)}`
                          + (
                            selectedGame.opponent_rank_of
                              ? ` / ${selectedGame.opponent_rank_of}`
                              : ""
                          )
                        : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt
                      style={{ color: snapshotTokens.textMuted }}
                      className="text-[11px] font-semibold uppercase tracking-wide"
                    >
                      {positionGroup} FPTS Allowed
                    </dt>
                    <dd
                      className="mt-1 font-semibold tabular-nums"
                      style={{ color: snapshotTokens.textPrimary }}
                    >
                      {selectedGame.fpts_pct_vs_avg != null
                        ? `${selectedGame.fpts_pct_vs_avg > 0 ? "+" : ""}${formatMetricValue(selectedGame.fpts_pct_vs_avg, 1)}%`
                        : "—"}
                    </dd>
                  </div>
                </dl>
                {selectedGame.interpretation && (
                  <p
                    className="mt-4 rounded-[10px] border px-3 py-2.5 text-xs leading-5"
                    style={{
                      borderColor: snapshotTokens.border,
                      background: snapshotTokens.background,
                      color: snapshotTokens.textSecondary,
                    }}
                  >
                    <span
                      className="font-semibold"
                      style={{ color: snapshotTokens.purple }}
                    >
                      ✦{" "}
                    </span>
                    {selectedGame.interpretation}
                  </p>
                )}
              </div>

              <div>
                <p
                  className="text-[11px] font-semibold uppercase tracking-wide"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  Matchup Factors
                </p>
                <div className="mt-3 space-y-2">
                  {(selectedGame.factors || []).map((factor) => {
                    const styles = difficultyStyles(
                      factor.difficulty
                    );
                    return (
                      <div
                        key={factor.key}
                        className="flex items-center justify-between gap-3 text-sm"
                      >
                        <span
                          style={{
                            color: snapshotTokens.textSecondary,
                          }}
                        >
                          {factor.label}
                        </span>
                        <span
                          className="font-semibold"
                          style={{ color: styles.text }}
                        >
                          {factor.difficulty_label}
                        </span>
                      </div>
                    );
                  })}
                  {(selectedGame.factors || []).length === 0 && (
                    <p
                      className="text-sm"
                      style={{
                        color: snapshotTokens.textSecondary,
                      }}
                    >
                      Limited matchup factors available for this
                      opponent yet.
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </Section>
      )}

      {selectedGame && !selectedGame.is_bye && profile && (
        <Section
          title="Opponent Profile"
          subtitle={
            (profile.team_name || profile.team || "Opponent")
            + ` vs ${positionGroup}`
          }
        >
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {opponentMetrics(profile, positionGroup).map(
              (metric) => (
                <div
                  key={metric.label}
                  className="rounded-[10px] border p-3"
                  style={{ borderColor: snapshotTokens.border }}
                >
                  <p
                    className="text-[11px] font-semibold uppercase tracking-wide"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    {metric.label}
                  </p>
                  <p
                    className="mt-2 text-lg font-bold tabular-nums"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {metric.value}
                  </p>
                </div>
              )
            )}
          </div>
        </Section>
      )}

      <div className="grid gap-4 xl:grid-cols-2">
        <Section
          title="Matchup Trend"
          subtitle="Difficulty across the selected window"
        >
          {chartData.length === 0 ? (
            <p
              className="text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              No upcoming matchups to chart.
            </p>
          ) : (
            <div className="h-56 w-full">
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
                    domain={[1, 10]}
                    reversed
                    tick={{
                      fill: snapshotTokens.textMuted,
                      fontSize: 11,
                    }}
                    axisLine={false}
                    tickLine={false}
                    width={28}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: 8,
                      borderColor: snapshotTokens.border,
                    }}
                    formatter={(value: number) => [
                      formatMetricValue(value, 1),
                      "Difficulty / 10",
                    ]}
                    labelFormatter={(_, payload) => {
                      const point = payload?.[0]?.payload as
                        | {
                            opponent?: string;
                            difficulty_label?: string;
                          }
                        | undefined;
                      if (!point) {
                        return "";
                      }
                      return `${point.opponent || ""} · ${point.difficulty_label || ""}`;
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="difficulty_10"
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

        {matchups.recent_vs_upcoming && (
          <Section
            title="Recent vs. Upcoming"
            subtitle="Schedule difficulty comparison"
          >
            <div className="grid grid-cols-2 gap-3">
              <div
                className="rounded-[10px] border p-3"
                style={{ borderColor: snapshotTokens.border }}
              >
                <p
                  className="text-[11px] font-semibold uppercase tracking-wide"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  {matchups.recent_vs_upcoming.recent_label}
                </p>
                <p
                  className="mt-2 text-2xl font-bold tabular-nums"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {matchups.recent_vs_upcoming.recent_difficulty_10
                    != null
                    ? `${formatMetricValue(matchups.recent_vs_upcoming.recent_difficulty_10, 1)} / 10`
                    : "—"}
                </p>
              </div>
              <div
                className="rounded-[10px] border p-3"
                style={{ borderColor: snapshotTokens.border }}
              >
                <p
                  className="text-[11px] font-semibold uppercase tracking-wide"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  {matchups.recent_vs_upcoming.upcoming_label}
                </p>
                <p
                  className="mt-2 text-2xl font-bold tabular-nums"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {matchups.recent_vs_upcoming.upcoming_difficulty_10
                    != null
                    ? `${formatMetricValue(matchups.recent_vs_upcoming.upcoming_difficulty_10, 1)} / 10`
                    : "—"}
                </p>
              </div>
            </div>
            {matchups.recent_vs_upcoming.interpretation && (
              <p
                className="mt-4 text-xs leading-5"
                style={{ color: snapshotTokens.textSecondary }}
              >
                <span
                  className="font-semibold"
                  style={{ color: snapshotTokens.purple }}
                >
                  ✦ Why it matters
                </span>
                <span className="mt-1 block">
                  {matchups.recent_vs_upcoming.interpretation}
                </span>
              </p>
            )}
          </Section>
        )}
      </div>

      {matchups.playoff_outlook
        && matchups.playoff_outlook.weeks.length > 0 && (
        <Section
          title="Fantasy Playoff Outlook"
          subtitle="Weeks 15–17"
        >
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <DifficultyBadge
              difficulty={matchups.playoff_outlook.difficulty}
              label={matchups.playoff_outlook.difficulty_label}
            />
            <span
              className="text-xs"
              style={{ color: snapshotTokens.textSecondary }}
            >
              {matchups.playoff_outlook.favorable_count ?? 0} favorable
              · {matchups.playoff_outlook.neutral_count ?? 0} neutral
              · {matchups.playoff_outlook.difficult_count ?? 0}{" "}
              difficult
            </span>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {matchups.playoff_outlook.weeks.map((game) => (
              <div
                key={`playoff-${game.week}`}
                className="rounded-[10px] border p-3"
                style={{ borderColor: snapshotTokens.border }}
              >
                <p
                  className="text-[11px] font-semibold uppercase tracking-wide"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  W{game.week}
                </p>
                <p
                  className="mt-1 text-sm font-semibold"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {opponentLabel(game)}
                </p>
                <div className="mt-2">
                  <DifficultyBadge
                    difficulty={
                      game.is_bye ? "neutral" : game.difficulty
                    }
                    label={
                      game.is_bye
                        ? "Bye"
                        : game.difficulty_label
                    }
                  />
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="Full Schedule" subtitle={`Season ${matchups.season}`}>
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
                <th className="px-2 py-2 font-medium">Status</th>
                <th className="px-2 py-2 font-medium">Matchup</th>
                <th className="px-2 py-2 text-right font-medium">
                  FPTS Allowed
                </th>
              </tr>
            </thead>
            <tbody>
              {matchups.timeline.map((game) => (
                <tr
                  key={`full-${game.week}`}
                  className="border-b last:border-0"
                  style={{ borderColor: snapshotTokens.divider }}
                >
                  <td
                    className="py-2.5 pr-3 font-medium"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {game.week}
                  </td>
                  <td
                    className="px-2 py-2.5"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    {opponentLabel(game)}
                  </td>
                  <td
                    className="px-2 py-2.5 capitalize"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    {game.is_bye ? "Bye" : game.status}
                  </td>
                  <td className="px-2 py-2.5">
                    {game.is_bye ? (
                      <span
                        style={{ color: snapshotTokens.textMuted }}
                      >
                        —
                      </span>
                    ) : (
                      <DifficultyBadge
                        difficulty={game.difficulty}
                        label={game.difficulty_label}
                      />
                    )}
                  </td>
                  <td
                    className="px-2 py-2.5 text-right tabular-nums"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {game.is_bye || game.fpts_pct_vs_avg == null
                      ? "—"
                      : `${game.fpts_pct_vs_avg > 0 ? "+" : ""}${formatMetricValue(game.fpts_pct_vs_avg, 1)}%`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {matchups.data_note && (
        <p
          className="text-[11px] leading-4"
          style={{ color: snapshotTokens.textMuted }}
        >
          {matchups.data_note}
        </p>
      )}
    </div>
  );
}

function ordinal(value: number): string {
  const mod = value % 100;
  if (mod >= 10 && mod <= 20) {
    return "th";
  }
  switch (value % 10) {
    case 1:
      return "st";
    case 2:
      return "nd";
    case 3:
      return "rd";
    default:
      return "th";
  }
}

function opponentMetrics(
  profile: NonNullable<FantasyMatchupGame["opponent_profile"]>,
  positionGroup: string
): Array<{ label: string; value: string }> {
  const fpts =
    profile.fpts_allowed_avg != null
      ? formatMetricValue(profile.fpts_allowed_avg, 1)
      : "—";
  const pct =
    profile.pct_vs_avg != null
      ? `${profile.pct_vs_avg > 0 ? "+" : ""}${formatMetricValue(profile.pct_vs_avg, 1)}%`
      : "—";

  if (positionGroup === "QB") {
    return [
      { label: "Fantasy Points Allowed", value: fpts },
      { label: "Vs League Avg", value: pct },
      {
        label: "Pass Yards Allowed",
        value: formatMetricValue(profile.pass_yards_avg, 1),
      },
      {
        label: "Pass TDs Allowed",
        value: formatMetricValue(profile.pass_tds_avg, 1),
      },
    ];
  }
  if (positionGroup === "RB") {
    return [
      { label: "Fantasy Points Allowed", value: fpts },
      { label: "Vs League Avg", value: pct },
      {
        label: "Yards / Carry Allowed",
        value: formatMetricValue(profile.yards_per_carry, 2),
      },
      {
        label: "RB Targets Allowed",
        value: formatMetricValue(profile.targets_avg, 1),
      },
    ];
  }
  return [
    { label: "Fantasy Points Allowed", value: fpts },
    { label: "Vs League Avg", value: pct },
    {
      label: "Targets Allowed",
      value: formatMetricValue(profile.targets_avg, 1),
    },
    {
      label: "Receiving Yards Allowed",
      value: formatMetricValue(profile.receiving_yards_avg, 1),
    },
  ];
}
