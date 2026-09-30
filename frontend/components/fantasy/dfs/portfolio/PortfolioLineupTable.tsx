"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type { DfsPortfolioLineup } from "@/services/api";

interface Props {
  lineups: DfsPortfolioLineup[];
  selectedId: string | null;
  changedIds?: Set<string>;
  onSelect: (lineupId: string) => void;
  /** Match height of the optimal lineup panel; overflow scrolls. */
  maxHeight?: number | null;
}

export default function PortfolioLineupTable({
  lineups,
  selectedId,
  changedIds,
  onSelect,
  maxHeight,
}: Props) {
  return (
    <section
      className="flex min-h-0 flex-col overflow-hidden rounded-[10px] border"
      style={{
        borderColor: snapshotTokens.border,
        maxHeight: maxHeight && maxHeight > 0 ? maxHeight : undefined,
      }}
    >
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b px-4 py-3"
        style={{ borderColor: snapshotTokens.border }}
      >
        <h3
          className="text-sm font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          Generated Lineups
        </h3>
        {changedIds && changedIds.size > 0 && (
          <p
            className="text-xs font-semibold"
            style={{ color: snapshotTokens.warning }}
          >
            {changedIds.size} lineup
            {changedIds.size === 1 ? "" : "s"} changed
          </p>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-4 pb-3">
        <table className="min-w-full text-left text-sm">
          <thead className="sticky top-0 z-[1]" style={{ background: "#fff" }}>
            <tr
              className="border-b text-[11px] uppercase tracking-wide"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textMuted,
              }}
            >
              <th className="py-2 pr-3 font-semibold">#</th>
              <th className="py-2 pr-3 font-semibold">Script</th>
              <th className="py-2 pr-3 font-semibold">Projection</th>
              <th className="py-2 pr-3 font-semibold">Ceiling</th>
              <th className="py-2 pr-3 font-semibold">Ownership</th>
              <th className="py-2 pr-3 font-semibold">Salary</th>
              <th className="py-2 pr-3 font-semibold">Similarity</th>
              <th className="py-2 font-semibold">Strategy</th>
            </tr>
          </thead>
          <tbody>
            {lineups.map((lineup, index) => {
              const id = lineup.lineup_id;
              const active = selectedId === id;
              const changed = changedIds?.has(id) ?? false;
              return (
                <tr
                  key={id}
                  onClick={() => onSelect(id)}
                  className="cursor-pointer border-b"
                  style={{
                    borderColor: snapshotTokens.border,
                    background: active
                      ? snapshotTokens.blueLight
                      : changed
                        ? "rgba(245, 158, 11, 0.08)"
                        : "transparent",
                  }}
                >
                  <td
                    className="py-2 pr-3 font-semibold tabular-nums"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    <span className="inline-flex items-center gap-1.5">
                      {lineup.portfolio_index ?? index + 1}
                      {changed && (
                        <span
                          className="rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
                          style={{
                            background: snapshotTokens.warningLight,
                            color: snapshotTokens.warning,
                          }}
                        >
                          Changed
                        </span>
                      )}
                    </span>
                  </td>
                  <td
                    className="py-2 pr-3"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    {lineup.game_script_code || lineup.game_script_label ? (
                      <span title={lineup.game_script_implication || undefined}>
                        <span
                          className="font-semibold"
                          style={{ color: snapshotTokens.textPrimary }}
                        >
                          {lineup.game_script_code || "—"}
                        </span>
                        {lineup.game_script_label ? (
                          <span className="ml-1 text-xs">
                            {lineup.game_script_label}
                          </span>
                        ) : null}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td
                    className="py-2 pr-3 tabular-nums"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {lineup.projected_points.toFixed(1)}
                  </td>
                  <td
                    className="py-2 pr-3 tabular-nums"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    {lineup.projected_ceiling?.toFixed(1) ?? "—"}
                  </td>
                  <td
                    className="py-2 pr-3 tabular-nums"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    {lineup.projected_ownership != null
                      ? `${Math.round(lineup.projected_ownership)}%`
                      : "—"}
                  </td>
                  <td
                    className="py-2 pr-3 tabular-nums"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    ${lineup.salary_used.toLocaleString()}
                  </td>
                  <td
                    className="py-2 pr-3 tabular-nums"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    {lineup.similarity != null
                      ? `${Math.round(lineup.similarity * 100)}%`
                      : "—"}
                  </td>
                  <td
                    className="py-2 capitalize"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    {lineup.strategy || "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {lineups.length === 0 && (
          <p
            className="py-6 text-center text-sm"
            style={{ color: snapshotTokens.textSecondary }}
          >
            No lineups yet. Generate a portfolio to populate this
            table.
          </p>
        )}
      </div>
    </section>
  );
}
