"use client";

import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import type { ReactNode } from "react";

import GameScriptsPanel from "@/components/betting/GameScriptsPanel";
import {
  formatMarketValue,
  formatModelValue,
  modelSpreadOnSelection,
} from "@/components/betting/formatMarketValues";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import { BettingEvent, BettingMarket } from "@/services/api";

interface Props {
  event: BettingEvent;
  markets: BettingMarket[];
  onOpen: () => void;
  onSelectMarket?: (market: BettingMarket) => void;
}

export default function BettingGameCard({
  event,
  markets,
  onOpen,
  onSelectMarket,
}: Props) {
  const signal = event.primary_signal;
  const lines = orderMarkets(markets);

  return (
    <div
      className="rounded-xl border bg-white p-4 text-left transition-shadow hover:shadow-sm"
      style={{ borderColor: snapshotTokens.border }}
    >
      <button
        type="button"
        onClick={onOpen}
        className="w-full text-left"
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <p
              className="text-base font-semibold"
              style={{ color: snapshotTokens.textPrimary }}
            >
              {event.label}
            </p>
            <p
              className="mt-0.5 text-xs"
              style={{ color: snapshotTokens.textMuted }}
            >
              {formatStart(event.start_time)}
            </p>
          </div>
          {signal?.label ? (
            <span
              className="rounded-md px-2 py-1 text-[11px] font-medium"
              style={{
                background: snapshotTokens.blueLight,
                color: snapshotTokens.blue,
              }}
            >
              {signal.label}
            </span>
          ) : null}
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <ScoreBlock
            team={event.away_team || "Away"}
            projected={event.projected_away_score}
          />
          <ScoreBlock
            team={event.home_team || "Home"}
            projected={event.projected_home_score}
          />
        </div>
      </button>

      <div
        className="mt-4 space-y-2 border-t pt-3"
        style={{ borderColor: snapshotTokens.divider }}
      >
        {lines.length ? (
          lines.map((market) => (
            <MarketLineRow
              key={market.market_id}
              market={market}
              onSelect={
                onSelectMarket
                  ? () => onSelectMarket(market)
                  : onOpen
              }
            />
          ))
        ) : (
          <p
            className="text-xs"
            style={{ color: snapshotTokens.textMuted }}
          >
            No market lines available for this game.
          </p>
        )}
      </div>

      {(event.game_scripts?.length ?? 0) > 0 ? (
        <div
          className="mt-4 border-t pt-3"
          style={{ borderColor: snapshotTokens.divider }}
        >
          <GameScriptsPanel
            scripts={event.game_scripts ?? []}
            compact
          />
        </div>
      ) : null}

      {injurySummary(event) ? (
        <p
          className="mt-3 text-xs"
          style={{ color: snapshotTokens.textSecondary }}
        >
          {injurySummary(event)}
        </p>
      ) : null}
    </div>
  );
}

function MarketLineRow({
  market,
  onSelect,
}: {
  market: BettingMarket;
  onSelect: () => void;
}) {
  const opportunity = opportunityState(market);
  return (
    <button
      type="button"
      onClick={onSelect}
      title="View market analysis"
      className="group flex w-full cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition-all hover:-translate-y-px hover:border-[#9EC5FE] hover:shadow-sm"
      style={{
        borderColor: opportunity.border,
        background: opportunity.background,
      }}
      onMouseEnter={(event) => {
        event.currentTarget.style.background = snapshotTokens.blueLight;
        event.currentTarget.style.borderColor = "#9EC5FE";
      }}
      onMouseLeave={(event) => {
        event.currentTarget.style.background = opportunity.background;
        event.currentTarget.style.borderColor = opportunity.border;
      }}
    >
      <span
        className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-transform group-hover:scale-110"
        style={{
          background: opportunity.iconBg,
          color: opportunity.color,
        }}
        aria-hidden
      >
        {opportunity.icon}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.12em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            {market.market_type}
          </p>
          <p
            className="text-[11px] font-medium tabular-nums"
            style={{ color: opportunity.color }}
          >
            {formatDiff(market)}
          </p>
        </div>
        <div
          className="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-xs"
          style={{ color: snapshotTokens.textSecondary }}
        >
          <span
            className="font-medium tabular-nums"
            style={{ color: snapshotTokens.textPrimary }}
          >
            {market.selection}
          </span>
          <span>Market {formatMarketValue(market)}</span>
          <span>Model {formatModelValue(market)}</span>
        </div>
      </div>
      <span
        className="shrink-0 text-[11px] font-medium opacity-0 transition-opacity group-hover:opacity-100"
        style={{ color: snapshotTokens.blue }}
      >
        Open →
      </span>
    </button>
  );
}

function ScoreBlock({
  team,
  projected,
}: {
  team: string;
  projected?: number | null;
}) {
  return (
    <div>
      <p
        className="text-xs font-semibold uppercase tracking-[0.12em]"
        style={{ color: snapshotTokens.textMuted }}
      >
        {team}
      </p>
      <p
        className="mt-1 text-lg font-semibold tabular-nums"
        style={{ color: snapshotTokens.textPrimary }}
      >
        {projected != null ? projected.toFixed(1) : "—"}
      </p>
      <p
        className="text-[11px]"
        style={{ color: snapshotTokens.textMuted }}
      >
        projected
      </p>
    </div>
  );
}

function orderMarkets(markets: BettingMarket[]): BettingMarket[] {
  const rank: Record<string, number> = {
    spread: 0,
    total: 1,
    moneyline: 2,
  };
  return [...markets].sort(
    (a, b) =>
      (rank[a.market_type] ?? 99) - (rank[b.market_type] ?? 99)
  );
}

function opportunityState(market: BettingMarket): {
  icon: ReactNode;
  color: string;
  background: string;
  border: string;
  iconBg: string;
} {
  const score = opportunityScore(market);

  if (score != null && score >= 1.5) {
    return {
      icon: <ArrowUp className="h-3.5 w-3.5" strokeWidth={2.5} />,
      color: snapshotTokens.success,
      background: snapshotTokens.successLight,
      border: "#B7E4C7",
      iconBg: "#D8F3E3",
    };
  }
  if (score != null && score <= -1.5) {
    return {
      icon: <ArrowDown className="h-3.5 w-3.5" strokeWidth={2.5} />,
      color: snapshotTokens.negative,
      background: snapshotTokens.negativeLight,
      border: "#F5C2C2",
      iconBg: "#FBE4E4",
    };
  }
  return {
    icon: <Minus className="h-3.5 w-3.5" strokeWidth={2.5} />,
    color: snapshotTokens.textMuted,
    background: snapshotTokens.white,
    border: snapshotTokens.border,
    iconBg: snapshotTokens.background,
  };
}

function opportunityScore(market: BettingMarket): number | null {
  if (market.market_type === "moneyline") {
    return market.edge_probability ?? market.edge ?? null;
  }
  if (market.market_type === "spread") {
    const cushion = spreadCushion(market);
    if (cushion != null) return cushion;
  }
  if (market.edge_probability != null) return market.edge_probability;
  return market.edge ?? null;
}

function spreadCushion(market: BettingMarket): number | null {
  if (market.model_projection == null || market.line == null) {
    return null;
  }
  const selectionModel = modelOnSelection(market);
  if (selectionModel == null) return null;
  // Favorite -7 vs model -12 → +5 cover room.
  // Dog +7 vs model +2 → +5 cover room.
  return Number((market.line - selectionModel).toFixed(1));
}

function modelOnSelection(market: BettingMarket): number | null {
  return modelSpreadOnSelection(market);
}

function formatDiff(market: BettingMarket): string {
  if (market.market_type === "moneyline") {
    if (market.edge_probability == null) return "Aligned";
    const value = market.edge_probability;
    return `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;
  }
  if (market.market_type === "spread") {
    const cushion = spreadCushion(market);
    if (cushion == null) return "—";
    return `${cushion > 0 ? "+" : ""}${cushion.toFixed(1)}`;
  }
  if (market.edge == null) return "—";
  const value = market.edge;
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

function formatStart(value?: string | null): string {
  if (!value) return "Kickoff TBD";
  const trimmed = value.trim();

  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (dateOnly) {
    const date = new Date(
      Number(dateOnly[1]),
      Number(dateOnly[2]) - 1,
      Number(dateOnly[3])
    );
    return date.toLocaleDateString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  }

  const localDt =
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?/.exec(
      trimmed
    );
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(trimmed);
  if (localDt && !hasZone) {
    const date = new Date(
      Number(localDt[1]),
      Number(localDt[2]) - 1,
      Number(localDt[3]),
      Number(localDt[4]),
      Number(localDt[5]),
      Number(localDt[6] || "0")
    );
    const showTime =
      Number(localDt[4]) !== 0 || Number(localDt[5]) !== 0;
    if (!showTime) {
      return date.toLocaleDateString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
      });
    }
    return date.toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }

  const date = new Date(trimmed);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function injurySummary(event: BettingEvent): string | null {
  const notes = (event.injuries ?? []).filter(
    (injury) =>
      injury.is_starter
      && Math.abs(injury.projection_impact_pts ?? 0) >= 0.3
  );
  if (!notes.length) return null;
  const top = notes
    .slice(0, 2)
    .map((injury) => {
      const impact = injury.projection_impact_pts ?? 0;
      const signed =
        impact === 0
          ? ""
          : ` ${impact > 0 ? "+" : ""}${impact.toFixed(1)}`;
      return `${injury.player_name} ${injury.game_status || "Unavailable"}${signed}`;
    })
    .join(" · ");
  const extra =
    notes.length > 2 ? ` +${notes.length - 2} more` : "";
  return `Injury: ${top}${extra}`;
}
