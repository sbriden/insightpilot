import {
    DataProduct,
    DataProductConfiguration,
  } from "@/types/report";
  
  
  interface Dashboard {
    id: string;
  }
  
  
  export function buildProductConfiguration(
    product: DataProduct,
    dashboards: Dashboard[]
  ): DataProductConfiguration {
  
    return {
  
      id: product.id,
  
      name: product.name,
  
      description:
        product.description,
  
      selectedAnalyses:
        product.analyses.map(
          analysis =>
            analysis.id
        ).filter(Boolean),
  
      selectedInsights:
        (product.insights ?? []).map(
          insight =>
            insight.id
        ),

      selectedMetrics:
        (product.metrics ?? []).map(
          metric =>
            metric.id
        ),
  
      updatedAt:
        new Date().toISOString(),
  
    };
  }