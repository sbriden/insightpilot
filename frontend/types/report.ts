export interface DatasetSummary {
  rows: number;
  columns: number;
  data_quality_score: number;
}

export interface DatasetColumns {
  names: string[];
  numeric: string[];
  categorical: string[];
}

export interface DatasetProfile {
  summary: DatasetSummary;
  columns: DatasetColumns;
  missing_values: Record<string, number>;
  statistics: Record<string, unknown>;
}

export interface NumericMetric {
  count: number;
  sum: number;
  mean: number;
  median: number;
  min: number;
  max: number;
  std: number;
  missing: number;
  zeros: number;
  negative_values: number;
}

export interface CategoricalMetric {
  count: number;
  unique_values: number;
  missing: number;
  top_values: Record<string, number>;
}

export interface DateMetric {
  earliest: string;
  latest: string;
  unique_dates: number;
  timespan_days: number;
}

export interface DatasetMetrics {
  dataset: {
    rows: number;
    columns: number;
    duplicates: number;
    missing_cells: number;
    missing_percentage: number;
  };

  numeric: Record<string, NumericMetric>;

  categorical: Record<string, CategoricalMetric>;

  dates: Record<string, DateMetric>;
}

export interface DatasetClassification {
  type: string;
  confidence: number;
  matched_fields: string[];
}

export interface SemanticConcept {
  concept: string;
  sourceColumn: string;
  dataType: string;
  confidence: number;
  role: string;
}

export interface SemanticGrain {
  grain: string;
  label: string;
  confidence: number;
  supporting_evidence?: Array<{
    signal: string;
    columns: string[];
    detail?: string;
  }>;
  explanation?: string;
  alternative_grains?: Array<{
    grain: string;
    label: string;
    confidence: number;
  }>;
}

export interface SemanticModel {
  concepts: SemanticConcept[];
  dimensions: SemanticConcept[];
  measures: SemanticConcept[];
  entities: SemanticConcept[];
  dates: SemanticConcept[];
  identifiers: SemanticConcept[];
  statuses: SemanticConcept[];
  geography: SemanticConcept[];
  grain: SemanticGrain;
}

export interface AnalyticalCapability {
  capability: string;
  label: string;
  supported: boolean;
  confidence: number;
  required_concepts: string[];
  explanation: string;
  matched_columns: string[];
}

export interface AnalyticalCandidate {
  id: string;
  title: string;
  description: string;
  domain: string;
  executable: boolean;
  required_capabilities: string[];
  matched_capabilities: string[];
  archetypes: string[];
  confidence: number;
  explanation: string;
}

export interface AnalyticalCandidateResult {
  candidates: AnalyticalCandidate[];
  candidate_count: number;
  archetype: string | null;
  supported_capabilities: string[];
}

/** Traceability for a candidate finding. */
export interface FindingProvenance {
  source_columns: string[];
  dimensions: string[];
  filters: Array<{
    field?: string | null;
    op?: string | null;
    value?: unknown;
    expression?: string | null;
    label?: string;
  }>;
  calculations: string[];
  /** Structured recipe for reproducing the result. */
  calculation?: CalculationSpec;
  row_scope?: string | null;
  input_values?: Record<string, unknown>;
  /** Dataset relationship for multi-dataset comparison. */
  dataset?: DatasetTraceability;
}

/**
 * Relationship between an Insight and the analyzed dataset.
 * Critical once users can upload multiple datasets / compare runs.
 */
export interface DatasetTraceability {
  dataset_id?: string | null;
  dataset_version?: string | number | null;
  dataset_identity?: string | null;
  dataset_label?: string | null;
  /** ISO analysis timestamp. */
  analyzed_at?: string | null;
  source_columns: string[];
  filters: FindingProvenance["filters"];
  /** Records excluded from the analysis (DQ acknowledgements). */
  records_excluded: Array<{
    type?: string;
    label?: string;
    count?: number | null;
    rate?: number | null;
    field?: string | null;
    description?: string | null;
  }>;
  analytical_method: {
    analysis_type?: string | null;
    calculation?: CalculationSpec;
    steps?: string[];
  };
}

/**
 * Machine-readable recipe retained so the engine can reproduce
 * an Insight. Not required to be end-user-facing yet.
 */
export interface CalculationSpec {
  analysis_type?: string | null;
  measure?: string | null;
  dimension?: string | null;
  aggregation?: string | null;
  grouping?: string | string[] | null;
  ranking?: string | null;
  top_n?: number | null;
  comparison?: string | null;
  filters?: FindingProvenance["filters"];
  source_columns?: string[];
  parameters?: Record<string, unknown>;
}

/** Confidence in an analytical finding — evidence strength only. */
export type FindingConfidence =
  | "high"
  | "medium"
  | "low"
  | string;

export const FINDING_CONFIDENCE_LEVELS = [
  "high",
  "medium",
  "low",
] as const;

export const FINDING_CONFIDENCE_DESCRIPTIONS: Record<
  string,
  string
> = {
  high: "Strong data quality and clear analytical signal",
  medium: "Reasonable signal but limitations exist",
  low: "Potentially interesting but insufficient evidence",
};

/**
 * Business importance of a finding — independent of confidence.
 * High importance + medium confidence should still surface.
 */
export type FindingImportance =
  | "high"
  | "medium"
  | "low"
  | string;

export const FINDING_IMPORTANCE_LEVELS = [
  "high",
  "medium",
  "low",
] as const;

export const FINDING_IMPORTANCE_DESCRIPTIONS: Record<
  string,
  string
> = {
  high: "Material business significance — worth attention",
  medium: "Notable but not necessarily urgent",
  low: "Limited business significance on its own",
};

/** Surfacing priority for promoted Insights. */
export type InsightTier =
  | "critical"
  | "important"
  | "supporting"
  | string;

export const INSIGHT_TIER_LEVELS = [
  "critical",
  "important",
  "supporting",
] as const;

export const INSIGHT_TIER_LABELS: Record<string, string> = {
  critical: "Tier 1 — Critical",
  important: "Tier 2 — Important",
  supporting: "Tier 3 — Supporting",
};

export const INSIGHT_TIER_DESCRIPTIONS: Record<string, string> = {
  critical: "Insights the user should almost certainly see",
  important: "Worth surfacing, but less urgent",
  supporting:
    "Useful for exploration; should not dominate initial results",
};

/**
 * Machine-readable supporting fact / aggregate for evidence.
 */
export interface EvidenceMetric {
  key: string;
  label: string;
  value: number | string | boolean | null;
  unit?: string | null;
}

/** One group / category / entity in entity-level evidence. */
export interface EvidenceBreakdownEntity {
  id?: string | null;
  label: string;
  value?: number | string | boolean | null;
  unit?: string | null;
  share?: number | null;
  extras?: Record<string, unknown>;
}

/** Aggregate evidence row — e.g. region current / previous / change. */
export interface AggregateEvidenceRow {
  id?: string | null;
  label: string;
  current?: number | string | null;
  previous?: number | string | null;
  change?: number | string | null;
  change_pct?: number | null;
  unit?: string | null;
  extras?: Record<string, unknown>;
}

/** Distribution bucket — e.g. overtime share by department. */
export interface DistributionEvidenceBucket {
  id?: string | null;
  label: string;
  value?: number | string | null;
  share?: number | null;
  unit?: string | null;
  extras?: Record<string, unknown>;
}

/**
 * Reference to an underlying record (anomaly support).
 * Prefer identifiers over dumping full rows.
 */
export interface RecordEvidenceRef {
  record_id?: string | null;
  keys?: Record<string, unknown>;
  label?: string | null;
  fields?: Record<string, unknown>;
}

export type EvidenceLevel =
  | "aggregate"
  | "entity"
  | "distribution"
  | "record"
  | string;

export const EVIDENCE_LEVELS = [
  "aggregate",
  "entity",
  "distribution",
  "record",
] as const;

/** Summary section for a future "Show evidence" UI. */
export interface EvidenceShowSummary {
  /** Always deterministic_fact — never interpretation. */
  layer?: "deterministic_fact" | "interpretation";
  headline?: string;
  metric?: string | null;
  observed_value?: number | string | boolean | null;
  baseline?: number | string | boolean | null;
  comparison?: string | null;
  difference?: number | null;
  percentage_change?: number | null;
  population?: number | null;
  key_numbers: EvidenceMetric[];
}

/** Breakdown section — level-aware detail. */
export interface EvidenceShowBreakdown {
  level?: EvidenceLevel | null;
  levels_present?: EvidenceLevel[];
  dimension?: string | null;
  dimensions?: string[];
  entities: EvidenceBreakdownEntity[];
  aggregate?: {
    columns: string[];
    rows: AggregateEvidenceRow[];
  };
  distribution?: {
    dimension?: string | null;
    buckets: DistributionEvidenceBucket[];
  };
  /** Only populated when analyses opt into record-level evidence. */
  records?: RecordEvidenceRef[];
}

/** Methodology section — how the result was calculated. */
export interface EvidenceShowMethodology {
  steps: string[];
  calculation?: CalculationSpec;
}

/** Source section — dataset and columns used. */
export interface EvidenceShowSource {
  dataset?: string | null;
  dataset_id?: string | null;
  dataset_version?: string | number | null;
  analyzed_at?: string | null;
  columns: string[];
  filters?: FindingProvenance["filters"];
  records_excluded?: DatasetTraceability["records_excluded"];
  analytical_method?: DatasetTraceability["analytical_method"];
}

export type DataQualityIssueType =
  | "missing_data"
  | "duplicate_records"
  | "excluded_records"
  | "invalid_values"
  | "sample_size"
  | string;

export const DATA_QUALITY_ISSUE_TYPES = [
  "missing_data",
  "duplicate_records",
  "excluded_records",
  "invalid_values",
  "sample_size",
] as const;

/** One data-quality limitation that may affect reliability. */
export interface DataQualityIssue {
  type: DataQualityIssueType;
  label: string;
  count?: number | null;
  /** Fraction 0–1 when known (e.g. 0.18 = 18% missing). */
  rate?: number | null;
  field?: string | null;
  description?: string | null;
  extras?: Record<string, unknown>;
}

/**
 * Lightweight data-quality acknowledgements — not a scoring system.
 */
export interface DataQualityContext {
  issues: DataQualityIssue[];
  notes: string[];
  affects_reliability: boolean;
  has_limitations: boolean;
}

/**
 * UI contract for a "Show evidence" action.
 * Always present with all sections.
 */
export interface ShowEvidence {
  summary: EvidenceShowSummary;
  breakdown: EvidenceShowBreakdown;
  methodology: EvidenceShowMethodology;
  source: EvidenceShowSource;
  data_quality: DataQualityContext;
}

export const SHOW_EVIDENCE_SECTIONS = [
  "summary",
  "breakdown",
  "methodology",
  "source",
  "data_quality",
] as const;

/**
 * Structured evidence answering "Why is InsightPilot telling me this?"
 *
 * Holds deterministic facts behind a conclusion — numbers, methodology,
 * source, and data-quality limitations. Not interpretation.
 *
 * Evidence (fact): "Revenue was $4.7M across the top 10 customers,
 * representing 47% of total revenue."
 * Explanation (interpretation, later / AI): "This suggests the
 * business may be exposed to customer concentration risk."
 *
 * `show_evidence` organizes content for a future "Show evidence" UI.
 */
export interface StructuredEvidence {
  metric?: string | null;
  observed_value?: number | string | boolean | null;
  baseline?: number | string | boolean | null;
  comparison?: string | null;
  difference?: number | null;
  percentage_change?: number | null;
  population?: number | null;
  relevant_dimensions?: string[];
  filters?: FindingProvenance["filters"];
  source_columns?: string[];
  source_dataset?: string | null;
  source_dataset_id?: string | null;
  dataset_version?: string | number | null;
  analyzed_at?: string | null;
  records_excluded?: DatasetTraceability["records_excluded"];
  /** Calculation / methodology steps. */
  methodology?: string[];
  calculation?: CalculationSpec;
  /** Supporting aggregates behind the claim. */
  metrics: EvidenceMetric[];
  /** Optional row-level or grouped supporting records. */
  supporting_records?: Record<string, unknown>[];
  /** Explicit entity breakdown (legacy alias). */
  breakdown?: EvidenceBreakdownEntity[];
  /** Primary evidence granularity for this insight. */
  level?: EvidenceLevel | null;
  levels_present?: EvidenceLevel[];
  /** Aggregate table rows (region current/previous/change, …). */
  aggregate_rows?: AggregateEvidenceRow[];
  /** Entity-level contributions. */
  entities?: EvidenceBreakdownEntity[];
  /** Distribution across a dimension. */
  distribution?: DistributionEvidenceBucket[];
  /** Optional underlying record refs — never required. */
  records?: RecordEvidenceRef[];
  /** Data-quality limitations that may affect reliability. */
  data_quality?: DataQualityContext;
  summary?: string;
  /** Stable UI contract for "Show evidence". */
  show_evidence?: ShowEvidence;
}

/** Traceability carried by every promoted Insight. */
export interface InsightTraceability {
  candidate_finding_id: string;
  source_columns: string[];
  analysis_type: string;
  dimensions: string[];
  filters: FindingProvenance["filters"];
  calculations: string[];
  /** Structured recipe for reproducing the result. */
  calculation?: CalculationSpec;
  rule_id?: string | null;
  /** Dataset lineage for multi-dataset / version comparison. */
  dataset: DatasetTraceability;
}

/** Structured factual finding emitted by an analysis module. */
export interface CandidateFinding {
  id: string;
  analysis_type: string;
  metric: string;
  observed_value: number | string | null;
  baseline?: number | string | null;
  comparison?: string | null;
  magnitude?: number | null;
  magnitude_unit?: string | null;
  evidence: StructuredEvidence | string;
  /**
   * Confidence in the analytical finding (not the recommendation,
   * and not business importance). high | medium | low
   */
  confidence: FindingConfidence;
  /**
   * Business importance — independent of confidence.
   * Medium confidence must not hide high-importance findings.
   */
  importance: FindingImportance;
  relevant_dimensions: string[];
  source_columns: string[];
  provenance?: FindingProvenance;
  filters?: FindingProvenance["filters"];
  calculations?: string[];
  /** Structured recipe retained for reproducibility. */
  calculation?: CalculationSpec;
  rule_id?: string | null;
  /** Legacy severity alias; prefer `importance`. */
  severity?: string | null;
  title?: string | null;
  /** Explicit Insight gate; null/undefined → heuristics. */
  insight_eligible?: boolean | null;
}

/**
 * Validated finding — structurally sound candidate.
 *
 * Pipeline: Candidate Finding → Validated Finding → Insight
 * `insight_eligible` is a binary relevance gate, not a rank.
 */
export interface ValidatedFinding extends CandidateFinding {
  stage: "validated" | string;
  validation_notes: string[];
  insight_eligible: boolean;
  insight_eligibility_reason?: string | null;
}

/** Business domain for a promoted insight. */
export type InsightCategory =
  | "Revenue"
  | "Customer"
  | "Operations"
  | "Profitability"
  | "Product"
  | "Other"
  | string;

/** Analytical shape of a promoted insight — domain-agnostic. */
export type InsightType =
  | "trend"
  | "growth_decline"
  | "anomaly"
  | "concentration"
  | "comparison"
  | "segment_difference"
  | "contribution"
  | "distribution"
  | "relationship"
  | "opportunity"
  | "risk"
  | "other"
  | string;

/** Canonical catalog (excludes other). Intentionally small. */
export const INSIGHT_TYPES = [
  "trend",
  "growth_decline",
  "anomaly",
  "concentration",
  "comparison",
  "segment_difference",
  "contribution",
  "distribution",
  "relationship",
  "opportunity",
  "risk",
] as const;

export interface InsightScoreFactors {
  magnitude: number;
  business_impact: number;
  confidence: number;
  novelty: number;
  relevance: number;
  actionability: number;
  data_quality: number;
}

/**
 * Deterministic ranking payload for promoted Insights.
 * `total` is 0–100; factor values are 0–1.
 */
export interface InsightScore {
  total: number;
  factors: InsightScoreFactors;
  weights: InsightScoreFactors;
  version: string;
}

/**
 * Standardized Insight promoted from an insight-eligible
 * validated finding (not every candidate becomes an Insight).
 *
 * Fact fields (insight_id through analysis_type, excluding
 * business_impact / potential_drivers / recommendation) are
 * established by deterministic analysis.
 *
 * `business_impact` is an estimate when determinable.
 * `ai_interpretation` is the AI Insight Contract — separate from
 * deterministic `finding` / evidence.
 * `potential_drivers` / `recommendation` / `explanation` may mirror
 * the contract for older consumers.
 * `scoring` ranks Insights after eligibility gates.
 */
export interface PromotedInsight {
  insight_id: string;
  title: string;
  category: InsightCategory;
  insight_type: InsightType;
  /** Deterministic finding — factual observation only. */
  finding: string;
  metric: string;
  observed_value: number | string | null;
  baseline?: number | string | null;
  magnitude?: number | null;
  dimensions: string[];
  /** Machine-readable support for "why this insight?" */
  evidence: StructuredEvidence;
  /**
   * Confidence in the analytical finding — not whether to act
   * on the recommendation, and not business importance.
   * high | medium | low
   */
  confidence: FindingConfidence;
  /**
   * Business importance — independent of confidence.
   * high | medium | low
   */
  importance: FindingImportance;
  /**
   * Surfacing tier — Critical / Important / Supporting.
   * Independent of confidence; complementary to importance.
   */
  tier: InsightTier;
  /** Estimated significance when determinable. */
  business_impact?: string | null;
  /**
   * Hypotheses that may explain the finding — not proven causes.
   * Prefer `ai_interpretation.potential_drivers`.
   */
  potential_drivers: string[];
  /** Suggested next action — prefer `ai_interpretation.recommended_action`. */
  recommendation?: string | null;
  /**
   * AI Insight Contract — interpretive layer separate from
   * the deterministic finding.
   */
  ai_interpretation?: AIInsightContract | null;
  /**
   * @deprecated Legacy mirror of `ai_interpretation`.
   */
  explanation?: InsightExplanation | null;
  candidate_finding_id: string;
  source_columns: string[];
  analysis_type: string;
  /**
   * Structured recipe so the engine can reproduce the result.
   * Retained for the pipeline; not required in end-user UI yet.
   */
  calculation?: CalculationSpec;
  traceability: InsightTraceability;
  comparison?: string | null;
  magnitude_unit?: string | null;
  rule_id?: string | null;
  severity?: string | null;
  /** Deterministic multi-factor ranking score. */
  scoring: InsightScore;
  /**
   * Redundancy metadata from ranking consolidation.
   * Cluster winners list suppressed siblings; suppressed
   * items are omitted from default API responses.
   */
  redundancy?: InsightRedundancy;
}

export interface InsightRedundancy {
  version: string;
  cluster_key: string;
  cluster_size: number;
  suppressed: boolean;
  suppressed_insight_ids: string[];
  suppressed_rule_ids: string[];
  related_titles: string[];
  kept_insight_id?: string;
}

/** Field-layer contract for PromotedInsight consumers. */
export const INSIGHT_FACT_FIELDS = [
  "insight_id",
  "title",
  "category",
  "insight_type",
  "finding",
  "metric",
  "observed_value",
  "baseline",
  "magnitude",
  "dimensions",
  "evidence",
  "confidence",
  "importance",
  "tier",
  "source_columns",
  "analysis_type",
  "calculation",
] as const;

export const INSIGHT_ESTIMATED_FIELDS = [
  "business_impact",
] as const;

export const INSIGHT_INTERPRETIVE_FIELDS = [
  "ai_interpretation",
  "potential_drivers",
  "recommendation",
  "explanation",
] as const;

/**
 * AI Insight Contract — interpretive layer over a deterministic Insight.
 *
 * Visible product layers (kept separate for trust):
 *   Fact: "Northeast revenue declined 18% compared with the previous period."
 *   Interpretation: "The decline is material relative to overall revenue performance."
 *   Recommendation: "Investigate the largest customer and product-level contributors."
 */
export interface AIInsightContract {
  /** AI interpretation of what the finding means. */
  summary: string;
  /** Potential business significance. */
  why_it_matters: string;
  /** Drivers supported by evidence only. */
  potential_drivers: string[];
  /** Reasonable next action or investigation. */
  recommended_action: string;
  /** Data-quality / confidence limitations. */
  caveats: string[];
  /** Always interpretation — never deterministic evidence. */
  layer: "interpretation" | string;
  /** fallback until an LLM is wired; ai when generated. */
  source: "fallback" | "ai" | string;
}

export const AI_INSIGHT_CONTRACT_KEYS = [
  "summary",
  "why_it_matters",
  "potential_drivers",
  "recommended_action",
  "caveats",
  "layer",
  "source",
] as const;

/** @deprecated Prefer AIInsightContract. */
export type InsightExplanation = AIInsightContract & {
  what_happened?: string;
  drivers?: string[];
  next_action?: string;
};

export const INSIGHT_EXPLANATION_KEYS = AI_INSIGHT_CONTRACT_KEYS;

export const INSIGHT_SCORING_FIELDS = ["scoring"] as const;

export interface DatasetArchetype {
  primary: string | null;
  confidence: number;
  alternatives: Array<{
    archetype: string;
    label: string;
    confidence: number;
  }>;
  label?: string;
  explanation?: string;
  supporting_concepts?: string[];
}

/** Developer inspection surface for semantic engine correctness. */
export interface SemanticUnderstanding {
  detected_concepts: SemanticConcept[];
  source_columns: string[];
  inferred_grain: SemanticGrain;
  detected_measures: SemanticConcept[];
  detected_dimensions: SemanticConcept[];
  detected_dates: SemanticConcept[];
  detected_entities: SemanticConcept[];
  detected_capabilities: AnalyticalCapability[];
  archetype_classification: DatasetArchetype;
}

export interface Recommendation {
  id: string;
  title: string;
  description: string;
  priority: string;
  category: string;
}

export interface Insight {
  severity: "high" | "medium" | "low";
  category: string;
  title: string;
  description: string;
}

/**
 * Concise leadership brief from top ranked explained Insights.
 * Designed for a 30–60 second read — not a lengthy report.
 */
export interface InsightExecutiveBriefItem {
  rank: number;
  insight_id?: string | null;
  title: string;
  fact: string;
  tier?: string | null;
  importance?: string | null;
}

export interface InsightExecutiveBrief {
  version?: string;
  what_matters_most: InsightExecutiveBriefItem[];
  /** AI / fallback synthesis across the highlighted Insights. */
  why_it_matters: string;
  /** Cross-insight investigation focus for leadership. */
  leadership_investigate: string[];
  estimated_reading_seconds?: number;
  layer?: string;
  source?: "fallback" | "ai" | string;
}

export interface ExecutiveBrief {
  overview: string;
  key_findings: string[];
  risks: string[];
  opportunities: {
    id: string;
    title?: string;
    category?: string;
  }[];
  next_steps: string[];
}

export interface DashboardMetric {
  id: string;
  title: string;
  value: string;
  subtitle?: string;
}

export interface DashboardVisualization {
  id: string;
  title: string;
  chart: string;
  dataset: string;
  x?: string;
  y?: string;
  description?: string;
  takeaway?: string;
  business_question?: string;
  priority?: string;
}

export interface DashboardInsight {
  severity: string;
  message: string;
}

export interface ColumnProfile {
  name: string;
  role: string;
  unique_count: number;
  null_count: number;
  data_type: string;
}

export interface DatasetAnalysis {
  profile: DatasetProfile;
  metrics: DatasetMetrics;
  classification: DatasetClassification;
  semantic_model?: SemanticModel;
  capabilities?: AnalyticalCapability[];
  dataset_archetype?: DatasetArchetype;
  analytical_candidates?: AnalyticalCandidate[];
  candidate_findings?: CandidateFinding[];
  validated_findings?: ValidatedFinding[];
  promoted_insights?: PromotedInsight[];
  semantic_understanding?: SemanticUnderstanding;
  recommendations: Recommendation[];
  insights: Insight[];
  analysis_dashboards: AnalysisDashboard[];
  column_profiles: ColumnProfile[];
  visualizations: VisualizationRecommendation[];
  executive_brief: ExecutiveBrief | null;
  data_products: DataProduct[];
  selected_product_ids?: string[];
}

export interface VisualizationRecommendation {
  id: string;
  title: string;
  chart: string;
  x: string;
  y?: string;
  reason: string;
  priority: number;
}

export interface AnalysisDashboardMetric {
  id: string;
  title: string;
  value: string;
  subtitle?: string;
}

export interface AnalysisDashboardInsight {
  severity: string;
  message: string;
  title?: string;
  priority?: string;
  category?: string;
  what_happened?: string;
  why_it_matters?: string;
  recommended_action?: string;
}

export interface AnalysisDashboard {
  id: string;
  title: string;
  summary: string;
  metrics: AnalysisDashboardMetric[];
  visualizations: any[];
  insights: AnalysisDashboardInsight[];
  candidate_findings?: CandidateFinding[];
  validated_findings?: ValidatedFinding[];
  promoted_insights?: PromotedInsight[];
  actions: string[];
  datasets: Record<
    string,
    any[]
  >;
}

export interface DataProductAnalysis {
  id: string;
  title: string;
  description?: string;
}


export interface DataProductMetric {
  id: string;
  name: string;
  value: unknown;
  description?: string;
  unit?: string;
}


export interface DataProductInsight {
  id: string;
  title: string;
  message: string;
  severity: string;
  priority?: "high" | "medium" | "low" | string;
  category?: string;
  /** Fact — deterministic observation. */
  what_happened?: string;
  /** Interpretation — what the fact may mean. */
  why_it_matters?: string;
  /** Recommendation — suggested next action. */
  recommended_action?: string;
}


export interface ProductChangeFinding {
  id: string;
  title: string;
  message: string;
  severity: string;
  direction?: "increase" | "decrease" | "unchanged" | string;
  category?: string;
  metric_id?: string;
  metric_name?: string;
  previous_value?: number;
  current_value?: number;
  absolute_change?: number;
  relative_change_percent?: number | null;
  unit?: string;
}


export interface ProductChangeSummary {
  previous_version: number;
  current_version: number;
  has_meaningful_changes: boolean;
  overview: string;
  finding_count: number;
  increases: number;
  decreases: number;
  findings: ProductChangeFinding[];
  data_quality_overview?: string;
  data_quality_finding_count?: number;
  data_quality_findings?: ProductChangeFinding[];
}


export interface ProductExecutiveSummaryItem {
  priority: "high" | "medium" | "low" | string;
  category: string;
  headline: string;
  detail: string;
}


export interface ProductExecutiveSummary {
  what_we_found: string;
  what_matters: ProductExecutiveSummaryItem[];
  what_to_do_next: string[];
}


export type ProductHealthStatus =
  | "healthy"
  | "warning"
  | "critical";


export interface ProductHealthChecks {
  required_fields_present: boolean;
  data_quality_acceptable: boolean;
  no_major_anomalies: boolean;
  product_generated_successfully: boolean;
}


export interface ProductHealth {
  status: ProductHealthStatus;
  label: string;
  summary: string;
  reasons: string[];
  checks?: ProductHealthChecks;
}


export interface InsightTierCount {
  tier_1: number;
  tier_2: number;
  tier_3: number;
  critical: number;
  important: number;
  supporting: number;
}

export interface InsightInitialTierSummary {
  tier: 1 | 2 | 3 | number;
  key: InsightTier;
  label: string;
  count: number;
}

/**
 * Alpha Initial Results Contract.
 * Primary surface is recommended_insights (~5), not the full list.
 */
export interface InsightInitialResults {
  version: string;
  total_discovered: number;
  tier_counts: InsightTierCount;
  tiers: InsightInitialTierSummary[];
  recommended_cap: number;
  recommended_count: number;
  recommended_insight_ids: string[];
  recommended_insights: PromotedInsight[];
  headline: string;
  summary: string;
  /** Concise leadership brief from explained recommended Insights. */
  executive_brief?: InsightExecutiveBrief | null;
}

export interface DataProduct {
  id: string;
  name: string;
  description: string;
  business_purpose?: string;
  /**
   * Origin of this product instance.
   * user_created — from a user's dataset
   * native — InsightPilot-maintained
   */
  product_type?: "user_created" | "native";
  source_dataset?: string;
  status: string;
  coverage: number;
  version: number;
  definition_id?: string;
  dataset_identity?: string;
  previous_product_id?: string | null;
  analyses: DataProductAnalysis[];
  metrics?: DataProductMetric[];
  insights?: DataProductInsight[];
  /** Lifted from dashboards; also nested on each dashboard. */
  candidate_findings?: CandidateFinding[];
  /** Validated subset of candidates (structural gate). */
  validated_findings?: ValidatedFinding[];
  /** Insights from insight-eligible validated findings only. */
  promoted_insights?: PromotedInsight[];
  /** Alpha contract: tier counts + recommended surface set. */
  insight_initial_results?: InsightInitialResults;
  /** Concise leadership brief (also nested under insight_initial_results). */
  executive_brief?: InsightExecutiveBrief | null;
  /** AI enrichment status for this product version (cached). */
  ai_status?: {
    available?: boolean;
    mode?: "ai" | "fallback" | string;
    reason?: string;
    message?: string | null;
    generated_at?: string;
  } | null;
  dashboards?: AnalysisDashboard[];
  change_summary?: ProductChangeSummary | null;
  executive_summary?: ProductExecutiveSummary | null;
  health?: ProductHealth | null;
  metadata?: Record<
    string,
    unknown
  >;
  created_at?: string;
  updated_at?: string;
}

export interface DataProductConfiguration {
  id: string;
  name: string;
  description: string;
  selectedAnalyses: string[];
  selectedInsights: string[];
  selectedMetrics: string[];
  updatedAt: string;
}