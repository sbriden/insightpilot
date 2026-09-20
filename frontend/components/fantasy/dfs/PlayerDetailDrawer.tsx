"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type { DfsPlayer } from "@/services/api";

interface Props {
  player: DfsPlayer | null;
  inLineup: boolean;
  locked: boolean;
  excluded: boolean;
  onClose: () => void;
  onAdd: () => void;
  onLock: () => void;
  onExclude: () => void;
  onOpenOverview: () => void;
}

export default function PlayerDetailDrawer({
  player,
  inLineup,
  locked,
  excluded,
  onClose,
  onAdd,
  onLock,
  onExclude,
  onOpenOverview,
}: Props) {
  if (!player) {
    return null;
  }

  const why =
    player.signals?.map((signal) => signal.label).join(" · ")
    || player.primary_signal?.label
    || "Stable role with usable projection.";

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-black/30"
        aria-label="Close drawer"
        onClick={onClose}
      />
      <aside
        className="relative z-10 flex h-full w-full max-w-md flex-col overflow-auto border-l bg-white shadow-xl"
        style={{ borderColor: snapshotTokens.border }}
      >
        <div
          className="flex items-start justify-between gap-3 border-b px-4 py-4"
          style={{ borderColor: snapshotTokens.divider }}
        >
          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-wide"
              style={{ color: snapshotTokens.textMuted }}
            >
              {player.position} · {player.team || "FA"}
            </p>
            <h3
              className="mt-1 text-lg font-semibold"
              style={{ color: snapshotTokens.navy }}
            >
              {player.name}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-sm"
            style={{ color: snapshotTokens.textMuted }}
          >
            Close
          </button>
        </div>

        <div className="space-y-4 p-4">
          <div className="grid grid-cols-3 gap-2">
            <Stat label="Projection" value={player.projection.toFixed(1)} />
            <Stat
              label="Ceiling"
              value={player.ceiling?.toFixed(1) ?? "—"}
            />
            <Stat
              label="Floor"
              value={player.floor?.toFixed(1) ?? "—"}
            />
            <Stat
              label="Salary"
              value={`$${player.salary.toLocaleString()}`}
            />
            <Stat
              label="Ownership"
              value={
                player.projected_ownership != null
                  ? `${(player.projected_ownership * 100).toFixed(0)}%`
                  : "—"
              }
            />
            <Stat
              label="Value"
              value={player.value?.toFixed(2) ?? "—"}
            />
          </div>

          <div>
            <p
              className="text-[11px] font-semibold uppercase tracking-wide"
              style={{ color: snapshotTokens.textMuted }}
            >
              Why InsightPilot likes him
            </p>
            <p
              className="mt-1 text-sm"
              style={{ color: snapshotTokens.textSecondary }}
            >
              {why}
              {player.matchup_label
                ? ` Matchup: ${player.matchup_label}.`
                : ""}
            </p>
          </div>

          {(player.injury_status || excluded) && (
            <div
              className="rounded-lg border px-3 py-2 text-sm"
              style={{
                borderColor: snapshotTokens.warning,
                color: snapshotTokens.textSecondary,
              }}
            >
              {excluded
                ? "Player is excluded from optimization."
                : `Status: ${player.injury_status}`}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={inLineup}
              onClick={onAdd}
              className="rounded-lg px-3 py-2 text-sm font-semibold text-white disabled:opacity-40"
              style={{ background: snapshotTokens.blue }}
            >
              {inLineup ? "In lineup" : "Add to lineup"}
            </button>
            <button
              type="button"
              onClick={onLock}
              className="rounded-lg border px-3 py-2 text-sm font-semibold"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textPrimary,
              }}
            >
              {locked ? "Unlock" : "Lock"}
            </button>
            <button
              type="button"
              onClick={onExclude}
              className="rounded-lg border px-3 py-2 text-sm"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.negative,
              }}
            >
              {excluded ? "Un-exclude" : "Exclude"}
            </button>
            <button
              type="button"
              onClick={onOpenOverview}
              className="rounded-lg border px-3 py-2 text-sm"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.blue,
              }}
            >
              View Player Overview
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}

function Stat({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div
      className="rounded-lg border px-2.5 py-2"
      style={{ borderColor: snapshotTokens.divider }}
    >
      <p
        className="text-[10px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        {label}
      </p>
      <p
        className="mt-1 text-sm font-semibold tabular-nums"
        style={{ color: snapshotTokens.navy }}
      >
        {value}
      </p>
    </div>
  );
}
