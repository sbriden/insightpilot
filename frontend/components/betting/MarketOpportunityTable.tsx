"use client";

import {
  formatMarketValue,
  formatModelValue,
} from "@/components/betting/formatMarketValues";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import { BettingMarket } from "@/services/api";

interface Props {
  markets: BettingMarket[];
  onSelect: (market: BettingMarket) => void;
}

export default function MarketOpportunityTable({
  markets,
  onSelect,
}: Props) {
  if (!markets.length) {
    return (
      <div
        className="rounded-xl border bg-white px-4 py-8 text-center text-sm"
        style={{
          borderColor: snapshotTokens.border,
          color: snapshotTokens.textMuted,
        }}
      >
        No markets match the current filters.
      </div>
    );
  }

  return (
    <div
      className="overflow-hidden rounded-xl border bg-white"
      style={{ borderColor: snapshotTokens.border }}
    >
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead
            style={{
              background: snapshotTokens.background,
              color: snapshotTokens.textMuted,
            }}
          >
            <tr className="text-[11px] uppercase tracking-[0.12em]">
              <th className="px-3 py-2.5 font-semibold">Game</th>
              <th className="px-3 py-2.5 font-semibold">Market</th>
              <th className="px-3 py-2.5 font-semibold">Selection</th>
              <th className="px-3 py-2.5 font-semibold text-right">
                Market
              </th>
              <th className="px-3 py-2.5 font-semibold text-right">
                Model
              </th>
              <th className="px-3 py-2.5 font-semibold text-right">
                Edge
              </th>
              <th className="px-3 py-2.5 font-semibold">
                Confidence
              </th>
              <th className="min-w-[280px] px-3 py-2.5 font-semibold">
                Opportunity
              </th>
            </tr>
          </thead>
          <tbody>
            {markets.map((market) => (
              <tr
                key={market.market_id}
                className="group cursor-pointer border-t transition-colors hover:bg-[#EAF3FF]"
                style={{ borderColor: snapshotTokens.divider }}
                onClick={() => onSelect(market)}
                title="View market analysis"
              >
                <td
                  className="px-3 py-2.5 font-medium"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {market.event_label || "—"}
                </td>
                <td
                  className="px-3 py-2.5 capitalize"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {market.market_type}
                </td>
                <td
                  className="px-3 py-2.5"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {market.selection}
                </td>
                <td
                  className="px-3 py-2.5 text-right tabular-nums"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {formatMarketValue(market)}
                </td>
                <td
                  className="px-3 py-2.5 text-right tabular-nums"
                  style={{ color: snapshotTokens.textPrimary }}
                >
                  {formatModelValue(market)}
                </td>
                <td
                  className="px-3 py-2.5 text-right tabular-nums font-medium"
                  style={{
                    color: edgeColor(market.edge),
                  }}
                >
                  {formatEdge(market)}
                </td>
                <td
                  className="px-3 py-2.5"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  {market.confidence || "—"}
                </td>
                <td
                  className="max-w-md px-3 py-2.5 text-xs leading-relaxed"
                  style={{ color: snapshotTokens.textSecondary }}
                >
                  <span className="inline-flex items-start gap-2">
                    <span className="min-w-0 flex-1">
                      {market.opportunity || "—"}
                    </span>
                    <span
                      className="shrink-0 pt-0.5 text-[11px] font-medium opacity-0 transition-opacity group-hover:opacity-100"
                      style={{ color: snapshotTokens.blue }}
                    >
                      Open →
                    </span>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatEdge(market: BettingMarket): string {
  if (market.edge == null) return "—";
  const value = market.edge;
  const suffix =
    market.market_type === "moneyline" ? "%" : "";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}${suffix}`;
}

function edgeColor(edge: number | null | undefined): string {
  if (edge == null) return snapshotTokens.textMuted;
  if (edge > 0.5) return snapshotTokens.success;
  if (edge < -0.5) return snapshotTokens.negative;
  return snapshotTokens.textSecondary;
}
