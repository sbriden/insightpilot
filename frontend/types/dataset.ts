export interface DatasetType {
  id: string;
  name: string;
  description: string;
  keywords: string[];
  example_fields: string[];
  product_ids: string[];
}


/* --------------------------------------------------------------------------
 * Data Product
 * -------------------------------------------------------------------------- */

export interface DataProductRequirement {
  id: string;

  name: string;

  description: string;

  business_purpose?: string;

  /** user_created | native */
  product_type?: "user_created" | "native";

  dataset_types: string[];

  grain: string;

  required_fields: string[];

  optional_fields: string[];

  analyses: string[];

  field_opportunities?: FieldOpportunity[];
}


/* --------------------------------------------------------------------------
 * Field Opportunity
 * -------------------------------------------------------------------------- */

export interface FieldOpportunity {
  field: string;

  description?: string;

  analyses: string[];

  metrics?: string[];

  priority?: "high" | "medium" | "low";

  required?: boolean;
}


/* --------------------------------------------------------------------------
 * Uploaded Dataset Field
 * -------------------------------------------------------------------------- */


/* --------------------------------------------------------------------------
 * Data Sources
 * -------------------------------------------------------------------------- */

export type DataSourceKind = "csv" | "nflverse";

export interface DataSourceOption {
  id: string;
  name: string;
  description: string;
  kind: "upload" | "connector";
  homepage?: string;
}

export interface NflverseDatasetOption {
  id: string;
  name: string;
  description: string;
  supports_seasons: boolean;
  default_seasons_count: number;
  history_lookback_seasons?: number;
  historical_season_count?: number;
  domain: string;
  domain_label: string;
  notes?: string | null;
}

export interface NflverseDomain {
  id: string;
  label: string;
}

export interface NflverseCatalog {
  source_id: string;
  current_season: number;
  historical_seasons?: number[];
  historical_season_count?: number;
  foundation?: string;
  datasets: NflverseDatasetOption[];
  domains?: NflverseDomain[];
  available_seasons: number[];
  refresh_scopes?: string[];
  ingest_modes?: Array<{
    id: string;
    label: string;
    description: string;
    layers: string[];
    season_scope: string;
  }>;
  ingest_layers?: string[];
}

export interface NflverseSelection {
  datasetId: string;
  datasetName: string;
  seasons: number[];
  label: string;
  preMapped?: boolean;
  rowCount?: number;
}

export interface NflversePreviewResult {
  source_id: string;
  dataset_id: string;
  dataset_name: string;
  seasons: number[];
  label: string;
  row_count: number;
  column_count: number;
  fields: DatasetField[];
  sample_rows: Record<string, unknown>[];
  sample_row_count: number;
  pre_mapped: boolean;
  prebuilt_mappings: FieldMapping[];
  notes?: string | null;
}

export type NflverseIngestMode =
  | "historical"
  | "incremental"
  | "reprocess";

export interface NflverseValidationCheck {
  check_id: string;
  label: string;
  severity: string;
  passed: boolean;
  message: string;
  dataset_id?: string | null;
  count?: number;
}

export interface NflverseValidationReport {
  passed: boolean;
  status: string;
  message: string;
  error_count: number;
  warning_count: number;
  seasons?: number[];
  checks?: NflverseValidationCheck[];
}

export interface NflverseDataQualityResult {
  source_id: string;
  product: string;
  label: string;
  description: string;
  current_season: number;
  seasons: number[];
  report_source: "live" | "ingestion_state" | "none" | string;
  status: string;
  passed: boolean;
  message: string;
  validation: NflverseValidationReport | null;
  latest_ingest?: {
    job_key?: string;
    mode?: string;
    seasons?: number[];
    status?: string;
    finished_at?: string | null;
    updated_at?: string | null;
    row_count_total?: number;
    detail?: Record<string, unknown>;
  } | null;
}

export interface NflverseRefreshResult {
  source_id: string;
  mode?: string;
  mode_label?: string;
  scope: string;
  seasons: number[];
  current_season: number;
  historical_season_count: number;
  layers?: string[];
  datasets_refreshed: number;
  row_count_total?: number;
  force_refresh?: boolean;
  persisted?: boolean;
  started_at?: string;
  finished_at?: string;
  status?: string;
  message?: string;
  validation_blocked_derived?: boolean;
  validation?: NflverseValidationReport;
  results: Array<{
    dataset_id: string;
    seasons: number[];
    row_count: number;
    persisted: boolean;
    force_refresh: boolean;
  }>;
}


export interface DatasetField {
  name: string;

  normalizedName: string;

  dataType?: string;
}


/* --------------------------------------------------------------------------
 * Business Concept Identification
 *
 * Generalized semantic understanding of uploaded dataset columns,
 * independent of product-specific field mappings.
 * -------------------------------------------------------------------------- */

export type ConceptRole =
  | "entity"
  | "measure"
  | "date"
  | "category"
  | "identifier"
  | "status"
  | "geography";

export interface BusinessConcept {
  concept: string;

  sourceColumn: string;

  dataType: string;

  confidence: number;

  role: ConceptRole;
}

export interface ConceptIdentificationResult {
  concepts: BusinessConcept[];

  columnCount: number;

  identifiedCount: number;
}


/* --------------------------------------------------------------------------
 * Analytical Capability Detection
 *
 * Determines what analyses a dataset supports based on its semantic model.
 * -------------------------------------------------------------------------- */

export interface AnalyticalCapability {
  capability: string;

  label: string;

  supported: boolean;

  confidence: number;

  required_concepts: string[];

  explanation: string;

  matched_columns?: string[];
}

export interface CapabilityDetectionResult {
  capabilities: AnalyticalCapability[];

  supported_count: number;

  total_count: number;
}


/* --------------------------------------------------------------------------
 * Analytical Candidate Generation
 *
 * Maps supported capabilities + archetype to applicable analyses.
 * -------------------------------------------------------------------------- */

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


/* --------------------------------------------------------------------------
 * Dataset Classification
 *
 * Maps identified business concepts to a dataset archetype and recommends
 * a matching dataset type for the create-product flow.
 * -------------------------------------------------------------------------- */

export type DatasetArchetype =
  | "sales_revenue"
  | "customer"
  | "operations"
  | "finance"
  | "workforce";

export interface AlternativeArchetype {
  archetype: string;

  label: string;

  confidence: number;
}

export interface ArchetypeScore {
  archetype: string;

  label: string;

  score: number;
}

export interface DatasetClassificationResult {
  primary_archetype: string | null;

  label: string;

  confidence: number;

  supporting_concepts: string[];

  explanation: string;

  alternative_archetypes: AlternativeArchetype[];

  all_scores: ArchetypeScore[];
}

export interface DatasetTypeRecommendation {
  /** Dataset type id to pre-select (e.g. "sales"). */
  datasetTypeId: string | null;

  /** Human-readable archetype label from the classifier. */
  label: string;

  confidence: number;

  explanation: string;

  /** Confidence by dataset type id for card badges. */
  confidenceByTypeId: Record<string, number>;
}


/* --------------------------------------------------------------------------
 * Dataset Grain Determination
 *
 * Infers what each row represents (transaction, customer, etc.) from
 * identified concepts, identifiers, and relationships.
 * -------------------------------------------------------------------------- */

export type DatasetGrain =
  | "transaction"
  | "customer"
  | "subscription"
  | "employee"
  | "invoice"
  | "operational_event"
  | "product"
  | "account"
  | "player_week"
  | "player_game"
  | "unknown";

export interface GrainEvidence {
  signal: string;

  columns: string[];

  detail: string;
}

export interface AlternativeGrain {
  grain: string;

  label: string;

  confidence: number;
}

export interface GrainScore {
  grain: string;

  label: string;

  score: number;
}

export interface ColumnStatInput {
  name: string;

  unique_ratio?: number;

  unique_count?: number;

  row_count?: number;
}

export interface GrainDeterminationResult {
  grain: DatasetGrain | string;

  label: string;

  confidence: number;

  supporting_evidence: GrainEvidence[];

  explanation: string;

  alternative_grains: AlternativeGrain[];

  all_scores: GrainScore[];
}


/* --------------------------------------------------------------------------
 * Shared Semantic Field
 * -------------------------------------------------------------------------- */

export interface SemanticField {
  field: string;

  definition?: string;

  keyRelationships?: string;

  typicalBusinessQuestions?: string[];

  required: boolean;

  requiredBy: string[];

  optionalFor: string[];

  usedByProducts: string[];

  analyses: string[];
}


/* --------------------------------------------------------------------------
 * Shared Field Mapping
 * -------------------------------------------------------------------------- */

export interface FieldMapping {
  requiredField: string;

  uploadedField: string | null;

  matchType:
    | "exact"
    | "normalized"
    | "fuzzy"
    | "manual"
    | "missing"
    | "unmapped"
    | "reused";

  confidence: number;

  required: boolean;

  valid: boolean;
}


/* --------------------------------------------------------------------------
 * Dataset Mapping
 * -------------------------------------------------------------------------- */

export interface DatasetMapping {
  datasetType: string;

  datasetTypeName?: string;

  uploadedFields: DatasetField[];

  semanticFields: SemanticField[];

  mappings: FieldMapping[];

  mappedFieldCount: number;

  semanticFieldCount: number;

  coverage: number;
}


/* --------------------------------------------------------------------------
 * Product Dataset Mapping
 * -------------------------------------------------------------------------- */

export interface ProductDatasetMapping {
  productId: string;

  productName: string;

  uploadedFields: DatasetField[];

  mappings: FieldMapping[];

  requiredFieldCount: number;

  mappedRequiredFieldCount: number;

  coverage: number;
}


/* --------------------------------------------------------------------------
 * Dataset Mapping Result
 * -------------------------------------------------------------------------- */

export interface DatasetMappingResult {
  datasetType?: string;

  productId?: string;

  mappings: FieldMapping[];

  requiredFields?: string[];

  optionalFields?: string[];

  matchedRequiredFields?: string[];

  matchedOptionalFields?: string[];

  missingRequiredFields?: string[];

  availableOptionalFields?: string[];

  requiredCoverage?: number;

  overallCoverage?: number;

  canAnalyze: boolean;
}


/* --------------------------------------------------------------------------
 * Product Coverage
 * -------------------------------------------------------------------------- */

export interface ProductCoverageResult {
  product_id: string;

  product_name: string;

  coverage_percent: number;

  required_coverage_percent?: number;

  required_fields: string[];

  mapped_required_fields: string[];

  missing_required_fields: string[];

  available_optional_fields: string[];

  missing_optional_fields: string[];

  opportunities: FieldOpportunity[];

  can_analyze: boolean;

  metadata: {
    required_field_count: number;

    mapped_required_count: number;

    optional_field_count: number;

    available_optional_count: number;

    opportunity_count: number;

    total_field_count?: number;

    available_field_count?: number;
  };
}


/* --------------------------------------------------------------------------
 * Data Coverage Result
 *
 * Product-specific coverage calculated from the shared dataset mapping.
 * -------------------------------------------------------------------------- */

export interface DataCoverageResult
  extends ProductCoverageResult {}