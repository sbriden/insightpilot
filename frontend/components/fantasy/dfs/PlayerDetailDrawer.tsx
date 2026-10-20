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

function ProjectionBreakdown({ player }: { player: DfsPlayer }) {
  const parts = (player.scoring_components?.components ?? []).filter(
    (part) => Math.abs(part.points ?? 0) >= 0.05,
  );
  if (parts.length === 0) {
    return null;
  }
  return (
    <div>
      <p
        className="text-[11px] font-semibold uppercase tracking-wide"
        style={{ color: snapshotTokens.textMuted }}
      >
        Projection breakdown
      </p>
      <ul className="mt-1 space-y-1">
        {parts.map((part) => (
          <li
            key={part.key}
            className="flex items-baseline justify-between gap-3 text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            <span>
              {part.label}
              {part.stat != null ? (
                <span className="text-xs">
                  {" "}
                  {part.stat.toFixed(1)} {part.stat_label}
                  {part.opportunities != null && part.rate != null
                    ? ` · ${part.opportunities.toFixed(1)} ${part.opportunity_label} × ${part.rate.toFixed(2)}`
                    : ""}
                </span>
              ) : null}
            </span>
            <span className="tabular-nums">
              {(part.points ?? 0) > 0 ? "+" : ""}
              {(part.points ?? 0).toFixed(1)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
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
              label={
                player.simulation?.ceiling_percentile
                  ? `Ceiling (p${player.simulation.ceiling_percentile})`
                  : "Ceiling"
              }
              value={player.ceiling?.toFixed(1) ?? "—"}
            />
            <Stat
              label={
                player.simulation?.floor_percentile
                  ? `Floor (p${player.simulation.floor_percentile})`
                  : "Floor"
              }
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

          {player.simulation?.upside_probability != null &&
          player.simulation?.bust_probability != null ? (
            <p
              className="text-xs leading-snug"
              style={{ color: snapshotTokens.textSecondary }}
            >
              {`In the simulated games, ${(player.simulation.upside_probability * 100).toFixed(0)}% clear ${player.simulation.upside_threshold?.toFixed(1)} and ${(player.simulation.bust_probability * 100).toFixed(0)}% fall under ${player.simulation.bust_threshold?.toFixed(1)}. The floor and ceiling are percentiles, not guarantees.`}
            </p>
          ) : null}

          {player.forecast?.strong_outcome_probability != null ? (
            <p
              className="text-xs leading-snug"
              style={{ color: snapshotTokens.textSecondary }}
            >
              {`${(player.forecast.strong_outcome_probability * 100).toFixed(0)}% of simulated games reach ${player.forecast.strong_outcome_threshold?.toFixed(0)} points. Mean ${player.forecast.expected_points?.toFixed(1) ?? "—"}, median ${player.forecast.median_projection?.toFixed(1) ?? "—"}.`}
            </p>
          ) : null}

          {(player.raw_projection != null ||
            player.base_projection != null ||
            player.projection_adjustment != null ||
            player.opponent) && (
            <div
              className="rounded-lg border px-3 py-2 text-sm"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textSecondary,
              }}
            >
              {player.opponent
                ? `vs ${player.opponent}`
                : "No opponent this week"}
              {player.matchup_label
                ? ` · ${player.matchup_label}`
                : ""}
              {player.raw_projection != null
                ? ` · raw ${player.raw_projection.toFixed(1)}`
                : ""}
              {player.insightpilot_projection != null
                ? ` → IP ${player.insightpilot_projection.toFixed(1)}`
                : player.base_projection != null
                  ? ` → IP ${player.base_projection.toFixed(1)}`
                  : ""}
              {player.projection_adjustment != null &&
              Math.abs(player.projection_adjustment) >= 0.1
                ? ` (${player.projection_adjustment > 0 ? "+" : ""}${player.projection_adjustment.toFixed(1)})`
                : ""}
              {player.projection_confidence
                ? ` · ${player.projection_confidence} confidence`
                : ""}
              {player.environment_score != null
                ? ` · env ${Math.round(player.environment_score)}`
                : ""}
              {player.projection_adjustment_reason ? (
                <p className="mt-1.5 text-xs leading-snug">
                  {player.projection_adjustment_reason}
                </p>
              ) : null}
              {player.projection_environment_reason ? (
                <p className="mt-1.5 text-xs leading-snug">
                  {player.projection_environment_reason}
                </p>
              ) : null}
            </div>
          )}

          <ProjectionBreakdown player={player} />

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
