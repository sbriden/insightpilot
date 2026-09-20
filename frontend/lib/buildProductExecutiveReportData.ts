import {
  DataProduct,
  DataProductInsight,
  DataProductMetric,
  ProductExecutiveSummary,
  ProductHealth,
} from "@/types/report";

import {
  normalizeInsights,
} from "@/lib/insightModel";

import {
  resolveProductExecutiveSummary,
} from "@/lib/productExecutiveSummary";

import {
  resolveProductHealth,
} from "@/lib/productHealth";

import {
  formatMetricValue,
  selectHeadlineKpis,
} from "@/lib/productKpis";

import {
  RankedProductOpportunity,
  extractTopOpportunities,
  formatOpportunityValue,
} from "@/lib/productOpportunities";


export interface ProductExecutiveReportData {
  productName: string;
  description: string;
  businessPurpose?: string;
  version: number;
  status: string;
  coverage: number;
  health: ProductHealth;
  generatedAt: string;
  updatedAt?: string;
  summary: ProductExecutiveSummary;
  kpis: DataProductMetric[];
  opportunities: RankedProductOpportunity[];
  insights: DataProductInsight[];
  changeOverview?: string | null;
  analyses: string[];
}


export function buildProductExecutiveReportData(
  product: Pick<
    DataProduct,
    | "name"
    | "description"
    | "business_purpose"
    | "version"
    | "status"
    | "coverage"
    | "analyses"
    | "metrics"
    | "insights"
    | "dashboards"
    | "change_summary"
    | "executive_summary"
    | "health"
    | "metadata"
    | "updated_at"
  >
): ProductExecutiveReportData {

  const analyses =
    (product.analyses ?? []).map(
      (analysis) =>
        typeof analysis === "string"
          ? analysis
          : analysis.title ??
            analysis.id ??
            "Analysis"
    );

  return {
    productName: product.name,
    description: product.description,
    businessPurpose: product.business_purpose,
    version: product.version,
    status: product.status,
    coverage: product.coverage,
    health: resolveProductHealth(product),
    generatedAt: new Date().toISOString(),
    updatedAt: product.updated_at,
    summary: resolveProductExecutiveSummary(product),
    kpis: selectHeadlineKpis(
      product.metrics ?? [],
      6
    ),
    opportunities: extractTopOpportunities(
      product.dashboards ?? [],
      product.insights ?? [],
      5
    ),
    insights: normalizeInsights(
      product.insights ?? []
    ).slice(0, 8),
    changeOverview:
      product.change_summary
        ?.has_meaningful_changes
        ? product.change_summary.overview
        : null,
    analyses,
  };

}


export function formatReportMetricValue(
  metric: DataProductMetric
): string {

  const raw =
    formatMetricValue(metric.value);

  if (
    raw === "—"
  ) {
    return raw;
  }

  if (metric.unit === "$") {
    return `$${raw}`;
  }

  if (metric.unit === "%") {
    return `${raw}%`;
  }

  if (metric.unit) {
    return `${raw} ${metric.unit}`;
  }

  return raw;

}


export function formatReportStatus(
  status: string
): string {

  const normalized =
    String(status ?? "unknown")
      .toLowerCase();

  const labels: Record<
    string,
    string
  > = {
    ready: "Ready",
    partial: "Partial",
    limited: "Limited",
    draft: "Draft",
    archived: "Archived",
    unknown: "Unknown",
  };

  return (
    labels[normalized] ??
    normalized.charAt(0).toUpperCase() +
      normalized.slice(1)
  );

}


export function buildReportFilename(
  productName: string,
  version: number
): string {

  const slug =
    productName
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) ||
    "data-product";

  return `${slug}-executive-report-v${version}.pdf`;

}


export function formatReportDate(
  value?: string
): string {

  if (!value) {
    return new Date().toLocaleDateString(
      undefined,
      {
        year: "numeric",
        month: "long",
        day: "numeric",
      }
    );
  }

  const parsed =
    Date.parse(value);

  if (Number.isNaN(parsed)) {
    return value;
  }

  return new Date(parsed).toLocaleDateString(
    undefined,
    {
      year: "numeric",
      month: "long",
      day: "numeric",
    }
  );

}


export function formatReportOpportunityValue(
  opportunity: RankedProductOpportunity
): string {

  return (
    formatOpportunityValue(
      opportunity.potential
    ) ?? "—"
  );

}
