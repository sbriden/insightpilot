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


export type FantasyScoringFormat = "ppr" | "half_ppr" | "standard";


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
  projection?: number | null;
  scoring?: FantasyScoringFormat | string | null;
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
    scoring?: FantasyScoringFormat | string;
  } = {}
): Promise<{
  players: FantasyPlayerSearchHit[];
  count: number;
  scoring?: FantasyScoringFormat | string;
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
  if (options.scoring) {
    params.set("scoring", String(options.scoring));
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
  logo_url?: string | null;
}


export interface FantasyTeamRecord {
  wins: number;
  losses: number;
  ties: number;
  point_differential?: number | null;
}


export interface FantasyTeamOffense {
  points?: number | null;
  points_per_game?: number | null;
  yards?: number | null;
  yards_per_game?: number | null;
  yards_per_play?: number | null;
  epa_per_play?: number | null;
  pass_epa_per_attempt?: number | null;
  rush_epa_per_attempt?: number | null;
  pass_rate?: number | null;
  seconds_per_play?: number | null;
  red_zone_td_rate?: number | null;
  turnovers?: number | null;
  turnovers_per_game?: number | null;
}


export interface FantasyTeamDefense {
  points_allowed?: number | null;
  points_allowed_per_game?: number | null;
  yards_allowed?: number | null;
  yards_allowed_per_game?: number | null;
  pass_yards_allowed_per_game?: number | null;
  rush_yards_allowed_per_game?: number | null;
  pass_epa_allowed_per_game?: number | null;
  rush_epa_allowed_per_game?: number | null;
  sack_rate?: number | null;
  pressure_rate?: number | null;
}


export interface FantasyTeamEfficiency {
  completion_pct?: number | null;
  yards_per_attempt?: number | null;
  yards_per_carry?: number | null;
  catch_rate?: number | null;
  yards_per_target?: number | null;
  yards_per_reception?: number | null;
}


export interface FantasyTeamTotals {
  games?: number | null;
  record?: FantasyTeamRecord | null;
  offense?: FantasyTeamOffense | null;
  defense?: FantasyTeamDefense | null;
  efficiency?: FantasyTeamEfficiency | null;
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
  team_totals?: FantasyTeamTotals | null;
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
  opponent?: string | null;
  opponent_label?: string | null;
  home_away?: string | null;
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
  salary_source?: string | null;
  projection: number;
  raw_projection?: number | null;
  insightpilot_projection?: number | null;
  base_projection?: number | null;
  projection_adjustment?: number | null;
  projection_adjustment_reason?: string | null;
  projection_confidence?: string | null;
  sample_size_confidence?: string | null;
  current_season_games?: number | null;
  historical_games?: number | null;
  historical_baseline?: number | null;
  matchup_adjustment_factor?: number | null;
  floor?: number | null;
  ceiling?: number | null;
  projected_ownership?: number | null;
  ownership_label?: string | null;
  value?: number | null;
  matchup_rating?: string | null;
  matchup_label?: string | null;
  matchup_score?: number | null;
  environment_score?: number | null;
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
  correlation?: DfsLineupCorrelation | null;
  lineup_correlation_score?: number | null;
}

export interface DfsCorrelationPair {
  player_id: string;
  correlated_player_id: string;
  player_name?: string | null;
  correlated_player_name?: string | null;
  correlation_type?: string;
  correlation_score: number;
  confidence?: string | null;
  confidence_score?: number | null;
  correlation_reason?: string | null;
  source?: string | null;
  rule_id?: string | null;
}

export interface DfsLineupCorrelation {
  lineup_correlation_score?: number;
  positive_correlation?: number;
  negative_correlation?: number;
  concentration_penalty?: number;
  soft_constraint_penalty?: number;
  pair_count?: number;
  pairs?: DfsCorrelationPair[];
  positive_pairs?: DfsCorrelationPair[];
  negative_pairs?: DfsCorrelationPair[];
}

export interface DfsPortfolioCorrelationExposure {
  player_id: string;
  correlated_player_id: string;
  player_name?: string | null;
  correlated_player_name?: string | null;
  correlation_score: number;
  correlation_reason?: string | null;
  lineups: number;
  exposure: number;
  exposure_pct: number;
}

export interface DfsPortfolioCorrelationSummary {
  lineup_count?: number;
  positive_correlation_exposure?: DfsPortfolioCorrelationExposure[];
  negative_correlation_exposure?: DfsPortfolioCorrelationExposure[];
  narrative?: string | null;
}

export interface DfsSlate {
  slate_id: string;
  sport: string;
  label: string;
  season: number;
  week?: number | null;
  kind?: string | null;
  contest_type?: DfsContestType | string;
  scoring?: FantasyScoringFormat | string;
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

export type DfsPortfolioStrategy =
  | "max_projection"
  | "balanced"
  | "tournament"
  | "contrarian"
  | "cash"
  | "gpp"
  | "custom";

export interface DfsPortfolioExposureRow {
  player_id: string;
  name?: string | null;
  position?: string | null;
  team?: string | null;
  opponent?: string | null;
  projection?: number | null;
  ceiling?: number | null;
  floor?: number | null;
  projected_ownership?: number | null;
  salary?: number | null;
  lineups: number;
  lineup_count: number;
  generated_lineup_count?: number;
  exposure: number;
  exposure_pct: number;
  captain_lineups?: number;
  captain_exposure?: number;
  captain_exposure_pct?: number;
  min_exposure?: number | null;
  max_exposure?: number | null;
  max_allowed_exposure?: number | null;
  max_allowed_lineups?: number | null;
  remaining_capacity?: number | null;
  min_captain_exposure?: number | null;
  max_captain_exposure?: number | null;
  locked?: boolean;
  excluded?: boolean;
}

export interface DfsPortfolioSignal {
  id: string;
  type: string;
  severity?: string;
  explanation?: string;
  action?: string;
  player_id?: string;
  exposure?: number;
  similarity?: number;
  unique_players?: number;
  threshold?: number;
}

export interface DfsPortfolioSummary {
  portfolio_id: string;
  slate_id: string;
  site: string;
  contest_type: string;
  strategy: string;
  risk?: string;
  lineup_count: number;
  requested_lineup_count?: number;
  max_lineup_similarity?: number;
  default_max_exposure?: number;
  unique_players: number;
  average_projection: number;
  average_ceiling: number;
  average_floor?: number;
  average_ownership: number;
  average_salary: number;
  average_salary_remaining?: number;
  best_projection?: number;
  lowest_projection?: number;
  unique_lineups?: number;
  min_unique_players?: number;
  average_lineup_similarity: number;
  diversity_label: string;
  constraints?: Record<string, unknown>;
}

export interface DfsPortfolioLineup extends DfsLineup {
  portfolio_index?: number;
  similarity?: number | null;
  player_ids?: string[];
  game_script_id?: string | null;
  game_script_label?: string | null;
  game_script_code?: string | null;
  game_script_weight?: number | null;
  game_script_implication?: string | null;
  game_script_raw_probability?: number | null;
}

export interface DfsGameScriptAllocation {
  script_id: string;
  label?: string | null;
  code?: string | null;
  weight: number;
  lineup_count: number;
  target_lineup_count?: number | null;
  raw_probability?: number | null;
  implication?: string | null;
  favorite?: string | null;
  underdog?: string | null;
}

export interface DfsPortfolioGameScripts {
  favorite?: string | null;
  underdog?: string | null;
  home_team?: string | null;
  away_team?: string | null;
  projected_total?: number | null;
  market_total?: number | null;
  market_spread?: number | null;
  allocations: DfsGameScriptAllocation[];
  note?: string | null;
}

export interface DfsPortfolioResult {
  portfolio: DfsPortfolioSummary & {
    game_scripts?: DfsPortfolioGameScripts | null;
  };
  lineups: DfsPortfolioLineup[];
  exposure: { players: DfsPortfolioExposureRow[] };
  similarity: {
    average: number;
    most_similar_pairs: Array<{
      lineup_a?: string;
      lineup_b?: string;
      index_a?: number;
      index_b?: number;
      similarity: number;
      shared_players: number;
      roster_size: number;
    }>;
  };
  correlation?: DfsPortfolioCorrelationSummary | null;
  core?: Array<{
    player_id: string;
    name?: string | null;
    position?: string | null;
    exposure: number;
    exposure_pct: number;
    lineups: number;
  }>;
  differentiators?: Array<{
    player_id: string;
    name?: string | null;
    position?: string | null;
    exposure: number;
    exposure_pct: number;
    lineups: number;
  }>;
  signals: DfsPortfolioSignal[];
  alerts: DfsPortfolioSignal[];
  player_diagnostics?: Array<{
    player_id: string;
    name?: string | null;
    position?: string | null;
    projection?: number | null;
    exposure: number;
    exposure_pct: number;
    lineups: number;
    max_exposure: number;
    max_allowed_lineups: number;
    remaining_capacity: number;
    candidate_lineups_with_player: number;
    reasons: string[];
    why_not_more: string;
  }>;
  game_scripts?: DfsPortfolioGameScripts | null;
  optimization_metadata?: Record<string, unknown>;
  slate?: {
    slate_id: string;
    label?: string;
    freshness?: DfsSlate["freshness"];
  };
}

export async function generateDfsPortfolio(payload: {
  slate_id: string;
  site?: DfsSiteId;
  contest_type?: DfsContestType | string;
  scoring?: FantasyScoringFormat | string;
  lineup_count?: number;
  strategy?: DfsPortfolioStrategy | string;
  risk?: DfsRisk | string;
  max_lineup_similarity?: number | null;
  min_unique_players?: number | null;
  default_max_exposure?: number | null;
  default_max_captain_exposure?: number | null;
  player_exposure?: {
    min?: Record<string, number>;
    max?: Record<string, number>;
    target?: Record<string, number>;
    captain_min?: Record<string, number>;
    captain_max?: Record<string, number>;
    lock?: string[];
    exclude?: string[];
  };
  locked_players?: string[];
  excluded_players?: string[];
  season?: number | null;
  seed?: number | null;
}): Promise<DfsPortfolioResult> {
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/dfs/portfolio`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  return handleResponse(response);
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


export async function listDfsWeeks(
  season?: number | null
): Promise<{
  season: number;
  weeks: number[];
  current_week: number;
}> {
  const params = new URLSearchParams();
  if (season != null) {
    params.set("season", String(season));
  }
  const query = params.toString()
    ? `?${params.toString()}`
    : "";
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/dfs/weeks${query}`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}


export async function listDfsSlates(
  season?: number | null,
  contestType?: DfsContestType | string | null,
  week?: number | null
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
  if (week != null) {
    params.set("week", String(week));
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
    scoring?: FantasyScoringFormat | string;
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
  if (options.scoring) {
    params.set("scoring", String(options.scoring));
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
    scoring?: FantasyScoringFormat | string;
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

/* ------------------------------------------------------------------ */
/* Sports Betting                                                      */
/* ------------------------------------------------------------------ */

export type BettingMarketType =
  | "spread"
  | "total"
  | "moneyline"
  | string;

export type BettingConfidence = "High" | "Moderate" | "Low" | string;

export interface BettingEnsembleEstimates {
  estimates?: Record<string, number | null | undefined>;
  projection_mean?: number | null;
  projection_stddev?: number | null;
  model_agreement?: number | null;
  n_models?: number | null;
  unit?: string | null;
  label?: string | null;
  range?: number | null;
}

export interface BettingModelDisagreement {
  spread?: BettingEnsembleEstimates | null;
  total?: BettingEnsembleEstimates | null;
  models_available?: string[];
  note?: string | null;
}

export interface BettingSignal {
  signal_id: string;
  event_id: string;
  market_id?: string | null;
  signal_type: string;
  label: string;
  direction?: string | null;
  confidence?: BettingConfidence | null;
  explanation?: string | null;
  event_label?: string | null;
}

export interface BettingMarket {
  market_id: string;
  event_id: string;
  event_label?: string | null;
  start_time?: string | null;
  sport?: string;
  league?: string;
  home_team?: string | null;
  away_team?: string | null;
  market_type: BettingMarketType;
  selection: string;
  line?: number | null;
  price?: number | null;
  opening_line?: number | null;
  opening_price?: number | null;
  current_line?: number | null;
  current_price?: number | null;
  line_move?: number | null;
  model_probability?: number | null;
  raw_model_probability?: number | null;
  probability_calibrated?: boolean;
  probability_calibration_method?: string | null;
  market_probability?: number | null;
  model_fair_price?: number | null;
  model_projection?: number | null;
  market_implied_projection?: number | null;
  projection_mean?: number | null;
  projection_stddev?: number | null;
  model_agreement?: number | null;
  model_agreement_label?: string | null;
  ensemble_estimates?: Record<string, number | null | undefined> | null;
  ensemble_n_models?: number | null;
  model_disagreement?: BettingEnsembleEstimates | null;
  edge?: number | null;
  edge_probability?: number | null;
  expected_value?: number | null;
  confidence?: BettingConfidence | null;
  confidence_explanation?: string | null;
  direction?: string | null;
  primary_signal?: string | null;
  opportunity?: string | null;
  prediction?: {
    has_prediction?: boolean;
    market_type?: string | null;
    selection?: string | null;
    direction?: string | null;
    model_projection?: number | null;
    market_projection?: number | null;
    raw_probability?: number | null;
    calibrated_probability?: number | null;
    note?: string | null;
  } | null;
  data_quality?: {
    score?: number | null;
    label?: string | null;
    factors?: string[];
  } | null;
  bet_qualification?: {
    qualified?: boolean;
    no_bet?: boolean;
    actionable?: boolean;
    status?: "strong_bet" | "lean" | "pass" | string | null;
    label?: "Strong Bet" | "Lean" | "Pass" | string | null;
    summary?: string | null;
    reasons_pass?: string[];
    reasons_fail?: string[];
    gates?: Record<string, boolean>;
    market_movement?: {
      invalidates?: boolean;
      reason?: string | null;
    } | null;
  } | null;
  bet_qualified?: boolean;
  bet_status?: "strong_bet" | "lean" | "pass" | string | null;
  bet_label?: "Strong Bet" | "Lean" | "Pass" | string | null;
  no_bet?: boolean;
  decision_pipeline?: string[];
  status?: string | null;
  source?: string | null;
}

export interface BettingInjuryNote {
  player_id: string;
  player_name: string;
  team?: string | null;
  team_id?: string | null;
  position?: string | null;
  depth_order?: number | null;
  depth_label?: string | null;
  game_status?: string | null;
  practice_status?: string | null;
  injury_type?: string | null;
  is_starter?: boolean;
  impact_side?: "offense" | "defense" | string | null;
  role_multiplier?: number | null;
  base_impact?: number | null;
  raw_magnitude?: number | null;
  own_score_delta?: number | null;
  opponent_score_delta?: number | null;
  projection_impact_pts?: number | null;
  quality_factors?: {
    starter_quality?: number;
    replacement_quality?: number;
    snap_expectation?: number;
    team_dependency?: number;
    backup_performance?: number;
    scheme_impact?: number;
  } | null;
  is_expected_to_play?: boolean | null;
}

export interface BettingGameScript {
  script_id: string;
  label: string;
  summary?: string | null;
  probability: number;
  explanation?: string | null;
  drivers?: string[];
  favorite?: string | null;
  underdog?: string | null;
}

export interface BettingEvent {
  event_id: string;
  sport?: string;
  league?: string;
  season?: number | null;
  week?: number | null;
  start_time?: string | null;
  status?: string | null;
  home_team?: string | null;
  away_team?: string | null;
  home_team_name?: string | null;
  away_team_name?: string | null;
  label: string;
  market_spread?: number | null;
  market_total?: number | null;
  market_home_score?: number | null;
  market_away_score?: number | null;
  projected_home_score?: number | null;
  projected_away_score?: number | null;
  projected_total?: number | null;
  model_spread?: number | null;
  residual_home?: number | null;
  residual_away?: number | null;
  opening_spread?: number | null;
  current_spread?: number | null;
  opening_total?: number | null;
  current_total?: number | null;
  opening_moneyline?: number | null;
  current_moneyline?: number | null;
  spread_move?: number | null;
  total_move?: number | null;
  moneyline_move?: number | null;
  market_movement?: {
    opening_spread?: number | null;
    current_spread?: number | null;
    opening_total?: number | null;
    current_total?: number | null;
    opening_moneyline?: number | null;
    current_moneyline?: number | null;
    spread_move?: number | null;
    total_move?: number | null;
    moneyline_move?: number | null;
    moved?: boolean;
    seconds_since_move?: number | null;
    spread_velocity?: number | null;
    total_velocity?: number | null;
    consensus_move?: string | null;
    vs_model?: {
      label?: string | null;
      aligned?: boolean | null;
      explanation?: string | null;
    } | null;
    note?: string | null;
  } | null;
  residuals?: {
    architecture?: string | null;
    residual_home?: number | null;
    residual_away?: number | null;
    raw_residual_home?: number | null;
    raw_residual_away?: number | null;
    total_residual_home?: number | null;
    total_residual_away?: number | null;
    shrink?: number | null;
    confidence?: string | null;
    situational_residual_home?: number | null;
    situational_residual_away?: number | null;
  } | null;
  model_disagreement?: BettingModelDisagreement | null;
  projection_blend?: {
    confidence?: string | null;
    market_weight?: number | null;
    model_weight?: number | null;
    mode?: string | null;
    formula?: string | null;
  } | null;
  game_scripts?: BettingGameScript[];
  injury_adjustment_home?: number | null;
  injury_adjustment_away?: number | null;
  injuries?: BettingInjuryNote[];
  model_drivers?: string[];
  injury_report_week?: number | null;
  primary_signal?: BettingSignal | null;
  market_ids?: string[];
  market_timestamp?: string | null;
  source?: string | null;
}

export interface BettingSlate {
  sport: string;
  league: string;
  season: number;
  week: number;
  slate_id: string;
  label: string;
  game_count: number;
  market_count: number;
  model_coverage_pct: number;
  markets_with_edge: number;
  markets_qualified?: number;
  markets_strong_bet?: number;
  markets_lean?: number;
  markets_no_bet?: number;
  average_confidence: BettingConfidence;
  events: BettingEvent[];
  markets: BettingMarket[];
  signals: BettingSignal[];
  source?: string | null;
  source_note?: string | null;
  generated_at?: string | null;
  injury_report_week?: number | null;
}

export async function listBettingWeeks(
  season?: number | null
): Promise<{
  sport: string;
  league: string;
  season: number;
  weeks: number[];
  current_week: number | null;
}> {
  const params = new URLSearchParams();
  if (season != null) {
    params.set("season", String(season));
  }
  params.set("sport", "NFL");
  const query = `?${params.toString()}`;
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/betting/weeks${query}`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}

export async function getBettingSlate(options?: {
  season?: number | null;
  week?: number | null;
}): Promise<BettingSlate> {
  const params = new URLSearchParams();
  params.set("sport", "NFL");
  if (options?.season != null) {
    params.set("season", String(options.season));
  }
  if (options?.week != null) {
    params.set("week", String(options.week));
  }
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/betting/slate?${params.toString()}`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}

export interface BettingModelResultRow {
  market_id?: string;
  event_id?: string;
  event_label?: string | null;
  market_type?: string | null;
  selection?: string | null;
  line?: number | null;
  bet_line?: number | null;
  closing_line?: number | null;
  bet_price?: number | null;
  closing_price?: number | null;
  clv?: number | null;
  clv_unit?: string | null;
  beat_close?: boolean | null;
  result?: string | null;
  model_correct?: boolean | null;
  model_probability?: number | null;
  edge?: number | null;
  confidence?: string | null;
  home_score?: number | null;
  away_score?: number | null;
  actual_total?: number | null;
  actual_spread?: number | null;
  model_total?: number | null;
  model_spread?: number | null;
  total_error?: number | null;
  spread_error?: number | null;
  home_team?: string | null;
  away_team?: string | null;
  projection_captured_at?: string | null;
  units?: number | null;
  edge_bucket?: string | null;
  favorite_underdog?: string | null;
  home_away?: string | null;
  week?: number | null;
}

export interface BettingClvBreakdownRow {
  key: string;
  bets: number;
  decided: number;
  correct: number;
  hit_rate?: number | null;
  average_clv?: number | null;
  median_clv?: number | null;
  beat_close_pct?: number | null;
  units?: number | null;
  roi_pct?: number | null;
  average_edge?: number | null;
  average_closing_edge?: number | null;
  sample_size?: number | null;
  win_rate?: number | null;
  lo?: number | null;
  hi?: number | null;
  mean_predicted_pct?: number | null;
  calibration_gap?: number | null;
  calibration?: {
    mean_predicted_pct?: number | null;
    actual_win_pct?: number | null;
    gap_pp?: number | null;
    n?: number | null;
  } | null;
}

export interface BettingMarketPerformanceCard {
  market_type?: string;
  label?: string;
  key?: string;
  bets?: number;
  sample_size?: number | null;
  decided?: number;
  correct?: number;
  hit_rate?: number | null;
  ats_win_pct?: number | null;
  ou_win_pct?: number | null;
  win_pct?: number | null;
  roi_pct?: number | null;
  units?: number | null;
  average_clv?: number | null;
  median_clv?: number | null;
  mae?: number | null;
  mean_predicted_pct?: number | null;
  calibration_gap?: number | null;
  brier?: number | null;
  quality_score?: number | null;
  confidence_weight?: number | null;
  confidence_active?: boolean;
  high_min?: number | null;
  moderate_min?: number | null;
  calibration?: {
    mean_predicted_pct?: number | null;
    actual_win_pct?: number | null;
    gap_pp?: number | null;
    brier?: number | null;
    n?: number | null;
  } | null;
}

export interface BettingMarketPerformance {
  markets?: {
    spread?: BettingMarketPerformanceCard;
    total?: BettingMarketPerformanceCard;
    moneyline?: BettingMarketPerformanceCard;
    [key: string]: BettingMarketPerformanceCard | undefined;
  };
  ranking?: string[];
  best_market?: string | null;
  note?: string | null;
  active?: boolean;
}

export interface BettingEdgeConfidenceDiagnostics {
  thresholds?: {
    active?: boolean;
    method?: string | null;
    sample_size?: number | null;
    high_min?: number | null;
    moderate_min?: number | null;
    note?: string | null;
    by_market?: Record<
      string,
      {
        active?: boolean;
        high_min?: number | null;
        moderate_min?: number | null;
        weight?: number | null;
        quality_score?: number | null;
        sample_size?: number | null;
      }
    >;
  } | null;
  baseline?: {
    win_rate?: number | null;
    roi_pct?: number | null;
    average_clv?: number | null;
    sample_size?: number | null;
  } | null;
  buckets?: BettingClvBreakdownRow[];
  by_market?: Record<string, unknown>;
  market_note?: string | null;
  note?: string | null;
}

export interface BettingModelResultsSummary {
  total_markets: number;
  decided: number;
  model_correct: number;
  model_incorrect: number;
  push: number;
  hit_rate?: number | null;
  ats_win_pct?: number | null;
  ou_win_pct?: number | null;
  ml_win_pct?: number | null;
  average_clv?: number | null;
  median_clv?: number | null;
  beat_close_pct?: number | null;
  units?: number | null;
  roi_pct?: number | null;
  average_edge?: number | null;
  average_closing_edge?: number | null;
  clv?: {
    bets?: number;
    decided?: number;
    ats_win_pct?: number | null;
    ou_win_pct?: number | null;
    ml_win_pct?: number | null;
    average_clv?: number | null;
    median_clv?: number | null;
    beat_close_pct?: number | null;
    units?: number | null;
    roi_pct?: number | null;
    average_edge?: number | null;
    average_closing_edge?: number | null;
    note?: string | null;
  } | null;
  average_total_error?: number | null;
  average_spread_error?: number | null;
  average_abs_total_error?: number | null;
  average_abs_spread_error?: number | null;
  by_market: BettingClvBreakdownRow[];
  by_confidence: BettingClvBreakdownRow[];
  by_edge_bucket?: BettingClvBreakdownRow[];
  by_favorite_underdog?: BettingClvBreakdownRow[];
  by_home_away?: BettingClvBreakdownRow[];
  by_week?: BettingClvBreakdownRow[];
  edge_confidence?: BettingEdgeConfidenceDiagnostics | null;
  market_performance?: BettingMarketPerformance | null;
  calibration: Array<{
    bucket: string;
    bets: number;
    predicted_midpoint: number;
    actual_win_rate?: number | null;
  }>;
  settled_markets: BettingModelResultRow[];
  games_settled: number;
  performance_trend?: BettingPerformanceTrendPoint[];
  trend_summary?: BettingPerformanceTrendSummary | null;
  note?: string | null;
}

export interface BettingPerformanceTrendPoint {
  season: number;
  week: number;
  label: string;
  markets: number;
  decided: number;
  correct: number;
  hit_rate?: number | null;
  cumulative_hit_rate?: number | null;
  hit_rate_delta?: number | null;
  games_settled: number;
  average_total_error?: number | null;
  average_abs_spread_error?: number | null;
}

export interface BettingPerformanceTrendSummary {
  weeks: number;
  latest_week?: number | null;
  latest_hit_rate?: number | null;
  season_hit_rate?: number | null;
  hit_rate_delta?: number | null;
  first_week?: number | null;
  direction?: "improving" | "declining" | "flat" | string | null;
}

export interface BettingCalibrationFeedback {
  sample_games?: number;
  total_bias?: number;
  spread_bias?: number;
  raw_mean_total_error?: number | null;
  raw_mean_spread_error?: number | null;
  active?: boolean;
  dampen?: number | null;
  note?: string | null;
}

export interface BettingResultsPayload {
  sport: string;
  league: string;
  season: number;
  week: number;
  slate_id?: string;
  label?: string;
  model_results: BettingModelResultsSummary;
  calibration_feedback?: BettingCalibrationFeedback | null;
  probability_calibration?: {
    active?: boolean;
    method?: string | null;
    sample_size?: number | null;
    metrics?: {
      brier_raw?: number | null;
      brier_calibrated?: number | null;
      ece_raw?: number | null;
      ece_calibrated?: number | null;
      empirical_win_rate?: number | null;
      mean_predicted_raw?: number | null;
      mean_predicted_calibrated?: number | null;
      n?: number | null;
    } | null;
    note?: string | null;
  } | null;
  edge_confidence?: BettingEdgeConfidenceDiagnostics | null;
  market_performance?: BettingMarketPerformance | null;
  generated_at?: string | null;
}

export async function getBettingResults(options?: {
  season?: number | null;
  week?: number | null;
}): Promise<BettingResultsPayload> {
  const params = new URLSearchParams();
  params.set("sport", "NFL");
  if (options?.season != null) {
    params.set("season", String(options.season));
  }
  if (options?.week != null) {
    params.set("week", String(options.week));
  }
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/betting/results?${params.toString()}`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}

export type BettingPositionStatus =
  | "open"
  | "live"
  | "won"
  | "lost"
  | "push"
  | "void"
  | "cancelled";

export interface BettingPortfolioPosition {
  position_id: string;
  market_id: string;
  event_id: string;
  event_label?: string | null;
  sport?: string | null;
  home_team?: string | null;
  away_team?: string | null;
  market_type?: string | null;
  selection?: string | null;
  entry_price?: number | null;
  entry_line?: number | null;
  entry_timestamp?: string | null;
  current_price?: number | null;
  current_line?: number | null;
  model_probability?: number | null;
  market_probability?: number | null;
  edge?: number | null;
  expected_value?: number | null;
  confidence?: BettingConfidence | string | null;
  exposure: number;
  status: BettingPositionStatus | string;
  sportsbook?: string | null;
  notes?: string | null;
  closing_price?: number | null;
  closing_line?: number | null;
  result?: string | null;
  clv?: number | null;
  entry_model_probability?: number | null;
  price_movement?: number | null;
  model_change?: number | null;
  assumption_tags?: string[];
  bet_type?: "single" | "parlay" | string | null;
  parlay_size?: "small" | "medium" | "large" | string | null;
  leg_count?: number | null;
  legs?: Array<{
    market_id?: string;
    event_id?: string;
    event_label?: string | null;
    selection?: string | null;
    market_type?: string | null;
    price?: number | null;
    line?: number | null;
    model_probability?: number | null;
    confidence?: string | null;
  }>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BettingPortfolioAlert {
  signal_id: string;
  title: string;
  body: string;
  cta?: string | null;
}

export interface BettingPortfolioHealthRow {
  id: string;
  label: string;
  value: string;
  detail?: string | null;
}

export interface BettingPortfolioExposureRow {
  positions: number;
  exposure: number;
  exposure_pct: number;
  team?: string;
  game?: string;
  event_id?: string;
  market?: string;
  sport?: string;
}

export interface BettingPortfolioCorrelation {
  left_position_id: string;
  right_position_id: string;
  left_selection?: string | null;
  right_selection?: string | null;
  score: number;
  label: string;
  reasons: string[];
}

export interface BettingPortfolioAnalytics {
  summary: {
    open_positions: number;
    total_exposure: number;
    average_model_edge?: number | null;
    average_confidence?: string | null;
    games_represented: number;
    correlation?: string | null;
  };
  health: BettingPortfolioHealthRow[];
  alerts: BettingPortfolioAlert[];
  exposure: {
    team: BettingPortfolioExposureRow[];
    game: BettingPortfolioExposureRow[];
    sport: BettingPortfolioExposureRow[];
    market: BettingPortfolioExposureRow[];
  };
  correlations: BettingPortfolioCorrelation[];
  assumptions: Array<{ assumption: string; positions: number }>;
  model_vs_market: {
    average_market_probability?: number | null;
    average_model_probability?: number | null;
    average_difference?: number | null;
    average_edge?: number | null;
  };
  edge_distribution: Array<{ bucket: string; count: number }>;
  confidence_distribution: Array<{
    confidence: string;
    count: number;
    pct: number;
  }>;
  price_movements: Array<{
    position_id: string;
    selection?: string | null;
    entry_price?: number | null;
    current_price?: number | null;
    movement?: number | null;
  }>;
  signals?: string[];
}

export interface BettingPortfolioAnalyzeResult {
  portfolio_id: string;
  season?: number | null;
  week?: number | null;
  slate_id?: string | null;
  status_filter?: string;
  positions: BettingPortfolioPosition[];
  visible_positions: BettingPortfolioPosition[];
  analytics: BettingPortfolioAnalytics;
  results: {
    total_positions: number;
    won: number;
    lost: number;
    push: number;
    void?: number;
    win_rate?: number | null;
    total_exposure?: number;
    profit_loss?: number | null;
    roi_pct?: number | null;
    average_odds?: number | null;
    average_model_edge?: number | null;
    average_clv?: number | null;
    by_market?: Array<{
      key: string;
      bets: number;
      won: number;
      lost: number;
      win_rate?: number | null;
      exposure: number;
      profit_loss: number;
      roi_pct?: number | null;
      average_edge?: number | null;
    }>;
    by_confidence?: Array<{
      key: string;
      bets: number;
      won: number;
      lost: number;
      win_rate?: number | null;
      exposure: number;
      profit_loss: number;
      roi_pct?: number | null;
      average_edge?: number | null;
    }>;
    by_bet_type?: Array<{
      key: string;
      bets: number;
      won: number;
      lost: number;
      win_rate?: number | null;
      exposure: number;
      profit_loss: number;
      roi_pct?: number | null;
      average_edge?: number | null;
    }>;
    calibration?: Array<{
      bucket: string;
      bets: number;
      predicted_midpoint: number;
      actual_win_rate?: number | null;
    }>;
    settled_positions?: Array<
      BettingPortfolioPosition & {
        profit_loss?: number | null;
        clv_points?: number | null;
      }
    >;
    note?: string | null;
  };
  calculated_at?: string | null;
}

export async function analyzeBettingPortfolio(payload: {
  positions: BettingPortfolioPosition[];
  season?: number | null;
  week?: number | null;
  status_filter?: string;
}): Promise<BettingPortfolioAnalyzeResult> {
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/betting/portfolio/analyze`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    }
  );
  return handleResponse(response);
}

export interface BettingPortfolioGeneration {
  total_exposure: number;
  risk_exposure: number;
  risk: string;
  allocated_exposure: number;
  position_count: number;
  single_count?: number;
  parlay_count?: number;
  parlay_size_counts?: {
    small?: number;
    medium?: number;
    large?: number;
  };
  target_single_pct?: number;
  target_parlay_pct?: number;
  candidates_considered?: number;
  max_positions?: number;
  max_per_game?: number;
  note?: string | null;
}

export interface BettingPortfolioGenerateResult
  extends BettingPortfolioAnalyzeResult {
  generation: BettingPortfolioGeneration;
}

export async function generateBettingPortfolio(payload: {
  total_exposure: number;
  risk_exposure: number;
  season?: number | null;
  week?: number | null;
  risk?: "conservative" | "balanced" | "aggressive" | string;
  market_types?: string[];
}): Promise<BettingPortfolioGenerateResult> {
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/betting/portfolio/generate`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    }
  );
  return handleResponse(response);
}

export async function createBettingPortfolioPosition(payload: {
  market: BettingMarket;
  exposure?: number;
  notes?: string | null;
  sportsbook?: string | null;
  entry_price?: number | null;
  entry_line?: number | null;
}): Promise<BettingPortfolioPosition> {
  const response = await fetch(
    `${API_BASE_URL}/api/sources/nflverse/betting/portfolio/position`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    }
  );
  return handleResponse(response);
}

/* ── Analytical Applications ───────────────────────────────── */

export interface AnalyticalApplicationAnalysis {
  analysis_key: string;
  display_order: number;
  navigation_group?: string | null;
}

export interface AnalyticalApplication {
  id: string;
  name: string;
  description: string;
  icon?: string | null;
  status: string;
  analyses: AnalyticalApplicationAnalysis[];
  created_at?: string;
  updated_at?: string;
}

export async function listAnalyticalApplications(): Promise<
  AnalyticalApplication[]
> {
  const response = await fetch(
    `${API_BASE_URL}/api/applications`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}

export async function getAnalyticalApplication(
  applicationId: string
): Promise<AnalyticalApplication> {
  const response = await fetch(
    `${API_BASE_URL}/api/applications/${encodeURIComponent(applicationId)}`,
    { cache: "no-store" }
  );
  return handleResponse(response);
}

export async function createAnalyticalApplication(payload: {
  name: string;
  description?: string;
  icon?: string | null;
  analyses: AnalyticalApplicationAnalysis[];
}): Promise<AnalyticalApplication> {
  const response = await fetch(
    `${API_BASE_URL}/api/applications`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    }
  );
  return handleResponse(response);
}

export async function updateAnalyticalApplication(
  applicationId: string,
  payload: {
    name?: string;
    description?: string;
    icon?: string | null;
    analyses?: AnalyticalApplicationAnalysis[];
  }
): Promise<AnalyticalApplication> {
  const response = await fetch(
    `${API_BASE_URL}/api/applications/${encodeURIComponent(applicationId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    }
  );
  return handleResponse(response);
}

export async function deleteAnalyticalApplication(
  applicationId: string
): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/applications/${encodeURIComponent(applicationId)}`,
    {
      method: "DELETE",
      cache: "no-store",
    }
  );
  await handleResponse(response);
}
