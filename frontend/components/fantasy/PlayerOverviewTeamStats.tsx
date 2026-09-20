"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  FantasyTeamPlayerStats,
  FantasyTeamStats,
  FantasyTeamSummary,
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
          <div>
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
              Season leaders, roster production, and depth
              chart for one franchise.
            </p>
          </div>
          <label className="block text-sm">
            <span
              className="mb-1 block text-[11px] font-semibold uppercase tracking-wide"
              style={{ color: snapshotTokens.textMuted }}
            >
              Team
            </span>
            <select
              value={teamAbbr}
              disabled={loadingTeams || teams.length === 0}
              onChange={(event) =>
                setTeamAbbr(event.target.value)
              }
              className="min-w-[12rem] rounded-lg border bg-white px-3 py-2 text-sm outline-none"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textPrimary,
              }}
            >
              {teams.map((team) => (
                <option
                  key={team.team_id || team.abbreviation}
                  value={team.abbreviation}
                >
                  {team.abbreviation} — {team.name}
                </option>
              ))}
            </select>
          </label>
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
