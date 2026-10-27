/**
 * Analyses owned by the Sports Betting native product.
 */
export interface SportsBettingAnalysis {
  id: string;
  title: string;
  description: string;
}

export const SPORTS_BETTING_ANALYSES: SportsBettingAnalysis[] = [
  {
    id: "sports_betting",
    title: "Sports Betting",
    description:
      "Compare market prices with InsightPilot projections across NFL and College Football spreads, totals, and moneylines.",
  },
  {
    id: "betting.daily_slate",
    title: "Daily Bet Slate",
    description:
      "Generate a market-probability randomized daily card across sports with risk-based unit allocation and parlays.",
  },
];
