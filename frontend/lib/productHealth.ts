import {
  DataProduct,
  ProductHealth,
  ProductHealthStatus,
} from "@/types/report";


function normalizeStatus(
  value?: string | null
): ProductHealthStatus {

  const normalized =
    String(value ?? "healthy")
      .trim()
      .toLowerCase();

  if (
    normalized === "critical" ||
    normalized === "unhealthy"
  ) {
    return "critical";
  }

  if (
    normalized === "warning" ||
    normalized === "degraded"
  ) {
    return "warning";
  }

  return "healthy";

}


function countInsights(
  insights: DataProduct["insights"],
  priorities: Set<string>
): number {

  return (insights ?? []).filter(
    insight =>
      priorities.has(
        String(
          insight.priority ??
          insight.severity ??
          "low"
        ).toLowerCase()
      )
  ).length;

}


function changeHasHighSeverity(
  changeSummary: DataProduct["change_summary"]
): boolean {

  return (changeSummary?.findings ?? []).some(
    finding =>
      String(
        finding.severity ?? "low"
      ).toLowerCase() === "high"
  );

}


export function buildProductHealth(
  product: Pick<
    DataProduct,
    | "status"
    | "coverage"
    | "insights"
    | "change_summary"
    | "metadata"
    | "dashboards"
  >
): ProductHealth {

  const metadata =
    product.metadata ?? {};

  const canAnalyze =
    metadata.can_analyze !== false;

  const requiredCoverage =
    Number(
      metadata.required_coverage ??
      (canAnalyze ? 100 : 0)
    );

  const overallCoverage =
    Number(
      metadata.field_coverage ??
      product.coverage ??
      0
    );

  const dataQualityScore =
    metadata.data_quality_score !== undefined
      ? Number(metadata.data_quality_score)
      : null;

  const missingPercentage =
    metadata.missing_percentage !== undefined
      ? Number(metadata.missing_percentage)
      : null;

  const analysisCount =
    Number(
      metadata.analysis_count ??
      product.dashboards?.length ??
      0
    );

  const expectedAnalysisCount =
    Number(
      metadata.expected_analysis_count ??
      analysisCount
    );

  const highInsights = countInsights(
    product.insights,
    new Set(["high", "critical"])
  );

  const notableInsights = countInsights(
    product.insights,
    new Set(["high", "critical", "medium", "warning"])
  );

  const requiredFieldsPresent =
    canAnalyze &&
    requiredCoverage >= 100;

  const dataQualityAcceptable =
    (dataQualityScore === null ||
      dataQualityScore >= 70) &&
    (missingPercentage === null ||
      missingPercentage < 15);

  const noMajorAnomalies =
    highInsights === 0 &&
    !changeHasHighSeverity(
      product.change_summary
    );

  const productGeneratedSuccessfully =
    canAnalyze &&
    analysisCount > 0 &&
    product.status !== "limited";

  let status: ProductHealthStatus = "healthy";
  const reasons: string[] = [];

  if (!requiredFieldsPresent) {
    status = "critical";
    reasons.push(
      "Required fields are missing for this product."
    );
  }

  if (
    dataQualityScore !== null &&
    dataQualityScore < 50
  ) {
    status = "critical";
    reasons.push(
      "Dataset quality score indicates a major data-quality failure."
    );
  }

  if (
    missingPercentage !== null &&
    missingPercentage >= 30
  ) {
    status = "critical";
    reasons.push(
      "Missing data exceeds acceptable limits for reliable analysis."
    );
  }

  if (
    canAnalyze &&
    expectedAnalysisCount > 0 &&
    analysisCount === 0
  ) {
    status = "critical";
    reasons.push(
      "The product could not generate its supporting analyses."
    );
  }

  if (status !== "critical") {

    if (
      dataQualityScore !== null &&
      dataQualityScore >= 50 &&
      dataQualityScore < 70
    ) {
      status = "warning";
      reasons.push(
        "Data quality has degraded below the preferred threshold."
      );
    }

    if (
      missingPercentage !== null &&
      missingPercentage >= 15 &&
      missingPercentage < 30
    ) {
      status = "warning";
      reasons.push(
        "Missing values may affect analysis reliability."
      );
    }

    if (
      product.change_summary?.has_meaningful_changes &&
      ((product.change_summary.finding_count ?? 0) >= 2 ||
        changeHasHighSeverity(product.change_summary))
    ) {
      status = "warning";
      reasons.push(
        "Significant metric changes were detected since the previous version."
      );
    }

    if (
      requiredFieldsPresent &&
      overallCoverage < 80
    ) {
      status = "warning";
      reasons.push(
        "Optional fields are missing, limiting product coverage."
      );
    }

    if (
      highInsights > 0 ||
      notableInsights >= 3
    ) {
      status = "warning";
      reasons.push(
        "Notable anomalies were identified in product insights."
      );
    }

    if (
      expectedAnalysisCount > 0 &&
      analysisCount > 0 &&
      analysisCount < expectedAnalysisCount
    ) {
      status = "warning";
      reasons.push(
        "Some expected analyses did not complete for this product."
      );
    }

    if (product.status === "partial") {
      status = "warning";
      reasons.push(
        "Field coverage is only partial for this product."
      );
    }
  }

  if (
    status === "healthy" &&
    requiredFieldsPresent &&
    dataQualityAcceptable &&
    noMajorAnomalies &&
    productGeneratedSuccessfully
  ) {
    reasons.splice(
      0,
      reasons.length,
      "Required fields are present.",
      "Data quality is acceptable.",
      "No major anomalies were detected.",
      "The product was generated successfully."
    );
  }

  const labels: Record<
    ProductHealthStatus,
    string
  > = {
    healthy: "Healthy",
    warning: "Warning",
    critical: "Critical",
  };

  const summaries: Record<
    ProductHealthStatus,
    string
  > = {
    healthy:
      "This product is ready to use with acceptable data quality.",
    warning:
      "This product is usable, but review the flagged issues before acting on results.",
    critical:
      "This product cannot be relied on until the underlying data issues are resolved.",
  };

  return {
    status,
    label: labels[status],
    summary: summaries[status],
    reasons: reasons.slice(0, 6),
    checks: {
      required_fields_present:
        requiredFieldsPresent,
      data_quality_acceptable:
        dataQualityAcceptable,
      no_major_anomalies: noMajorAnomalies,
      product_generated_successfully:
        productGeneratedSuccessfully,
    },
  };

}


export function resolveProductHealth(
  product: Pick<
    DataProduct,
    | "health"
    | "status"
    | "coverage"
    | "insights"
    | "change_summary"
    | "metadata"
    | "dashboards"
  >
): ProductHealth {

  if (
    product.health?.status &&
    product.health.label
  ) {
    return {
      ...product.health,
      status: normalizeStatus(
        product.health.status
      ),
    };
  }

  return buildProductHealth(product);

}


export const HEALTH_STYLES: Record<
  ProductHealthStatus,
  {
    badge: string;
    panel: string;
    dot: string;
  }
> = {
  healthy: {
    badge: "bg-green-100 text-green-800 ring-green-200",
    panel: "border-green-200 bg-green-50",
    dot: "bg-green-500",
  },
  warning: {
    badge: "bg-amber-100 text-amber-900 ring-amber-200",
    panel: "border-amber-200 bg-amber-50",
    dot: "bg-amber-500",
  },
  critical: {
    badge: "bg-red-100 text-red-800 ring-red-200",
    panel: "border-red-200 bg-red-50",
    dot: "bg-red-500",
  },
};
