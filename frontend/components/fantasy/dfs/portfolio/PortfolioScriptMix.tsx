"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import type { DfsPortfolioGameScripts } from "@/services/api";

interface Props {
  gameScripts: DfsPortfolioGameScripts | null | undefined;
}

export default function PortfolioScriptMix({ gameScripts }: Props) {
  if (!gameScripts?.allocations?.length) {
    return null;
  }

  const favorite = gameScripts.favorite || "Favorite";
  const underdog = gameScripts.underdog || "Underdog";

  return (
    <section
      className="rounded-[10px] border px-3 py-2.5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3
          className="text-sm font-semibold"
          style={{ color: snapshotTokens.navy }}
        >
          Script Mix
        </h3>
        <p
          className="text-[11px]"
          style={{ color: snapshotTokens.textMuted }}
        >
          {favorite} vs {underdog} · weights sum to 100%
        </p>
      </div>

      <div className="mt-2 overflow-x-auto">
        <table className="min-w-full text-left text-xs">
          <thead>
            <tr
              className="border-b text-[10px] uppercase tracking-wide"
              style={{
                borderColor: snapshotTokens.border,
                color: snapshotTokens.textMuted,
              }}
            >
              <th className="py-1 pr-2 font-semibold">Script</th>
              <th className="py-1 pr-2 font-semibold">Weight</th>
              <th className="py-1 pr-2 font-semibold">Lineups</th>
              <th className="py-1 font-semibold min-w-[5rem]">Mix</th>
            </tr>
          </thead>
          <tbody>
            {gameScripts.allocations.map((row) => {
              const pct = Math.round(row.weight * 100);
              const target =
                typeof row.target_lineup_count === "number"
                  ? row.target_lineup_count
                  : null;
              return (
                <tr
                  key={row.script_id}
                  className="border-b last:border-0"
                  style={{ borderColor: snapshotTokens.border }}
                  title={row.implication || undefined}
                >
                  <td className="py-1.5 pr-2">
                    <span
                      className="font-semibold tabular-nums"
                      style={{ color: snapshotTokens.textPrimary }}
                    >
                      {row.code || "—"}
                    </span>
                    <span
                      className="ml-1.5"
                      style={{ color: snapshotTokens.textSecondary }}
                    >
                      {row.label || row.script_id}
                    </span>
                  </td>
                  <td
                    className="py-1.5 pr-2 font-semibold tabular-nums"
                    style={{ color: snapshotTokens.blue }}
                  >
                    {pct}%
                  </td>
                  <td
                    className="py-1.5 pr-2 tabular-nums"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    {row.lineup_count}
                    {target != null && target !== row.lineup_count
                      ? ` / ${target}`
                      : ""}
                  </td>
                  <td className="py-1.5">
                    <div
                      className="h-1.5 overflow-hidden rounded-full"
                      style={{ background: snapshotTokens.divider }}
                    >
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${Math.max(2, Math.min(100, pct))}%`,
                          background: snapshotTokens.blue,
                        }}
                      />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
