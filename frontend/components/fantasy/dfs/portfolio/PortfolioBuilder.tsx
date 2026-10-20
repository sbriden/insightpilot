"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import LineupCard from "@/components/fantasy/dfs/LineupCard";
import PortfolioCorrelation from "@/components/fantasy/dfs/portfolio/PortfolioCorrelation";
import PortfolioHealth from "@/components/fantasy/dfs/portfolio/PortfolioHealth";
import PortfolioInsights from "@/components/fantasy/dfs/portfolio/PortfolioInsights";
import PortfolioLineupTable from "@/components/fantasy/dfs/portfolio/PortfolioLineupTable";
import PortfolioScriptMix from "@/components/fantasy/dfs/portfolio/PortfolioScriptMix";
import PortfolioSetup from "@/components/fantasy/dfs/portfolio/PortfolioSetup";
import PortfolioSummary from "@/components/fantasy/dfs/portfolio/PortfolioSummary";
import PlayerExposureTable from "@/components/fantasy/dfs/portfolio/PlayerExposureTable";
import PlayerSnapshotModal from "@/components/fantasy/snapshot/PlayerSnapshotModal";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import {
  DfsContestType,
  DfsPortfolioLineup,
  DfsPortfolioResult,
  DfsPortfolioStrategy,
  DfsRisk,
  DfsSiteId,
  DfsSlate,
  FantasyPlayerSnapshot,
  generateDfsPortfolio,
  getFantasyPlayerSnapshot,
} from "@/services/api";

interface Props {
  slate: DfsSlate;
  site: DfsSiteId;
  contestType: DfsContestType;
  risk: DfsRisk;
  seedLockedIds: Set<string>;
  seedExcludedIds: Set<string>;
}

type StoredPortfolio = {
  constraints: {
    lineupCount: number;
    strategy: DfsPortfolioStrategy;
    maxSimilarity: number;
    minUniquePlayers?: number;
    defaultMaxExposure: number;
    defaultMaxCaptainExposure?: number;
    minMap: Record<string, number>;
    maxMap: Record<string, number>;
    captainMaxMap?: Record<string, number>;
    lockedIds: string[];
    excludedIds: string[];
  };
  result: DfsPortfolioResult;
  savedAt: string;
};

function storageKey(
  slateId: string,
  site: string,
  contest: string
) {
  return `ip-dfs-portfolio:${slateId}:${site}:${contest}`;
}

function lineupFingerprint(lineup: DfsPortfolioLineup): string {
  const ids = (
    lineup.player_ids ??
    lineup.players.map((player) => player.player_id)
  )
    .map((id) => String(id))
    .filter(Boolean)
    .sort();
  return ids.join("|");
}

type PortfolioDetailTab =
  | "included"
  | "excluded"
  | "constrained"
  | "insights"
  | "correlation";

const PORTFOLIO_DETAIL_TABS: Array<{
  id: PortfolioDetailTab;
  label: string;
}> = [
  { id: "included", label: "Included" },
  { id: "excluded", label: "Excluded" },
  { id: "constrained", label: "Constrained" },
  { id: "insights", label: "Insights" },
  { id: "correlation", label: "Correlation Exposure" },
];

type PortfolioDefaults = {
  maxSimilarity: number;
  minUniquePlayers: number;
  defaultMaxExposure: number;
  defaultMaxCaptainExposure: number;
};

const STRATEGY_DEFAULTS: Record<
  DfsPortfolioStrategy,
  PortfolioDefaults
> = {
  max_projection: {
    maxSimilarity: 0.92,
    minUniquePlayers: 1,
    defaultMaxExposure: 0.85,
    defaultMaxCaptainExposure: 0.6,
  },
  balanced: {
    maxSimilarity: 0.8,
    minUniquePlayers: 2,
    defaultMaxExposure: 0.7,
    defaultMaxCaptainExposure: 0.45,
  },
  tournament: {
    maxSimilarity: 0.7,
    minUniquePlayers: 2,
    defaultMaxExposure: 0.55,
    defaultMaxCaptainExposure: 0.35,
  },
  contrarian: {
    maxSimilarity: 0.65,
    minUniquePlayers: 3,
    defaultMaxExposure: 0.45,
    defaultMaxCaptainExposure: 0.3,
  },
  // Back-compat aliases for saved local portfolios.
  cash: {
    maxSimilarity: 0.92,
    minUniquePlayers: 1,
    defaultMaxExposure: 0.85,
    defaultMaxCaptainExposure: 0.6,
  },
  gpp: {
    maxSimilarity: 0.7,
    minUniquePlayers: 2,
    defaultMaxExposure: 0.55,
    defaultMaxCaptainExposure: 0.35,
  },
  custom: {
    maxSimilarity: 0.8,
    minUniquePlayers: 2,
    defaultMaxExposure: 0.7,
    defaultMaxCaptainExposure: 0.45,
  },
};

const SHOWDOWN_MAX_EXPOSURE: Record<DfsPortfolioStrategy, number> = {
  max_projection: 0.6,
  balanced: 0.45,
  tournament: 0.35,
  contrarian: 0.3,
  cash: 0.6,
  gpp: 0.35,
  custom: 0.45,
};

function portfolioDefaults(
  strategy: DfsPortfolioStrategy,
  showdown: boolean
): PortfolioDefaults {
  const base = STRATEGY_DEFAULTS[strategy];
  if (!showdown) {
    return base;
  }
  return {
    maxSimilarity: Math.min(base.maxSimilarity, 0.75),
    minUniquePlayers: Math.min(4, base.minUniquePlayers + 1),
    defaultMaxExposure: SHOWDOWN_MAX_EXPOSURE[strategy],
    defaultMaxCaptainExposure: Math.min(
      base.defaultMaxCaptainExposure,
      0.35
    ),
  };
}

export default function PortfolioBuilder({
  slate,
  site,
  contestType,
  risk,
  seedLockedIds,
  seedExcludedIds,
}: Props) {
  const isShowdown = contestType === "showdown";
  const opening = portfolioDefaults("balanced", isShowdown);
  const [lineupCount, setLineupCount] = useState(20);
  const [strategy, setStrategy] =
    useState<DfsPortfolioStrategy>("balanced");
  const [maxSimilarity, setMaxSimilarity] = useState(
    opening.maxSimilarity
  );
  const [minUniquePlayers, setMinUniquePlayers] = useState(
    opening.minUniquePlayers
  );
  const [defaultMaxExposure, setDefaultMaxExposure] = useState(
    opening.defaultMaxExposure
  );
  const [defaultMaxCaptainExposure, setDefaultMaxCaptainExposure] =
    useState(opening.defaultMaxCaptainExposure);
  const [minMap, setMinMap] = useState<Record<string, number>>(
    {}
  );
  const [maxMap, setMaxMap] = useState<Record<string, number>>(
    {}
  );
  const [captainMaxMap, setCaptainMaxMap] = useState<
    Record<string, number>
  >({});
  const [lockedIds, setLockedIds] = useState<Set<string>>(
    () => new Set(seedLockedIds)
  );
  const [excludedIds, setExcludedIds] = useState<Set<string>>(
    () => new Set(seedExcludedIds)
  );
  const [result, setResult] = useState<DfsPortfolioResult | null>(
    null
  );
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [positionFilter, setPositionFilter] = useState("All");
  const [detailTab, setDetailTab] =
    useState<PortfolioDetailTab>("included");
  const [selectedLineupId, setSelectedLineupId] = useState<
    string | null
  >(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [changedLineupIds, setChangedLineupIds] = useState<
    Set<string>
  >(() => new Set());
  const [hydrated, setHydrated] = useState(false);
  const [overviewOpen, setOverviewOpen] = useState(false);
  const [overviewSnapshot, setOverviewSnapshot] =
    useState<FantasyPlayerSnapshot | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);
  const [overviewError, setOverviewError] = useState<
    string | null
  >(null);
  const [optimalPanelHeight, setOptimalPanelHeight] = useState<
    number | null
  >(null);
  const optimalPanelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setHydrated(false);
    try {
      const raw = localStorage.getItem(
        storageKey(slate.slate_id, site, contestType)
      );
      if (!raw) {
        const defaults = portfolioDefaults(
          "balanced",
          contestType === "showdown"
        );
        setLineupCount(20);
        setStrategy("balanced");
        setMaxSimilarity(defaults.maxSimilarity);
        setMinUniquePlayers(defaults.minUniquePlayers);
        setDefaultMaxExposure(defaults.defaultMaxExposure);
        setDefaultMaxCaptainExposure(
          defaults.defaultMaxCaptainExposure
        );
        setMinMap({});
        setMaxMap({});
        setCaptainMaxMap({});
        setResult(null);
        setChangedLineupIds(new Set());
        setSelectedLineupId(null);
        setSavedAt(null);
        setHydrated(true);
        return;
      }
      const parsed = JSON.parse(raw) as StoredPortfolio;
      if (parsed?.constraints) {
        setLineupCount(parsed.constraints.lineupCount || 20);
        setStrategy(parsed.constraints.strategy || "balanced");
        setMaxSimilarity(
          parsed.constraints.maxSimilarity ?? 0.8
        );
        setMinUniquePlayers(
          parsed.constraints.minUniquePlayers ??
            STRATEGY_DEFAULTS[
              parsed.constraints.strategy || "balanced"
            ]?.minUniquePlayers ??
            2
        );
        setDefaultMaxExposure(
          parsed.constraints.defaultMaxExposure ?? 0.7
        );
        setDefaultMaxCaptainExposure(
          parsed.constraints.defaultMaxCaptainExposure ?? 0.45
        );
        setMinMap(parsed.constraints.minMap || {});
        setMaxMap(parsed.constraints.maxMap || {});
        setCaptainMaxMap(parsed.constraints.captainMaxMap || {});
        setLockedIds(
          new Set(parsed.constraints.lockedIds || [])
        );
        setExcludedIds(
          new Set(parsed.constraints.excludedIds || [])
        );
      }
      if (parsed?.result) {
        setResult(parsed.result);
        setSavedAt(parsed.savedAt || null);
        setChangedLineupIds(new Set());
        const first = parsed.result.lineups?.[0]?.lineup_id;
        if (first) {
          setSelectedLineupId(first);
        }
      }
    } catch {
      // Ignore corrupt local saves.
    } finally {
      setHydrated(true);
    }
  }, [slate.slate_id, site, contestType]);

  useEffect(() => {
    const node = optimalPanelRef.current;
    if (!node || typeof ResizeObserver === "undefined") {
      setOptimalPanelHeight(null);
      return;
    }
    const update = () => {
      const height = Math.round(node.getBoundingClientRect().height);
      setOptimalPanelHeight(height > 0 ? height : null);
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(node);
    return () => observer.disconnect();
  }, [selectedLineupId, result?.lineups.length]);

  const selectedLineup = useMemo(() => {
    if (!result || !selectedLineupId) {
      return null;
    }
    return (
      result.lineups.find(
        (item) => item.lineup_id === selectedLineupId
      ) ?? null
    );
  }, [result, selectedLineupId]);

  const teamByPlayerId = useMemo(() => {
    const map = new Map<string, string>();
    for (const player of slate.players ?? []) {
      if (player.player_id && player.team) {
        map.set(player.player_id, player.team);
      }
    }
    for (const row of result?.exposure.players ?? []) {
      if (row.player_id && row.team) {
        map.set(row.player_id, row.team);
      }
    }
    return map;
  }, [slate.players, result?.exposure.players]);

  const insightCore = useMemo(
    () =>
      (result?.core ?? []).map((item) => ({
        ...item,
        team:
          item.team ??
          teamByPlayerId.get(item.player_id) ??
          null,
      })),
    [result?.core, teamByPlayerId]
  );

  const insightDifferentiators = useMemo(
    () =>
      (result?.differentiators ?? []).map((item) => ({
        ...item,
        team:
          item.team ??
          teamByPlayerId.get(item.player_id) ??
          null,
      })),
    [result?.differentiators, teamByPlayerId]
  );

  const slots =
    slate.roster.map((item) => item.slot) ??
    (contestType === "showdown"
      ? ["CPT", "FLEX", "FLEX", "FLEX", "FLEX", "FLEX"]
      : [
          "QB",
          "RB",
          "RB",
          "WR",
          "WR",
          "WR",
          "TE",
          "FLEX",
          "DST",
        ]);

  function applyStrategy(next: DfsPortfolioStrategy) {
    setStrategy(next);
    const defaults = portfolioDefaults(next, isShowdown);
    setMaxSimilarity(defaults.maxSimilarity);
    setMinUniquePlayers(defaults.minUniquePlayers);
    setDefaultMaxExposure(defaults.defaultMaxExposure);
    setDefaultMaxCaptainExposure(defaults.defaultMaxCaptainExposure);
  }

  function persistPortfolio(nextResult: DfsPortfolioResult) {
    const stamp = new Date().toISOString();
    const payload: StoredPortfolio = {
      constraints: {
        lineupCount,
        strategy,
        maxSimilarity,
        minUniquePlayers,
        defaultMaxExposure,
        defaultMaxCaptainExposure,
        minMap,
        maxMap,
        captainMaxMap,
        lockedIds: Array.from(lockedIds),
        excludedIds: Array.from(excludedIds),
      },
      result: nextResult,
      savedAt: stamp,
    };
    localStorage.setItem(
      storageKey(slate.slate_id, site, contestType),
      JSON.stringify(payload)
    );
    setSavedAt(stamp);
  }

  async function runGenerate() {
    setGenerating(true);
    setError(null);
    const previousFingerprints = (result?.lineups ?? []).map(
      lineupFingerprint
    );
    try {
      const payload = await generateDfsPortfolio({
        slate_id: slate.slate_id,
        site,
        contest_type: contestType,
        lineup_count: lineupCount,
        strategy,
        risk,
        max_lineup_similarity: maxSimilarity,
        min_unique_players: minUniquePlayers,
        default_max_exposure: defaultMaxExposure,
        default_max_captain_exposure: isShowdown
          ? defaultMaxCaptainExposure
          : undefined,
        season: slate.season,
        player_exposure: {
          min: minMap,
          max: maxMap,
          ...(isShowdown
            ? { captain_max: captainMaxMap }
            : {}),
          lock: Array.from(lockedIds),
          exclude: Array.from(excludedIds),
        },
        locked_players: Array.from(lockedIds),
        excluded_players: Array.from(excludedIds),
      });
      const changed = new Set<string>();
      if (previousFingerprints.length > 0) {
        payload.lineups.forEach((lineup, index) => {
          if (
            previousFingerprints[index] !==
            lineupFingerprint(lineup)
          ) {
            changed.add(lineup.lineup_id);
          }
        });
      }
      setChangedLineupIds(changed);
      setResult(payload);
      persistPortfolio(payload);
      setSelectedLineupId(
        payload.lineups[0]?.lineup_id ?? null
      );
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Unable to generate portfolio."
      );
    } finally {
      setGenerating(false);
    }
  }

  function savePortfolio() {
    if (!result) {
      return;
    }
    persistPortfolio(result);
  }

  function exportPortfolio() {
    if (!result) {
      return;
    }
    const blob = new Blob(
      [JSON.stringify(result, null, 2)],
      { type: "application/json" }
    );
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${slate.slate_id}-portfolio.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function resetPortfolio() {
    setResult(null);
    setSelectedLineupId(null);
    setMinMap({});
    setMaxMap({});
    setCaptainMaxMap({});
    setLockedIds(new Set());
    setExcludedIds(new Set());
    setSavedAt(null);
    setChangedLineupIds(new Set());
    localStorage.removeItem(
      storageKey(slate.slate_id, site, contestType)
    );
  }

  async function openPlayerOverview(playerId: string) {
    setOverviewOpen(true);
    setOverviewLoading(true);
    setOverviewError(null);
    setOverviewSnapshot(null);
    try {
      const response = await getFantasyPlayerSnapshot(
        playerId,
        slate.season ?? null
      );
      setOverviewSnapshot(response.snapshot);
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

  if (!hydrated) {
    return (
      <div
        className="rounded-[10px] border px-4 py-8 text-center text-sm"
        style={{
          borderColor: snapshotTokens.border,
          color: snapshotTokens.textSecondary,
        }}
      >
        Loading saved portfolio…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            className="text-xl font-semibold tracking-tight"
            style={{ color: snapshotTokens.navy }}
          >
            Portfolio Builder
          </h2>
          <p
            className="mt-1 max-w-2xl text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Build and diversify a portfolio of lineups using
            player exposure, correlation, ownership, and lineup
            construction controls.
          </p>
          {savedAt && (
            <p
              className="mt-1 text-xs"
              style={{ color: snapshotTokens.textMuted }}
            >
              Saved locally {new Date(savedAt).toLocaleString()}
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => void runGenerate()}
            disabled={generating}
            className="rounded-lg px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
            style={{ background: snapshotTokens.blue }}
          >
            {generating
              ? "Generating…"
              : result
                ? "Regenerate Portfolio"
                : "Generate Portfolio"}
          </button>
          <button
            type="button"
            onClick={savePortfolio}
            disabled={!result}
            className="rounded-lg border px-3 py-2 text-sm font-semibold disabled:opacity-40"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textPrimary,
            }}
          >
            Save Portfolio
          </button>
          <button
            type="button"
            onClick={exportPortfolio}
            disabled={!result}
            className="rounded-lg border px-3 py-2 text-sm font-semibold disabled:opacity-40"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textPrimary,
            }}
          >
            Export
          </button>
          <button
            type="button"
            onClick={resetPortfolio}
            className="rounded-lg border px-3 py-2 text-sm font-semibold"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textSecondary,
            }}
          >
            Reset
          </button>
        </div>
      </div>

      <PortfolioSetup
        lineupCount={lineupCount}
        strategy={strategy}
        maxSimilarity={maxSimilarity}
        minUniquePlayers={minUniquePlayers}
        defaultMaxExposure={defaultMaxExposure}
        defaultMaxCaptainExposure={defaultMaxCaptainExposure}
        showCaptainLimits={isShowdown}
        onLineupCount={setLineupCount}
        onStrategy={applyStrategy}
        onMaxSimilarity={setMaxSimilarity}
        onMinUniquePlayers={setMinUniquePlayers}
        onDefaultMaxExposure={setDefaultMaxExposure}
        onDefaultMaxCaptainExposure={setDefaultMaxCaptainExposure}
      />

      {error && (
        <p
          className="text-sm"
          style={{ color: snapshotTokens.negative }}
        >
          {error}
        </p>
      )}

      <PortfolioSummary portfolio={result?.portfolio ?? null} />

      <PortfolioScriptMix
        gameScripts={
          result?.game_scripts
          ?? result?.portfolio?.game_scripts
          ?? null
        }
      />

      {result && (
        <PortfolioHealth
          signals={result.signals}
          alerts={result.alerts}
          onViewExposure={() => {
            setDetailTab("included");
            document
              .getElementById("portfolio-exposure")
              ?.scrollIntoView({ behavior: "smooth" });
          }}
        />
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(18rem,0.8fr)]">
        <PortfolioLineupTable
          lineups={result?.lineups ?? []}
          selectedId={selectedLineupId}
          changedIds={changedLineupIds}
          onSelect={setSelectedLineupId}
          maxHeight={
            selectedLineup ? optimalPanelHeight : undefined
          }
        />

        {selectedLineup && (
          <div
            ref={optimalPanelRef}
            className="lg:sticky lg:top-3 lg:self-start"
          >
            <LineupCard
              lineup={selectedLineup}
              slots={slots}
              lockedIds={lockedIds}
              activeSlotIndex={null}
              onSelectSlot={() => undefined}
              onSelectPlayer={(playerId) => {
                void openPlayerOverview(playerId);
              }}
              onPlacePlayer={() => undefined}
              onRemove={() => undefined}
              onLockToggle={() => undefined}
            />
            <p
              className="mt-2 text-xs"
              style={{ color: snapshotTokens.textMuted }}
            >
              Lineup{" "}
              {selectedLineup.portfolio_index ??
                (result?.lineups.findIndex(
                  (item) =>
                    item.lineup_id === selectedLineup.lineup_id
                ) ?? -1) + 1}{" "}
              of {result?.lineups.length ?? 0}
              {changedLineupIds.has(selectedLineup.lineup_id)
                ? " · changed on last regenerate"
                : ""}
            </p>
          </div>
        )}
      </div>

      <section
        id="portfolio-exposure"
        className="rounded-[10px] border p-4"
        style={{ borderColor: snapshotTokens.border }}
      >
        <div
          className="flex flex-wrap gap-1 border-b pb-2"
          style={{ borderColor: snapshotTokens.border }}
          role="tablist"
          aria-label="Portfolio player analysis"
        >
          {PORTFOLIO_DETAIL_TABS.map((tab) => {
            const active = detailTab === tab.id;
            const excludedCount =
              tab.id === "excluded" ? excludedIds.size : 0;
            return (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setDetailTab(tab.id)}
                className="rounded-md px-3 py-1.5 text-sm font-semibold"
                style={{
                  background: active
                    ? snapshotTokens.blueLight
                    : "transparent",
                  color: active
                    ? snapshotTokens.blue
                    : snapshotTokens.textSecondary,
                }}
              >
                {tab.label}
                {excludedCount > 0 ? ` (${excludedCount})` : ""}
              </button>
            );
          })}
        </div>

        <div className="mt-4" role="tabpanel">
          {(detailTab === "included" ||
            detailTab === "excluded") && (
            <PlayerExposureTable
              rows={result?.exposure.players ?? []}
              slatePlayers={slate.players ?? []}
              positionFilter={positionFilter}
              minMap={minMap}
              maxMap={maxMap}
              captainMaxMap={captainMaxMap}
              lockedIds={lockedIds}
              excludedIds={excludedIds}
              showCaptainLimits={isShowdown}
              variant={detailTab}
              onPositionFilter={setPositionFilter}
              onSelectPlayer={(playerId) => {
                void openPlayerOverview(playerId);
              }}
              onMin={(playerId, value) => {
                setMinMap((current) => {
                  const next = { ...current };
                  if (value == null) {
                    delete next[playerId];
                  } else {
                    next[playerId] = value;
                  }
                  return next;
                });
                if (value != null && value > 0) {
                  setExcludedIds((current) => {
                    if (!current.has(playerId)) {
                      return current;
                    }
                    const cleaned = new Set(current);
                    cleaned.delete(playerId);
                    return cleaned;
                  });
                }
              }}
              onMax={(playerId, value) => {
                setMaxMap((current) => {
                  const next = { ...current };
                  if (value == null) {
                    delete next[playerId];
                  } else {
                    next[playerId] = value;
                  }
                  return next;
                });
              }}
              onCaptainMax={(playerId, value) => {
                setCaptainMaxMap((current) => {
                  const next = { ...current };
                  if (value == null) {
                    delete next[playerId];
                  } else {
                    next[playerId] = value;
                  }
                  return next;
                });
              }}
              onLock={(playerId) => {
                setLockedIds((current) => {
                  const next = new Set(current);
                  if (next.has(playerId)) {
                    next.delete(playerId);
                  } else {
                    next.add(playerId);
                    setExcludedIds((excluded) => {
                      const cleaned = new Set(excluded);
                      cleaned.delete(playerId);
                      return cleaned;
                    });
                  }
                  return next;
                });
              }}
              onExclude={(playerId) => {
                setExcludedIds((current) => {
                  const next = new Set(current);
                  next.add(playerId);
                  return next;
                });
                setLockedIds((locked) => {
                  if (!locked.has(playerId)) {
                    return locked;
                  }
                  const cleaned = new Set(locked);
                  cleaned.delete(playerId);
                  return cleaned;
                });
                setMinMap((current) => {
                  if (!(playerId in current)) {
                    return current;
                  }
                  const next = { ...current };
                  delete next[playerId];
                  return next;
                });
              }}
              onInclude={(playerId) => {
                setExcludedIds((current) => {
                  if (!current.has(playerId)) {
                    return current;
                  }
                  const next = new Set(current);
                  next.delete(playerId);
                  return next;
                });
              }}
              onForceInclude={(playerId, minExposure) => {
                const floor = Math.max(
                  0.01,
                  Math.min(1, minExposure)
                );
                setExcludedIds((current) => {
                  if (!current.has(playerId)) {
                    return current;
                  }
                  const next = new Set(current);
                  next.delete(playerId);
                  return next;
                });
                setMinMap((current) => ({
                  ...current,
                  [playerId]: floor,
                }));
                setMaxMap((current) => {
                  const existing = current[playerId];
                  if (existing != null && existing >= floor) {
                    return current;
                  }
                  return {
                    ...current,
                    [playerId]: Math.max(
                      floor,
                      defaultMaxExposure
                    ),
                  };
                });
              }}
            />
          )}

          {detailTab === "constrained" && (
            <ConstrainedPlayersPanel
              diagnostics={result?.player_diagnostics}
              metadata={result?.optimization_metadata}
            />
          )}

          {detailTab === "insights" && (
            <PortfolioInsights
              signals={result?.signals ?? []}
              core={insightCore}
              differentiators={insightDifferentiators}
              similarPairs={result?.similarity.most_similar_pairs}
              embedded
            />
          )}

          {detailTab === "correlation" && (
            <PortfolioCorrelation
              correlation={result?.correlation}
              embedded
            />
          )}
        </div>
      </section>

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
    </div>
  );
}

function ConstrainedPlayersPanel({
  diagnostics,
  metadata,
}: {
  diagnostics?: DfsPortfolioResult["player_diagnostics"];
  metadata?: DfsPortfolioResult["optimization_metadata"];
}) {
  const rows = [...(diagnostics ?? [])]
    .filter(
      (row) =>
        row.remaining_capacity > 0 ||
        (row.reasons?.length ?? 0) > 0
    )
    .sort((a, b) => {
      const aGap =
        Math.max(0, a.max_exposure) - Math.max(0, a.exposure);
      const bGap =
        Math.max(0, b.max_exposure) - Math.max(0, b.exposure);
      if (bGap !== aGap) {
        return bGap - aGap;
      }
      return (
        Number(b.projection ?? 0) - Number(a.projection ?? 0)
      );
    })
    .slice(0, 16);

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p
          className="text-xs"
          style={{ color: snapshotTokens.textSecondary }}
        >
          Players below their exposure caps — muted segment is
          unused room to max.
        </p>
        <div
          className="flex items-center gap-3 text-[11px]"
          style={{ color: snapshotTokens.textMuted }}
        >
          <span className="inline-flex items-center gap-1">
            <span
              className="inline-block h-1.5 w-1.5 rounded-sm"
              style={{ background: snapshotTokens.blue, opacity: 0.55 }}
            />
            Exposure
          </span>
          <span className="inline-flex items-center gap-1">
            <span
              className="inline-block h-1.5 w-1.5 rounded-sm"
              style={{ background: snapshotTokens.border }}
            />
            Gap to max
          </span>
        </div>
      </div>
      {rows.length === 0 ? (
        <p
          className="mt-3 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          Generate a portfolio to see constrained-player diagnostics.
        </p>
      ) : (
        <div className="mt-3 space-y-2">
          {rows.map((row) => {
            const maxPct = Math.max(
              0,
              Math.min(100, Math.round(row.max_exposure * 100))
            );
            const exposurePct = Math.max(
              0,
              Math.min(
                100,
                Math.round(
                  row.exposure_pct ?? row.exposure * 100
                )
              )
            );
            const usedPct = Math.min(exposurePct, maxPct);
            const gapPct = Math.max(0, maxPct - usedPct);
            return (
              <div
                key={row.player_id}
                className="rounded-md border px-3 py-2"
                style={{ borderColor: snapshotTokens.border }}
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p
                    className="text-sm font-semibold"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {row.name || row.player_id}
                    {row.position ? ` · ${row.position}` : ""}
                  </p>
                  <p
                    className="text-xs tabular-nums"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    Proj {Number(row.projection ?? 0).toFixed(1)} ·{" "}
                    {exposurePct}% / {maxPct}%
                    {gapPct > 0 ? ` · −${gapPct} pts` : ""}
                  </p>
                </div>
                <div
                  className="relative mt-1.5 h-1 w-full overflow-hidden rounded-full"
                  style={{ background: snapshotTokens.divider }}
                  title={`${exposurePct}% of ${maxPct}% max`}
                >
                  <div
                    className="absolute inset-y-0 left-0 rounded-full"
                    style={{
                      width: `${usedPct}%`,
                      background: snapshotTokens.blue,
                      opacity: 0.45,
                    }}
                  />
                  {gapPct > 0 && (
                    <div
                      className="absolute inset-y-0"
                      style={{
                        left: `${usedPct}%`,
                        width: `${gapPct}%`,
                        background: snapshotTokens.border,
                      }}
                    />
                  )}
                </div>
                <p
                  className="mt-1.5 text-xs"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {row.why_not_more}
                </p>
              </div>
            );
          })}
        </div>
      )}
      {metadata ? (
        <p
          className="mt-3 text-[11px]"
          style={{ color: snapshotTokens.textMuted }}
        >
          Audit:{" "}
          {String(
            metadata.candidate_lineups_generated ??
              metadata.candidates_generated ??
              "—"
          )}{" "}
          candidates →{" "}
          {String(
            metadata.candidate_lineups_selected ??
              metadata.lineups_selected ??
              "—"
          )}{" "}
          selected
          {metadata.rejected
            ? ` · Rejected: ${JSON.stringify(metadata.rejected)}`
            : ""}
        </p>
      ) : null}
    </div>
  );
}
