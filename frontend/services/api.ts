import {
  DatasetType,
  FieldMapping,
  DatasetField,
  ConceptIdentificationResult,
  CapabilityDetectionResult,
  AnalyticalCapability,
  AnalyticalCandidateResult,
  DatasetClassificationResult,
  BusinessConcept,
  GrainDeterminationResult,
  ColumnStatInput,
  DataSourceOption,
  NflverseCatalog,
  NflversePreviewResult,
  NflverseRefreshResult,
  NflverseDataQualityResult,
  NflverseIngestMode,
} from "@/types/dataset";

import {
  DatasetAnalysis,
  SemanticUnderstanding,
} from "@/types/report";


const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";


async function handleResponse<T>(
  response: Response
): Promise<T> {

  if (!response.ok) {

    let message =
      "An unexpected error occurred.";

    try {

      const error =
        await response.json();

      message =
        error.detail ??
        error.message ??
        message;

    } catch {}

    throw new Error(
      message
    );

  }

  return response.json();

}


/* --------------------------------------------------------------------------
 * Upload Dataset
 *
 * Sends the uploaded dataset, shared field mappings, and ALL selected
 * data product IDs to the backend.
 *
 * Product-specific required fields are evaluated before this request
 * is made in page.tsx.
 * ------------------------------------------------------------------------ */

export async function uploadDataset(
  file: File,
  mappings: FieldMapping[] = [],
  productIds: string[] = []
): Promise<DatasetAnalysis> {

  const formData =
    new FormData();


  formData.append(
    "file",
    file
  );


  formData.append(
    "mappings",
    JSON.stringify(
      mappings
    )
  );


  /*
   * Send the complete list of selected
   * products.
   *
   * JSON is used so the backend receives
   * the product IDs as a single structured
   * value instead of losing all but the
   * first selection.
   */

  if (
    productIds.length > 0
  ) {

    formData.append(
      "product_ids",
      JSON.stringify(
        productIds
      )
    );

  }


  console.log(
    "Uploading dataset:",
    {
      file:
        file.name,

      productIds,

      mappingCount:
        mappings.length,
    }
  );


  const response =
    await fetch(
      `${API_BASE_URL}/api/upload/`,
      {
        method:
          "POST",

        body:
          formData,
      }
    );


  return handleResponse<DatasetAnalysis>(
    response
  );

}


/* --------------------------------------------------------------------------
 * External Data Sources
 * ------------------------------------------------------------------------ */

export async function getDataSources(): Promise<{
  sources: DataSourceOption[];
}> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/sources/`
    );

  return handleResponse(
    response
  );

}


export async function getNflverseCatalog(): Promise<NflverseCatalog> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/sources/nflverse/datasets`
    );

  return handleResponse<NflverseCatalog>(
    response
  );

}


export async function previewNflverseDataset(
  datasetId: string,
  seasons: number[] = []
): Promise<NflversePreviewResult> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/sources/nflverse/preview`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          dataset_id: datasetId,
          seasons,
        }),
      }
    );

  return handleResponse<NflversePreviewResult>(
    response
  );

}


export interface FantasyPlayerSearchHit {
  player_id: string;
  name: string;
  position?: string | null;
  depth_order?: number | null;
  depth_chart?: string | null;
  team?: string | null;
  status?: string | null;
  injury_type?: string | null;
  injury_status?: string | null;
  fantasy_points?: number | null;
  games?: number | null;
  fppg?: number | null;
  production_score?: number | null;
  opportunity_score?: number | null;
  fantasy_value_score?: number | null;
  ownership?: number | null;
  overall_assessment?: string | null;
}


export interface FantasyPlayerTakeaway {
  type: string;
  headline: string;
  body: string;
  source?: string;
}


export interface FantasyPlayerRecommendation {
  headline: string;
  body: string;
  source?: string;
}


export interface FantasySeasonMetric {
  key: string;
  label: string;
  value: number | null;
}


export interface FantasySeasonStats {
  season: number;
  games: number;
  fantasy_points?: number | null;
  metrics: FantasySeasonMetric[];
}


export interface FantasyReplacementPlayer {
  player_id: string;
  name: string;
  position?: string | null;
  team?: string | null;
  fantasy_points?: number | null;
  fantasy_value_score?: number | null;
  opportunity_score?: number | null;
  production_score?: number | null;
  ownership?: number | null;
  headshot_url?: string | null;
  overall_assessment?: string | null;
}


export interface FantasyPlayerSnapshot {
  player_id: string;
  name?: string | null;
  position?: string | null;
  depth_order?: number | null;
  depth_chart?: string | null;
  position_depth_chart?: FantasyPositionDepthChart | null;
  is_team_defense?: boolean;
  team?: string | null;
  status?: string | null;
  injury_type?: string | null;
  injury_status?: string | null;
  season?: number | null;
  week?: number | null;
  birth_date?: string | null;
  age?: number | null;
  rookie_season?: number | null;
  experience_years?: number | null;
  headshot_url?: string | null;
  espn_id?: string | null;
  overall_assessment?: string | null;
  assessment_narrative?: string | null;
  key_takeaways?: FantasyPlayerTakeaway[];
  recommendation?: FantasyPlayerRecommendation | null;
  fantasy_value_score?: number | null;
  production_score?: number | null;
  opportunity_score?: number | null;
  efficiency_score?: number | null;
  trend_score?: number | null;
  season_stats?: FantasySeasonStats | null;
  position_rank?: number | null;
  overall_rank?: number | null;
  position_pool_size?: number | null;
  overall_pool_size?: number | null;
  ownership?: number | null;
  replacements?: FantasyReplacementPlayer[];
  primary_signal_type?: string | null;
  primary_signal_strength?: number | null;
  evidence_source?: string | null;
  performance?: PlayerPerformanceBlock | null;
}


export interface PlayerMetricField {
  key: string;
  label: string;
}


export interface PlayerGameMetrics {
  season: number;
  week: number;
  label?: string;
  opponent?: string | null;
  opponent_label?: string | null;
  home_away?: string | null;
  production: Record<string, number | null | undefined>;
  opportunity: Record<string, number | null | undefined>;
}


export interface PlayerPerformanceBlock {
  position_group?: string;
  production_fields: PlayerMetricField[];
  opportunity_fields: PlayerMetricField[];
  recent_games: PlayerGameMetrics[];
  framing?: string;
}


export async function listFantasyPlayers(
  options: {
    query?: string;
    position?: string;
    team?: string;
    limit?: number;
  } = {}
): Promise<{
  players: FantasyPlayerSearchHit[];
  count: number;
}> {

  const params = new URLSearchParams();
  if (options.query) {
    params.set("q", options.query);
  }
  if (options.position) {
    params.set("position", options.position);
  }
  if (options.team) {
    params.set("team", options.team);
  }
  if (options.limit != null) {
    params.set("limit", String(options.limit));
  }

  const query =
    params.toString()
      ? `?${params.toString()}`
      : "";

  const response =
    await fetch(
      `${API_BASE_URL}/api/sources/nflverse/players${query}`,
      { cache: "no-store" }
    );

  return handleResponse(response);

}


export interface FantasyTeamSummary {
  team_id: string;
  abbreviation: string;
  name: string;
  conference?: string | null;
  division?: string | null;
}


export interface FantasyTeamPlayerStats {
  player_id: string;
  name?: string | null;
  position?: string | null;
  status?: string | null;
  games?: number | null;
  pass_attempts?: number | null;
  pass_completions?: number | null;
  pass_yards?: number | null;
  pass_tds?: number | null;
  interceptions?: number | null;
  rush_attempts?: number | null;
  rush_yards?: number | null;
  rush_tds?: number | null;
  targets?: number | null;
  receptions?: number | null;
  receiving_yards?: number | null;
  receiving_tds?: number | null;
}


export interface FantasyDepthChartEntry {
  player_id: string;
  name?: string | null;
  depth_order?: number | null;
  role?: string | null;
}


export interface FantasyPositionDepthPlayer {
  player_id: string;
  name?: string | null;
  depth_order?: number | null;
  depth_position?: string | null;
  depth_chart?: string | null;
  role?: string | null;
  is_current_player?: boolean;
}


export interface FantasyPositionDepthChart {
  position?: string | null;
  season?: number | null;
  week?: number | null;
  as_of?: string | null;
  players: FantasyPositionDepthPlayer[];
}


export interface FantasyDepthChartGroup {
  position: string;
  players: FantasyDepthChartEntry[];
}


export interface FantasyTeamStats {
  team: FantasyTeamSummary;
  season?: number | null;
  depth_season?: number | null;
  depth_week?: number | null;
  depth_as_of?: string | null;
  players: FantasyTeamPlayerStats[];
  passing_leaders: FantasyTeamPlayerStats[];
  rushing_leaders: FantasyTeamPlayerStats[];
  receiving_leaders: FantasyTeamPlayerStats[];
  depth_chart: FantasyDepthChartGroup[];
}


export async function listFantasyTeams(): Promise<{
  teams: FantasyTeamSummary[];
  count: number;
}> {
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/teams`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}


export async function getFantasyTeamStats(
  team: string,
  season?: number | null
): Promise<{ stats: FantasyTeamStats }> {
  const params = new URLSearchParams();
  if (season != null) {
    params.set("season", String(season));
  }
  const query = params.toString()
    ? `?${params.toString()}`
    : "";
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/teams/${encodeURIComponent(team)}/stats${query}`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}


export async function searchFantasyPlayers(
  query: string,
  limit: number = 20
): Promise<{
  query: string;
  players: FantasyPlayerSearchHit[];
  count: number;
}> {

  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
  });

  const response =
    await fetch(
      `${API_BASE_URL}/api/sources/nflverse/players/search?${params.toString()}`
    );

  return handleResponse(response);

}


export type FantasyScoringFormat = "ppr" | "half_ppr" | "standard";


export interface FantasyStatsMetric {
  key: string;
  label: string;
  value: number;
  context?: string | null;
  format?: "number" | "integer" | "percent" | string;
}


export interface FantasyStatsBreakdownGroup {
  title: string;
  metrics: FantasyStatsMetric[];
}


export interface FantasyStatsProduction {
  fantasy_points?: number | null;
  fppg?: number | null;
  games?: number | null;
  games_context?: string | null;
  position_rank?: number | null;
  position_rank_label?: string | null;
  weekly_ceiling?: number | null;
  ceiling_week?: number | null;
  weekly_floor?: number | null;
  floor_week?: number | null;
  top_12_finishes?: number | null;
  top_12_rate?: number | null;
}


export interface FantasyStatsConsistency {
  fppg?: number | null;
  median?: number | null;
  stdev?: number | null;
  ceiling?: number | null;
  floor?: number | null;
  top_12_finishes?: number | null;
  top_24_finishes?: number | null;
  games_10_plus?: number | null;
  games?: number | null;
  weekly_points?: number[];
}


export interface FantasyStatsSeasonRow {
  season?: number | null;
  games?: number | null;
  fantasy_points?: number | null;
  fppg?: number | null;
  rush_yards?: number | null;
  receptions?: number | null;
  receiving_yards?: number | null;
  targets?: number | null;
  pass_yards?: number | null;
  pass_tds?: number | null;
  interceptions?: number | null;
  touchdowns?: number | null;
  fg_made?: number | null;
  fg_att?: number | null;
  fg_made_50_plus?: number | null;
  pat_made?: number | null;
  position_group?: string | null;
}


export interface FantasyStatsGameRow {
  season?: number | null;
  week?: number | null;
  opponent?: string | null;
  opponent_label?: string | null;
  fantasy_points?: number | null;
  points_allowed?: number | null;
  sacks?: number | null;
  pass_completions?: number | null;
  pass_attempts?: number | null;
  pass_yards?: number | null;
  pass_tds?: number | null;
  interceptions?: number | null;
  rush_attempts?: number | null;
  rush_yards?: number | null;
  rush_tds?: number | null;
  targets?: number | null;
  receptions?: number | null;
  receiving_yards?: number | null;
  receiving_tds?: number | null;
  touchdowns?: number | null;
  fg_made?: number | null;
  fg_att?: number | null;
  fg_made_40_49?: number | null;
  fg_made_50_plus?: number | null;
  pat_made?: number | null;
  pat_att?: number | null;
  position_group?: string | null;
}


export interface FantasyPlayerStats {
  player_id: string;
  name?: string | null;
  position?: string | null;
  position_group?: string | null;
  team?: string | null;
  season: number;
  scoring: FantasyScoringFormat;
  available_seasons: number[];
  fantasy_production?: FantasyStatsProduction | null;
  production_breakdown: FantasyStatsBreakdownGroup[];
  volume: FantasyStatsMetric[];
  efficiency: FantasyStatsMetric[];
  consistency?: FantasyStatsConsistency | null;
  season_history: FantasyStatsSeasonRow[];
  game_log: FantasyStatsGameRow[];
  empty_message?: string | null;
  data_note?: string | null;
}


export async function getFantasyPlayerStats(
  playerId: string,
  options: {
    season?: number | null;
    scoring?: FantasyScoringFormat | string;
  } = {}
): Promise<{ stats: FantasyPlayerStats }> {
  const params = new URLSearchParams();
  if (options.season != null) {
    params.set("season", String(options.season));
  }
  if (options.scoring) {
    params.set("scoring", String(options.scoring));
  }
  const query = params.toString()
    ? `?${params.toString()}`
    : "";
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/players/${encodeURIComponent(playerId)}/stats${query}`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}


export type FantasyUsagePeriod =
  | "full_season"
  | "last_8"
  | "last_6"
  | "last_4"
  | "last_3";

export type FantasyUsageDirection =
  | "increasing"
  | "decreasing"
  | "stable"
  | "volatile"
  | "insufficient";

export interface FantasyUsageMetricCard {
  key: string;
  label: string;
  value: number;
  previous_value?: number | null;
  format?: "number" | "percent" | string;
  direction: FantasyUsageDirection | string;
  change_pct?: number | null;
  change_pts?: number | null;
  change_label?: string | null;
}

export interface FantasyUsageSignal {
  signal_type: string;
  category?: string | null;
  direction: FantasyUsageDirection | string;
  headline: string;
  body?: string | null;
  confidence?: "high" | "moderate" | "low" | string;
  metric?: string | null;
  sample_size?: number | null;
  classification?: string | null;
}

export interface FantasyUsageRoleChangeMetric {
  key: string;
  label: string;
  current: number;
  previous: number;
  change_pct?: number | null;
  change_pts?: number | null;
  direction: FantasyUsageDirection | string;
  format?: "number" | "percent" | string;
}

export interface FantasyUsageRoleChange {
  current_label: string;
  previous_label: string;
  metrics: FantasyUsageRoleChangeMetric[];
  interpretation?: string | null;
}

export interface FantasyUsageOppProdPoint {
  week?: number | null;
  label?: string | null;
  opportunity: number;
  production: number;
}

export interface FantasyUsageOppVsProd {
  points: FantasyUsageOppProdPoint[];
  opportunity_metric: { key: string; label: string };
  production_metric: { key: string; label: string };
  classification?: string | null;
  interpretation?: string | null;
}

export interface FantasyUsageConsistency {
  metric_key: string;
  metric_label: string;
  format?: "number" | "percent" | string;
  median?: number | null;
  average?: number | null;
  low?: number | null;
  high?: number | null;
  threshold_counts?: Array<{
    label: string;
    count: number;
    total: number;
  }>;
}

export interface FantasyUsagePositionContext {
  position_group: string;
  metrics: Array<{
    key: string;
    label: string;
    player: number;
    position_avg: number;
    format?: "number" | "percent" | string;
  }>;
}

export interface FantasyPlayerUsage {
  player_id: string;
  name?: string | null;
  position?: string | null;
  position_group?: string | null;
  team?: string | null;
  season: number;
  period: FantasyUsagePeriod | string;
  period_games: number;
  scoring: FantasyScoringFormat | string;
  available_seasons: number[];
  data_through_week?: number | null;
  sample_size: number;
  role_opportunity: FantasyUsageMetricCard[];
  chart_metrics: Array<{ key: string; label: string }>;
  weekly_usage: PlayerGameMetrics[];
  signals: FantasyUsageSignal[];
  recent_role_change?: FantasyUsageRoleChange | null;
  opportunity_vs_production?: FantasyUsageOppVsProd | null;
  consistency?: FantasyUsageConsistency | null;
  position_context?: FantasyUsagePositionContext | null;
  empty_message?: string | null;
  data_note?: string | null;
}


export async function getFantasyPlayerUsage(
  playerId: string,
  options: {
    season?: number | null;
    period?: FantasyUsagePeriod | string;
    scoring?: FantasyScoringFormat | string;
  } = {}
): Promise<{ usage: FantasyPlayerUsage }> {
  const params = new URLSearchParams();
  if (options.season != null) {
    params.set("season", String(options.season));
  }
  if (options.period) {
    params.set("period", String(options.period));
  }
  if (options.scoring) {
    params.set("scoring", String(options.scoring));
  }
  const query = params.toString()
    ? `?${params.toString()}`
    : "";
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/players/${encodeURIComponent(playerId)}/usage${query}`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}


export type FantasyMatchupView =
  | "next_4"
  | "next_6"
  | "next_8"
  | "rest_of_season"
  | "full_season";

export type FantasyMatchupDifficulty =
  | "very_favorable"
  | "favorable"
  | "neutral"
  | "difficult"
  | "very_difficult";

export interface FantasyMatchupFactor {
  key: string;
  label: string;
  score?: number | null;
  difficulty: FantasyMatchupDifficulty | string;
  difficulty_label: string;
}

export interface FantasyMatchupOpponentProfile {
  team?: string | null;
  team_name?: string | null;
  fpts_allowed_avg?: number | null;
  rank?: number | null;
  rank_of?: number | null;
  pct_vs_avg?: number | null;
  rush_yards_avg?: number | null;
  rush_tds_avg?: number | null;
  yards_per_carry?: number | null;
  targets_avg?: number | null;
  receptions_avg?: number | null;
  receiving_yards_avg?: number | null;
  receiving_tds_avg?: number | null;
  pass_yards_avg?: number | null;
  pass_tds_avg?: number | null;
  pass_attempts_avg?: number | null;
  sample_games?: number | null;
}

export interface FantasyMatchupGame {
  week: number;
  game_id?: string | null;
  game_date?: string | null;
  opponent?: string | null;
  opponent_name?: string | null;
  opponent_team_id?: string | null;
  home_away?: "vs" | "@" | string | null;
  is_bye?: boolean;
  status?: "played" | "upcoming" | "bye" | string;
  matchup_score?: number | null;
  pass_matchup_score?: number | null;
  rush_matchup_score?: number | null;
  receiving_matchup_score?: number | null;
  position_matchup_score?: number | null;
  difficulty?: FantasyMatchupDifficulty | string | null;
  difficulty_label?: string | null;
  difficulty_10?: number | null;
  opponent_rank?: number | null;
  opponent_rank_of?: number | null;
  fpts_allowed_avg?: number | null;
  fpts_pct_vs_avg?: number | null;
  factors?: FantasyMatchupFactor[];
  interpretation?: string | null;
  opponent_profile?: FantasyMatchupOpponentProfile | null;
}

export interface FantasyMatchupSignal {
  signal_type: string;
  category?: string | null;
  direction?: string | null;
  headline: string;
  body?: string | null;
  confidence?: "high" | "moderate" | "low" | string;
}

export interface FantasyPlayerMatchups {
  player_id: string;
  name?: string | null;
  position?: string | null;
  position_group?: string | null;
  team?: string | null;
  season: number;
  view: FantasyMatchupView | string;
  scoring: FantasyScoringFormat | string;
  available_seasons: number[];
  current_week?: number | null;
  data_through_week?: number | null;
  next_matchup?: FantasyMatchupGame | null;
  outlook_summary?: {
    schedule_difficulty_10?: number | null;
    schedule_difficulty?: FantasyMatchupDifficulty | string;
    schedule_difficulty_label?: string | null;
    favorable_count?: number;
    neutral_count?: number;
    difficult_count?: number;
    overall?: string | null;
    overall_label?: string | null;
  } | null;
  insight_outlook?: {
    headline?: string | null;
    body?: string | null;
    overall?: string | null;
    overall_label?: string | null;
    favorable_count?: number;
    neutral_count?: number;
    difficult_count?: number;
  } | null;
  signals: FantasyMatchupSignal[];
  upcoming_matchups: FantasyMatchupGame[];
  timeline: FantasyMatchupGame[];
  recent_vs_upcoming?: {
    recent_label?: string | null;
    upcoming_label?: string | null;
    recent_avg_score?: number | null;
    upcoming_avg_score?: number | null;
    recent_difficulty_10?: number | null;
    upcoming_difficulty_10?: number | null;
    interpretation?: string | null;
  } | null;
  playoff_outlook?: {
    weeks: FantasyMatchupGame[];
    avg_score?: number | null;
    difficulty?: FantasyMatchupDifficulty | string | null;
    difficulty_label?: string | null;
    favorable_count?: number;
    neutral_count?: number;
    difficult_count?: number;
  } | null;
  empty_message?: string | null;
  data_note?: string | null;
}


export async function getFantasyPlayerMatchups(
  playerId: string,
  options: {
    season?: number | null;
    view?: FantasyMatchupView | string;
    scoring?: FantasyScoringFormat | string;
  } = {}
): Promise<{ matchups: FantasyPlayerMatchups }> {
  const params = new URLSearchParams();
  if (options.season != null) {
    params.set("season", String(options.season));
  }
  if (options.view) {
    params.set("view", String(options.view));
  }
  if (options.scoring) {
    params.set("scoring", String(options.scoring));
  }
  const query = params.toString()
    ? `?${params.toString()}`
    : "";
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/players/${encodeURIComponent(playerId)}/matchups${query}`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}


export type FantasyNewsCategory =
  | "all"
  | "injury"
  | "practice"
  | "role"
  | "team"
  | "depth_chart";

export type FantasyNewsImpactLevel =
  | "all"
  | "high"
  | "moderate"
  | "low";

export type FantasyNewsLookback =
  | "last_24h"
  | "last_3d"
  | "last_7d"
  | "last_30d"
  | "season";

export interface FantasyNewsImpact {
  level?: FantasyNewsImpactLevel | string | null;
  label?: string | null;
  summary?: string | null;
  fantasy_impact?: string | null;
  role_impact?: string | null;
  availability?: string | null;
  confidence?: string | null;
}

export interface FantasyNewsDevelopment {
  id: string;
  event_type?: string | null;
  category?: string | null;
  season?: number | null;
  week?: number | null;
  occurred_at?: string | null;
  subject?: {
    player_id?: string | null;
    name?: string | null;
    relationship?: string | null;
    position?: string | null;
  } | null;
  headline: string;
  body?: string | null;
  facts?: Record<string, unknown> | null;
  impact?: FantasyNewsImpact | null;
  source?: string | null;
  source_label?: string | null;
}

export interface FantasyNewsImportantDevelopment {
  category?: string | null;
  label?: string | null;
  summary?: string | null;
  impact_level?: string | null;
  week?: number | null;
  development_id?: string | null;
}

export interface FantasyPlayerNews {
  player_id: string;
  name?: string | null;
  position?: string | null;
  team?: string | null;
  season: number;
  lookback?: FantasyNewsLookback | string;
  category?: FantasyNewsCategory | string;
  impact_filter?: FantasyNewsImpactLevel | string;
  available_seasons: number[];
  current_week?: number | null;
  last_checked_at?: string | null;
  featured?: FantasyNewsDevelopment | null;
  important_developments: FantasyNewsImportantDevelopment[];
  developments: FantasyNewsDevelopment[];
  counts: {
    total: number;
    high: number;
    moderate: number;
    low: number;
  };
  empty_message?: string | null;
  data_note?: string | null;
}

export async function getFantasyPlayerNews(
  playerId: string,
  options: {
    season?: number | null;
    lookback?: FantasyNewsLookback | string;
    category?: FantasyNewsCategory | string;
    impact?: FantasyNewsImpactLevel | string;
  } = {}
): Promise<{ news: FantasyPlayerNews }> {
  const params = new URLSearchParams();
  if (options.season != null) {
    params.set("season", String(options.season));
  }
  if (options.lookback) {
    params.set("lookback", String(options.lookback));
  }
  if (options.category) {
    params.set("category", String(options.category));
  }
  if (options.impact) {
    params.set("impact", String(options.impact));
  }
  const query = params.toString()
    ? `?${params.toString()}`
    : "";
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/players/${encodeURIComponent(playerId)}/news${query}`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}


export async function getFantasyPlayerSnapshot(
  playerId: string,
  season?: number | null,
  week?: number | null
): Promise<{
  snapshot: FantasyPlayerSnapshot;
}> {

  const params = new URLSearchParams();
  if (season != null) {
    params.set("season", String(season));
  }
  if (week != null) {
    params.set("week", String(week));
  }

  const query =
    params.toString()
      ? `?${params.toString()}`
      : "";

  const response =
    await fetch(
      `${API_BASE_URL}/api/sources/nflverse/players/${encodeURIComponent(playerId)}/snapshot${query}`
    );

  return handleResponse(response);

}


export type DfsSiteId = "draftkings" | "fanduel" | string;
export type DfsContestType = "classic" | "showdown";
export type DfsRisk = "conservative" | "balanced" | "aggressive";

export interface DfsSignal {
  id: string;
  label: string;
  tone?: string;
  body?: string;
}

export interface DfsPlayer {
  dfs_player_id: string;
  player_id: string;
  name: string;
  position: string;
  eligible_positions?: string[];
  team?: string | null;
  opponent?: string | null;
  salary: number;
  projection: number;
  floor?: number | null;
  ceiling?: number | null;
  projected_ownership?: number | null;
  ownership_label?: string | null;
  value?: number | null;
  matchup_rating?: string | null;
  matchup_label?: string | null;
  primary_signal?: DfsSignal | null;
  signals?: DfsSignal[];
  status?: string | null;
  injury_status?: string | null;
  overall_assessment?: string | null;
  is_team_defense?: boolean;
}

export interface DfsLineupPlayer extends DfsPlayer {
  slot: string;
  locked?: boolean;
  is_captain?: boolean;
  base_salary?: number;
  base_projection?: number;
  captain_multiplier?: number | null;
}

export interface DfsLineupInsight {
  id: string;
  tone?: string;
  text: string;
}

export interface DfsLineup {
  lineup_id: string;
  slate_id: string;
  site: string;
  contest_type: string;
  strategy?: string;
  risk?: string;
  players: DfsLineupPlayer[];
  salary_used: number;
  salary_remaining: number;
  salary_cap: number;
  projected_points: number;
  projected_floor?: number | null;
  projected_ceiling?: number | null;
  projected_ownership?: number | null;
  value?: number | null;
  roster_filled: number;
  roster_size: number;
  valid: boolean;
  insights?: DfsLineupInsight[];
  signals?: DfsSignal[];
  edge_summary?: string | null;
}

export interface DfsSlate {
  slate_id: string;
  sport: string;
  label: string;
  season: number;
  week?: number | null;
  kind?: string | null;
  contest_type?: DfsContestType | string;
  site: string;
  site_name: string;
  salary_cap: number;
  captain_multiplier?: number | null;
  roster: Array<{ slot: string; positions: string[]; is_captain?: boolean }>;
  players: DfsPlayer[];
  player_count: number;
  teams?: string[];
  games?: Array<Record<string, unknown>>;
  freshness?: {
    projections_updated_at?: string;
    ownership_updated_at?: string;
    salaries_updated_at?: string;
    note?: string;
  };
}

export interface DfsOptimizeResult {
  lineup: DfsLineup;
  alternatives: DfsLineup[];
  insights: DfsLineupInsight[];
  signals: DfsSignal[];
  optimization_metadata: Record<string, unknown>;
  slate?: {
    slate_id: string;
    label?: string;
    freshness?: DfsSlate["freshness"];
  };
}


export async function listDfsSites(): Promise<{
  sites: Array<{
    id: string;
    name: string;
    salary_cap: number;
    roster_size: number;
    slots: string[];
  }>;
}> {
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/dfs/sites`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}


export async function listDfsSlates(
  season?: number | null,
  contestType?: DfsContestType | string | null
): Promise<{
  slates: Array<{
    slate_id: string;
    sport: string;
    label: string;
    season: number;
    week?: number | null;
    kind?: string;
    contest_type?: string;
    start_label?: string;
    game_count?: number;
    teams?: string[];
  }>;
  count: number;
}> {
  const params = new URLSearchParams();
  if (season != null) {
    params.set("season", String(season));
  }
  if (contestType) {
    params.set("contest_type", String(contestType));
  }
  const query = params.toString()
    ? `?${params.toString()}`
    : "";
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/dfs/slates${query}`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}


export async function getDfsSlate(
  slateId: string,
  options: {
    site?: DfsSiteId;
    season?: number | null;
    contest_type?: DfsContestType | string;
    limit?: number;
  } = {}
): Promise<{ slate: DfsSlate }> {
  const params = new URLSearchParams();
  if (options.site) {
    params.set("site", String(options.site));
  }
  if (options.season != null) {
    params.set("season", String(options.season));
  }
  if (options.contest_type) {
    params.set("contest_type", String(options.contest_type));
  }
  if (options.limit != null) {
    params.set("limit", String(options.limit));
  }
  const query = params.toString()
    ? `?${params.toString()}`
    : "";
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/dfs/slate/${encodeURIComponent(slateId)}${query}`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}


export async function optimizeDfsLineup(
  payload: {
    slate_id: string;
    site?: DfsSiteId;
    contest_type?: DfsContestType | string;
    risk?: DfsRisk | string;
    strategy?: string;
    locked_players?: string[];
    excluded_players?: string[];
    min_salary?: number | null;
    max_ownership?: number | null;
    season?: number | null;
  }
): Promise<DfsOptimizeResult> {
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/dfs/optimize`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  return handleResponse(response);
}


export interface DfsSalaryUploadResult {
  site: string;
  contest_type: string;
  season: number;
  week: number;
  filename?: string | null;
  rows_parsed: number;
  matched: number;
  unmatched: number;
  persisted: number;
  unmatched_samples?: Array<{
    name?: string | null;
    team?: string | null;
    position?: string | null;
    salary?: number | null;
    reason?: string;
  }>;
  matched_samples?: Array<{
    player_id: string;
    name?: string | null;
    team?: string | null;
    position?: string | null;
    salary: number;
    match_score?: number | null;
  }>;
}


export async function uploadDfsSalaries(options: {
  file: File;
  site: DfsSiteId;
  contestType: DfsContestType;
  season?: number | null;
  week?: number | null;
}): Promise<DfsSalaryUploadResult> {
  const formData = new FormData();
  formData.append("file", options.file);
  formData.append("site", options.site);
  formData.append("contest_type", options.contestType);
  if (options.season != null) {
    formData.append("season", String(options.season));
  }
  if (options.week != null) {
    formData.append("week", String(options.week));
  }
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/dfs/salaries/upload`,
    {
      method: "POST",
      body: formData,
    }
  );
  return handleResponse(response);
}


export async function refreshNflverseData(
  modeOrScope:
    | NflverseIngestMode
    | "historical"
    | "current"
    | "incremental"
    | "reprocess"
    | "seasons" = "incremental",
  seasons: number[] = [],
  datasetIds: string[] = [],
  persist: boolean = true,
  layers: string[] = []
): Promise<NflverseRefreshResult> {

  const mode =
    modeOrScope === "current"
      ? "incremental"
      : modeOrScope === "seasons"
        ? undefined
        : modeOrScope;

  const response =
    await fetch(
      `${API_BASE_URL}/api/sources/nflverse/refresh`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          mode,
          scope: modeOrScope === "seasons" ? "seasons" : modeOrScope,
          seasons,
          dataset_ids: datasetIds,
          layers,
          persist,
        }),
      }
    );

  return handleResponse<NflverseRefreshResult>(
    response
  );

}


export async function getNflverseDataQuality(
  live: boolean = true
): Promise<NflverseDataQualityResult> {

  const params = new URLSearchParams({
    live: live ? "true" : "false",
  });

  const response =
    await fetch(
      `${API_BASE_URL}/api/sources/nflverse/quality?${params.toString()}`
    );

  return handleResponse<NflverseDataQualityResult>(
    response
  );

}


export async function analyzeNflverseDataset(
  datasetId: string,
  seasons: number[] = [],
  mappings: FieldMapping[] = [],
  productIds: string[] = []
): Promise<DatasetAnalysis> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/sources/nflverse/analyze`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          dataset_id: datasetId,
          seasons,
          mappings,
          product_ids: productIds,
        }),
      }
    );

  return handleResponse<DatasetAnalysis>(
    response
  );

}


/* --------------------------------------------------------------------------
 * Data Products
 * ------------------------------------------------------------------------ */

export async function createDataProduct(
  product: unknown
) {

  const response =
    await fetch(
      `${API_BASE_URL}/api/data-products/`,
      {
        method:
          "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify(
            product
          ),
      }
    );


  if (!response.ok) {

    const errorText =
      await response.text();

    throw new Error(
      `Failed to create data product: ${errorText}`
    );

  }


  return response.json();

}


export async function getDataProducts() {

  const url =
    `${API_BASE_URL}/api/data-products`;

  const response =
    await fetch(
      url
    );


  if (!response.ok) {

    const errorText =
      await response.text();

    throw new Error(
      `Failed to load data products: ${errorText}`
    );

  }


  return response.json();

}


export async function getProductVersions(
  definitionId: string
) {

  const response =
    await fetch(
      `${API_BASE_URL}/api/data-products/by-definition/${encodeURIComponent(definitionId)}/versions`
    );


  if (!response.ok) {

    const errorText =
      await response.text();

    throw new Error(
      `Failed to load product versions: ${errorText}`
    );

  }


  return response.json();

}


export async function getDataProduct(
  productId: string
) {

  const response =
    await fetch(
      `${API_BASE_URL}/api/data-products/${productId}`
    );


  if (!response.ok) {

    const errorText =
      await response.text();

    throw new Error(
      `Failed to load data product: ${errorText}`
    );

  }


  return response.json();

}


export async function archiveDataProduct(
  productId: string
) {

  const response =
    await fetch(
      `${API_BASE_URL}/api/data-products/${productId}`,
      {
        method:
          "DELETE",
      }
    );


  if (!response.ok) {

    const errorText =
      await response.text();

    throw new Error(
      `Failed to archive data product: ${errorText}`
    );

  }


  return response.json();

}


export async function updateDataProduct(
  productId: string,
  product: any
) {

  const url =
    `${API_BASE_URL}/api/data-products/${productId}`;


  console.log(
    "================================="
  );

  console.log(
    "UPDATE DATA PRODUCT"
  );

  console.log(
    "API_BASE_URL:",
    API_BASE_URL
  );

  console.log(
    "productId:",
    productId
  );

  console.log(
    "URL:",
    url
  );

  console.log(
    "================================="
  );


  try {

    const response =
      await fetch(
        url,
        {
          method:
            "PUT",

          headers: {
            "Content-Type":
              "application/json",
          },

          body:
            JSON.stringify(
              product
            ),
        }
      );


    console.log(
      "UPDATE RESPONSE STATUS:",
      response.status
    );


    if (!response.ok) {

      const errorText =
        await response.text();


      console.error(
        "UPDATE RESPONSE:",
        errorText
      );


      throw new Error(
        `Failed to update data product: ${errorText}`
      );

    }


    return response.json();

  } catch (error) {

    console.error(
      "UPDATE FETCH ERROR:",
      error
    );


    console.error(
      "UPDATE FETCH ERROR NAME:",
      error instanceof Error
        ? error.name
        : "unknown"
    );


    console.error(
      "UPDATE FETCH ERROR MESSAGE:",
      error instanceof Error
        ? error.message
        : "unknown"
    );


    throw error;

  }

}


/* --------------------------------------------------------------------------
 * Dataset Types
 * ------------------------------------------------------------------------ */

export async function getDatasetTypes(): Promise<DatasetType[]> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/datasets/types`
    );


  if (!response.ok) {

    const errorText =
      await response.text();

    throw new Error(
      `Failed to load dataset types: ${errorText}`
    );

  }


  return response.json();

}


/* --------------------------------------------------------------------------
 * Dataset Type → Data Products
 * ------------------------------------------------------------------------ */

export async function getDatasetTypeDataProducts(
  datasetTypeId: string
) {

  const response =
    await fetch(
      `${API_BASE_URL}/api/datasets/${datasetTypeId}/data-products`
    );


  if (!response.ok) {

    const errorText =
      await response.text();

    throw new Error(
      `Failed to load data products: ${errorText}`
    );

  }


  return response.json();

}


/* --------------------------------------------------------------------------
 * Saved Field Mappings (cross-browser)
 * ------------------------------------------------------------------------ */

export interface SavedFieldMappingsRecord {
  dataset_type_id: string;
  uploaded_columns: string[];
  mappings: FieldMapping[];
  updated_at?: string | null;
}

export async function getSavedFieldMappings(
  datasetTypeId: string
): Promise<SavedFieldMappingsRecord | null> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/datasets/${datasetTypeId}/field-mappings`
    );


  if (response.status === 404) {
    return null;
  }


  if (!response.ok) {

    const errorText =
      await response.text();

    throw new Error(
      `Failed to load saved field mappings: ${errorText}`
    );

  }


  return response.json();

}


export async function saveSavedFieldMappings(
  datasetTypeId: string,
  payload: {
    uploaded_columns: string[];
    mappings: FieldMapping[];
  }
): Promise<SavedFieldMappingsRecord> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/datasets/${datasetTypeId}/field-mappings`,
      {
        method: "PUT",

        headers: {
          "Content-Type":
            "application/json",
        },

        body: JSON.stringify(payload),
      }
    );


  if (!response.ok) {

    const errorText =
      await response.text();

    throw new Error(
      `Failed to save field mappings: ${errorText}`
    );

  }


  return response.json();

}


/* --------------------------------------------------------------------------
 * Field Mapping
 * ------------------------------------------------------------------------ */

export async function mapDatasetFields(
  datasetType: string,
  productId: string,
  uploadedFields: string[]
) {

  const response =
    await fetch(
      `${API_BASE_URL}/api/datasets/field-mapping`,
      {
        method:
          "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify({
            dataset_type:
              datasetType,

            product_id:
              productId,

            uploaded_fields:
              uploadedFields,
          }),
      }
    );


  if (!response.ok) {

    const errorText =
      await response.text();

    throw new Error(
      `Failed to map dataset fields: ${errorText}`
    );

  }


  return response.json();

}


/* --------------------------------------------------------------------------
 * Business Concept Identification
 * ------------------------------------------------------------------------ */

export async function identifyBusinessConcepts(
  columns: DatasetField[]
): Promise<ConceptIdentificationResult> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/datasets/identify-concepts`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          columns: columns.map(
            column => ({
              name: column.name,
              dataType:
                column.dataType,
            })
          ),
        }),
      }
    );


  return handleResponse<
    ConceptIdentificationResult
  >(response);

}


/* --------------------------------------------------------------------------
 * Analytical Capability Detection
 * ------------------------------------------------------------------------ */

export async function detectAnalyticalCapabilities(
  concepts: BusinessConcept[]
): Promise<CapabilityDetectionResult> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/datasets/detect-capabilities`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          concepts,
        }),
      }
    );


  return handleResponse<
    CapabilityDetectionResult
  >(response);

}


/* --------------------------------------------------------------------------
 * Analytical Candidate Generation
 * ------------------------------------------------------------------------ */

export async function generateAnalyticalCandidates(
  capabilities: AnalyticalCapability[],
  datasetArchetype?: {
    primary?: string | null;
    primary_archetype?: string | null;
    confidence?: number;
  } | null,
  primaryArchetype?: string | null
): Promise<AnalyticalCandidateResult> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/datasets/generate-analysis-candidates`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          capabilities,
          dataset_archetype:
            datasetArchetype ?? undefined,
          primary_archetype:
            primaryArchetype ??
            datasetArchetype?.primary ??
            datasetArchetype?.primary_archetype ??
            undefined,
        }),
      }
    );


  return handleResponse<
    AnalyticalCandidateResult
  >(response);

}


/* --------------------------------------------------------------------------
 * Dataset Classification
 * ------------------------------------------------------------------------ */

export async function classifyDataset(
  concepts: BusinessConcept[]
): Promise<DatasetClassificationResult> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/datasets/classify`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          concepts,
        }),
      }
    );


  return handleResponse<
    DatasetClassificationResult
  >(response);

}


/* --------------------------------------------------------------------------
 * Dataset Grain Determination
 * ------------------------------------------------------------------------ */

export async function determineDatasetGrain(
  concepts: BusinessConcept[],
  columnStats: ColumnStatInput[] = []
): Promise<GrainDeterminationResult> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/datasets/determine-grain`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          concepts,
          column_stats: columnStats,
        }),
      }
    );


  return handleResponse<
    GrainDeterminationResult
  >(response);

}


/* --------------------------------------------------------------------------
 * Semantic Understanding (developer debug)
 * ------------------------------------------------------------------------ */

export async function fetchSemanticUnderstanding(
  columns: DatasetField[],
  columnStats: ColumnStatInput[] = []
): Promise<{
  semantic_model: unknown;
  capabilities: unknown[];
  dataset_archetype: unknown;
  semantic_understanding: SemanticUnderstanding;
}> {

  const response =
    await fetch(
      `${API_BASE_URL}/api/datasets/semantic-understanding`,
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          columns: columns.map(
            (column) => ({
              name: column.name,
              dataType: column.dataType,
            })
          ),
          column_stats: columnStats,
        }),
      }
    );

  return handleResponse(response);

}


/* --------------------------------------------------------------------------
 * Data Coverage
 * ------------------------------------------------------------------------ */

export async function calculateDataCoverage(
  productId: string,
  uploadedFields: string[],
  mappings: FieldMapping[]
) {

  const response =
    await fetch(
      `${API_BASE_URL}/api/data-products/coverage`,
      {
        method:
          "POST",

        headers: {
          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify({

            product_id:
              productId,

            uploaded_fields:
              uploadedFields,

            mappings,

          }),
      }
    );


  if (!response.ok) {

    const errorText =
      await response.text();

    throw new Error(
      `Failed to calculate data coverage: ${errorText}`
    );

  }


  return response.json();

}