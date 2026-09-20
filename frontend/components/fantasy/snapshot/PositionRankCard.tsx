"use client";

import { FantasyPlayerSnapshot } from "@/services/api";

import { snapshotTokens } from "./tokens";

export default function PositionRankCard({
  active,
}: {
  active: FantasyPlayerSnapshot;
}) {
  const rows = [
    {
      label: active.position || "Pos",
      rank: active.position_rank,
      pool: active.position_pool_size,
    },
    {
      label: "Overall",
      rank: active.overall_rank,
      pool: active.overall_pool_size,
    },
  ];

  return (
    <section
      className="rounded-[10px] border bg-white p-4 sm:p-5"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-[15px] font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        Position Rank
      </h3>
      <p
        className="mt-1 text-xs"
        style={{ color: snapshotTokens.textSecondary }}
      >
        Season PPR fantasy points ranking
      </p>
      <div className="mt-3 space-y-2">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex items-center justify-between rounded-lg border px-3 py-2.5"
            style={{
              borderColor: snapshotTokens.divider,
              background: snapshotTokens.background,
            }}
          >
            <span
              className="text-sm font-medium"
              style={{ color: snapshotTokens.textSecondary }}
            >
              {row.label}
            </span>
            <span
              className="text-lg font-bold tabular-nums"
              style={{ color: snapshotTokens.navy }}
            >
              {row.rank != null ? `#${row.rank}` : "—"}
              {row.pool != null && (
                <span
                  className="ml-1 text-xs font-medium"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  / {row.pool}
                </span>
              )}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
