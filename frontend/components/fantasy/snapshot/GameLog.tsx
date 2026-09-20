"use client";

import { PlayerGameMetrics } from "@/services/api";

import {
  formatMetricValue,
  snapshotTokens,
} from "./tokens";

interface Props {
  games: PlayerGameMetrics[];
  position?: string | null;
}

function columnsForPosition(position?: string | null) {
  const pos = (position || "").toUpperCase();
  if (pos === "QB") {
    return [
      { key: "pass_yards", label: "Pass Yds", bucket: "production" as const },
      { key: "pass_tds", label: "Pass TD", bucket: "production" as const },
      { key: "rush_yards", label: "Rush Yds", bucket: "production" as const },
      { key: "fantasy_points", label: "FPTS", bucket: "production" as const },
    ];
  }
  if (pos === "RB" || pos === "FB" || pos === "HB") {
    return [
      { key: "rush_yards", label: "Rush Yds", bucket: "production" as const },
      { key: "receiving_yards", label: "Rec Yds", bucket: "production" as const },
      { key: "total_tds", label: "TD", bucket: "production" as const },
      { key: "fantasy_points", label: "FPTS", bucket: "production" as const },
    ];
  }
  if (pos === "K" || pos === "PK") {
    return [
      { key: "fg_made", label: "FG", bucket: "production" as const },
      { key: "fg_att", label: "FGA", bucket: "production" as const },
      { key: "fg_made_50_plus", label: "50+", bucket: "production" as const },
      { key: "pat_made", label: "XP", bucket: "production" as const },
      { key: "fantasy_points", label: "FPTS", bucket: "production" as const },
    ];
  }
  if (pos === "DEF" || pos === "DST") {
    return [
      { key: "points_allowed", label: "PA", bucket: "production" as const },
      { key: "sacks", label: "Sack", bucket: "production" as const },
      { key: "interceptions", label: "INT", bucket: "production" as const },
      { key: "fumbles_recovered", label: "FR", bucket: "production" as const },
      { key: "fantasy_points", label: "FPTS", bucket: "production" as const },
    ];
  }
  return [
    { key: "targets", label: "Tgt", bucket: "production" as const },
    { key: "receptions", label: "Rec", bucket: "production" as const },
    { key: "receiving_yards", label: "Rec Yds", bucket: "production" as const },
    { key: "fantasy_points", label: "FPTS", bucket: "production" as const },
  ];
}

export default function GameLog({
  games,
  position,
}: Props) {
  const columns = columnsForPosition(position);
  // Show newest first
  const rows = [...games].reverse().slice(0, 5);

  return (
    <section
      className="rounded-[10px] border bg-white p-4 sm:p-5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-[15px] font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Recent Game Log
      </h3>
      <p
        className="mt-1 text-xs"
        style={{ color: snapshotTokens.textSecondary }}
      >
        Last {rows.length || 5} games · factual box score
      </p>

      {rows.length === 0 ? (
        <p
          className="mt-4 text-sm"
          style={{ color: snapshotTokens.textSecondary }}
        >
          No recent games available for this player yet.
        </p>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr
                className="border-b text-[11px] uppercase tracking-wide"
                style={{
                  borderColor: snapshotTokens.divider,
                  color: snapshotTokens.textMuted,
                }}
              >
                <th className="py-2 pr-3 font-medium">Week</th>
                <th className="px-2 py-2 font-medium">Opp</th>
                {columns.map((column) => (
                  <th
                    key={column.key}
                    className="px-2 py-2 text-right font-medium"
                  >
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((game) => (
                <tr
                  key={`${game.season}-${game.week}`}
                  className="border-b last:border-0"
                  style={{ borderColor: snapshotTokens.divider }}
                >
                  <td
                    className="py-2.5 pr-3 font-medium"
                    style={{ color: snapshotTokens.textPrimary }}
                  >
                    {game.label || `W${game.week}`}
                  </td>
                  <td
                    className="px-2 py-2.5"
                    style={{ color: snapshotTokens.textSecondary }}
                  >
                    {game.opponent_label
                      || game.opponent
                      || "—"}
                  </td>
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className="px-2 py-2.5 text-right tabular-nums font-semibold"
                      style={{
                        color: snapshotTokens.textPrimary,
                      }}
                    >
                      {formatMetricValue(
                        game[column.bucket]?.[column.key]
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
