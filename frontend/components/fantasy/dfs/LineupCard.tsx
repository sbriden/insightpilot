"use client";

import { useState } from "react";

import {
  DFS_PLAYER_MIME,
  readDfsDragData,
  setDfsDragData,
} from "@/components/fantasy/dfs/drag";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type {
  DfsCorrelationPair,
  DfsLineup,
  DfsLineupPlayer,
} from "@/services/api";

interface Props {
  lineup: DfsLineup | null;
  slots: string[];
  lockedIds: Set<string>;
  activeSlotIndex: number | null;
  onSelectSlot: (slotIndex: number) => void;
  onSelectPlayer: (playerId: string) => void;
  onPlacePlayer: (
    playerId: string,
    slotIndex?: number | null
  ) => void;
  onRemove: (playerId: string) => void;
  onLockToggle: (playerId: string) => void;
}

export default function LineupCard({
  lineup,
  slots,
  lockedIds,
  activeSlotIndex,
  onSelectSlot,
  onSelectPlayer,
  onPlacePlayer,
  onRemove,
  onLockToggle,
}: Props) {
  const rows = buildSlotRows(slots, lineup?.players ?? []);
  const [dragOverIndex, setDragOverIndex] = useState<
    number | null
  >(null);

  return (
    <section
      className="rounded-[10px] border bg-white p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3
          className="text-[15px] font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          Optimal Lineup
        </h3>
        {lineup && (
          <p
            className="text-xs tabular-nums"
            style={{ color: snapshotTokens.textMuted }}
          >
            {lineup.projected_points.toFixed(1)} pts
            {lineup.lineup_correlation_score != null
              ? ` · corr ${lineup.lineup_correlation_score >= 0 ? "+" : ""}${lineup.lineup_correlation_score.toFixed(2)}`
              : ""}
          </p>
        )}
      </div>

      <p
        className="mt-1 text-[11px]"
        style={{ color: snapshotTokens.textMuted }}
      >
        {activeSlotIndex == null
          ? "Drag players in, or click a seat then pick from the pool. Hover a player for correlations."
          : `Selected ${slotLabel(slots[activeSlotIndex], activeSlotIndex, slots)} — drop or pick a player to ${rows[activeSlotIndex]?.player ? "swap" : "fill"}.`}
      </p>

      <div className="mt-3 space-y-1.5">
        {rows.map((row) => {
          const active = activeSlotIndex === row.index;
          const dropTarget = dragOverIndex === row.index;
          const playerPairs = row.player
            ? correlationsForPlayer(
                lineup?.correlation,
                row.player.player_id
              )
            : [];
          return (
            <div
              key={`${row.slot}-${row.index}`}
              role="button"
              tabIndex={0}
              onClick={() => onSelectSlot(row.index)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelectSlot(row.index);
                }
              }}
              onDragOver={(event) => {
                const types = Array.from(
                  event.dataTransfer.types
                );
                if (
                  !types.includes(DFS_PLAYER_MIME)
                  && !types.includes("text/plain")
                ) {
                  return;
                }
                event.preventDefault();
                event.stopPropagation();
                event.dataTransfer.dropEffect = "copy";
                setDragOverIndex(row.index);
              }}
              onDragLeave={(event) => {
                if (
                  event.currentTarget.contains(
                    event.relatedTarget as Node | null
                  )
                ) {
                  return;
                }
                setDragOverIndex((current) =>
                  current === row.index ? null : current
                );
              }}
              onDrop={(event) => {
                event.preventDefault();
                event.stopPropagation();
                setDragOverIndex(null);
                const payload = readDfsDragData(
                  event.dataTransfer
                );
                if (!payload) {
                  return;
                }
                onPlacePlayer(payload.playerId, row.index);
              }}
              className="group relative flex cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-2 outline-none transition-colors"
              style={{
                borderColor: dropTarget
                  ? snapshotTokens.blue
                  : active
                    ? snapshotTokens.blue
                    : snapshotTokens.divider,
                background: dropTarget || active
                  ? snapshotTokens.blueLight
                  : "transparent",
                boxShadow:
                  dropTarget || active
                    ? `inset 3px 0 0 ${snapshotTokens.blue}`
                    : undefined,
              }}
            >
              <span
                className="w-10 shrink-0 text-[11px] font-semibold uppercase"
                style={{
                  color:
                    row.slot === "CPT" || active || dropTarget
                      ? snapshotTokens.blue
                      : snapshotTokens.textMuted,
                }}
              >
                {row.slot}
              </span>
              {row.player ? (
                <>
                  <button
                    type="button"
                    draggable
                    onDragStart={(event) => {
                      event.stopPropagation();
                      setDfsDragData(event.dataTransfer, {
                        playerId: row.player!.player_id,
                        source: "lineup",
                      });
                    }}
                    className="min-w-0 flex-1 cursor-grab text-left active:cursor-grabbing"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelectSlot(row.index);
                      onSelectPlayer(row.player!.player_id);
                    }}
                  >
                    <p
                      className="truncate text-sm font-medium"
                      style={{
                        color: snapshotTokens.textPrimary,
                      }}
                    >
                      {row.player.name}
                      {row.player.is_captain ? " · CPT" : ""}
                      {playerPairs.length > 0 ? (
                        <span
                          className="ml-1 text-[10px] font-semibold"
                          style={{ color: snapshotTokens.blue }}
                          aria-hidden
                        >
                          ↕
                        </span>
                      ) : null}
                    </p>
                    <p
                      className="text-[11px]"
                      style={{
                        color: snapshotTokens.textMuted,
                      }}
                    >
                      {row.player.team || "—"}
                      {row.player.opponent
                        ? ` vs ${row.player.opponent}`
                        : ""}
                      {" · "}
                      $
                      {(
                        row.player.salary || 0
                      ).toLocaleString()}
                    </p>
                  </button>
                  <span
                    className="shrink-0 text-sm font-semibold tabular-nums"
                    style={{ color: snapshotTokens.navy }}
                  >
                    {row.player.projection?.toFixed(1) ?? "—"}
                  </span>
                  <button
                    type="button"
                    title={
                      lockedIds.has(row.player.player_id)
                        ? "Unlock"
                        : "Lock"
                    }
                    onClick={(event) => {
                      event.stopPropagation();
                      onLockToggle(row.player!.player_id);
                    }}
                    className="rounded px-1.5 text-[11px] font-semibold"
                    style={{
                      color: lockedIds.has(
                        row.player.player_id
                      )
                        ? snapshotTokens.blue
                        : snapshotTokens.textMuted,
                      background: lockedIds.has(
                        row.player.player_id
                      )
                        ? snapshotTokens.blueLight
                        : "transparent",
                    }}
                  >
                    {lockedIds.has(row.player.player_id)
                      ? "Locked"
                      : "Lock"}
                  </button>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onRemove(row.player!.player_id);
                    }}
                    className="rounded px-1.5 text-[11px]"
                    style={{
                      color: snapshotTokens.negative,
                    }}
                  >
                    Remove
                  </button>
                  {playerPairs.length > 0 ? (
                    <CorrelationTooltip
                      playerName={row.player.name}
                      pairs={playerPairs}
                      playerId={row.player.player_id}
                    />
                  ) : null}
                </>
              ) : (
                <p
                  className="flex-1 text-sm"
                  style={{
                    color:
                      active || dropTarget
                        ? snapshotTokens.blue
                        : snapshotTokens.textMuted,
                  }}
                >
                  {dropTarget
                    ? "Drop player…"
                    : active
                      ? "Select a player…"
                      : "Empty"}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {lineup && (
        <div
          className="mt-3 space-y-1 border-t pt-3 text-xs"
          style={{ borderColor: snapshotTokens.divider }}
        >
          <Row
            label="Salary"
            value={`$${lineup.salary_used.toLocaleString()} / $${lineup.salary_cap.toLocaleString()}`}
          />
          <Row
            label="Projection"
            value={lineup.projected_points.toFixed(1)}
          />
          <Row
            label="Ownership"
            value={
              lineup.projected_ownership != null
                ? `${lineup.projected_ownership.toFixed(0)}%`
                : "—"
            }
          />
        </div>
      )}
    </section>
  );
}

function CorrelationTooltip({
  playerName,
  playerId,
  pairs,
}: {
  playerName: string;
  playerId: string;
  pairs: DfsCorrelationPair[];
}) {
  return (
    <div
      className="pointer-events-none absolute left-2 right-2 top-full z-40 mt-1 hidden rounded-lg border bg-white p-2.5 shadow-lg group-hover:block group-focus-within:block"
      style={{ borderColor: snapshotTokens.border }}
      role="tooltip"
    >
      <p
        className="text-[10px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        Correlations · {playerName}
      </p>
      <ul className="mt-1.5 space-y-1.5">
        {pairs.slice(0, 5).map((pair) => {
          const otherId =
            pair.player_id === playerId
              ? pair.correlated_player_id
              : pair.player_id;
          const otherName =
            pair.player_id === playerId
              ? pair.correlated_player_name
              : pair.player_name;
          const positive = pair.correlation_score > 0;
          return (
            <li
              key={`${pair.player_id}-${pair.correlated_player_id}-${pair.rule_id ?? ""}`}
              className="text-xs"
            >
              <div className="flex flex-wrap items-baseline gap-x-1.5">
                <span
                  className="font-semibold tabular-nums"
                  style={{
                    color: positive
                      ? snapshotTokens.success
                      : snapshotTokens.warning,
                  }}
                >
                  ↕ {positive ? "+" : ""}
                  {pair.correlation_score.toFixed(2)}
                </span>
                <span style={{ color: snapshotTokens.textPrimary }}>
                  {otherName || otherId}
                </span>
                {pair.confidence ? (
                  <span
                    className="text-[10px] uppercase tracking-wide"
                    style={{ color: snapshotTokens.textMuted }}
                  >
                    {pair.confidence}
                  </span>
                ) : null}
              </div>
              {pair.correlation_reason ? (
                <p
                  className="mt-0.5 leading-snug"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {positive ? "Positive" : "Negative"}:{" "}
                  {pair.correlation_reason}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function correlationsForPlayer(
  correlation: DfsLineup["correlation"] | undefined,
  playerId: string
): DfsCorrelationPair[] {
  if (!correlation) {
    return [];
  }
  const all = correlation.pairs?.length
    ? correlation.pairs
    : [
        ...(correlation.positive_pairs ?? []),
        ...(correlation.negative_pairs ?? []),
      ];
  return all
    .filter(
      (pair) =>
        pair.player_id === playerId
        || pair.correlated_player_id === playerId
    )
    .sort(
      (a, b) =>
        Math.abs(b.correlation_score) - Math.abs(a.correlation_score)
    );
}

function slotLabel(
  slot: string,
  index: number,
  slots: string[]
): string {
  const same = slots.filter((item) => item === slot).length;
  if (same <= 1) {
    return slot;
  }
  const ordinal =
    slots.slice(0, index + 1).filter((item) => item === slot)
      .length;
  return `${slot}${ordinal}`;
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

function Row({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex justify-between gap-3">
      <span style={{ color: snapshotTokens.textMuted }}>
        {label}
      </span>
      <span
        className="tabular-nums font-medium"
        style={{ color: snapshotTokens.textPrimary }}
      >
        {value}
      </span>
    </div>
  );
}
