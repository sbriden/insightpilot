"use client";

import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import TeamLogo from "@/components/teams/TeamLogo";
import type { DfsPortfolioSignal } from "@/services/api";

interface InsightPlayerRow {
  player_id?: string;
  name?: string | null;
  team?: string | null;
  exposure_pct: number;
}

interface Props {
  signals: DfsPortfolioSignal[];
  core?: InsightPlayerRow[];
  differentiators?: InsightPlayerRow[];
  similarPairs?: Array<{
    index_a?: number;
    index_b?: number;
    shared_players: number;
    roster_size: number;
    similarity: number;
  }>;
  /** When true, omit outer card chrome (parent tabs own it). */
  embedded?: boolean;
}

export default function PortfolioInsights({
  signals,
  core,
  differentiators,
  similarPairs,
  embedded = false,
}: Props) {
  const body = (
      <div className={embedded ? "grid gap-4 lg:grid-cols-3" : "mt-3 grid gap-4 lg:grid-cols-3"}>
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Signals
          </p>
          <ul className="mt-2 space-y-2">
            {signals.length === 0 && (
              <li
                className="text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                Generate a portfolio to see structured insights.
              </li>
            )}
            {signals.map((signal) => (
              <li
                key={signal.id}
                className="rounded-md border px-3 py-2 text-sm"
                style={{
                  borderColor: snapshotTokens.border,
                  color: snapshotTokens.textSecondary,
                }}
              >
                <span
                  className="block text-[10px] font-semibold uppercase tracking-wide"
                  style={{ color: snapshotTokens.textMuted }}
                >
                  {signal.type.replace(/_/g, " ")}
                </span>
                {signal.explanation}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Portfolio Core
          </p>
          <ul className="mt-2 space-y-1.5">
            {(core ?? []).length === 0 && (
              <li
                className="text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                No core players yet.
              </li>
            )}
            {(core ?? []).map((item) => (
              <InsightPlayerListItem
                key={`${item.name}-${item.exposure_pct}`}
                item={item}
              />
            ))}
          </ul>
          <p
            className="mt-3 text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Differentiators
          </p>
          <ul className="mt-2 space-y-1.5">
            {(differentiators ?? []).length === 0 && (
              <li
                className="text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                No low-exposure differentiators yet.
              </li>
            )}
            {(differentiators ?? []).map((item) => (
              <InsightPlayerListItem
                key={`${item.name}-${item.exposure_pct}`}
                item={item}
              />
            ))}
          </ul>
        </div>

        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-wide"
            style={{ color: snapshotTokens.textMuted }}
          >
            Most Similar Lineups
          </p>
          <ul className="mt-2 space-y-2">
            {(similarPairs ?? []).length === 0 && (
              <li
                className="text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                Similarity pairs appear after generation.
              </li>
            )}
            {(similarPairs ?? []).map((pair) => (
              <li
                key={`${pair.index_a}-${pair.index_b}`}
                className="text-sm"
                style={{ color: snapshotTokens.textSecondary }}
              >
                Lineup {pair.index_a} ↔ Lineup {pair.index_b}
                <span className="block text-xs">
                  {pair.shared_players} / {pair.roster_size}{" "}
                  players shared (
                  {Math.round(pair.similarity * 100)}%)
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
  );

  if (embedded) {
    return body;
  }

  return (
    <section
      className="rounded-[10px] border p-4"
      style={{ borderColor: snapshotTokens.border }}
    >
      <h3
        className="text-sm font-semibold"
        style={{ color: snapshotTokens.navy }}
      >
        InsightPilot Portfolio Insights
      </h3>
      {body}
    </section>
  );
}

function InsightPlayerListItem({ item }: { item: InsightPlayerRow }) {
  return (
    <li
      className="flex items-center justify-between gap-2 text-sm"
      style={{ color: snapshotTokens.textPrimary }}
    >
      <span className="flex min-w-0 items-center gap-1.5">
        <TeamLogo abbreviation={item.team} size={16} />
        <span className="truncate">{item.name}</span>
      </span>
      <span className="shrink-0 tabular-nums">
        {item.exposure_pct.toFixed(0)}%
      </span>
    </li>
  );
}
