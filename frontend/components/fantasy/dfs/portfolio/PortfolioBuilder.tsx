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

const STRATEGY_DEFAULTS: Record<
  DfsPortfolioStrategy,
  {
    maxSimilarity: number;
    minUniquePlayers: number;
    defaultMaxExposure: number;
    defaultMaxCaptainExposure: number;
  }
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

export default function PortfolioBuilder({
  slate,
  site,
  contestType,
  risk,
  seedLockedIds,
  seedExcludedIds,
}: Props) {
  const isShowdown = contestType === "showdown";
  const [lineupCount, setLineupCount] = useState(20);
  const [strategy, setStrategy] =
    useState<DfsPortfolioStrategy>("balanced");
  const [maxSimilarity, setMaxSimilarity] = useState(0.8);
  const [minUniquePlayers, setMinUniquePlayers] = useState(2);
  const [defaultMaxExposure, setDefaultMaxExposure] =
    useState(0.7);
  const [defaultMaxCaptainExposure, setDefaultMaxCaptainExposure] =
    useState(0.45);
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
    const defaults = STRATEGY_DEFAULTS[next];
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
          const floor = Math.max(0.01, Math.min(1, minExposure));
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
              [playerId]: Math.max(floor, defaultMaxExposure),
            };
          });
        }}
      />

      {result?.player_diagnostics &&
      result.player_diagnostics.length > 0 ? (
        <section
          className="rounded-[10px] border p-4"
          style={{ borderColor: snapshotTokens.border }}
        >
          <h3
            className="text-sm font-semibold"
            style={{ color: snapshotTokens.navy }}
          >
            Why isn’t this player appearing?
          </h3>
          <p
            className="mt-1 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Top projected players and constrained players with
            exposure below their configured caps.
          </p>
          <div className="mt-3 space-y-2">
            {result.player_diagnostics
              .filter(
                (row) =>
                  row.remaining_capacity > 0 ||
                  (row.reasons?.length ?? 0) > 0
              )
              .slice(0, 8)
              .map((row) => (
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
                      Proj {Number(row.projection ?? 0).toFixed(1)} ·
                      Exposure {row.exposure_pct.toFixed(0)}% /{" "}
                      {Math.round(row.max_exposure * 100)}%
                    </p>
                  </div>
                  <p
                    className="mt-1 text-xs"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    {row.why_not_more}
                  </p>
                </div>
              ))}
          </div>
          {result.optimization_metadata ? (
            <p
              className="mt-3 text-[11px]"
              style={{ color: snapshotTokens.textMuted }}
            >
              Audit:{" "}
              {String(
                result.optimization_metadata
                  .candidate_lineups_generated ??
                  result.optimization_metadata.candidates_generated ??
                  "—"
              )}{" "}
              candidates →{" "}
              {String(
                result.optimization_metadata
                  .candidate_lineups_selected ??
                  result.optimization_metadata.lineups_selected ??
                  "—"
              )}{" "}
              selected
              {result.optimization_metadata.rejected
                ? ` · Rejected: ${JSON.stringify(
                    result.optimization_metadata.rejected
                  )}`
                : ""}
            </p>
          ) : null}
        </section>
      ) : null}

      <PortfolioInsights
        signals={result?.signals ?? []}
        core={result?.core}
        differentiators={result?.differentiators}
        similarPairs={result?.similarity.most_similar_pairs}
      />

      <PortfolioCorrelation correlation={result?.correlation} />

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
