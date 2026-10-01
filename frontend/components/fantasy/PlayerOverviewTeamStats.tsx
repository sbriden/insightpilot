"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { ChevronDown } from "lucide-react";

import {
  FantasyTeamDefense,
  FantasyTeamEfficiency,
  FantasyTeamOffense,
  FantasyTeamPlayerStats,
  FantasyTeamRecord,
  FantasyTeamStats,
  FantasyTeamSummary,
  FantasyTeamTotals,
  getFantasyTeamStats,
  listFantasyTeams,
} from "@/services/api";

import {
  formatMetricValue,
  snapshotTokens,
} from "@/components/fantasy/snapshot/tokens";

interface Props {
  onSelectPlayer: (playerId: string) => void;
}

function formatCount(
  value: number | null | undefined
): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  return Math.round(value).toLocaleString();
}

function formatDecimal(
  value: number | null | undefined,
  digits = 1
): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatSigned(
  value: number | null | undefined,
  digits = 2
): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  const body = formatDecimal(Math.abs(value), digits);
  if (value > 0) {
    return `+${body}`;
  }
  if (value < 0) {
    return `-${body}`;
  }
  return body;
}

function formatPercent(
  value: number | null | undefined
): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function recordLabel(record: FantasyTeamRecord): string {
  const base = `${record.wins}–${record.losses}`;
  if (record.ties > 0) {
    return `${base}–${record.ties}`;
  }
  return base;
}

function statTiles(
  pairs: Array<[string, string]>
): Array<{ label: string; value: string }> {
  return pairs
    .filter(([, value]) => value !== "—")
    .map(([label, value]) => ({ label, value }));
}

function TeamLogo({
  abbreviation,
  logoUrl,
  size = 36,
}: {
  abbreviation: string;
  logoUrl?: string | null;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  if (!logoUrl || failed) {
    return (
      <span
        className="inline-flex shrink-0 items-center justify-center rounded-full text-[10px] font-semibold"
        style={{
          width: size,
          height: size,
          background: snapshotTokens.blueLight,
          color: snapshotTokens.blue,
        }}
      >
        {abbreviation.slice(0, 3)}
      </span>
    );
  }
  return (
    <img
      src={logoUrl}
      alt=""
      width={size}
      height={size}
      className="shrink-0 object-contain"
      style={{ width: size, height: size }}
      onError={() => setFailed(true)}
    />
  );
}

function StatGroup({
  title,
  tiles,
}: {
  title: string;
  tiles: Array<{ label: string; value: string }>;
}) {
  if (tiles.length === 0) {
    return null;
  }
  return (
    <div>
      <h5
        className="text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {title}
      </h5>
      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {tiles.map((tile) => (
          <div
            key={tile.label}
            className="rounded-lg border px-3 py-2"
            style={{
              borderColor: snapshotTokens.divider,
              background: snapshotTokens.background,
            }}
          >
            <p
              className="text-[10px] font-semibold uppercase tracking-wide"
              style={{ color: snapshotTokens.textMuted }}
            >
              {tile.label}
            </p>
            <p
              className="mt-1 text-base font-semibold tabular-nums"
              style={{ color: snapshotTokens.navy }}
            >
              {tile.value}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function offenseTiles(offense: FantasyTeamOffense | null | undefined) {
  if (!offense) {
    return [];
  }
  return statTiles([
    ["Points", formatCount(offense.points)],
    ["PPG", formatDecimal(offense.points_per_game, 1)],
    ["Yards", formatCount(offense.yards)],
    ["Yds/G", formatDecimal(offense.yards_per_game, 1)],
    ["Yds/play", formatDecimal(offense.yards_per_play, 2)],
    ["EPA/play", formatSigned(offense.epa_per_play, 3)],
    [
      "Pass EPA/att",
      formatSigned(offense.pass_epa_per_attempt, 3),
    ],
    [
      "Rush EPA/att",
      formatSigned(offense.rush_epa_per_attempt, 3),
    ],
    ["Pass rate", formatPercent(offense.pass_rate)],
    ["RZ TD%", formatPercent(offense.red_zone_td_rate)],
    ["TO/G", formatDecimal(offense.turnovers_per_game, 2)],
  ]);
}

function defenseTiles(defense: FantasyTeamDefense | null | undefined) {
  if (!defense) {
    return [];
  }
  return statTiles([
    ["PA", formatCount(defense.points_allowed)],
    ["PA/G", formatDecimal(defense.points_allowed_per_game, 1)],
    ["Yds allowed", formatCount(defense.yards_allowed)],
    [
      "Yds allowed/G",
      formatDecimal(defense.yards_allowed_per_game, 1),
    ],
    [
      "Pass yds/G",
      formatDecimal(defense.pass_yards_allowed_per_game, 1),
    ],
    [
      "Rush yds/G",
      formatDecimal(defense.rush_yards_allowed_per_game, 1),
    ],
    [
      "Pass EPA/G",
      formatSigned(defense.pass_epa_allowed_per_game, 2),
    ],
    [
      "Rush EPA/G",
      formatSigned(defense.rush_epa_allowed_per_game, 2),
    ],
    ["Sack%", formatPercent(defense.sack_rate)],
    ["Pressure%", formatPercent(defense.pressure_rate)],
  ]);
}

function efficiencyTiles(
  efficiency: FantasyTeamEfficiency | null | undefined
) {
  if (!efficiency) {
    return [];
  }
  return statTiles([
    ["Cmp%", formatPercent(efficiency.completion_pct)],
    ["Y/A", formatDecimal(efficiency.yards_per_attempt, 2)],
    ["Y/C", formatDecimal(efficiency.yards_per_carry, 2)],
    ["Catch%", formatPercent(efficiency.catch_rate)],
    ["Y/Tgt", formatDecimal(efficiency.yards_per_target, 2)],
    ["Y/Rec", formatDecimal(efficiency.yards_per_reception, 2)],
  ]);
}

function TeamTotalsPanel({
  totals,
}: {
  totals: FantasyTeamTotals;
}) {
  const offense = offenseTiles(totals.offense);
  const defense = defenseTiles(totals.defense);
  const efficiency = efficiencyTiles(totals.efficiency);
  if (
    !totals.record
    && offense.length === 0
    && defense.length === 0
    && efficiency.length === 0
  ) {
    return null;
  }

  const differential = totals.record?.point_differential;

  return (
    <section
      className="rounded-[10px] border bg-white p-4 sm:p-5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4
          className="text-[15px] font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          Team totals
        </h4>
        <p
          className="text-xs"
          style={{ color: snapshotTokens.textMuted }}
        >
          {totals.games != null
            ? `${totals.games} regular-season game${totals.games === 1 ? "" : "s"}`
            : "Season aggregates"}
        </p>
      </div>
      {totals.record && (
        <p
          className="mt-3 text-sm font-semibold tabular-nums"
          style={{ color: snapshotTokens.textPrimary }}
        >
          {recordLabel(totals.record)}
          {differential != null && (
            <span
              className="ml-2 font-medium"
              style={{
                color:
                  differential > 0
                    ? snapshotTokens.success
                    : differential < 0
                      ? snapshotTokens.negative
                      : snapshotTokens.textSecondary,
              }}
            >
              · {formatSigned(differential, 0)} pts
            </span>
          )}
        </p>
      )}
      <div className="mt-4 space-y-4">
        <StatGroup title="Offense" tiles={offense} />
        <StatGroup title="Efficiency" tiles={efficiency} />
        <StatGroup title="Defense" tiles={defense} />
      </div>
    </section>
  );
}

function metric(
  player: FantasyTeamPlayerStats,
  key: keyof FantasyTeamPlayerStats
): string {
  const value = player[key];
  if (typeof value === "number") {
    return formatMetricValue(value, Number.isInteger(value) ? 0 : 1);
  }
  return "—";
}

function LeaderTable({
  title,
  players,
  columns,
  onSelectPlayer,
}: {
  title: string;
  players: FantasyTeamPlayerStats[];
  columns: Array<{
    key: keyof FantasyTeamPlayerStats;
    label: string;
  }>;
  onSelectPlayer: (playerId: string) => void;
}) {
  return (
    <section
      className="rounded-[10px] border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h4
        className="text-[13px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {title}
      </h4>
      {players.length === 0 ? (
        <p
          className="mt-3 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          No leaders yet for this season.
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr
                className="border-b text-[11px] uppercase tracking-wide"
                style={{
                  borderColor: snapshotTokens.divider,
                  color: snapshotTokens.textMuted,
                }}
              >
                <th className="py-2 pr-3 font-medium">Player</th>
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
              {players.map((player) => (
                <tr
                  key={player.player_id}
                  className="cursor-pointer border-b last:border-0"
                  style={{ borderColor: snapshotTokens.divider }}
                  onClick={() =>
                    onSelectPlayer(player.player_id)
                  }
                >
                  <td
                    className="py-2 pr-3 font-medium"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {player.name || "—"}
                    {player.position && (
                      <span
                        className="ml-1.5 text-xs font-normal"
                        style={{
                          color: snapshotTokens.textMuted,
                        }}
                      >
                        {player.position}
                      </span>
                    )}
                  </td>
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className="px-2 py-2 text-right tabular-nums"
                      style={{
                        color: snapshotTokens.textPrimary,
                      }}
                    >
                      {metric(player, column.key)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default function PlayerOverviewTeamStats({
  onSelectPlayer,
}: Props) {
  const [teams, setTeams] = useState<FantasyTeamSummary[]>(
    []
  );
  const [teamAbbr, setTeamAbbr] = useState("");
  const [teamMenuOpen, setTeamMenuOpen] = useState(false);
  const teamMenuRef = useRef<HTMLDivElement | null>(null);
  const [stats, setStats] = useState<FantasyTeamStats | null>(
    null
  );
  const [loadingTeams, setLoadingTeams] = useState(true);
  const [loadingStats, setLoadingStats] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        setLoadingTeams(true);
        const result = await listFantasyTeams();
        if (cancelled) {
          return;
        }
        const next = result.teams ?? [];
        setTeams(next);
        if (!teamAbbr && next.length > 0) {
          setTeamAbbr(next[0].abbreviation);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load teams."
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingTeams(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // Only load teams once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!teamAbbr) {
      setStats(null);
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        setLoadingStats(true);
        setError(null);
        const result = await getFantasyTeamStats(teamAbbr);
        if (cancelled) {
          return;
        }
        setStats(result.stats);
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        setStats(null);
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load team stats."
        );
      } finally {
        if (!cancelled) {
          setLoadingStats(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [teamAbbr]);

  useEffect(() => {
    function onPointerDown(event: MouseEvent) {
      if (
        teamMenuRef.current
        && !teamMenuRef.current.contains(event.target as Node)
      ) {
        setTeamMenuOpen(false);
      }
    }
    window.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener(
        "mousedown",
        onPointerDown
      );
    };
  }, []);

  const roster = useMemo(() => {
    const players = stats?.players ?? [];
    return [...players].sort((left, right) => {
      const pos = (left.position || "").localeCompare(
        right.position || ""
      );
      if (pos !== 0) {
        return pos;
      }
      return (left.name || "").localeCompare(right.name || "");
    });
  }, [stats]);

  const selectedTeam = teams.find(
    (team) => team.abbreviation === teamAbbr
  );

  return (
    <div className="space-y-4">
      <section
        className="rounded-[10px] border bg-white p-4 sm:p-5"
        style={{ borderColor: snapshotTokens.border }}
      >
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            {selectedTeam && (
              <TeamLogo
                key={selectedTeam.logo_url || selectedTeam.abbreviation}
                abbreviation={selectedTeam.abbreviation}
                logoUrl={selectedTeam.logo_url}
                size={48}
              />
            )}
            <div className="min-w-0">
              <h3
                className="text-[15px] font-semibold"
                style={{ color: snapshotTokens.navy }}
              >
                Team Stats
              </h3>
              <p
                className="mt-1 text-xs"
                style={{ color: snapshotTokens.textSecondary }}
              >
                Season totals, efficiency, leaders, and the
                depth chart for one franchise.
              </p>
            </div>
          </div>
          <div ref={teamMenuRef} className="relative block text-sm">
            <span
              className="mb-1 block text-[11px] font-semibold uppercase tracking-wide"
              style={{ color: snapshotTokens.textMuted }}
            >
              Team
            </span>
            <button
              type="button"
              disabled={loadingTeams || teams.length === 0}
              onClick={() =>
                setTeamMenuOpen((open) => !open)
              }
              className="flex min-w-[14rem] items-center gap-2 rounded-lg border bg-white px-3 py-2 text-left disabled:opacity-60"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textPrimary,
              }}
              aria-haspopup="listbox"
              aria-expanded={teamMenuOpen}
            >
              {selectedTeam && (
                <TeamLogo
                  key={`menu-${selectedTeam.logo_url || selectedTeam.abbreviation}`}
                  abbreviation={selectedTeam.abbreviation}
                  logoUrl={selectedTeam.logo_url}
                  size={22}
                />
              )}
              <span className="min-w-0 flex-1 truncate">
                {selectedTeam
                  ? `${selectedTeam.abbreviation} — ${selectedTeam.name}`
                  : "Select a team"}
              </span>
              <ChevronDown className="h-4 w-4 shrink-0" />
            </button>
            {teamMenuOpen && (
              <ul
                className="absolute right-0 z-30 mt-1 max-h-72 w-72 overflow-auto rounded-lg border bg-white py-1 shadow-lg"
                style={{ borderColor: snapshotTokens.border }}
                role="listbox"
              >
                {teams.map((team) => {
                  const selected =
                    team.abbreviation === teamAbbr;
                  return (
                    <li key={team.team_id || team.abbreviation}>
                      <button
                        type="button"
                        role="option"
                        aria-selected={selected}
                        className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm"
                        style={{
                          background: selected
                            ? snapshotTokens.blueLight
                            : "transparent",
                          color: snapshotTokens.textPrimary,
                        }}
                        onClick={() => {
                          setTeamAbbr(team.abbreviation);
                          setTeamMenuOpen(false);
                        }}
                      >
                        <TeamLogo
                          abbreviation={team.abbreviation}
                          logoUrl={team.logo_url}
                          size={22}
                        />
                        <span className="truncate">
                          {team.abbreviation} — {team.name}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        {selectedTeam && (
          <p
            className="mt-3 text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            {[
              selectedTeam.name,
              selectedTeam.conference,
              selectedTeam.division,
              stats?.season != null
                ? `${stats.season} season`
                : null,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        )}
      </section>

      {error && (
        <p
          className="text-sm"
          style={{ color: snapshotTokens.negative }}
        >
          {error}
        </p>
      )}

      {loadingStats && (
        <div className="space-y-3 animate-pulse">
          <div
            className="h-40 rounded-[10px]"
            style={{ background: snapshotTokens.divider }}
          />
          <div
            className="h-56 rounded-[10px]"
            style={{ background: snapshotTokens.divider }}
          />
        </div>
      )}

      {!loadingStats && stats && (
        <>
          {stats.team_totals && (
            <TeamTotalsPanel totals={stats.team_totals} />
          )}
          <div className="grid gap-4 lg:grid-cols-3">
            <LeaderTable
              title="Passing leaders"
              players={stats.passing_leaders}
              onSelectPlayer={onSelectPlayer}
              columns={[
                { key: "pass_yards", label: "Yds" },
                { key: "pass_tds", label: "TD" },
                { key: "interceptions", label: "INT" },
                { key: "pass_completions", label: "Cmp" },
                { key: "pass_attempts", label: "Att" },
              ]}
            />
            <LeaderTable
              title="Rushing leaders"
              players={stats.rushing_leaders}
              onSelectPlayer={onSelectPlayer}
              columns={[
                { key: "rush_yards", label: "Yds" },
                { key: "rush_tds", label: "TD" },
                { key: "rush_attempts", label: "Att" },
              ]}
            />
            <LeaderTable
              title="Receiving leaders"
              players={stats.receiving_leaders}
              onSelectPlayer={onSelectPlayer}
              columns={[
                { key: "receiving_yards", label: "Yds" },
                { key: "receiving_tds", label: "TD" },
                { key: "receptions", label: "Rec" },
                { key: "targets", label: "Tgt" },
              ]}
            />
          </div>

          <section
            className="rounded-[10px] border bg-white p-4 sm:p-5"
            style={{ borderColor: snapshotTokens.border }}
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h4
                className="text-[15px] font-semibold"
                style={{ color: snapshotTokens.navy }}
              >
                Depth chart
              </h4>
              <p
                className="text-xs"
                style={{ color: snapshotTokens.textMuted }}
              >
                {stats.depth_season != null
                  ? `As of ${stats.depth_season}`
                    + (stats.depth_week != null
                      ? ` W${stats.depth_week}`
                      : "")
                    + (stats.depth_as_of
                      ? ` · ${stats.depth_as_of}`
                      : "")
                  : "No depth chart available"}
              </p>
            </div>
            {stats.depth_chart.length === 0 ? (
              <p
                className="mt-3 text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                Depth chart data is not available for this
                team yet.
              </p>
            ) : (
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {stats.depth_chart.map((group) => (
                  <div
                    key={group.position}
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
                      {group.position}
                    </p>
                    <ul className="mt-2 space-y-1.5">
                      {group.players.map((player) => (
                        <li key={player.player_id}>
                          <button
                            type="button"
                            onClick={() =>
                              onSelectPlayer(player.player_id)
                            }
                            className="flex w-full items-center justify-between gap-2 text-left text-sm"
                          >
                            <span
                              className="truncate font-medium"
                              style={{
                                color: snapshotTokens.textPrimary,
                              }}
                            >
                              {player.depth_order != null
                                && `${player.depth_order}. `}
                              {player.name || "—"}
                            </span>
                            {player.role && (
                              <span
                                className="shrink-0 text-[11px] capitalize"
                                style={{
                                  color: snapshotTokens.textMuted,
                                }}
                              >
                                {player.role}
                              </span>
                            )}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section
            className="rounded-[10px] border bg-white p-4 sm:p-5"
            style={{ borderColor: snapshotTokens.border }}
          >
            <h4
              className="text-[15px] font-semibold"
              style={{ color: snapshotTokens.navy }}
            >
              Season player stats
            </h4>
            <p
              className="mt-1 text-xs"
              style={{ color: snapshotTokens.textSecondary }}
            >
              Totals from games played for{" "}
              {stats.team.abbreviation}
              {stats.season != null
                ? ` in ${stats.season}`
                : ""}
              .
            </p>
            {roster.length === 0 ? (
              <p
                className="mt-4 text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                No player-game rows for this team yet.
              </p>
            ) : (
              <div className="mt-3 max-h-[28rem] overflow-auto">
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
                      {[
                        "Player",
                        "Pos",
                        "G",
                        "Pass Yds",
                        "Pass TD",
                        "Rush Yds",
                        "Rec",
                        "Rec Yds",
                        "Rec TD",
                      ].map((label) => (
                        <th
                          key={label}
                          className={`px-2 py-2 font-medium ${
                            label === "Player"
                              ? "text-left"
                              : "text-right"
                          }`}
                        >
                          {label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {roster.map((player) => (
                      <tr
                        key={player.player_id}
                        className="cursor-pointer border-b last:border-0"
                        style={{
                          borderColor: snapshotTokens.divider,
                        }}
                        onClick={() =>
                          onSelectPlayer(player.player_id)
                        }
                      >
                        <td
                          className="px-2 py-2 font-medium"
                          style={{
                            color: snapshotTokens.textPrimary,
                          }}
                        >
                          {player.name || "—"}
                        </td>
                        <td
                          className="px-2 py-2 text-right"
                          style={{
                            color: snapshotTokens.textSecondary,
                          }}
                        >
                          {player.position || "—"}
                        </td>
                        {(
                          [
                            "games",
                            "pass_yards",
                            "pass_tds",
                            "rush_yards",
                            "receptions",
                            "receiving_yards",
                            "receiving_tds",
                          ] as const
                        ).map((key) => (
                          <td
                            key={key}
                            className="px-2 py-2 text-right tabular-nums"
                            style={{
                              color: snapshotTokens.textPrimary,
                            }}
                          >
                            {metric(player, key)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
