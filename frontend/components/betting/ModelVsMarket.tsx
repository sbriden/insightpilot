"use client";

import {
  formatMarketValue,
  formatModelValue,
} from "@/components/betting/formatMarketValues";
import { snapshotTokens } from "@/components/fantasy/snapshot/tokens";
import { BettingMarket } from "@/services/api";

interface Props {
  market: BettingMarket;
}

export default function ModelVsMarket({ market }: Props) {
  const marketValue = formatMarketValue(market);
  const modelValue = formatModelValue(market);
  const marketPos = positionFor(market, "market");
  const modelPos = positionFor(market, "model");

  return (
    <div className="space-y-3">
      <div className="relative h-10">
        <div
          className="absolute left-0 right-0 top-1/2 h-0.5 -translate-y-1/2"
          style={{ background: snapshotTokens.divider }}
        />
        <Marker
          label="Market"
          value={marketValue}
          left={marketPos}
          tone="market"
        />
        <Marker
          label="Model"
          value={modelValue}
          left={modelPos}
          tone="model"
        />
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.12em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            Market
          </p>
          <p
            className="mt-1 font-semibold tabular-nums"
            style={{ color: snapshotTokens.textPrimary }}
          >
            {marketValue}
          </p>
        </div>
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.12em]"
            style={{ color: snapshotTokens.textMuted }}
          >
            InsightPilot
          </p>
          <p
            className="mt-1 font-semibold tabular-nums"
            style={{ color: snapshotTokens.blue }}
          >
            {modelValue}
          </p>
        </div>
      </div>
    </div>
  );
}

function Marker({
  label,
  value,
  left,
  tone,
}: {
  label: string;
  value: string;
  left: number;
  tone: "market" | "model";
}) {
  const color =
    tone === "model" ? snapshotTokens.blue : snapshotTokens.navy;
  return (
    <div
      className="absolute top-0 -translate-x-1/2"
      style={{ left: `${left}%` }}
      title={`${label}: ${value}`}
    >
      <div
        className="h-3 w-3 rounded-full border-2 bg-white"
        style={{ borderColor: color }}
      />
      <p
        className="mt-1 whitespace-nowrap text-[10px] font-medium"
        style={{ color }}
      >
        {label}
      </p>
    </div>
  );
}

function positionFor(
  market: BettingMarket,
  side: "market" | "model"
): number {
  const marketNum =
    market.market_type === "moneyline"
      ? (market.market_probability ?? 0.5) * 100
      : Number(
          market.line
            ?? market.market_implied_projection
            ?? 0
        );
  let modelNum: number;
  if (market.market_type === "moneyline") {
    modelNum = (market.model_probability ?? 0.5) * 100;
  } else if (
    market.market_type === "spread"
    && market.model_projection != null
  ) {
    const selectionIsHome =
      market.home_team != null
      && market.selection.startsWith(`${market.home_team} `);
    modelNum = selectionIsHome
      ? market.model_projection
      : -market.model_projection;
  } else {
    modelNum = Number(market.model_projection ?? marketNum);
  }
  const min = Math.min(marketNum, modelNum) - 4;
  const max = Math.max(marketNum, modelNum) + 4;
  const span = max - min || 1;
  const value = side === "market" ? marketNum : modelNum;
  return Math.max(
    8,
    Math.min(92, ((value - min) / span) * 100)
  );
}
