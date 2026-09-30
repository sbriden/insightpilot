import { BettingMarket } from "@/services/api";

/** Shared Market / Model display formatting for betting UI. */

export function formatAmerican(
  price: number | null | undefined
): string {
  if (price == null || Number.isNaN(price)) return "—";
  const rounded = Math.round(price);
  return rounded > 0 ? `+${rounded}` : String(rounded);
}

export function formatSignedNumber(
  value: number | null | undefined,
  digits = 1
): string {
  if (value == null || Number.isNaN(value)) return "—";
  const fixed = Number(value.toFixed(digits));
  return fixed > 0 ? `+${fixed}` : String(fixed);
}

export function modelSpreadOnSelection(
  market: BettingMarket
): number | null {
  if (market.model_projection == null) return null;
  if (market.market_type !== "spread") {
    return market.model_projection;
  }
  const selectionIsHome =
    market.home_team != null
    && market.selection.startsWith(`${market.home_team} `);
  return selectionIsHome
    ? market.model_projection
    : -market.model_projection;
}

export function formatMarketValue(market: BettingMarket): string {
  if (market.market_type === "moneyline") {
    // Keep moneyline Market/Model in American odds.
    return formatAmerican(market.price);
  }
  if (market.market_type === "spread") {
    if (market.line != null) {
      return formatSignedNumber(market.line);
    }
    if (market.market_implied_projection != null) {
      return formatSignedNumber(market.market_implied_projection);
    }
    return "—";
  }
  // Totals and other continuous lines.
  if (market.line != null) return String(market.line);
  if (market.market_implied_projection != null) {
    return String(market.market_implied_projection);
  }
  return "—";
}

export function formatModelValue(market: BettingMarket): string {
  if (market.market_type === "moneyline") {
    // Align with market American odds (fair price from model prob).
    if (market.model_fair_price != null) {
      return formatAmerican(market.model_fair_price);
    }
    return "—";
  }
  if (market.market_type === "spread") {
    return formatSignedNumber(modelSpreadOnSelection(market));
  }
  if (market.model_projection != null) {
    return String(market.model_projection);
  }
  return "—";
}
