"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  HelpCircle,
  MinusCircle,
  XCircle,
} from "lucide-react";

import {
  FantasyPlayerSearchHit,
  FantasyPlayerSnapshot,
  FantasyScoringFormat,
  getFantasyPlayerSnapshot,
  listFantasyPlayers,
} from "@/services/api";

import MultiSelectFilter, {
  MULTI_SELECT_NONE,
} from "@/components/fantasy/MultiSelectFilter";
import PlayerOverviewCompare from "@/components/fantasy/PlayerOverviewCompare";
import PlayerOverviewScatter from "@/components/fantasy/PlayerOverviewScatter";
import PlayerOverviewTeamStats from "@/components/fantasy/PlayerOverviewTeamStats";
import PlayerSnapshotModal from "@/components/fantasy/snapshot/PlayerSnapshotModal";
import type { SnapshotTabId } from "@/components/fantasy/snapshot/PlayerTabs";
import {
  assessmentStyles,
  formatScore as formatSnapshotScore,
  snapshotTokens,
} from "@/components/fantasy/snapshot/tokens";

export type PlayerSnapshotData = FantasyPlayerSnapshot;

type SortKey =
  | "name"
  | "position"
  | "team"
  | "status"
  | "fantasy_points"
  | "fppg"
  | "projection"
  | "production_score"
  | "opportunity_score"
  | "fantasy_value_score";

type SortDir = "asc" | "desc";

type OverviewTab = "table" | "scatter" | "compare" | "teams";

interface Props {
  /** Optional preloaded snapshots from the analysis dashboard. */
  snapshots?: PlayerSnapshotData[];
  /** Open player detail on this tab when a player is selected. */
  initialDetailTab?: SnapshotTabId;
  /** Notify parent (e.g. application context) when a player is opened. */
  onPlayerSelect?: (playerId: string) => void;
}

const POSITIONS = [
  "QB",
  "RB",
  "WR",
  "TE",
  "K",
  "DEF",
] as const;

const SCORING_OPTIONS: Array<{
  id: FantasyScoringFormat;
  label: string;
}> = [
  { id: "ppr", label: "PPR" },
  { id: "half_ppr", label: "Half PPR" },
  { id: "standard", label: "Standard" },
];

const NUMERIC_SORT_KEYS: SortKey[] = [
  "fantasy_points",
  "fppg",
  "projection",
  "production_score",
  "opportunity_score",
  "fantasy_value_score",
];

const OVERVIEW_TABS: Array<{
  id: OverviewTab;
  label: string;
}> = [
  { id: "table", label: "Table" },
  { id: "scatter", label: "Scatter" },
  { id: "compare", label: "Compare" },
  { id: "teams", label: "Team Stats" },
];

function displayValue(value: unknown): string {
  if (value == null || value === "") {
    return "—";
  }
  return String(value);
}

function displayPosition(
  player: FantasyPlayerSearchHit
): string {
  if (player.depth_chart) {
    return player.depth_chart;
  }
  return displayValue(player.position);
}

function formatPoints(value: unknown): string {
  if (value == null || value === "") {
    return "—";
  }
  const numeric =
    typeof value === "number"
      ? value
      : Number(value);
  if (!Number.isFinite(numeric)) {
    return "—";
  }
  return numeric.toFixed(1);
}

function formatScore(value: unknown): string {
  if (value == null || value === "") {
    return "—";
  }
  const numeric =
    typeof value === "number"
      ? value
      : Number(value);
  if (!Number.isFinite(numeric)) {
    return "—";
  }
  return formatSnapshotScore(numeric);
}

function scoreValue(
  player: FantasyPlayerSearchHit,
  key: SortKey
): number | null {
  if (key === "fantasy_points") {
    return player.fantasy_points ?? null;
  }
  if (key === "fppg") {
    return player.fppg ?? null;
  }
  if (key === "projection") {
    return player.projection ?? null;
  }
  if (key === "production_score") {
    return player.production_score ?? null;
  }
  if (key === "opportunity_score") {
    return player.opportunity_score ?? null;
  }
  if (key === "fantasy_value_score") {
    return player.fantasy_value_score ?? null;
  }
  return null;
}

function compareText(
  left: string | null | undefined,
  right: string | null | undefined
): number {
  return (left || "").localeCompare(
    right || "",
    undefined,
    { sensitivity: "base" }
  );
}

function normalizeStatus(
  status: string | null | undefined
): string {
  const value = String(status || "").trim();
  return value || "Unknown";
}

function StatusIcon({
  status,
  injuryType,
  injuryStatus,
}: {
  status: string | null | undefined;
  injuryType?: string | null | undefined;
  injuryStatus?: string | null | undefined;
}) {
  const rosterLabel = normalizeStatus(status);
  const bodyPart = String(injuryType || "").trim();
  const reportStatus = String(injuryStatus || "").trim();
  const iconSource = reportStatus || rosterLabel;
  const lower = iconSource.toLowerCase();
  const clearWhileActive =
    !reportStatus
    && (
      rosterLabel.toLowerCase() === "active"
      || rosterLabel.toLowerCase().includes("healthy")
    );

  let Icon = Circle;
  let color = snapshotTokens.textMuted;
  let title = rosterLabel;
  if (bodyPart && reportStatus) {
    title = `${bodyPart} - ${reportStatus}`;
  } else if (bodyPart) {
    title = `${bodyPart} - ${rosterLabel}`;
  } else if (reportStatus) {
    title = `${rosterLabel} — ${reportStatus}`;
  }

  if (clearWhileActive) {
    Icon = CheckCircle2;
    color = snapshotTokens.success;
  } else if (
    lower === "active"
    || lower.includes("healthy")
  ) {
    Icon = CheckCircle2;
    color = snapshotTokens.success;
  } else if (
    lower.includes("out")
    || lower.includes("ir")
    || lower.includes("pup")
    || lower.includes("suspend")
  ) {
    Icon = XCircle;
    color = snapshotTokens.negative;
  } else if (
    lower.includes("doubt")
    || lower.includes("question")
    || lower.includes("injur")
    || lower.includes("limited")
    || lower.includes("did not participate")
    || lower.includes("full participation")
  ) {
    Icon = AlertTriangle;
    color = "#B45309";
  } else if (
    lower.includes("inactive")
    || lower.includes("reserve")
    || lower.includes("practice")
  ) {
    Icon = MinusCircle;
    color = snapshotTokens.textMuted;
  } else if (lower === "unknown") {
    Icon = HelpCircle;
    color = snapshotTokens.textMuted;
  } else if (reportStatus) {
    Icon = AlertTriangle;
    color = "#B45309";
  }

  return (
    <span
      className="inline-flex"
      title={title}
      aria-label={title}
    >
      <Icon
        className="h-4 w-4"
        style={{ color }}
      />
    </span>
  );
}

function matchesMulti(
  value: string | null | undefined,
  selected: string[],
  emptyMeansAll: boolean
): boolean {
  if (
    selected.length === 1
    && selected[0] === MULTI_SELECT_NONE
  ) {
    return false;
  }
  if (emptyMeansAll && selected.length === 0) {
    return true;
  }
  if (selected.length === 0) {
    return false;
  }
  const normalized = normalizeStatus(value);
  return selected.some(
    (option) =>
      option.toLowerCase() === normalized.toLowerCase()
  );
}

export default function PlayerSnapshot({
  snapshots: _snapshots = [],
  initialDetailTab = "snapshot",
  onPlayerSelect,
}: Props) {
  const [players, setPlayers] = useState<
    FantasyPlayerSearchHit[]
  >([]);
  const [loadingList, setLoadingList] =
    useState(true);
  const [listError, setListError] = useState<
    string | null
  >(null);

  const [overviewTab, setOverviewTab] =
    useState<OverviewTab>("table");
  const [search, setSearch] = useState("");
  const [positionFilter, setPositionFilter] =
    useState<string[]>([]);
  const [teamFilter, setTeamFilter] =
    useState<string[]>([]);
  const [statusFilter, setStatusFilter] =
    useState<string[]>(["Active"]);
  const [scoring, setScoring] =
    useState<FantasyScoringFormat>("ppr");
  const [sortKey, setSortKey] =
    useState<SortKey>("fantasy_points");
  const [sortDir, setSortDir] =
    useState<SortDir>("desc");

  const [selectedId, setSelectedId] = useState<
    string | null
  >(null);
  const [active, setActive] =
    useState<PlayerSnapshotData | null>(null);
  const [loadingSnapshot, setLoadingSnapshot] =
    useState(false);
  const [snapshotError, setSnapshotError] =
    useState<string | null>(null);
  const [listRefreshNonce, setListRefreshNonce] =
    useState(0);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        setLoadingList(true);
        setListError(null);
        const result = await listFantasyPlayers({
          limit: 2000,
          scoring,
        });
        if (cancelled) {
          return;
        }
        setPlayers(result.players ?? []);
      } catch (error) {
        if (cancelled) {
          return;
        }
        setPlayers([]);
        setListError(
          error instanceof Error
            ? error.message
            : "Unable to load players."
        );
      } finally {
        if (!cancelled) {
          setLoadingList(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [listRefreshNonce, scoring]);

  useEffect(() => {
    const onDataRefreshed = () => {
      setListRefreshNonce((current) => current + 1);
    };
    window.addEventListener(
      "insightpilot:fantasy-data-refreshed",
      onDataRefreshed
    );
    return () => {
      window.removeEventListener(
        "insightpilot:fantasy-data-refreshed",
        onDataRefreshed
      );
    };
  }, []);

  useEffect(() => {
    if (!selectedId) {
      return;
    }

    let cancelled = false;

    void (async () => {
      try {
        setLoadingSnapshot(true);
        setSnapshotError(null);
        const result =
          await getFantasyPlayerSnapshot(selectedId);
        if (cancelled) {
          return;
        }
        setActive(result.snapshot);
      } catch (error) {
        if (cancelled) {
          return;
        }
        setActive(null);
        setSnapshotError(
          error instanceof Error
            ? error.message
            : "Unable to load player snapshot."
        );
      } finally {
        if (!cancelled) {
          setLoadingSnapshot(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) {
      return;
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeModal();
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener(
        "keydown",
        onKeyDown
      );
    };
  }, [selectedId]);

  const teams = useMemo(
    () =>
      Array.from(
        new Set(
          players
            .map((player) => player.team)
            .filter(
              (team): team is string =>
                Boolean(team)
            )
        )
      ).sort(),
    [players]
  );

  const statuses = useMemo(() => {
    const values = Array.from(
      new Set(
        players.map((player) =>
          normalizeStatus(player.status)
        )
      )
    ).sort((left, right) =>
      left.localeCompare(right, undefined, {
        sensitivity: "base",
      })
    );
    // Keep Active first when present.
    return values.sort((left, right) => {
      if (left === "Active") {
        return -1;
      }
      if (right === "Active") {
        return 1;
      }
      return left.localeCompare(right);
    });
  }, [players]);

  const rows = useMemo(() => {
    const needle = search.trim().toLowerCase();

    const filtered = players.filter((player) => {
      if (
        positionFilter.length === 1
        && positionFilter[0] === MULTI_SELECT_NONE
      ) {
        return false;
      }
      if (positionFilter.length > 0) {
        const pos = (player.position || "").toUpperCase();
        if (!positionFilter.includes(pos)) {
          return false;
        }
      }

      if (
        teamFilter.length === 1
        && teamFilter[0] === MULTI_SELECT_NONE
      ) {
        return false;
      }
      if (teamFilter.length > 0) {
        const team = (player.team || "").toUpperCase();
        if (
          !teamFilter.some(
            (option) => option.toUpperCase() === team
          )
        ) {
          return false;
        }
      }

      if (
        !matchesMulti(
          player.status,
          statusFilter,
          false
        )
      ) {
        return false;
      }

      if (!needle) {
        return true;
      }

      const haystack = [
        player.name,
        player.position,
        player.team,
        player.status,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return haystack.includes(needle);
    });

    const sorted = [...filtered].sort((left, right) => {
      if (NUMERIC_SORT_KEYS.includes(sortKey)) {
        const leftPts = scoreValue(left, sortKey);
        const rightPts = scoreValue(right, sortKey);

        if (leftPts == null && rightPts == null) {
          return compareText(left.name, right.name);
        }
        if (leftPts == null) {
          return 1;
        }
        if (rightPts == null) {
          return -1;
        }

        const cmp = leftPts - rightPts;
        if (cmp === 0) {
          return compareText(left.name, right.name);
        }
        return sortDir === "asc" ? cmp : -cmp;
      }

      const cmp =
        sortKey === "name"
          ? compareText(left.name, right.name)
          : sortKey === "position"
            ? compareText(left.position, right.position)
            : sortKey === "team"
              ? compareText(left.team, right.team)
              : compareText(left.status, right.status);

      return sortDir === "asc" ? cmp : -cmp;
    });

    return sorted;
  }, [
    players,
    search,
    positionFilter,
    teamFilter,
    statusFilter,
    sortKey,
    sortDir,
  ]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((dir) =>
        dir === "asc" ? "desc" : "asc"
      );
      return;
    }
    setSortKey(key);
    setSortDir(
      NUMERIC_SORT_KEYS.includes(key) ? "desc" : "asc"
    );
  }

  function openPlayer(playerId: string) {
    setSelectedId(playerId);
    onPlayerSelect?.(playerId);
  }

  function closeModal() {
    setSelectedId(null);
    setActive(null);
    setSnapshotError(null);
    setLoadingSnapshot(false);
  }

  function sortLabel(key: SortKey): string {
    if (sortKey !== key) {
      return "";
    }
    return sortDir === "asc" ? " ↑" : " ↓";
  }

  return (
    <section
      className="overflow-hidden rounded-[10px] border bg-white"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div
        className="border-b px-5 py-4 sm:px-6"
        style={{
          borderColor: snapshotTokens.divider,
          background: snapshotTokens.background,
        }}
      >
        <p
          className="text-xs font-semibold uppercase tracking-[0.16em]"
          style={{ color: snapshotTokens.textMuted }}
        >
          Player Overview
        </p>
        <h3
          className="mt-1 text-lg font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          Players
        </h3>
        <p
          className="mt-1 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          Browse the table, explore opportunity vs
          production, compare players, or dig into team
          leaders and depth charts.
        </p>

        <div
          className="mt-4 flex flex-wrap gap-1 border-b pb-2"
          style={{ borderColor: snapshotTokens.border }}
          role="tablist"
          aria-label="Player overview views"
        >
          {OVERVIEW_TABS.map((tab) => {
            const selected = overviewTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => setOverviewTab(tab.id)}
                className="rounded-md px-3 py-1.5 text-sm font-semibold"
                style={{
                  background: selected
                    ? snapshotTokens.blueLight
                    : "transparent",
                  color: selected
                    ? snapshotTokens.blue
                    : snapshotTokens.textSecondary,
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {overviewTab !== "teams" && (
      <div
        className="flex flex-wrap items-center gap-3 border-b bg-white px-4 py-3 sm:px-5"
        style={{ borderColor: snapshotTokens.divider }}
      >
        <label
          className="sr-only"
          htmlFor="player-table-search"
        >
          Search players
        </label>
        <input
          id="player-table-search"
          type="search"
          value={search}
          onChange={(event) =>
            setSearch(event.target.value)
          }
          placeholder="Search name, position, team…"
          className="min-w-[12rem] flex-1 rounded-lg border bg-white px-3 py-2 text-sm outline-none focus:ring-2"
          style={{
            borderColor: snapshotTokens.border,
            color: snapshotTokens.textPrimary,
          }}
          autoComplete="off"
        />

        <MultiSelectFilter
          label="Pos"
          options={[...POSITIONS]}
          selected={positionFilter}
          onChange={setPositionFilter}
          emptyMeansAll
        />
        <MultiSelectFilter
          label="Team"
          options={teams}
          selected={teamFilter}
          onChange={setTeamFilter}
          emptyMeansAll
        />
        <MultiSelectFilter
          label="Status"
          options={statuses}
          selected={statusFilter}
          onChange={setStatusFilter}
          emptyMeansAll={false}
        />
        <label className="block min-w-[8.5rem]">
          <span
            className="mb-1 block text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Scoring
          </span>
          <select
            value={scoring}
            onChange={(event) =>
              setScoring(
                event.target.value as FantasyScoringFormat
              )
            }
            className="w-full rounded-lg border bg-white px-2.5 py-2 text-sm"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textPrimary,
            }}
          >
            {SCORING_OPTIONS.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <p
          className="ml-auto text-xs"
          style={{ color: snapshotTokens.textMuted }}
        >
          {loadingList
            ? "Loading…"
            : `${rows.length} player${rows.length === 1 ? "" : "s"}`}
        </p>
      </div>
      )}

      {listError && overviewTab !== "teams" && (
        <p
          className="px-5 py-3 text-sm"
          style={{ color: snapshotTokens.negative }}
        >
          {listError}
        </p>
      )}

      <div className="p-4 sm:p-5">
        {overviewTab === "table" && (
          <div className="max-h-[32rem] overflow-auto rounded-[10px] border" style={{ borderColor: snapshotTokens.border }}>
            <table className="min-w-full divide-y text-sm" style={{ borderColor: snapshotTokens.divider }}>
              <thead
                className="sticky top-0 text-left text-xs uppercase tracking-wide"
                style={{
                  background: snapshotTokens.background,
                  color: snapshotTokens.textMuted,
                }}
              >
                <tr>
                  {(
                    [
                      ["name", "Name"],
                      ["position", "Pos"],
                      ["team", "Team"],
                      ["fantasy_points", "Pts"],
                      ["fppg", "PPG"],
                      ["projection", "Proj"],
                      ["production_score", "Prod"],
                      ["opportunity_score", "Opp"],
                      ["fantasy_value_score", "Assess"],
                      ["status", "Status"],
                    ] as const
                  ).map(([key, label]) => (
                    <th key={key} className="px-4 py-3 font-medium">
                      <button
                        type="button"
                        onClick={() => toggleSort(key)}
                        className="inline-flex items-center gap-0.5"
                        style={{ color: snapshotTokens.textSecondary }}
                      >
                        {label}
                        <span style={{ color: snapshotTokens.blue }}>
                          {sortLabel(key)}
                        </span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody
                className="divide-y bg-white"
                style={{ borderColor: snapshotTokens.divider }}
              >
                {loadingList ? (
                  <tr>
                    <td
                      colSpan={10}
                      className="px-4 py-10 text-center"
                      style={{ color: snapshotTokens.textSecondary }}
                    >
                      Loading players…
                    </td>
                  </tr>
                ) : rows.length === 0 ? (
                  <tr>
                    <td
                      colSpan={10}
                      className="px-4 py-10 text-center"
                      style={{ color: snapshotTokens.textSecondary }}
                    >
                      No players match the current filters.
                    </td>
                  </tr>
                ) : (
                  rows.map((player) => {
                    const tone = assessmentStyles(
                      player.overall_assessment
                    );
                    return (
                      <tr
                        key={player.player_id}
                        className="cursor-pointer transition"
                        style={{ background: "transparent" }}
                        onMouseEnter={(event) => {
                          event.currentTarget.style.background =
                            snapshotTokens.blueLight;
                        }}
                        onMouseLeave={(event) => {
                          event.currentTarget.style.background =
                            "transparent";
                        }}
                        onClick={() =>
                          openPlayer(player.player_id)
                        }
                      >
                        <td
                          className="px-4 py-3 font-medium"
                          style={{ color: snapshotTokens.textPrimary }}
                        >
                          {player.name}
                        </td>
                        <td
                          className="px-4 py-3"
                          style={{ color: snapshotTokens.textSecondary }}
                        >
                          {displayPosition(player)}
                        </td>
                        <td
                          className="px-4 py-3"
                          style={{ color: snapshotTokens.textSecondary }}
                        >
                          {displayValue(player.team)}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums font-semibold"
                          style={{ color: snapshotTokens.textPrimary }}
                        >
                          {formatPoints(player.fantasy_points)}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums"
                          style={{ color: snapshotTokens.textPrimary }}
                        >
                          {formatPoints(player.fppg)}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums font-semibold"
                          style={{ color: snapshotTokens.blue }}
                        >
                          {formatPoints(player.projection)}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums"
                          style={{ color: snapshotTokens.textPrimary }}
                        >
                          {formatScore(player.production_score)}
                        </td>
                        <td
                          className="px-4 py-3 tabular-nums"
                          style={{ color: snapshotTokens.textPrimary }}
                        >
                          {formatScore(player.opportunity_score)}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-semibold tabular-nums"
                            style={{
                              background: tone.bg,
                              color: tone.text,
                            }}
                            title={
                              player.overall_assessment
                              || undefined
                            }
                          >
                            {formatScore(
                              player.fantasy_value_score
                            )}
                            {player.overall_assessment
                              && player.fantasy_value_score
                                != null && (
                                <span className="font-medium uppercase tracking-wide opacity-80">
                                  {player.overall_assessment}
                                </span>
                              )}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <StatusIcon
                            status={player.status}
                            injuryType={player.injury_type}
                            injuryStatus={player.injury_status}
                          />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}

        {overviewTab === "scatter" && (
          <PlayerOverviewScatter
            players={rows}
            onSelectPlayer={openPlayer}
          />
        )}

        {overviewTab === "compare" && (
          <PlayerOverviewCompare
            players={rows}
            onOpenPlayer={openPlayer}
          />
        )}

        {overviewTab === "teams" && (
          <PlayerOverviewTeamStats
            onSelectPlayer={openPlayer}
          />
        )}
      </div>

      {selectedId && (
        <PlayerSnapshotModal
          active={active}
          loading={loadingSnapshot}
          error={snapshotError}
          onClose={closeModal}
          onSelectPlayer={openPlayer}
          initialTab={initialDetailTab}
        />
      )}
    </section>
  );
}

export function snapshotsFromDashboard(
  dashboard: {
    datasets?: Record<string, unknown>;
  } | null | undefined
): PlayerSnapshotData[] {
  const rows = dashboard?.datasets?.player_snapshots;
  if (!Array.isArray(rows)) {
    return [];
  }

  return rows.filter(
    (row): row is PlayerSnapshotData =>
      row != null
      && typeof row === "object"
      && typeof (row as PlayerSnapshotData).player_id
        === "string"
  );
}
