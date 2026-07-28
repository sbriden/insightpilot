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

export interface DatasetAnalysis {
  profile: DatasetProfile;
  metrics: DatasetMetrics;
  classification: DatasetClassification;
}