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

export interface AnalysisDashboard {
  id: string;
  title: string;
  summary: string;

  metrics: DashboardMetric[];

  datasets: Record<string, unknown>;

  visualizations: DashboardVisualization[];

  insights: DashboardInsight[];

  actions: string[];
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
  recommendations: Recommendation[];
  insights: Insight[];
  analysis_dashboards: AnalysisDashboard[];
  column_profiles: ColumnProfile[];
  visualizations: VisualizationRecommendation[];
  executive_brief: ExecutiveBrief | null;
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