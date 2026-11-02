import type { ScoresandoddsLeague } from "@/services/api";
import type { NflverseIngestMode } from "@/types/dataset";

export type RefreshPipelineId =
  | "nfl_fantasy"
  | "college_football"
  | "market_odds";

export type RefreshJobKind =
  | "nflverse"
  | "sportsdataverse"
  | "scoresandodds";

export interface PipelineStage {
  id: string;
  label: string;
  tables: string[];
}

export interface RefreshProductRef {
  id: string;
  name: string;
  href: string;
}

export interface RefreshJob {
  id: string;
  pipelineId: RefreshPipelineId;
  kind: RefreshJobKind;
  title: string;
  summary: string;
  /** Season / cadence hint shown under the title. */
  cadence: string;
  mode?: NflverseIngestMode;
  league?: ScoresandoddsLeague;
  /** Pipeline stages this job writes. */
  layers: string[];
  /** Fully-qualified or schema-qualified table names. */
  tables: string[];
  products: RefreshProductRef[];
}

export interface RefreshPipeline {
  id: RefreshPipelineId;
  title: string;
  source: string;
  schema: string;
  description: string;
  stages: PipelineStage[];
  products: RefreshProductRef[];
}

const FANTASY_PRODUCT: RefreshProductRef = {
  id: "fantasy_football",
  name: "Fantasy Football",
  href: "/products/fantasy-football",
};

const BETTING_PRODUCT: RefreshProductRef = {
  id: "sports_betting",
  name: "Sports Betting",
  href: "/products/sports-betting",
};

export const NFL_PIPELINE: RefreshPipeline = {
  id: "nfl_fantasy",
  title: "NFL Fantasy pipeline",
  source: "nflverse",
  schema: "fantasy_football",
  description:
    "Dims and facts from nflverse, then analytics and intelligence "
    + "that power Fantasy Football and NFL betting analyses.",
  stages: [
    {
      id: "dims",
      label: "Dims",
      tables: ["dim_team", "dim_player", "dim_game"],
    },
    {
      id: "facts",
      label: "Facts",
      tables: [
        "fact_player_game",
        "fact_player_usage",
        "fact_player_efficiency",
        "fact_team_game",
        "fact_defensive_game",
        "fact_injury",
        "fact_depth_chart",
        "fact_market",
        "fact_game_market",
      ],
    },
    {
      id: "analytics",
      label: "Analytics",
      tables: [
        "player_usage_trend",
        "player_opportunity",
        "player_efficiency",
        "player_matchup",
        "player_environment",
      ],
    },
    {
      id: "intelligence",
      label: "Intelligence",
      tables: ["player_fantasy_profile", "fantasy_signal"],
    },
    {
      id: "domain",
      label: "Domain",
      tables: ["player_fundamentals"],
    },
  ],
  products: [FANTASY_PRODUCT, BETTING_PRODUCT],
};

export const CFB_PIPELINE: RefreshPipeline = {
  id: "college_football",
  title: "College Football pipeline",
  source: "sportsdataverse",
  schema: "college_football",
  description:
    "Teams, schedule, box scores, and lines for college football "
    + "betting and market analysis.",
  stages: [
    {
      id: "dims",
      label: "Dims",
      tables: ["dim_team", "dim_player", "dim_game"],
    },
    {
      id: "facts",
      label: "Facts",
      tables: [
        "fact_player_game",
        "fact_team_game",
        "fact_defensive_game",
        "fact_game_market",
      ],
    },
  ],
  products: [BETTING_PRODUCT],
};

export const ODDS_PIPELINE: RefreshPipeline = {
  id: "market_odds",
  title: "Market odds pipeline",
  source: "ScoresAndOdds",
  schema: "fact_game_market",
  description:
    "Consensus and opening lines scraped from ScoresAndOdds into "
    + "the matching league fact_game_market table.",
  stages: [
    {
      id: "source",
      label: "ScoresAndOdds",
      tables: [],
    },
    {
      id: "facts",
      label: "Markets",
      tables: ["fact_game_market"],
    },
  ],
  products: [BETTING_PRODUCT],
};

export const REFRESH_PIPELINES: RefreshPipeline[] = [
  NFL_PIPELINE,
  CFB_PIPELINE,
  ODDS_PIPELINE,
];

const NFL_FULL_LAYERS = NFL_PIPELINE.stages.map((s) => s.id);
const NFL_FULL_TABLES = NFL_PIPELINE.stages.flatMap((s) => s.tables);
const NFL_REPROCESS_LAYERS = ["analytics", "intelligence"];
const NFL_REPROCESS_TABLES = NFL_PIPELINE.stages
  .filter((s) => NFL_REPROCESS_LAYERS.includes(s.id))
  .flatMap((s) => s.tables);

const CFB_FULL_LAYERS = CFB_PIPELINE.stages.map((s) => s.id);
const CFB_FULL_TABLES = CFB_PIPELINE.stages.flatMap((s) => s.tables);
const CFB_REPROCESS_LAYERS = ["facts"];
const CFB_REPROCESS_TABLES = CFB_PIPELINE.stages
  .filter((s) => CFB_REPROCESS_LAYERS.includes(s.id))
  .flatMap((s) => s.tables);

/** Unique, non-overlapping refresh operations shown on /refresh. */
export const REFRESH_JOBS: RefreshJob[] = [
  {
    id: "nfl-incremental",
    pipelineId: "nfl_fantasy",
    kind: "nflverse",
    title: "NFL weekly update",
    summary:
      "Pull the live season from nflverse and rebuild the full "
      + "fantasy stack for the current week.",
    cadence: "Current season · weekly",
    mode: "incremental",
    layers: NFL_FULL_LAYERS,
    tables: NFL_FULL_TABLES.map((t) => `fantasy_football.${t}`),
    products: [FANTASY_PRODUCT, BETTING_PRODUCT],
  },
  {
    id: "nfl-historical",
    pipelineId: "nfl_fantasy",
    kind: "nflverse",
    title: "NFL historical seed",
    summary:
      "One-time bootstrap across several seasons. Use for first "
      + "load or after a schema wipe — not for weekly updates.",
    cadence: "Multi-season · bootstrap",
    mode: "historical",
    layers: NFL_FULL_LAYERS,
    tables: NFL_FULL_TABLES.map((t) => `fantasy_football.${t}`),
    products: [FANTASY_PRODUCT, BETTING_PRODUCT],
  },
  {
    id: "nfl-reprocess",
    pipelineId: "nfl_fantasy",
    kind: "nflverse",
    title: "NFL reprocess derived",
    summary:
      "Rebuild analytics and intelligence from facts already in "
      + "Postgres. Does not re-fetch nflverse source tables.",
    cadence: "Derived layers only",
    mode: "reprocess",
    layers: NFL_REPROCESS_LAYERS,
    tables: NFL_REPROCESS_TABLES.map((t) => `fantasy_football.${t}`),
    products: [FANTASY_PRODUCT, BETTING_PRODUCT],
  },
  {
    id: "cfb-incremental",
    pipelineId: "college_football",
    kind: "sportsdataverse",
    title: "CFB weekly update",
    summary:
      "Refresh the live college football season into dims and facts.",
    cadence: "Current season · weekly",
    mode: "incremental",
    layers: CFB_FULL_LAYERS,
    tables: CFB_FULL_TABLES.map((t) => `college_football.${t}`),
    products: [BETTING_PRODUCT],
  },
  {
    id: "cfb-historical",
    pipelineId: "college_football",
    kind: "sportsdataverse",
    title: "CFB historical seed",
    summary:
      "Bootstrap several CFB seasons (dims + facts) for trends "
      + "and backtesting.",
    cadence: "Multi-season · bootstrap",
    mode: "historical",
    layers: CFB_FULL_LAYERS,
    tables: CFB_FULL_TABLES.map((t) => `college_football.${t}`),
    products: [BETTING_PRODUCT],
  },
  {
    id: "cfb-reprocess",
    pipelineId: "college_football",
    kind: "sportsdataverse",
    title: "CFB reprocess facts",
    summary:
      "Rebuild fact tables from sportsdataverse loaders using "
      + "existing dims.",
    cadence: "Facts only",
    mode: "reprocess",
    layers: CFB_REPROCESS_LAYERS,
    tables: CFB_REPROCESS_TABLES.map((t) => `college_football.${t}`),
    products: [BETTING_PRODUCT],
  },
  {
    id: "odds-nfl",
    pipelineId: "market_odds",
    kind: "scoresandodds",
    title: "NFL odds",
    summary:
      "Consensus and opening lines for the current NFL week into "
      + "fantasy_football.fact_game_market.",
    cadence: "Current week",
    league: "nfl",
    layers: ["facts"],
    tables: ["fantasy_football.fact_game_market"],
    products: [BETTING_PRODUCT],
  },
  {
    id: "odds-ncaaf",
    pipelineId: "market_odds",
    kind: "scoresandodds",
    title: "NCAAF odds",
    summary:
      "Consensus and opening lines for the current CFB week into "
      + "college_football.fact_game_market.",
    cadence: "Current week",
    league: "ncaaf",
    layers: ["facts"],
    tables: ["college_football.fact_game_market"],
    products: [BETTING_PRODUCT],
  },
  {
    id: "odds-nba",
    pipelineId: "market_odds",
    kind: "scoresandodds",
    title: "NBA odds",
    summary:
      "Dated NBA slate lines into sports_odds.fact_game_market.",
    cadence: "Current slate",
    league: "nba",
    layers: ["facts"],
    tables: ["sports_odds.fact_game_market"],
    products: [BETTING_PRODUCT],
  },
  {
    id: "odds-nhl",
    pipelineId: "market_odds",
    kind: "scoresandodds",
    title: "NHL odds",
    summary:
      "Dated NHL slate lines into sports_odds.fact_game_market.",
    cadence: "Current slate",
    league: "nhl",
    layers: ["facts"],
    tables: ["sports_odds.fact_game_market"],
    products: [BETTING_PRODUCT],
  },
  {
    id: "odds-mlb",
    pipelineId: "market_odds",
    kind: "scoresandodds",
    title: "MLB odds",
    summary:
      "Dated MLB slate lines into sports_odds.fact_game_market.",
    cadence: "Current slate",
    league: "mlb",
    layers: ["facts"],
    tables: ["sports_odds.fact_game_market"],
    products: [BETTING_PRODUCT],
  },
  {
    id: "odds-ncaab",
    pipelineId: "market_odds",
    kind: "scoresandodds",
    title: "NCAAB odds",
    summary:
      "Dated NCAAB slate lines into sports_odds.fact_game_market.",
    cadence: "Current slate",
    league: "ncaab",
    layers: ["facts"],
    tables: ["sports_odds.fact_game_market"],
    products: [BETTING_PRODUCT],
  },
];

export function jobsForPipeline(
  pipelineId: RefreshPipelineId
): RefreshJob[] {
  return REFRESH_JOBS.filter((job) => job.pipelineId === pipelineId);
}

export const ODDS_LAST_REFRESH_STORAGE_KEY =
  "insightpilot:odds-last-refresh";

export type OddsLastRefreshMap = Partial<
  Record<ScoresandoddsLeague, string>
>;

export function readOddsLastRefresh(): OddsLastRefreshMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(
      ODDS_LAST_REFRESH_STORAGE_KEY
    );
    if (!raw) return {};
    const parsed = JSON.parse(raw) as OddsLastRefreshMap;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function writeOddsLastRefresh(
  league: ScoresandoddsLeague,
  iso: string
): OddsLastRefreshMap {
  const next = { ...readOddsLastRefresh(), [league]: iso };
  if (typeof window !== "undefined") {
    window.localStorage.setItem(
      ODDS_LAST_REFRESH_STORAGE_KEY,
      JSON.stringify(next)
    );
  }
  return next;
}
