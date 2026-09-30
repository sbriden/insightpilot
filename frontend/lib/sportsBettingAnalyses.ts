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
      "Compare market prices with InsightPilot projections across NFL spreads, totals, and moneylines.",
  },
];
