/**
 * Canonical Analysis Registry — reusable analyses owned by data products.
 * Analytical Applications reference these by analysis_key; they do not
 * duplicate analysis logic.
 */

export type AnalysisDataProductId =
  | "fantasy_football"
  | "daily_fantasy"
  | "sports_betting";

export type SupportedContext =
  | "player"
  | "team"
  | "game"
  | "market"
  | "portfolio"
  | "slate"
  | "season"
  | "week";

export interface RegistryAnalysis {
  analysis_key: string;
  name: string;
  description: string;
  data_product_id: AnalysisDataProductId;
  data_product_label: string;
  category: string;
  /** Runtime component family */
  runtime:
    | "player_snapshot"
    | "dfs_analyzer"
    | "sports_betting";
  /** Optional nested tab / view within the runtime */
  view?: string;
  supported_context: SupportedContext[];
  icon?: string;
  status: "available" | "coming_soon";
}

export const ANALYSIS_REGISTRY: RegistryAnalysis[] = [
  {
    analysis_key: "fantasy.player_overview",
    name: "Player Overview",
    description:
      "Analyze a player's performance, usage, trends and fantasy outlook.",
    data_product_id: "fantasy_football",
    data_product_label: "Fantasy Football",
    category: "Player",
    runtime: "player_snapshot",
    view: "snapshot",
    supported_context: ["player", "team", "season", "week"],
    status: "available",
  },
  {
    analysis_key: "fantasy.player_stats",
    name: "Stats",
    description:
      "Dive into game logs and season statistical production.",
    data_product_id: "fantasy_football",
    data_product_label: "Fantasy Football",
    category: "Player",
    runtime: "player_snapshot",
    view: "stats",
    supported_context: ["player", "season", "week"],
    status: "available",
  },
  {
    analysis_key: "fantasy.player_usage",
    name: "Usage & Trends",
    description:
      "Understand how player opportunity and role are changing.",
    data_product_id: "fantasy_football",
    data_product_label: "Fantasy Football",
    category: "Player",
    runtime: "player_snapshot",
    view: "usage",
    supported_context: ["player", "season", "week"],
    status: "available",
  },
  {
    analysis_key: "fantasy.player_matchups",
    name: "Matchups",
    description:
      "Evaluate upcoming opponent environment and matchup outlook.",
    data_product_id: "fantasy_football",
    data_product_label: "Fantasy Football",
    category: "Player",
    runtime: "player_snapshot",
    view: "matchups",
    supported_context: ["player", "team", "week"],
    status: "available",
  },
  {
    analysis_key: "fantasy.player_news",
    name: "News",
    description:
      "Track injury, roster, and role-changing news for a player.",
    data_product_id: "fantasy_football",
    data_product_label: "Fantasy Football",
    category: "Player",
    runtime: "player_snapshot",
    view: "news",
    supported_context: ["player"],
    status: "available",
  },
  {
    analysis_key: "dfs.analyzer",
    name: "DFS Analyzer",
    description:
      "Analyze today's slate and identify the strongest DFS opportunities.",
    data_product_id: "daily_fantasy",
    data_product_label: "Daily Fantasy",
    category: "DFS",
    runtime: "dfs_analyzer",
    view: "analyzer",
    supported_context: ["slate", "player", "week"],
    status: "available",
  },
  {
    analysis_key: "dfs.optimizer",
    name: "Lineup Optimizer",
    description:
      "Build optimized DFS lineups under salary and roster constraints.",
    data_product_id: "daily_fantasy",
    data_product_label: "Daily Fantasy",
    category: "DFS",
    runtime: "dfs_analyzer",
    view: "optimizer",
    supported_context: ["slate", "portfolio", "week"],
    status: "available",
  },
  {
    analysis_key: "dfs.portfolio",
    name: "DFS Portfolio",
    description:
      "Manage exposure and construct a diversified lineup portfolio.",
    data_product_id: "daily_fantasy",
    data_product_label: "Daily Fantasy",
    category: "DFS",
    runtime: "dfs_analyzer",
    view: "portfolio",
    supported_context: ["portfolio", "slate"],
    status: "available",
  },
  {
    analysis_key: "betting.games",
    name: "Games",
    description:
      "Review InsightPilot game projections, scripts, and edges.",
    data_product_id: "sports_betting",
    data_product_label: "Sports Betting",
    category: "Betting",
    runtime: "sports_betting",
    view: "games",
    supported_context: ["game", "team", "week"],
    status: "available",
  },
  {
    analysis_key: "betting.markets",
    name: "Markets",
    description:
      "Compare market prices with model projections across spreads, totals, and moneylines.",
    data_product_id: "sports_betting",
    data_product_label: "Sports Betting",
    category: "Betting",
    runtime: "sports_betting",
    view: "markets",
    supported_context: ["market", "game", "week"],
    status: "available",
  },
  {
    analysis_key: "betting.portfolio",
    name: "Betting Portfolio",
    description:
      "Build and manage a portfolio of singles and parlays.",
    data_product_id: "sports_betting",
    data_product_label: "Sports Betting",
    category: "Betting",
    runtime: "sports_betting",
    view: "portfolio",
    supported_context: ["portfolio", "market", "game"],
    status: "available",
  },
  {
    analysis_key: "betting.results",
    name: "Results",
    description:
      "Review settled markets, model accuracy, and calibration feedback.",
    data_product_id: "sports_betting",
    data_product_label: "Sports Betting",
    category: "Betting",
    runtime: "sports_betting",
    view: "results",
    supported_context: ["game", "market", "week"],
    status: "available",
  },
];

export function getRegistryAnalysis(
  analysisKey: string
): RegistryAnalysis | undefined {
  return ANALYSIS_REGISTRY.find(
    (row) => row.analysis_key === analysisKey
  );
}

export function groupRegistryByProduct(): Array<{
  data_product_id: AnalysisDataProductId;
  data_product_label: string;
  analyses: RegistryAnalysis[];
}> {
  const order: AnalysisDataProductId[] = [
    "fantasy_football",
    "daily_fantasy",
    "sports_betting",
  ];
  return order.map((id) => {
    const analyses = ANALYSIS_REGISTRY.filter(
      (row) => row.data_product_id === id
    );
    return {
      data_product_id: id,
      data_product_label:
        analyses[0]?.data_product_label || id,
      analyses,
    };
  });
}

export function sourceProductLabels(
  analysisKeys: string[]
): string {
  const labels = new Set<string>();
  for (const key of analysisKeys) {
    const row = getRegistryAnalysis(key);
    if (row) labels.add(row.data_product_label);
  }
  return Array.from(labels).join(" · ");
}
