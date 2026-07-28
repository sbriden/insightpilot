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