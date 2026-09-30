"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import DfsSlateHeader, {
  type DfsWorkspaceTab,
} from "@/components/fantasy/dfs/DfsSlateHeader";
import LineupCard from "@/components/fantasy/dfs/LineupCard";
import LineupInsights from "@/components/fantasy/dfs/LineupInsights";
import OptimizationProgress from "@/components/fantasy/dfs/OptimizationProgress";
import PlayerDetailDrawer from "@/components/fantasy/dfs/PlayerDetailDrawer";
import PlayerPool from "@/components/fantasy/dfs/PlayerPool";
import PortfolioBuilder from "@/components/fantasy/dfs/portfolio/PortfolioBuilder";
import SlateSummary from "@/components/fantasy/dfs/SlateSummary";
import ValuePlays from "@/components/fantasy/dfs/ValuePlays";
import PlayerSnapshotModal from "@/components/fantasy/snapshot/PlayerSnapshotModal";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import {
  DfsContestType,
  DfsLineup,
  DfsLineupInsight,
  DfsLineupPlayer,
  DfsPlayer,
  DfsRisk,
  DfsSignal,
  DfsSiteId,
  DfsSlate,
  FantasyPlayerSnapshot,
  getDfsSlate,
  getFantasyPlayerSnapshot,
  listDfsSites,
  listDfsSlates,
  listDfsWeeks,
  optimizeDfsLineup,
} from "@/services/api";

export default function DailyFantasyAnalyzer({
  initialTab = "analyzer",
  hideTabBar = false,
}: {
  initialTab?: DfsWorkspaceTab;
  hideTabBar?: boolean;
} = {}) {
  const [sites, setSites] = useState<
    Array<{ id: string; name: string; salary_cap: number; slots: string[] }>
  >([]);
  const [weeks, setWeeks] = useState<number[]>([]);
  const [week, setWeek] = useState<number | null>(null);
  const [slates, setSlates] = useState<
    Array<{
      slate_id: string;
      label: string;
      week?: number | null;
      game_count?: number;
    }>
  >([]);
  const [site, setSite] = useState<DfsSiteId>("draftkings");
  const [slateId, setSlateId] = useState("");
  const [contestType, setContestType] =
    useState<DfsContestType>("classic");
  const [risk, setRisk] = useState<DfsRisk>("balanced");
  const [activeTab, setActiveTab] =
    useState<DfsWorkspaceTab>(initialTab);
  const [slate, setSlate] = useState<DfsSlate | null>(null);
  const [lineup, setLineup] = useState<DfsLineup | null>(null);
  const [lockedIds, setLockedIds] = useState<Set<string>>(
    () => new Set()
  );
  const [excludedIds, setExcludedIds] = useState<Set<string>>(
    () => new Set()
  );
  const [positionFilter, setPositionFilter] = useState("All");
  const [selectedId, setSelectedId] = useState<string | null>(
    null
  );
  const [loading, setLoading] = useState(true);
  const [optimizing, setOptimizing] = useState(false);
  const [optStep, setOptStep] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [constraintHint, setConstraintHint] = useState<
    string | null
  >(null);
  const [activeSlotIndex, setActiveSlotIndex] = useState<
    number | null
  >(null);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [overviewOpen, setOverviewOpen] = useState(false);
  const [overviewSnapshot, setOverviewSnapshot] =
    useState<FantasyPlayerSnapshot | null>(null);
  const [overviewLoading, setOverviewLoading] =
    useState(false);
  const [overviewError, setOverviewError] = useState<
    string | null
  >(null);
  const [salaryRefreshNonce, setSalaryRefreshNonce] =
    useState(0);
  const [portfolioMounted, setPortfolioMounted] = useState(false);
  const insightsRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setActiveTab(initialTab);
  }, [initialTab]);

  useEffect(() => {
    if (activeTab === "portfolio") {
      setPortfolioMounted(true);
    }
  }, [activeTab]);

  const playersById = useMemo(() => {
    const map = new Map<string, DfsPlayer>();
    for (const player of slate?.players ?? []) {
      map.set(player.player_id, player);
    }
    return map;
  }, [slate]);

  const selectedPlayer = selectedId
    ? playersById.get(selectedId) ?? null
    : null;

  const lineupIds = useMemo(
    () =>
      new Set(
        (lineup?.players ?? []).map(
          (player) => player.player_id
        )
      ),
    [lineup]
  );

  const slots =
    slate?.roster.map((item) => item.slot)
    ?? (contestType === "showdown"
      ? ["CPT", "FLEX", "FLEX", "FLEX", "FLEX", "FLEX"]
      : ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        setLoading(true);
        setError(null);
        const [siteResult, weekResult] = await Promise.all([
          listDfsSites(),
          listDfsWeeks(),
        ]);
        if (cancelled) {
          return;
        }
        setSites(siteResult.sites);
        if (siteResult.sites[0]?.id) {
          setSite(siteResult.sites[0].id);
        }
        setWeeks(weekResult.weeks);
        setWeek(weekResult.current_week);
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load DFS configuration."
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (week == null) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        setLoading(true);
        setError(null);
        const slateResult = await listDfsSlates(
          null,
          contestType,
          week
        );
        if (cancelled) {
          return;
        }
        setSlates(slateResult.slates);
        const preferred =
          slateResult.slates.find(
            (item) => (item.game_count ?? 0) > 0
          )?.slate_id
          ?? slateResult.slates[0]?.slate_id
          ?? "";
        setSlateId(preferred);
        setLineup(null);
        setLockedIds(new Set());
        setExcludedIds(new Set());
        setActiveSlotIndex(null);
        setAnalysisOpen(false);
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load DFS slates."
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [contestType, week]);

  useEffect(() => {
    const onSalariesUpdated = (event: Event) => {
      const detail = (
        event as CustomEvent<{
          site?: string;
          contest_type?: string;
        }>
      ).detail;
      if (detail?.site) {
        setSite(detail.site as DfsSiteId);
      }
      if (
        detail?.contest_type === "classic"
        || detail?.contest_type === "showdown"
      ) {
        setContestType(detail.contest_type);
      }
      setSalaryRefreshNonce((current) => current + 1);
      void listDfsWeeks().then((weekResult) => {
        setWeeks(weekResult.weeks);
        setWeek((current) =>
          current != null
          && weekResult.weeks.includes(current)
            ? current
            : weekResult.current_week
        );
      }).catch(() => undefined);
    };
    window.addEventListener(
      "insightpilot:dfs-salaries-updated",
      onSalariesUpdated
    );
    window.addEventListener(
      "insightpilot:fantasy-data-refreshed",
      onSalariesUpdated
    );
    return () => {
      window.removeEventListener(
        "insightpilot:dfs-salaries-updated",
        onSalariesUpdated
      );
      window.removeEventListener(
        "insightpilot:fantasy-data-refreshed",
        onSalariesUpdated
      );
    };
  }, []);

  useEffect(() => {
    if (!slateId) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await getDfsSlate(slateId, {
          site,
          contest_type: contestType,
          limit: contestType === "showdown" ? 100 : 250,
        });
        if (cancelled) {
          return;
        }
        setSlate(result.slate);
        setLineup(null);
        setConstraintHint(null);
        setAnalysisOpen(false);
        setActiveSlotIndex(
          contestType === "showdown" ? 0 : null
        );
      } catch (loadError) {
        if (!cancelled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load DFS slate."
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slateId, site, contestType, salaryRefreshNonce]);

  async function runOptimize() {
    if (!slateId) {
      return;
    }
    setOptimizing(true);
    setOptStep(0);
    setError(null);
    setConstraintHint(null);
    const timers = [0, 1, 2, 3, 4].map((step) =>
      window.setTimeout(() => setOptStep(step), step * 350)
    );
    try {
      const result = await optimizeDfsLineup({
        slate_id: slateId,
        site,
        contest_type: contestType,
        risk,
        locked_players: Array.from(lockedIds),
        excluded_players: Array.from(excludedIds),
      });
      setLineup(result.lineup);
      setActiveSlotIndex(null);
      setAnalysisOpen(true);
      if (!result.lineup.valid) {
        setConstraintHint(
          "No complete lineup satisfied every roster slot under the current constraints. Try unlocking a player or removing exclusions."
        );
      }
    } catch (optError) {
      setError(
        optError instanceof Error
          ? optError.message
          : "Optimization failed."
      );
      setConstraintHint(
        "Try lowering exclusivity constraints or changing contest type."
      );
    } finally {
      timers.forEach((timer) => window.clearTimeout(timer));
      setOptStep(5);
      setOptimizing(false);
    }
  }

  function analyzeLineup() {
    if (!lineup || lineup.players.length === 0) {
      setConstraintHint(
        "Add players to the lineup before analyzing."
      );
      return;
    }
    const { insights, signals, edge_summary } =
      buildClientLineupAnalysis(lineup);
    setLineup({
      ...lineup,
      insights,
      signals,
      edge_summary,
    });
    setAnalysisOpen(true);
    setConstraintHint(null);
    window.requestAnimationFrame(() => {
      insightsRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    });
  }

  function toggleLock(playerId: string) {
    const willLock = !lockedIds.has(playerId);
    setLockedIds((prev) => {
      const next = new Set(prev);
      if (willLock) {
        next.add(playerId);
      } else {
        next.delete(playerId);
      }
      return next;
    });
    if (willLock) {
      setExcludedIds((excluded) => {
        const copy = new Set(excluded);
        copy.delete(playerId);
        return copy;
      });
    }
    setLineup((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        players: current.players.map((player) =>
          player.player_id === playerId
            ? { ...player, locked: willLock }
            : player
        ),
      };
    });
  }

  function toggleExclude(playerId: string) {
    setExcludedIds((prev) => {
      const next = new Set(prev);
      if (next.has(playerId)) {
        next.delete(playerId);
      } else {
        next.add(playerId);
        setLockedIds((locked) => {
          const copy = new Set(locked);
          copy.delete(playerId);
          return copy;
        });
        setLineup((current) => {
          if (!current) {
            return current;
          }
          return {
            ...current,
            players: current.players.filter(
              (player) => player.player_id !== playerId
            ),
            roster_filled: current.players.filter(
              (player) => player.player_id !== playerId
            ).length,
          };
        });
      }
      return next;
    });
  }

  function removeFromLineup(playerId: string) {
    setLineup((current) => {
      if (!current) {
        return current;
      }
      const players = current.players.filter(
        (player) => player.player_id !== playerId
      );
      return recomputeLineup(current, players);
    });
    setLockedIds((prev) => {
      const next = new Set(prev);
      next.delete(playerId);
      return next;
    });
  }

  function addToLineup(
    playerId: string,
    slotIndex?: number | null
  ) {
    const player = playersById.get(playerId);
    if (!player || !slate) {
      return;
    }
    if (excludedIds.has(playerId)) {
      setConstraintHint(
        `${player.name} is excluded. Un-exclude them before adding.`
      );
      return;
    }
    const base = lineup ?? emptyLineup(slate);
    const rows = buildSlotRows(slots, base.players);
    const preferredSlot =
      slotIndex != null ? slotIndex : activeSlotIndex;
    const targetIndex =
      preferredSlot != null
      && preferredSlot >= 0
      && preferredSlot < slots.length
        ? preferredSlot
        : null;

    let nextPlayers = [...base.players];
    const existingIndex = nextPlayers.findIndex(
      (item) => item.player_id === playerId
    );

    if (targetIndex == null) {
      if (existingIndex >= 0) {
        return;
      }
      const openSlot = findOpenSlot(
        base,
        player,
        slots,
        slate
      );
      if (!openSlot) {
        setConstraintHint(
          contestType === "showdown"
            ? `No open CPT / FLEX seat for ${player.name}.`
            : `No open ${player.position} / FLEX slot for ${player.name}.`
        );
        return;
      }
      const placed = toLineupPlayer(
        player,
        openSlot,
        slate,
        lockedIds.has(playerId)
      );
      if (base.salary_used + (placed.salary || 0) > base.salary_cap) {
        setConstraintHint(
          `Adding ${player.name} would exceed the salary cap.`
        );
        return;
      }
      setConstraintHint(null);
      setLineup(
        recomputeLineup(base, [...nextPlayers, placed])
      );
      return;
    }

    const targetSlot = slots[targetIndex];
    const occupying = rows[targetIndex]?.player ?? null;

    if (occupying?.player_id === playerId) {
      setActiveSlotIndex(null);
      return;
    }

    if (existingIndex >= 0) {
      nextPlayers = nextPlayers.filter(
        (item) => item.player_id !== playerId
      );
    }
    if (occupying) {
      nextPlayers = nextPlayers.filter(
        (item) => item.player_id !== occupying.player_id
      );
    }

    if (!playerFitsSlot(player, targetSlot, slate)) {
      setConstraintHint(
        `${player.name} cannot fill the ${targetSlot} seat.`
      );
      return;
    }

    const placed = toLineupPlayer(
      player,
      targetSlot,
      slate,
      lockedIds.has(playerId)
    );
    const salaryUsed = nextPlayers.reduce(
      (sum, item) => sum + (item.salary || 0),
      0
    );
    if (salaryUsed + (placed.salary || 0) > base.salary_cap) {
      setConstraintHint(
        `Adding ${player.name} would exceed the salary cap.`
      );
      return;
    }

    setConstraintHint(null);
    setActiveSlotIndex(null);
    setLineup(recomputeLineup(base, [...nextPlayers, placed]));
  }

  async function openPlayerOverview(playerId: string) {
    setOverviewOpen(true);
    setOverviewLoading(true);
    setOverviewError(null);
    setOverviewSnapshot(null);
    setSelectedId(null);
    try {
      const result = await getFantasyPlayerSnapshot(
        playerId,
        slate?.season ?? null
      );
      setOverviewSnapshot(result.snapshot);
    } catch (loadError) {
      setOverviewError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to load player overview."
      );
    } finally {
      setOverviewLoading(false);
    }
  }

  function closePlayerOverview() {
    setOverviewOpen(false);
    setOverviewSnapshot(null);
    setOverviewError(null);
    setOverviewLoading(false);
  }

  function selectLineupSlot(slotIndex: number) {
    setActiveSlotIndex((current) =>
      current === slotIndex ? null : slotIndex
    );
  }

  const freshness = formatFreshness(slate);

  if (loading && !slate) {
    return (
      <div
        className="rounded-[10px] border px-4 py-10 text-center text-sm"
        style={{
          borderColor: snapshotTokens.border,
          color: snapshotTokens.textSecondary,
        }}
      >
        Loading Daily Fantasy Analyzer…
      </div>
    );
  }

  if (!slate && error) {
    return (
      <div
        className="rounded-[10px] border px-4 py-10 text-center text-sm"
        style={{
          borderColor: snapshotTokens.border,
          color: snapshotTokens.negative,
        }}
      >
        {error}
      </div>
    );
  }

  if (!slateId && !loading) {
    return (
      <div
        className="rounded-[10px] border px-4 py-10 text-center text-sm"
        style={{
          borderColor: snapshotTokens.border,
          color: snapshotTokens.textSecondary,
        }}
      >
        Select a slate to begin analyzing players and building
        lineups.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <DfsSlateHeader
        site={site}
        sites={sites}
        week={week}
        weeks={weeks}
        slateId={slateId}
        slates={slates}
        contestType={contestType}
        risk={risk}
        optimizing={optimizing}
        activeTab={activeTab}
        onSite={setSite}
        onWeek={setWeek}
        onSlate={setSlateId}
        onContest={setContestType}
        onRisk={setRisk}
        onOptimize={() => void runOptimize()}
        onTab={setActiveTab}
        freshness={freshness}
        hideTabs={hideTabBar}
      />

      {slate && portfolioMounted && (
        <div
          className={
            activeTab === "portfolio" ? "block" : "hidden"
          }
        >
          <PortfolioBuilder
            slate={slate}
            site={site}
            contestType={contestType}
            risk={risk}
            seedLockedIds={lockedIds}
            seedExcludedIds={excludedIds}
          />
        </div>
      )}

      {activeTab !== "portfolio" && (
        <>
          <OptimizationProgress
            active={optimizing}
            stepIndex={optStep}
          />

          {error && (
            <p
              className="text-sm"
              style={{ color: snapshotTokens.negative }}
            >
              {error}
            </p>
          )}
          {constraintHint && (
            <p
              className="text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              {constraintHint}
            </p>
          )}

          {(activeTab === "analyzer" ||
            activeTab === "optimizer") && (
            <SlateSummary
              lineup={lineup}
              showEdge={analysisOpen}
            />
          )}

          <div
            className={
              activeTab === "analyzer"
                ? "grid gap-4"
                : "grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(18rem,0.85fr)]"
            }
          >
            {(activeTab === "analyzer" ||
              activeTab === "optimizer") && (
              <div
                className={
                  activeTab === "optimizer"
                    ? "order-2 space-y-4 lg:order-1"
                    : "space-y-4"
                }
              >
                <PlayerPool
                  players={slate?.players ?? []}
                  positionFilter={positionFilter}
                  lockedIds={lockedIds}
                  excludedIds={excludedIds}
                  lineupIds={lineupIds}
                  onPositionFilter={setPositionFilter}
                  onSelectPlayer={setSelectedId}
                  onAdd={addToLineup}
                  onRemove={removeFromLineup}
                  onExclude={toggleExclude}
                />
                {activeTab === "analyzer" && (
                  <ValuePlays
                    players={slate?.players ?? []}
                    onSelectPlayer={setSelectedId}
                  />
                )}
              </div>
            )}

            {activeTab === "optimizer" && (
              <div className="order-1 space-y-4 lg:order-2 lg:sticky lg:top-3 lg:self-start">
                <LineupCard
                  lineup={lineup}
                  slots={slots}
                  lockedIds={lockedIds}
                  activeSlotIndex={activeSlotIndex}
                  onSelectSlot={selectLineupSlot}
                  onSelectPlayer={setSelectedId}
                  onPlacePlayer={addToLineup}
                  onRemove={removeFromLineup}
                  onLockToggle={toggleLock}
                />
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void runOptimize()}
                    disabled={optimizing}
                    className="rounded-lg px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                    style={{ background: snapshotTokens.blue }}
                  >
                    Re-optimize
                  </button>
                  <button
                    type="button"
                    onClick={analyzeLineup}
                    disabled={
                      !lineup || lineup.players.length === 0
                    }
                    className="rounded-lg border px-3 py-2 text-sm font-semibold disabled:opacity-40"
                    style={{
                      borderColor: snapshotTokens.border,
                      color: snapshotTokens.textPrimary,
                    }}
                  >
                    Analyze
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (lineup) {
                        exportLineupCsv(lineup, slots, slateId);
                      }
                    }}
                    disabled={
                      !lineup || lineup.players.length === 0
                    }
                    className="rounded-lg border px-3 py-2 text-sm font-semibold disabled:opacity-40"
                    style={{
                      borderColor: snapshotTokens.border,
                      color: snapshotTokens.textPrimary,
                    }}
                  >
                    Export CSV
                  </button>
                </div>
                <div ref={insightsRef}>
                  <LineupInsights
                    insights={
                      analysisOpen
                        ? lineup?.insights ?? []
                        : []
                    }
                    signals={
                      analysisOpen
                        ? lineup?.signals ?? []
                        : []
                    }
                    waiting={!analysisOpen}
                  />
                </div>
              </div>
            )}
          </div>

          <PlayerDetailDrawer
            player={selectedPlayer}
            inLineup={
              selectedId ? lineupIds.has(selectedId) : false
            }
            locked={
              selectedId ? lockedIds.has(selectedId) : false
            }
            excluded={
              selectedId ? excludedIds.has(selectedId) : false
            }
            onClose={() => setSelectedId(null)}
            onAdd={() => {
              if (selectedId) {
                addToLineup(selectedId);
              }
            }}
            onLock={() => {
              if (selectedId) {
                toggleLock(selectedId);
              }
            }}
            onExclude={() => {
              if (selectedId) {
                toggleExclude(selectedId);
              }
            }}
            onOpenOverview={() => {
              if (selectedId) {
                void openPlayerOverview(selectedId);
              }
            }}
          />

          {overviewOpen && (
            <PlayerSnapshotModal
              active={overviewSnapshot}
              loading={overviewLoading}
              error={overviewError}
              onClose={closePlayerOverview}
              onSelectPlayer={(playerId) => {
                void openPlayerOverview(playerId);
              }}
            />
          )}
        </>
      )}
    </div>
  );
}

function emptyLineup(slate: DfsSlate): DfsLineup {
  return {
    lineup_id: `manual-${slate.slate_id}`,
    slate_id: slate.slate_id,
    site: slate.site,
    contest_type: slate.contest_type || "classic",
    players: [],
    salary_used: 0,
    salary_remaining: slate.salary_cap,
    salary_cap: slate.salary_cap,
    projected_points: 0,
    projected_ownership: 0,
    roster_filled: 0,
    roster_size: slate.roster.length,
    valid: false,
    insights: [],
    signals: [],
  };
}

function csvEscape(value: string | number | null | undefined): string {
  const text = value == null ? "" : String(value);
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function exportLineupCsv(
  lineup: DfsLineup,
  slots: string[],
  slateId: string
) {
  const remaining = [...lineup.players];
  const ordered: Array<DfsLineupPlayer | null> = slots.map(
    (slot) => {
      const index = remaining.findIndex((player) => {
        const playerSlot = String(player.slot || "");
        if (playerSlot === slot) {
          return true;
        }
        if (slot === "DST" && playerSlot === "DEF") {
          return true;
        }
        return false;
      });
      if (index < 0) {
        return null;
      }
      const [player] = remaining.splice(index, 1);
      return player;
    }
  );
  for (const player of remaining) {
    const empty = ordered.findIndex((item) => item == null);
    if (empty < 0) {
      break;
    }
    ordered[empty] = player;
  }

  const wideHeader = slots.map(csvEscape).join(",");
  const wideRow = ordered
    .map((player) => csvEscape(player?.name ?? ""))
    .join(",");

  const detailHeader = [
    "slot",
    "name",
    "player_id",
    "team",
    "position",
    "salary",
    "projection",
    "ownership",
  ].join(",");
  const detailRows = ordered.map((player, index) =>
    [
      csvEscape(slots[index] ?? player?.slot ?? ""),
      csvEscape(player?.name ?? ""),
      csvEscape(player?.player_id ?? ""),
      csvEscape(player?.team ?? ""),
      csvEscape(player?.position ?? ""),
      csvEscape(player?.salary ?? ""),
      csvEscape(player?.projection ?? ""),
      csvEscape(
        player?.projected_ownership != null
          ? Number(player.projected_ownership).toFixed(3)
          : ""
      ),
    ].join(",")
  );

  const csv = [
    wideHeader,
    wideRow,
    "",
    detailHeader,
    ...detailRows,
  ].join("\n");

  const blob = new Blob([csv], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${slateId || "lineup"}-lineup.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function recomputeLineup(
  base: DfsLineup,
  players: DfsLineupPlayer[]
): DfsLineup {
  const salaryUsed = players.reduce(
    (sum, player) => sum + (player.salary || 0),
    0
  );
  const projected = players.reduce(
    (sum, player) => sum + (player.projection || 0),
    0
  );
  const ownership = players.reduce(
    (sum, player) =>
      sum + (player.projected_ownership || 0) * 100,
    0
  );
  return {
    ...base,
    players,
    salary_used: salaryUsed,
    salary_remaining: base.salary_cap - salaryUsed,
    projected_points: Math.round(projected * 10) / 10,
    projected_ownership: Math.round(ownership * 10) / 10,
    roster_filled: players.length,
    valid:
      players.length === base.roster_size
      && salaryUsed <= base.salary_cap,
  };
}

function toLineupPlayer(
  player: DfsPlayer,
  slot: string,
  slate: DfsSlate,
  locked: boolean
): DfsLineupPlayer {
  const multiplier =
    slot === "CPT"
      ? Number(slate.captain_multiplier || 1.5)
      : 1;
  const baseSalary = player.salary || 0;
  const slotProjection = player.projection || 0;
  return {
    ...player,
    slot,
    salary: Math.round(baseSalary * multiplier),
    base_salary: baseSalary,
    projection:
      Math.round(slotProjection * multiplier * 10) / 10,
    // Keep season FPPG base_projection from the slate player;
    // do not overwrite with the (already opponent-adjusted) slot proj.
    floor:
      player.floor == null
        ? player.floor
        : Math.round(player.floor * multiplier * 10) / 10,
    ceiling:
      player.ceiling == null
        ? player.ceiling
        : Math.round(player.ceiling * multiplier * 10) / 10,
    locked,
    is_captain: slot === "CPT",
    captain_multiplier: multiplier !== 1 ? multiplier : null,
  };
}

function playerFitsSlot(
  player: DfsPlayer,
  slot: string,
  slate: DfsSlate
): boolean {
  const key = slot.toUpperCase();
  const position = (player.position || "").toUpperCase();
  const isDefense = position === "DEF" || position === "DST";
  const isShowdown =
    slate.contest_type === "showdown"
    || slate.roster.some((item) => item.slot === "CPT");

  if (isShowdown && (key === "CPT" || key === "FLEX")) {
    return true;
  }
  // Classic FLEX is RB/WR/TE only — no defenses.
  if (key === "FLEX") {
    return ["RB", "WR", "TE"].includes(position);
  }
  if (key === "DST") {
    return isDefense;
  }
  return position === key;
}

function buildSlotRows(
  slots: string[],
  players: DfsLineupPlayer[]
) {
  const remaining = [...players];
  return slots.map((slot, index) => {
    const foundIndex = remaining.findIndex(
      (player) => player.slot === slot
    );
    const player =
      foundIndex >= 0
        ? remaining.splice(foundIndex, 1)[0]
        : null;
    return { slot, index, player };
  });
}

function findOpenSlot(
  lineup: DfsLineup,
  player: DfsPlayer,
  slots: string[],
  slate: DfsSlate
): string | null {
  const usedCounts = new Map<string, number>();
  for (const item of lineup.players) {
    usedCounts.set(
      item.slot,
      (usedCounts.get(item.slot) || 0) + 1
    );
  }
  const slotCapacity = new Map<string, number>();
  for (const slot of slots) {
    slotCapacity.set(
      slot,
      (slotCapacity.get(slot) || 0) + 1
    );
  }

  const isShowdown =
    slate.contest_type === "showdown"
    || slots.includes("CPT");

  // Showdown: CPT first, then FLEX seats.
  if (isShowdown) {
    for (const slot of slots) {
      if (slot !== "CPT" && slot !== "FLEX") {
        continue;
      }
      const capacity = slotCapacity.get(slot) || 0;
      const used = usedCounts.get(slot) || 0;
      if (used < capacity && playerFitsSlot(player, slot, slate)) {
        return slot;
      }
    }
    return null;
  }

  const position = (player.position || "").toUpperCase();
  const prefer =
    position === "DEF" || position === "DST"
      ? ["DST"]
      : position === "RB" || position === "WR" || position === "TE"
        ? [position, "FLEX"]
        : position === "K"
          ? ["K"]
          : [position];

  for (const slot of prefer) {
    const capacity = slotCapacity.get(slot) || 0;
    const used = usedCounts.get(slot) || 0;
    if (used < capacity) {
      return slot;
    }
  }
  return null;
}

function buildClientLineupAnalysis(lineup: DfsLineup): {
  insights: DfsLineupInsight[];
  signals: DfsSignal[];
  edge_summary: string;
} {
  const players = lineup.players ?? [];
  const insights: DfsLineupInsight[] = [];
  const signals: DfsSignal[] = [];

  if (players.length === 0) {
    return {
      insights: [
        {
          id: "empty",
          tone: "warning",
          text: "No lineup players selected yet.",
        },
      ],
      signals: [],
      edge_summary:
        "Add players to the lineup to generate an InsightPilot edge.",
    };
  }

  // Prefer engine-produced correlation explanations when present.
  for (const pair of (lineup.correlation?.positive_pairs ?? []).slice(
    0,
    3
  )) {
    insights.push({
      id: `corr-pos-${pair.player_id}-${pair.correlated_player_id}`,
      tone: "positive",
      text:
        `Positive correlation (${pair.correlation_score >= 0 ? "+" : ""}` +
        `${pair.correlation_score.toFixed(2)}): ` +
        `${pair.player_name} ↔ ${pair.correlated_player_name}. ` +
        `${pair.correlation_reason ?? ""}`.trim(),
    });
  }
  for (const pair of (lineup.correlation?.negative_pairs ?? []).slice(
    0,
    2
  )) {
    insights.push({
      id: `corr-neg-${pair.player_id}-${pair.correlated_player_id}`,
      tone: "warning",
      text:
        `Negative correlation (${pair.correlation_score.toFixed(2)}): ` +
        `${pair.player_name} ↔ ${pair.correlated_player_name}. ` +
        `${pair.correlation_reason ?? ""}`.trim(),
    });
  }

  const teamCounts = new Map<string, number>();
  for (const player of players) {
    const team = (player.team || "").toUpperCase();
    if (!team) {
      continue;
    }
    teamCounts.set(team, (teamCounts.get(team) || 0) + 1);
  }

  const qb = players.find(
    (player) => (player.position || "").toUpperCase() === "QB"
  );
  if (
    qb?.team
    && !(lineup.correlation?.positive_pairs?.length)
  ) {
    const qbTeam = qb.team.toUpperCase();
    const stacked = players.filter(
      (player) =>
        (player.team || "").toUpperCase() === qbTeam
        && ["WR", "TE"].includes(
          (player.position || "").toUpperCase()
        )
    );
    if (stacked.length > 0) {
      const names = stacked
        .slice(0, 2)
        .map((player) => player.name)
        .join(", ");
      insights.push({
        id: "qb_stack",
        tone: "positive",
        text: `Strong QB–pass-catcher correlation (${qb.name} with ${names}).`,
      });
      signals.push({
        id: "strong_game_stack",
        label: "Strong Game Stack",
        body: "QB and pass catcher(s) are correlated within the same projected game script.",
      });
    }
  }

  const favorable = players.filter((player) =>
    ["Very Favorable", "Favorable"].includes(
      player.matchup_label || ""
    )
  );
  if (favorable.length > 0) {
    insights.push({
      id: "matchups",
      tone: "positive",
      text: `${favorable.length} of ${players.length} players have favorable matchup signals.`,
    });
  }

  const lowOwned = players.filter(
    (player) => (player.projected_ownership ?? 1) <= 0.08
  );
  if (lowOwned.length > 0) {
    insights.push({
      id: "leverage",
      tone: "positive",
      text: `${lowOwned.length} lower-owned player${lowOwned.length === 1 ? "" : "s"} provide differentiation.`,
    });
    signals.push({
      id: "leverage_opportunity",
      label: "Leverage Opportunity",
      body: "One or more lineup spots combine solid projected production with below-average ownership.",
    });
  }

  const salaryCap = lineup.salary_cap || 0;
  const salaryUsed = lineup.salary_used || 0;
  if (salaryCap > 0) {
    const utilization = salaryUsed / salaryCap;
    if (utilization >= 0.97) {
      insights.push({
        id: "salary_use",
        tone: "positive",
        text: "Salary utilization is near the cap, preserving projected upside.",
      });
    } else if (utilization < 0.9) {
      insights.push({
        id: "salary_left",
        tone: "warning",
        text: "Meaningful salary remains unused — consider upgrading a flex or stack piece.",
      });
    }
  }

  const captain = players.find((player) => player.is_captain);
  if (captain) {
    insights.push({
      id: "captain",
      tone: "positive",
      text: `${captain.name} is locked in as captain at 1.5× projection and salary.`,
    });
  }

  const concentrated = [...teamCounts.entries()]
    .filter(([, count]) => count >= 3)
    .map(([team]) => team);
  if (concentrated.length > 0) {
    insights.push({
      id: "team_concentration",
      tone: "neutral",
      text: `Concentrated exposure to ${concentrated.join(", ")}.`,
    });
    signals.push({
      id: "concentrated_opportunity",
      label: "Concentrated Opportunity",
      body: "Multiple lineup players benefit from the same team environment.",
    });
  }

  if (insights.length === 0) {
    insights.push({
      id: "baseline",
      tone: "neutral",
      text: "Lineup constructed from InsightPilot projection, value, and contest strategy.",
    });
  }

  const parts: string[] = [];
  if (lineup.contest_type === "showdown") {
    parts.push("showdown captain leverage");
  }
  if (lineup.projected_points != null) {
    parts.push(
      `${lineup.projected_points.toFixed(1)} projected points`
    );
  }
  if (lineup.value != null && lineup.value >= 2.6) {
    parts.push("strong salary efficiency");
  }
  if (
    lineup.projected_ownership != null
    && lineup.projected_ownership < 110
  ) {
    parts.push("differentiated ownership");
  } else if (
    lineup.projected_ownership != null
    && lineup.projected_ownership > 140
  ) {
    parts.push("chalk-heavy construction");
  }

  let edge_summary: string;
  if (parts.length === 0) {
    edge_summary =
      "InsightPilot built this readout from projection, value, and contest strategy signals.";
  } else if (parts.length === 1) {
    edge_summary = `This lineup combines ${parts[0]}.`;
  } else {
    edge_summary = `This lineup combines ${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}.`;
  }

  return { insights, signals, edge_summary };
}

function formatFreshness(slate: DfsSlate | null): string | null {
  if (!slate?.freshness?.projections_updated_at) {
    return null;
  }
  const stamp = new Date(
    slate.freshness.projections_updated_at
  );
  if (Number.isNaN(stamp.getTime())) {
    return slate.freshness.note || null;
  }
  return `Projections updated ${stamp.toLocaleTimeString()} · ${slate.freshness.note || "synthetic slate"}`;
}
