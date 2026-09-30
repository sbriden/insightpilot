"use client";

import { useMemo, useState } from "react";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type {
  DfsPlayer,
  DfsPortfolioExposureRow,
} from "@/services/api";

interface Props {
  rows: DfsPortfolioExposureRow[];
  slatePlayers: DfsPlayer[];
  positionFilter: string;
  minMap: Record<string, number>;
  maxMap: Record<string, number>;
  captainMaxMap?: Record<string, number>;
  lockedIds: Set<string>;
  excludedIds: Set<string>;
  showCaptainLimits?: boolean;
  onPositionFilter: (value: string) => void;
  onMin: (playerId: string, value: number | null) => void;
  onMax: (playerId: string, value: number | null) => void;
  onCaptainMax?: (playerId: string, value: number | null) => void;
  onLock: (playerId: string) => void;
  onExclude: (playerId: string) => void;
  onInclude: (playerId: string) => void;
  onForceInclude: (playerId: string, minExposure: number) => void;
  onSelectPlayer?: (playerId: string) => void;
}

const POSITIONS = ["All", "QB", "RB", "WR", "TE", "DST"];
const DEFAULT_FORCE_MIN = 0.2;

export default function PlayerExposureTable({
  rows,
  slatePlayers,
  positionFilter,
  minMap,
  maxMap,
  captainMaxMap = {},
  lockedIds,
  excludedIds,
  showCaptainLimits = false,
  onPositionFilter,
  onMin,
  onMax,
  onCaptainMax,
  onLock,
  onExclude,
  onInclude,
  onForceInclude,
  onSelectPlayer,
}: Props) {
  const [forceQuery, setForceQuery] = useState("");
  const [forceMinPct, setForceMinPct] = useState(
    Math.round(DEFAULT_FORCE_MIN * 100)
  );

  const mergedRows = useMemo(
    () =>
      mergeExposureRows({
        rows,
        slatePlayers,
        excludedIds,
        lockedIds,
        minMap,
        maxMap,
        captainMaxMap,
      }),
    [
      rows,
      slatePlayers,
      excludedIds,
      lockedIds,
      minMap,
      maxMap,
      captainMaxMap,
    ]
  );

  const activeRows = mergedRows.filter(
    (row) => !excludedIds.has(row.player_id)
  );
  const excludedRows = mergedRows.filter((row) =>
    excludedIds.has(row.player_id)
  );

  const filteredActive = filterByPosition(activeRows, positionFilter);
  const filteredExcluded = filterByPosition(
    excludedRows,
    positionFilter
  );

  const forceSuggestions = useMemo(() => {
    const q = forceQuery.trim().toLowerCase();
    if (q.length < 1) {
      return [];
    }
    const alreadyVisible = new Set(
      mergedRows.map((row) => row.player_id)
    );
    return slatePlayers
      .filter((player) => {
        if (!player.player_id) {
          return false;
        }
        if (excludedIds.has(player.player_id)) {
          return false;
        }
        const hay = `${player.name} ${player.team ?? ""} ${
          player.position ?? ""
        }`.toLowerCase();
        return hay.includes(q);
      })
      .sort((a, b) => {
        const aIn = alreadyVisible.has(a.player_id) ? 1 : 0;
        const bIn = alreadyVisible.has(b.player_id) ? 1 : 0;
        if (aIn !== bIn) {
          return aIn - bIn;
        }
        return (b.projection ?? 0) - (a.projection ?? 0);
      })
      .slice(0, 8);
  }, [forceQuery, slatePlayers, mergedRows, excludedIds]);

  return (
    <section
      id="portfolio-exposure"
      className="rounded-[10px] border p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3
          className="text-sm font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          Player Exposure
        </h3>
        <div className="flex flex-wrap gap-1">
          {POSITIONS.map((pos) => (
            <button
              key={pos}
              type="button"
              onClick={() => onPositionFilter(pos)}
              className="rounded-md border px-2 py-1 text-[11px] font-semibold"
              style={{
                borderColor:
                  positionFilter === pos
                    ? snapshotTokens.blue
                    : snapshotTokens.border,
                color:
                  positionFilter === pos
                    ? snapshotTokens.blue
                    : snapshotTokens.textSecondary,
              }}
            >
              {pos}
            </button>
          ))}
        </div>
      </div>

      <div
        className="mt-3 rounded-md border px-3 py-2"
        style={{ borderColor: snapshotTokens.border }}
      >
        <p
          className="text-[11px] font-semibold uppercase tracking-wide"
          style={{ color: snapshotTokens.textMuted }}
        >
          Force include player
        </p>
        <p
          className="mt-1 text-xs"
          style={{ color: snapshotTokens.textSecondary }}
        >
          Add any slate player with a minimum exposure. Regenerate
          to pull them into lineups.
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            type="search"
            value={forceQuery}
            onChange={(event) => setForceQuery(event.target.value)}
            placeholder="Search slate players…"
            className="min-w-[12rem] flex-1 rounded border px-2 py-1.5 text-sm"
            style={{ borderColor: snapshotTokens.border }}
          />
          <label
            className="flex items-center gap-1 text-xs"
            style={{ color: snapshotTokens.textSecondary }}
          >
            Min%
            <input
              type="number"
              min={1}
              max={100}
              value={forceMinPct}
              onChange={(event) =>
                setForceMinPct(
                  Math.max(
                    1,
                    Math.min(100, Number(event.target.value) || 1)
                  )
                )
              }
              className="w-14 rounded border px-1.5 py-1 text-xs"
              style={{ borderColor: snapshotTokens.border }}
            />
          </label>
        </div>
        {forceSuggestions.length > 0 && (
          <ul className="mt-2 max-h-48 overflow-auto rounded border"
            style={{ borderColor: snapshotTokens.border }}
          >
            {forceSuggestions.map((player) => {
              const hasMin = minMap[player.player_id] != null;
              return (
                <li
                  key={player.player_id}
                  className="flex items-center justify-between gap-2 border-b px-2 py-1.5 text-sm last:border-b-0"
                  style={{ borderColor: snapshotTokens.border }}
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() =>
                      onSelectPlayer?.(player.player_id)
                    }
                  >
                    <span
                      className="block truncate font-medium"
                      style={{ color: snapshotTokens.textPrimary }}
                    >
                      {player.name}
                    </span>
                    <span
                      className="text-xs"
                      style={{ color: snapshotTokens.textMuted }}
                    >
                      {player.position}
                      {player.team ? ` · ${player.team}` : ""}
                      {player.projection != null
                        ? ` · ${player.projection.toFixed(1)} proj`
                        : ""}
                      {hasMin
                        ? ` · min ${Math.round(
                            minMap[player.player_id] * 100
                          )}%`
                        : ""}
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      onForceInclude(
                        player.player_id,
                        forceMinPct / 100
                      );
                      setForceQuery("");
                    }}
                    className="shrink-0 rounded border px-2 py-1 text-[11px] font-semibold"
                    style={{
                      borderColor: snapshotTokens.blue,
                      color: snapshotTokens.blue,
                    }}
                  >
                    {hasMin ? "Update min" : "Force include"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="mt-3 overflow-x-auto">
        <ExposureTableBody
          rows={filteredActive}
          showCaptainLimits={showCaptainLimits}
          minMap={minMap}
          maxMap={maxMap}
          captainMaxMap={captainMaxMap}
          lockedIds={lockedIds}
          excludedIds={excludedIds}
          onMin={onMin}
          onMax={onMax}
          onCaptainMax={onCaptainMax}
          onLock={onLock}
          onExclude={onExclude}
          onInclude={onInclude}
          onSelectPlayer={onSelectPlayer}
          emptyLabel="Generate a portfolio to see player exposure."
        />
      </div>

      {filteredExcluded.length > 0 && (
        <div className="mt-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4
              className="text-sm font-semibold"
              style={{ color: snapshotTokens.navy }}
            >
              Excluded players ({filteredExcluded.length})
            </h4>
            <p
              className="text-xs"
              style={{ color: snapshotTokens.textSecondary }}
            >
              Re-include without resetting the portfolio. Regenerate
              to use them again.
            </p>
          </div>
          <div className="mt-2 overflow-x-auto">
            <ExposureTableBody
              rows={filteredExcluded}
              showCaptainLimits={showCaptainLimits}
              minMap={minMap}
              maxMap={maxMap}
              captainMaxMap={captainMaxMap}
              lockedIds={lockedIds}
              excludedIds={excludedIds}
              onMin={onMin}
              onMax={onMax}
              onCaptainMax={onCaptainMax}
              onLock={onLock}
              onExclude={onExclude}
              onInclude={onInclude}
              onSelectPlayer={onSelectPlayer}
              emptyLabel="No excluded players."
              dimmed
            />
          </div>
        </div>
      )}
    </section>
  );
}

function ExposureTableBody({
  rows,
  showCaptainLimits,
  minMap,
  maxMap,
  captainMaxMap,
  lockedIds,
  excludedIds,
  onMin,
  onMax,
  onCaptainMax,
  onLock,
  onExclude,
  onInclude,
  onSelectPlayer,
  emptyLabel,
  dimmed = false,
}: {
  rows: DfsPortfolioExposureRow[];
  showCaptainLimits: boolean;
  minMap: Record<string, number>;
  maxMap: Record<string, number>;
  captainMaxMap: Record<string, number>;
  lockedIds: Set<string>;
  excludedIds: Set<string>;
  onMin: (playerId: string, value: number | null) => void;
  onMax: (playerId: string, value: number | null) => void;
  onCaptainMax?: (playerId: string, value: number | null) => void;
  onLock: (playerId: string) => void;
  onExclude: (playerId: string) => void;
  onInclude: (playerId: string) => void;
  onSelectPlayer?: (playerId: string) => void;
  emptyLabel: string;
  dimmed?: boolean;
}) {
  return (
    <>
      <table className="min-w-full text-left text-sm">
        <thead>
          <tr
            className="border-b text-[11px] uppercase tracking-wide"
            style={{
              borderColor: snapshotTokens.border,
              color: snapshotTokens.textMuted,
            }}
          >
            <th className="py-2 pr-3 font-semibold">Player</th>
            <th className="py-2 pr-3 font-semibold">Proj</th>
            <th className="py-2 pr-3 font-semibold">Lineups</th>
            <th className="py-2 pr-3 font-semibold">Exposure</th>
            <th className="py-2 pr-3 font-semibold">Cap</th>
            <th className="py-2 pr-3 font-semibold">Left</th>
            {showCaptainLimits ? (
              <>
                <th className="py-2 pr-3 font-semibold">CPT</th>
                <th className="py-2 pr-3 font-semibold">CPT Max%</th>
              </>
            ) : null}
            <th className="py-2 pr-3 font-semibold">Own</th>
            <th className="py-2 pr-3 font-semibold">Ceil</th>
            <th className="py-2 pr-3 font-semibold">Min%</th>
            <th className="py-2 pr-3 font-semibold">Max%</th>
            <th className="py-2 font-semibold">Controls</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const locked = lockedIds.has(row.player_id);
            const excluded = excludedIds.has(row.player_id);
            const forced =
              !excluded &&
              minMap[row.player_id] != null &&
              row.lineups === 0;
            return (
              <tr
                key={row.player_id}
                className="border-b"
                style={{
                  borderColor: snapshotTokens.border,
                  opacity: dimmed ? 0.72 : 1,
                  background: excluded
                    ? snapshotTokens.negativeLight
                    : forced
                      ? snapshotTokens.warningLight
                      : undefined,
                }}
              >
                <td className="py-2 pr-3">
                  <button
                    type="button"
                    className="text-left"
                    onClick={() => onSelectPlayer?.(row.player_id)}
                  >
                    <div
                      className="font-medium hover:underline"
                      style={{
                        color: snapshotTokens.textPrimary,
                        textDecoration: excluded
                          ? "line-through"
                          : undefined,
                      }}
                    >
                      {row.name}
                      {forced ? (
                        <span
                          className="ml-1 text-[10px] font-semibold uppercase tracking-wide"
                          style={{ color: snapshotTokens.warning }}
                        >
                          Force
                        </span>
                      ) : null}
                    </div>
                    <div
                      className="text-xs"
                      style={{ color: snapshotTokens.textMuted }}
                    >
                      {row.position}
                      {row.team ? ` · ${row.team}` : ""}
                      {row.opponent ? ` vs ${row.opponent}` : ""}
                    </div>
                  </button>
                  {!excluded && (
                    <ExposureBar
                      current={row.exposure}
                      min={minMap[row.player_id]}
                      max={
                        maxMap[row.player_id] ??
                        row.max_exposure ??
                        undefined
                      }
                    />
                  )}
                </td>
                <td
                  className="py-2 pr-3 tabular-nums"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {row.projection != null
                    ? Number(row.projection).toFixed(1)
                    : "—"}
                </td>
                <td
                  className="py-2 pr-3 tabular-nums"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {row.lineups}/{row.lineup_count}
                </td>
                <td
                  className="py-2 pr-3 font-semibold tabular-nums"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {row.exposure_pct.toFixed(0)}%
                </td>
                <td
                  className="py-2 pr-3 tabular-nums"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {Math.round(
                    (row.max_allowed_exposure ??
                      row.max_exposure ??
                      0) * 100
                  )}
                  %
                </td>
                <td
                  className="py-2 pr-3 tabular-nums"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {row.remaining_capacity ?? "—"}
                </td>
                {showCaptainLimits ? (
                  <>
                    <td
                      className="py-2 pr-3 tabular-nums"
                      style={{
                        color: snapshotTokens.textSecondary,
                      }}
                    >
                      {(row.captain_lineups ?? 0) > 0
                        ? `${(
                            row.captain_exposure_pct ?? 0
                          ).toFixed(0)}%`
                        : "—"}
                    </td>
                    <td className="py-2 pr-3">
                      <input
                        type="number"
                        min={0}
                        max={100}
                        disabled={excluded}
                        className="w-14 rounded border px-1.5 py-1 text-xs disabled:opacity-50"
                        style={{
                          borderColor: snapshotTokens.border,
                        }}
                        value={
                          captainMaxMap[row.player_id] != null
                            ? Math.round(
                                captainMaxMap[row.player_id] * 100
                              )
                            : ""
                        }
                        placeholder="—"
                        onChange={(event) => {
                          const raw = event.target.value;
                          if (raw === "") {
                            onCaptainMax?.(row.player_id, null);
                            return;
                          }
                          onCaptainMax?.(
                            row.player_id,
                            Math.max(
                              0,
                              Math.min(100, Number(raw))
                            ) / 100
                          );
                        }}
                      />
                    </td>
                  </>
                ) : null}
                <td
                  className="py-2 pr-3 tabular-nums"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {row.projected_ownership != null
                    ? `${Math.round(row.projected_ownership * 100)}%`
                    : "—"}
                </td>
                <td
                  className="py-2 pr-3 tabular-nums"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {row.ceiling?.toFixed(1) ?? "—"}
                </td>
                <td className="py-2 pr-3">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    disabled={excluded}
                    className="w-14 rounded border px-1.5 py-1 text-xs disabled:opacity-50"
                    style={{ borderColor: snapshotTokens.border }}
                    value={
                      minMap[row.player_id] != null
                        ? Math.round(minMap[row.player_id] * 100)
                        : ""
                    }
                    placeholder="—"
                    onChange={(event) => {
                      const raw = event.target.value;
                      if (raw === "") {
                        onMin(row.player_id, null);
                        return;
                      }
                      onMin(
                        row.player_id,
                        Math.max(0, Math.min(100, Number(raw))) /
                          100
                      );
                    }}
                  />
                </td>
                <td className="py-2 pr-3">
                  <input
                    type="number"
                    min={0}
                    max={100}
                    disabled={excluded}
                    className="w-14 rounded border px-1.5 py-1 text-xs disabled:opacity-50"
                    style={{ borderColor: snapshotTokens.border }}
                    value={
                      maxMap[row.player_id] != null
                        ? Math.round(maxMap[row.player_id] * 100)
                        : ""
                    }
                    placeholder="—"
                    onChange={(event) => {
                      const raw = event.target.value;
                      if (raw === "") {
                        onMax(row.player_id, null);
                        return;
                      }
                      onMax(
                        row.player_id,
                        Math.max(0, Math.min(100, Number(raw))) /
                          100
                      );
                    }}
                  />
                </td>
                <td className="py-2">
                  <div className="flex flex-wrap gap-1">
                    {excluded ? (
                      <button
                        type="button"
                        onClick={() => onInclude(row.player_id)}
                        className="rounded border px-1.5 py-0.5 text-[11px] font-semibold"
                        style={{
                          borderColor: snapshotTokens.success,
                          color: snapshotTokens.success,
                        }}
                      >
                        Include
                      </button>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() => onLock(row.player_id)}
                          className="rounded border px-1.5 py-0.5 text-[11px] font-semibold"
                          style={{
                            borderColor: locked
                              ? snapshotTokens.blue
                              : snapshotTokens.border,
                            color: locked
                              ? snapshotTokens.blue
                              : snapshotTokens.textSecondary,
                          }}
                        >
                          Lock
                        </button>
                        <button
                          type="button"
                          onClick={() => onExclude(row.player_id)}
                          className="rounded border px-1.5 py-0.5 text-[11px] font-semibold"
                          style={{
                            borderColor: snapshotTokens.border,
                            color: snapshotTokens.textSecondary,
                          }}
                        >
                          Exclude
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length === 0 && (
        <p
          className="py-6 text-center text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {emptyLabel}
        </p>
      )}
    </>
  );
}

function filterByPosition(
  rows: DfsPortfolioExposureRow[],
  positionFilter: string
): DfsPortfolioExposureRow[] {
  if (positionFilter === "All") {
    return rows;
  }
  return rows.filter((row) => {
    const pos = String(row.position || "").toUpperCase();
    if (positionFilter === "DST") {
      return pos === "DST" || pos === "DEF";
    }
    return pos === positionFilter;
  });
}

function mergeExposureRows({
  rows,
  slatePlayers,
  excludedIds,
  lockedIds,
  minMap,
  maxMap,
  captainMaxMap,
}: {
  rows: DfsPortfolioExposureRow[];
  slatePlayers: DfsPlayer[];
  excludedIds: Set<string>;
  lockedIds: Set<string>;
  minMap: Record<string, number>;
  maxMap: Record<string, number>;
  captainMaxMap: Record<string, number>;
}): DfsPortfolioExposureRow[] {
  const byId = new Map<string, DfsPortfolioExposureRow>();
  const lineupCount =
    rows[0]?.lineup_count ??
    rows[0]?.generated_lineup_count ??
    20;

  for (const row of rows) {
    byId.set(row.player_id, {
      ...row,
      excluded: excludedIds.has(row.player_id) || row.excluded,
      locked: lockedIds.has(row.player_id) || row.locked,
    });
  }

  const needed = new Set<string>([
    ...excludedIds,
    ...lockedIds,
    ...Object.keys(minMap),
    ...Object.keys(maxMap),
    ...Object.keys(captainMaxMap),
  ]);

  for (const player of slatePlayers) {
    const pid = player.player_id;
    if (!pid || !needed.has(pid) || byId.has(pid)) {
      continue;
    }
    byId.set(pid, {
      player_id: pid,
      name: player.name,
      position: player.position,
      team: player.team,
      opponent: player.opponent,
      projection: player.projection,
      ceiling: player.ceiling,
      floor: player.floor,
      projected_ownership: player.projected_ownership,
      salary: player.salary,
      lineups: 0,
      lineup_count: lineupCount,
      exposure: 0,
      exposure_pct: 0,
      captain_lineups: 0,
      captain_exposure: 0,
      captain_exposure_pct: 0,
      min_exposure: minMap[pid] ?? null,
      max_exposure: maxMap[pid] ?? null,
      locked: lockedIds.has(pid),
      excluded: excludedIds.has(pid),
    });
  }

  return Array.from(byId.values()).sort((a, b) => {
    const aEx = excludedIds.has(a.player_id) ? 1 : 0;
    const bEx = excludedIds.has(b.player_id) ? 1 : 0;
    if (aEx !== bEx) {
      return aEx - bEx;
    }
    if (b.exposure !== a.exposure) {
      return b.exposure - a.exposure;
    }
    return String(a.name || "").localeCompare(String(b.name || ""));
  });
}

function ExposureBar({
  current,
  min,
  max,
}: {
  current: number;
  min?: number;
  max?: number;
}) {
  const pct = Math.max(0, Math.min(100, current * 100));
  const minPct =
    min != null ? Math.max(0, Math.min(100, min * 100)) : null;
  const maxPct =
    max != null ? Math.max(0, Math.min(100, max * 100)) : null;

  return (
    <div className="relative mt-1.5 h-1.5 w-40 max-w-full rounded-full bg-slate-100">
      <div
        className="absolute inset-y-0 left-0 rounded-full"
        style={{
          width: `${pct}%`,
          background: snapshotTokens.blue,
        }}
      />
      {minPct != null && (
        <span
          className="absolute top-1/2 h-2.5 w-0.5 -translate-y-1/2"
          style={{
            left: `${minPct}%`,
            background: snapshotTokens.textMuted,
          }}
          title={`Min ${Math.round(minPct)}%`}
        />
      )}
      {maxPct != null && (
        <span
          className="absolute top-1/2 h-2.5 w-0.5 -translate-y-1/2"
          style={{
            left: `${maxPct}%`,
            background: snapshotTokens.warning,
          }}
          title={`Max ${Math.round(maxPct)}%`}
        />
      )}
    </div>
  );
}
