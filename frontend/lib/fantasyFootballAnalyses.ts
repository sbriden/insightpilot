/**
 * Analyses owned by the Fantasy Football native product.
 * Shown on the product Analyses tab.
 */
export interface FantasyFootballAnalysis {
  id: string;
  title: string;
  description: string;
}

export const FANTASY_FOOTBALL_ANALYSES: FantasyFootballAnalysis[] = [
  {
    id: "player_overview",
    title: "Player Overview",
    description:
      "Analyze a player's performance, usage, trends and fantasy outlook.",
  },
  {
    id: "daily_fantasy",
    title: "Daily Fantasy",
    description:
      "Analyze today's slate, identify the strongest DFS opportunities, and build optimized lineups.",
  },
];
