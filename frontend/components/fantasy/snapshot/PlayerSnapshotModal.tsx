"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";

import {
  FantasyPlayerSnapshot,
  FantasyReplacementPlayer,
  getFantasyPlayerSnapshot,
} from "@/services/api";

import FreeAgentReplacements from "./FreeAgentReplacements";
import GameLog from "./GameLog";
import KeyTakeaways from "./KeyTakeaways";
import PerformanceSummary from "./PerformanceSummary";
import PlayerComparison from "./PlayerComparison";
import PlayerHeader from "./PlayerHeader";
import PlayerMatchupsTab from "./PlayerMatchupsTab";
import PlayerNewsTab from "./PlayerNewsTab";
import PlayerProfile from "./PlayerProfile";
import PlayerStatsTab from "./PlayerStatsTab";
import PlayerTabs, {
  SnapshotTabId,
} from "./PlayerTabs";
import PlayerUsageTab from "./PlayerUsageTab";
import PositionDepthChart from "./PositionDepthChart";
import PositionRankCard from "./PositionRankCard";
import RecommendationCard from "./RecommendationCard";
import TrendChart from "./TrendChart";
import { snapshotTokens } from "./tokens";

interface Props {
  active: FantasyPlayerSnapshot | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onSelectPlayer?: (playerId: string) => void;
  initialTab?: SnapshotTabId;
}

export default function PlayerSnapshotModal({
  active,
  loading,
  error,
  onClose,
  onSelectPlayer,
  initialTab = "snapshot",
}: Props) {
  const [tab, setTab] =
    useState<SnapshotTabId>(initialTab);
  const [compareId, setCompareId] = useState<
    string | null
  >(null);
  const [compareOwnership, setCompareOwnership] =
    useState<number | null>(null);
  const [compareSnapshot, setCompareSnapshot] =
    useState<FantasyPlayerSnapshot | null>(null);
  const [compareLoading, setCompareLoading] =
    useState(false);
  const [compareError, setCompareError] = useState<
    string | null
  >(null);

  const recentGames =
    active?.performance?.recent_games ?? [];
  const comparing = Boolean(compareId);

  useEffect(() => {
    // Reset comparison when the primary player changes.
    setCompareId(null);
    setCompareOwnership(null);
    setCompareSnapshot(null);
    setCompareError(null);
    setTab(initialTab);
  }, [active?.player_id, initialTab]);

  useEffect(() => {
    if (!compareId) {
      setCompareSnapshot(null);
      setCompareError(null);
      setCompareLoading(false);
      return;
    }

    let cancelled = false;

    void (async () => {
      try {
        setCompareLoading(true);
        setCompareError(null);
        const result =
          await getFantasyPlayerSnapshot(compareId);
        if (cancelled) {
          return;
        }
        setCompareSnapshot(result.snapshot);
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        setCompareSnapshot(null);
        setCompareError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load comparison player."
        );
      } finally {
        if (!cancelled) {
          setCompareLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [compareId]);

  function startCompare(
    player: FantasyReplacementPlayer
  ) {
    setCompareId(player.player_id);
    setCompareOwnership(
      player.ownership ?? null
    );
  }

  function clearCompare() {
    setCompareId(null);
    setCompareOwnership(null);
    setCompareSnapshot(null);
    setCompareError(null);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4"
      style={{ background: "rgba(11, 31, 58, 0.45)" }}
      onClick={onClose}
    >
      <div
        className="flex max-h-[100vh] w-full max-w-[1100px] flex-col overflow-hidden rounded-t-2xl bg-white shadow-xl sm:max-h-[92vh] sm:rounded-2xl"
        style={{ background: snapshotTokens.background }}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="player-snapshot-title"
      >
        <div
          className="shrink-0 border-b bg-white px-5 py-4 sm:px-6 sm:py-5"
          style={{ borderColor: snapshotTokens.divider }}
        >
          <div className="mb-4 flex justify-end">
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-sm font-medium transition hover:bg-gray-50"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textSecondary,
              }}
              aria-label="Close"
            >
              <X className="h-4 w-4" />
              Close
            </button>
          </div>

          {loading && !active ? (
            <div className="space-y-3 animate-pulse">
              <div className="flex gap-4">
                <div
                  className="h-24 w-24 rounded-2xl"
                  style={{ background: snapshotTokens.divider }}
                />
                <div className="flex-1 space-y-2 pt-2">
                  <div
                    className="h-8 w-2/3 rounded"
                    style={{ background: snapshotTokens.divider }}
                  />
                  <div
                    className="h-4 w-1/3 rounded"
                    style={{ background: snapshotTokens.divider }}
                  />
                </div>
              </div>
            </div>
          ) : error && !active ? (
            <div className="py-8 text-center">
              <p
                className="text-base font-semibold"
                style={{ color: snapshotTokens.navy }}
              >
                Player data temporarily unavailable
              </p>
              <p
                className="mt-2 text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                {error}
              </p>
            </div>
          ) : active && !comparing ? (
            <PlayerHeader active={active} />
          ) : active && comparing ? (
            <div>
              <p
                className="text-xs font-semibold uppercase tracking-[0.16em]"
                style={{ color: snapshotTokens.textMuted }}
              >
                Replacement comparison
              </p>
              <h2
                id="player-snapshot-title"
                className="mt-1 text-[24px] font-bold tracking-tight sm:text-[28px]"
                style={{ color: snapshotTokens.navy }}
              >
                {active.name || "Player"}
                {" vs "}
                {compareSnapshot?.name
                  ?? (compareLoading ? "…" : "Free agent")}
              </h2>
              <p
                className="mt-1 text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                Side-by-side fantasy value, opportunity, and
                production for a waiver decision.
              </p>
            </div>
          ) : null}

          {active && !comparing && (
            <div className="mt-5">
              <PlayerTabs
                active={tab}
                onChange={setTab}
              />
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-6">
          {active && comparing && (
            <>
              {compareLoading && !compareSnapshot ? (
                <div className="space-y-4 animate-pulse">
                  <div
                    className="h-28 rounded-[10px]"
                    style={{ background: snapshotTokens.divider }}
                  />
                  <div
                    className="h-40 rounded-[10px]"
                    style={{ background: snapshotTokens.divider }}
                  />
                </div>
              ) : compareError && !compareSnapshot ? (
                <div
                  className="rounded-[10px] border bg-white px-5 py-10 text-center"
                  style={{ borderColor: snapshotTokens.border }}
                >
                  <p
                    className="text-base font-semibold"
                    style={{ color: snapshotTokens.navy }}
                  >
                    Comparison unavailable
                  </p>
                  <p
                    className="mt-2 text-sm"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    {compareError}
                  </p>
                  <button
                    type="button"
                    onClick={clearCompare}
                    className="mt-4 rounded-lg border px-3 py-2 text-sm font-medium"
                    style={{
                      borderColor: snapshotTokens.border,
                      color: snapshotTokens.textSecondary,
                    }}
                  >
                    Back to snapshot
                  </button>
                </div>
              ) : compareSnapshot ? (
                <PlayerComparison
                  base={active}
                  compare={compareSnapshot}
                  baseOwnership={active.ownership}
                  compareOwnership={
                    compareOwnership ?? compareSnapshot.ownership
                  }
                  onBack={clearCompare}
                  onOpenPlayer={onSelectPlayer}
                />
              ) : null}
            </>
          )}

          {active && !comparing && tab === "snapshot" && (
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(17rem,0.9fr)] lg:gap-5">
              <div className="min-w-0 space-y-4">
                <PerformanceSummary
                  seasonStats={active.season_stats}
                  productionScore={active.production_score}
                  opportunityScore={active.opportunity_score}
                />
                <TrendChart
                  games={recentGames}
                  trendScore={active.trend_score}
                />
                <GameLog
                  games={recentGames}
                  position={active.position}
                />
                {!active.is_team_defense && (
                  <PositionDepthChart
                    active={active}
                    onSelectPlayer={onSelectPlayer}
                  />
                )}
                <PlayerProfile active={active} />
              </div>

              <div className="min-w-0 space-y-4 lg:sticky lg:top-0 lg:self-start">
                <KeyTakeaways
                  takeaways={active.key_takeaways ?? []}
                />
                <RecommendationCard
                  recommendation={active.recommendation}
                />
                <PositionRankCard active={active} />
                <FreeAgentReplacements
                  replacements={
                    active.replacements ?? []
                  }
                  onSelect={startCompare}
                />
                <p
                  className="px-1 text-[11px] leading-4"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  ✦ InsightPilot Analysis is generated from
                  historical production, usage, and
                  current-season profile scores — separate
                  from raw box-score facts.
                </p>
              </div>
            </div>
          )}

          {active && !comparing && tab === "stats" && (
            <PlayerStatsTab
              playerId={active.player_id}
              defaultSeason={active.season}
            />
          )}

          {active && !comparing && tab === "usage" && (
            <PlayerUsageTab
              playerId={active.player_id}
              defaultSeason={active.season}
            />
          )}

          {active && !comparing && tab === "matchups" && (
            <PlayerMatchupsTab
              playerId={active.player_id}
              defaultSeason={active.season}
            />
          )}

          {active && !comparing && tab === "news" && (
            <PlayerNewsTab
              playerId={active.player_id}
              defaultSeason={active.season}
              onNavigateTab={(next) => setTab(next)}
            />
          )}

          {active
            && !comparing
            && tab !== "snapshot"
            && tab !== "stats"
            && tab !== "usage"
            && tab !== "matchups"
            && tab !== "news" && (
            <div
              className="rounded-[10px] border bg-white px-5 py-10 text-center"
              style={{ borderColor: snapshotTokens.border }}
            >
              <p
                className="text-base font-semibold"
                style={{ color: snapshotTokens.navy }}
              >
                Coming soon
              </p>
              <p
                className="mt-2 text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                This tab will expand Snapshot into deeper
                analysis without cluttering the first view.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
