"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  FantasyPlayerSearchHit,
  FantasyPlayerSnapshot,
  getFantasyPlayerSnapshot,
} from "@/services/api";

import SearchablePlayerSelect from "@/components/fantasy/SearchablePlayerSelect";
import PlayerComparison from "@/components/fantasy/snapshot/PlayerComparison";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";

interface Props {
  players: FantasyPlayerSearchHit[];
  onOpenPlayer?: (playerId: string) => void;
}

export default function PlayerOverviewCompare({
  players,
  onOpenPlayer,
}: Props) {
  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");
  const [left, setLeft] =
    useState<FantasyPlayerSnapshot | null>(null);
  const [right, setRight] =
    useState<FantasyPlayerSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const optionPlayers = useMemo(
    () => players,
    [players]
  );

  useEffect(() => {
    if (!leftId || !rightId || leftId === rightId) {
      setLeft(null);
      setRight(null);
      setError(
        leftId && rightId && leftId === rightId
          ? "Select two different players to compare."
          : null
      );
      setLoading(false);
      return;
    }

    let cancelled = false;

    void (async () => {
      try {
        setLoading(true);
        setError(null);
        const [leftResult, rightResult] =
          await Promise.all([
            getFantasyPlayerSnapshot(leftId),
            getFantasyPlayerSnapshot(rightId),
          ]);
        if (cancelled) {
          return;
        }
        setLeft(leftResult.snapshot);
        setRight(rightResult.snapshot);
      } catch (loadError) {
        if (cancelled) {
          return;
        }
        setLeft(null);
        setRight(null);
        setError(
          loadError instanceof Error
            ? loadError.message
            : "Unable to load players for comparison."
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
  }, [leftId, rightId]);

  return (
    <div className="space-y-4">
      <section
        className="rounded-[10px] border bg-white p-4 sm:p-5"
        style={{ borderColor: snapshotTokens.border }}
      >
        <h3
          className="text-[15px] font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          Select players
        </h3>
        <p
          className="mt-1 text-xs"
          style={{ color: snapshotTokens.textSecondary }}
        >
          Search and choose any two players from the current
          overview filters.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <SearchablePlayerSelect
            label="Player A"
            players={optionPlayers}
            value={leftId}
            excludeId={rightId}
            onChange={setLeftId}
          />
          <SearchablePlayerSelect
            label="Player B"
            players={optionPlayers}
            value={rightId}
            excludeId={leftId}
            onChange={setRightId}
          />
        </div>
      </section>

      {loading && (
        <div className="space-y-3 animate-pulse">
          <div
            className="h-28 rounded-[10px]"
            style={{ background: snapshotTokens.divider }}
          />
          <div
            className="h-40 rounded-[10px]"
            style={{ background: snapshotTokens.divider }}
          />
        </div>
      )}

      {!loading && error && (
        <div
          className="rounded-[10px] border bg-white px-4 py-6 text-sm"
          style={{
            borderColor: snapshotTokens.border,
            color: snapshotTokens.textSecondary,
          }}
        >
          {error}
        </div>
      )}

      {!loading && left && right && (
        <PlayerComparison
          base={left}
          compare={right}
          baseOwnership={left.ownership}
          compareOwnership={right.ownership}
          onOpenPlayer={onOpenPlayer}
        />
      )}

      {!loading && !error && (!leftId || !rightId) && (
        <div
          className="rounded-[10px] border border-dashed bg-white px-4 py-10 text-center text-sm"
          style={{
            borderColor: snapshotTokens.border,
            color: snapshotTokens.textSecondary,
          }}
        >
          Select two players to open the comparison.
        </div>
      )}
    </div>
  );
}
