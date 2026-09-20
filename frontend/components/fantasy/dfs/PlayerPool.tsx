"use client";

import { useMemo, useState } from "react";

import {
  DFS_PLAYER_MIME,
  readDfsDragData,
  setDfsDragData,
} from "@/components/fantasy/dfs/drag";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type { DfsPlayer, DfsSignal } from "@/services/api";

const POSITION_TABS = [
  "All",
  "QB",
  "RB",
  "WR",
  "TE",
  "FLEX",
  "K",
  "DST",
] as const;

interface Props {
  players: DfsPlayer[];
  positionFilter: string;
  lockedIds: Set<string>;
  excludedIds: Set<string>;
  lineupIds: Set<string>;
  onPositionFilter: (value: string) => void;
  onSelectPlayer: (playerId: string) => void;
  onAdd: (playerId: string) => void;
  onRemove: (playerId: string) => void;
  onExclude: (playerId: string) => void;
}

export default function PlayerPool({
  players,
  positionFilter,
  lockedIds,
  excludedIds,
  lineupIds,
  onPositionFilter,
  onSelectPlayer,
  onAdd,
  onRemove,
  onExclude,
}: Props) {
  const [search, setSearch] = useState("");
  const [dropActive, setDropActive] = useState(false);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return players.filter((player) => {
      const pos = (player.position || "").toUpperCase();
      if (positionFilter === "DST") {
        if (pos !== "DEF" && pos !== "DST") {
          return false;
        }
      } else if (positionFilter === "FLEX") {
        if (pos !== "RB" && pos !== "WR" && pos !== "TE") {
          return false;
        }
      } else if (
        positionFilter !== "All"
        && pos !== positionFilter
      ) {
        return false;
      }

      if (!needle) {
        return true;
      }
      const haystack = [
        player.name,
        player.team,
        player.opponent,
        player.position,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [players, positionFilter, search]);

  return (
    <section
      className="rounded-[10px] border bg-white"
      style={{
        borderColor: dropActive
          ? snapshotTokens.blue
          : snapshotTokens.border,
        boxShadow: dropActive
          ? `inset 0 0 0 1px ${snapshotTokens.blue}`
          : undefined,
      }}
      onDrop={(event) => {
        event.preventDefault();
        setDropActive(false);
        const payload = readDfsDragData(event.dataTransfer);
        if (!payload || payload.source !== "lineup") {
          return;
        }
        onRemove(payload.playerId);
      }}
      onDragOver={(event) => {
        const types = Array.from(event.dataTransfer.types);
        if (
          !types.includes(DFS_PLAYER_MIME)
          && !types.includes("text/plain")
        ) {
          return;
        }
        // Lineup drags use effectAllowed "move".
        if (event.dataTransfer.effectAllowed !== "move") {
          return;
        }
        event.preventDefault();
        event.dataTransfer.dropEffect = "move";
        setDropActive(true);
      }}
      onDragLeave={(event) => {
        if (
          event.currentTarget.contains(
            event.relatedTarget as Node | null
          )
        ) {
          return;
        }
        setDropActive(false);
      }}
    >
      <div
        className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3"
        style={{ borderColor: snapshotTokens.divider }}
      >
        <h3
          className="text-[15px] font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          Player Pool
        </h3>
        <p
          className="text-xs"
          style={{ color: snapshotTokens.textMuted }}
        >
          {dropActive
            ? "Drop to remove from lineup"
            : `${filtered.length} players${
                excludedIds.size > 0
                  ? ` · ${excludedIds.size} excluded`
                  : ""
              }`}
        </p>
      </div>

      <div
        className="border-b px-3 py-2"
        style={{ borderColor: snapshotTokens.divider }}
      >
        <label className="block">
          <span className="sr-only">Search players</span>
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search by name, team, or opponent…"
            className="w-full rounded-lg border bg-white px-3 py-2 text-sm outline-none"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textPrimary,
            }}
          />
        </label>
      </div>

      <div
        className="flex gap-1 overflow-x-auto border-b px-3 py-2"
        style={{ borderColor: snapshotTokens.divider }}
      >
        {POSITION_TABS.map((tab) => {
          const selected = positionFilter === tab;
          return (
            <button
              key={tab}
              type="button"
              onClick={() => onPositionFilter(tab)}
              className="shrink-0 rounded-md px-2.5 py-1.5 text-xs font-semibold"
              style={{
                background: selected
                  ? snapshotTokens.blueLight
                  : "transparent",
                color: selected
                  ? snapshotTokens.blue
                  : snapshotTokens.textSecondary,
              }}
            >
              {tab}
            </button>
          );
        })}
      </div>

      <div className="max-h-[36rem] overflow-auto">
        <table className="min-w-full text-left text-sm">
          <thead
            className="sticky top-0 text-[11px] uppercase tracking-wide"
            style={{
              background: snapshotTokens.background,
              color: snapshotTokens.textMuted,
            }}
          >
            <tr>
              <th className="px-3 py-2 font-medium">Player</th>
              <th className="px-2 py-2 font-medium">Pos</th>
              <th className="px-2 py-2 font-medium">Team</th>
              <th className="px-2 py-2 font-medium">Opp</th>
              <th className="px-2 py-2 text-right font-medium">
                Proj
              </th>
              <th className="px-2 py-2 text-right font-medium">
                Salary
              </th>
              <th className="px-2 py-2 text-right font-medium">
                Own%
              </th>
              <th className="px-2 py-2 text-right font-medium">
                Value
              </th>
              <th className="px-2 py-2 text-center font-medium">
                Matchup
              </th>
              <th className="px-2 py-2 text-center font-medium">
                Signal
              </th>
              <th className="px-3 py-2 text-right font-medium">
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((player) => {
              const inLineup = lineupIds.has(player.player_id);
              const locked = lockedIds.has(player.player_id);
              const excluded = excludedIds.has(
                player.player_id
              );
              return (
                <tr
                  key={player.player_id}
                  draggable={!excluded}
                  onDragStart={(event) => {
                    if (excluded) {
                      event.preventDefault();
                      return;
                    }
                    setDfsDragData(event.dataTransfer, {
                      playerId: player.player_id,
                      source: "pool",
                    });
                  }}
                  className="border-t cursor-grab active:cursor-grabbing"
                  style={{
                    borderColor: snapshotTokens.divider,
                    opacity: excluded ? 0.55 : 1,
                    background: excluded
                      ? snapshotTokens.background
                      : undefined,
                  }}
                >
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() =>
                        onSelectPlayer(player.player_id)
                      }
                      className="text-left"
                    >
                      <p
                        className="font-medium"
                        style={{
                          color: snapshotTokens.textPrimary,
                        }}
                      >
                        {player.name}
                        {locked && (
                          <span
                            className="ml-1 text-[10px] font-semibold"
                            style={{
                              color: snapshotTokens.blue,
                            }}
                          >
                            LOCKED
                          </span>
                        )}
                        {excluded && (
                          <span
                            className="ml-1 text-[10px] font-semibold"
                            style={{
                              color: snapshotTokens.negative,
                            }}
                          >
                            EXCLUDED
                          </span>
                        )}
                      </p>
                    </button>
                  </td>
                  <td
                    className="px-2 py-2"
                    style={{
                      color: snapshotTokens.textSecondary,
                    }}
                  >
                    {player.position}
                  </td>
                  <td
                    className="px-2 py-2"
                    style={{
                      color: snapshotTokens.textSecondary,
                    }}
                  >
                    {player.team || "—"}
                  </td>
                  <td
                    className="px-2 py-2"
                    style={{
                      color: snapshotTokens.textSecondary,
                    }}
                  >
                    {player.opponent
                      ? `vs ${player.opponent}`
                      : "—"}
                  </td>
                  <td
                    className="px-2 py-2 text-right tabular-nums font-semibold"
                    style={{
                      color: snapshotTokens.textPrimary,
                    }}
                  >
                    {player.projection?.toFixed(1) ?? "—"}
                  </td>
                  <td
                    className="px-2 py-2 text-right tabular-nums"
                    style={{
                      color: snapshotTokens.textSecondary,
                    }}
                  >
                    ${player.salary.toLocaleString()}
                  </td>
                  <td className="px-2 py-2 text-right">
                    <OwnershipIndicator
                      ownership={player.projected_ownership}
                      label={player.ownership_label}
                    />
                  </td>
                  <td
                    className="px-2 py-2 text-right tabular-nums"
                    style={{
                      color: snapshotTokens.textSecondary,
                    }}
                  >
                    {player.value?.toFixed(2) ?? "—"}
                  </td>
                  <td className="px-2 py-2 text-center">
                    <MatchupIndicator
                      label={player.matchup_label}
                    />
                  </td>
                  <td className="px-2 py-2 text-center">
                    <SignalIndicator
                      signal={player.primary_signal}
                    />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <div className="inline-flex gap-1">
                      <button
                        type="button"
                        disabled={inLineup || excluded}
                        onClick={() =>
                          onAdd(player.player_id)
                        }
                        className="rounded px-2 py-1 text-[11px] font-semibold disabled:opacity-40"
                        style={{
                          background: snapshotTokens.blueLight,
                          color: snapshotTokens.blue,
                        }}
                      >
                        {inLineup ? "In lineup" : "+ Add"}
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          onExclude(player.player_id)
                        }
                        className="rounded px-2 py-1 text-[11px] font-semibold"
                        style={{
                          color: excluded
                            ? snapshotTokens.negative
                            : snapshotTokens.textMuted,
                          background: excluded
                            ? "rgba(185, 28, 28, 0.08)"
                            : "transparent",
                        }}
                      >
                        {excluded ? "Excluded" : "Exclude"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p
            className="px-4 py-8 text-center text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            No players match this search or filter.
          </p>
        )}
      </div>
    </section>
  );
}

function OwnershipIndicator({
  ownership,
  label,
}: {
  ownership?: number | null;
  label?: string | null;
}) {
  if (ownership == null) {
    return (
      <span style={{ color: snapshotTokens.textMuted }}>—</span>
    );
  }
  const pct = ownership * 100;
  const band = (label || "").toLowerCase();
  const styles =
    band === "chalk"
      ? {
          bg: snapshotTokens.warningLight,
          text: "#B45309",
        }
      : band === "high"
        ? {
            bg: snapshotTokens.blueLight,
            text: snapshotTokens.blue,
          }
        : band === "contrarian" || band === "low"
          ? {
              bg: snapshotTokens.successLight,
              text: snapshotTokens.success,
            }
          : {
              bg: snapshotTokens.background,
              text: snapshotTokens.textSecondary,
            };
  const display =
    pct < 10 ? pct.toFixed(1) : pct.toFixed(0);
  const tooltip = label
    ? `${label} · ${pct.toFixed(1)}%`
    : `${pct.toFixed(1)}% ownership`;

  return (
    <span
      className="inline-flex rounded px-1.5 py-0.5 tabular-nums text-xs font-semibold"
      style={{
        background: styles.bg,
        color: styles.text,
      }}
      title={tooltip}
      aria-label={tooltip}
    >
      {display}%
    </span>
  );
}

function MatchupIndicator({
  label,
}: {
  label?: string | null;
}) {
  if (!label) {
    return (
      <span style={{ color: snapshotTokens.textMuted }}>—</span>
    );
  }
  const key = label.toLowerCase();
  const styles =
    key.includes("very favorable")
      ? {
          bg: snapshotTokens.successLight,
          text: snapshotTokens.success,
          mark: "●●",
        }
      : key.includes("favorable")
        ? {
            bg: "#EAF8EF",
            text: "#15803D",
            mark: "●",
          }
        : key.includes("difficult")
          ? {
              bg: snapshotTokens.negativeLight,
              text: snapshotTokens.negative,
              mark: "○",
            }
          : {
              bg: snapshotTokens.background,
              text: snapshotTokens.textSecondary,
              mark: "◦",
            };

  return (
    <span
      className="inline-flex h-6 w-6 items-center justify-center rounded-md text-[11px] font-semibold"
      style={{ background: styles.bg, color: styles.text }}
      title={label}
      aria-label={label}
    >
      <span aria-hidden>{styles.mark}</span>
    </span>
  );
}

function SignalIndicator({
  signal,
}: {
  signal?: DfsSignal | null;
}) {
  if (!signal?.label) {
    return (
      <span style={{ color: snapshotTokens.textMuted }}>—</span>
    );
  }
  const tone = (signal.tone || "neutral").toLowerCase();
  const styles =
    tone === "positive"
      ? {
          bg: snapshotTokens.successLight,
          text: snapshotTokens.success,
          mark: "↑",
        }
      : tone === "warning" || tone === "negative"
        ? {
            bg: snapshotTokens.warningLight,
            text: "#B45309",
            mark: "!",
          }
        : {
            bg: snapshotTokens.background,
            text: snapshotTokens.textSecondary,
            mark: "→",
          };
  const tooltip = signal.body
    ? `${signal.label} — ${signal.body}`
    : signal.label;

  return (
    <span
      className="inline-flex h-6 w-6 items-center justify-center rounded-md text-[12px] font-semibold"
      style={{ background: styles.bg, color: styles.text }}
      title={tooltip}
      aria-label={tooltip}
    >
      <span aria-hidden>{styles.mark}</span>
    </span>
  );
}
