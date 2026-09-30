"use client";

import { useEffect, useState } from "react";

import { useApplicationContext } from "@/components/applications/ApplicationContext";
import PlayerSnapshot from "@/components/fantasy/PlayerSnapshot";
import PlayerHeader from "@/components/fantasy/snapshot/PlayerHeader";
import PlayerMatchupsTab from "@/components/fantasy/snapshot/PlayerMatchupsTab";
import PlayerNewsTab from "@/components/fantasy/snapshot/PlayerNewsTab";
import PlayerStatsTab from "@/components/fantasy/snapshot/PlayerStatsTab";
import PlayerUsageTab from "@/components/fantasy/snapshot/PlayerUsageTab";
import PerformanceSummary from "@/components/fantasy/snapshot/PerformanceSummary";
import TrendChart from "@/components/fantasy/snapshot/TrendChart";
import GameLog from "@/components/fantasy/snapshot/GameLog";
import KeyTakeaways from "@/components/fantasy/snapshot/KeyTakeaways";
import RecommendationCard from "@/components/fantasy/snapshot/RecommendationCard";
import PositionRankCard from "@/components/fantasy/snapshot/PositionRankCard";
import PlayerProfile from "@/components/fantasy/snapshot/PlayerProfile";
import PositionDepthChart from "@/components/fantasy/snapshot/PositionDepthChart";
import type { SnapshotTabId } from "@/components/fantasy/snapshot/PlayerTabs";
import {
  FantasyPlayerSnapshot,
  getFantasyPlayerSnapshot,
  searchFantasyPlayers,
} from "@/services/api";

interface Props {
  view: SnapshotTabId;
}

function PlayerPicker({
  playerId,
  onSelect,
}: {
  playerId: string | null;
  onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<
    Array<{ player_id: string; name: string; position?: string; team?: string }>
  >([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setHits([]);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          setLoading(true);
          const result = await searchFantasyPlayers(q, 8);
          if (cancelled) return;
          setHits(
            (result.players || []).map((row) => ({
              player_id: row.player_id,
              name: row.name || row.player_id,
              position: row.position || undefined,
              team: row.team || undefined,
            }))
          );
        } catch {
          if (!cancelled) setHits([]);
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
    }, 220);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <label className="block text-sm font-medium text-gray-800">
        {playerId ? "Change player" : "Select a player"}
      </label>
      <input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search players…"
        className="mt-2 w-full max-w-md rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none focus:border-gray-900"
      />
      {loading ? (
        <p className="mt-2 text-xs text-gray-500">Searching…</p>
      ) : null}
      {hits.length > 0 ? (
        <ul className="mt-2 max-w-md divide-y divide-gray-100 rounded-lg border border-gray-200">
          {hits.map((hit) => (
            <li key={hit.player_id}>
              <button
                type="button"
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm text-gray-900 hover:bg-gray-50"
                onClick={() => {
                  onSelect(hit.player_id);
                  setQuery("");
                  setHits([]);
                }}
              >
                <span className="font-medium">{hit.name}</span>
                <span className="text-xs text-gray-500">
                  {[hit.position, hit.team].filter(Boolean).join(" · ")}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function PlayerDetailBody({
  active,
  view,
  onSelectPlayer,
}: {
  active: FantasyPlayerSnapshot;
  view: SnapshotTabId;
  onSelectPlayer: (id: string) => void;
}) {
  const recentGames = active.performance?.recent_games ?? [];

  if (view === "stats") {
    return (
      <PlayerStatsTab
        playerId={active.player_id}
        defaultSeason={active.season}
      />
    );
  }
  if (view === "usage") {
    return (
      <PlayerUsageTab
        playerId={active.player_id}
        defaultSeason={active.season}
      />
    );
  }
  if (view === "matchups") {
    return (
      <PlayerMatchupsTab
        playerId={active.player_id}
        defaultSeason={active.season}
      />
    );
  }
  if (view === "news") {
    return (
      <PlayerNewsTab
        playerId={active.player_id}
        defaultSeason={active.season}
      />
    );
  }

  return (
    <div className="space-y-4">
      <PlayerHeader active={active} />
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(17rem,0.9fr)]">
        <div className="min-w-0 space-y-4">
          <PerformanceSummary
            seasonStats={active.season_stats}
            productionScore={active.production_score}
            opportunityScore={active.opportunity_score}
          />
          <TrendChart games={recentGames} trendScore={active.trend_score} />
          <GameLog games={recentGames} position={active.position} />
          {!active.is_team_defense && (
            <PositionDepthChart
              active={active}
              onSelectPlayer={onSelectPlayer}
            />
          )}
          <PlayerProfile active={active} />
        </div>
        <div className="min-w-0 space-y-4">
          <KeyTakeaways takeaways={active.key_takeaways ?? []} />
          <RecommendationCard recommendation={active.recommendation} />
          <PositionRankCard active={active} />
        </div>
      </div>
    </div>
  );
}

export default function PlayerAnalysisRuntime({ view }: Props) {
  const { playerId, setPlayerId } = useApplicationContext();
  const [active, setActive] = useState<FantasyPlayerSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (view === "snapshot" || !playerId) {
      setActive(null);
      setError(null);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        setLoading(true);
        setError(null);
        const result = await getFantasyPlayerSnapshot(playerId);
        if (cancelled) return;
        setActive(result.snapshot);
      } catch (err) {
        if (cancelled) return;
        setActive(null);
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load player analysis."
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [playerId, view]);

  if (view === "snapshot") {
    return (
      <PlayerSnapshot
        initialDetailTab="snapshot"
        onPlayerSelect={setPlayerId}
      />
    );
  }

  return (
    <div className="space-y-4">
      <PlayerPicker playerId={playerId} onSelect={setPlayerId} />

      {!playerId ? (
        <div className="rounded-xl border border-gray-200 bg-white px-5 py-12 text-center">
          <p className="text-base font-semibold text-gray-900">
            Select a player to continue
          </p>
          <p className="mx-auto mt-2 max-w-md text-sm text-gray-600">
            Choose a player here, or open one from Player Overview —
            the selection is kept as you move between analyses.
          </p>
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-xl border border-gray-200 bg-white p-8 text-sm text-gray-500">
          Loading player…
        </div>
      ) : null}

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-800">
          {error}
        </div>
      ) : null}

      {active && !loading ? (
        <div className="rounded-xl border border-gray-200 bg-white p-5 sm:p-6">
          <div className="mb-4">
            <PlayerHeader active={active} />
          </div>
          <PlayerDetailBody
            active={active}
            view={view}
            onSelectPlayer={setPlayerId}
          />
        </div>
      ) : null}
    </div>
  );
}
