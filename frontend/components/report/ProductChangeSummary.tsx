"use client";

import {
  ProductChangeFinding,
  ProductChangeSummary,
} from "@/types/report";


interface ProductChangeSummaryPanelProps {
  changeSummary: ProductChangeSummary;
}


const SEVERITY_STYLES: Record<
  string,
  string
> = {
  critical: "bg-red-100 text-red-800",
  high: "bg-red-100 text-red-800",
  medium: "bg-amber-100 text-amber-900",
  low: "bg-gray-100 text-gray-700",
};


export default function ProductChangeSummaryPanel({
  changeSummary,
}: ProductChangeSummaryPanelProps) {

  const metricFindings =
    changeSummary.findings ?? [];

  const dataQualityFindings =
    changeSummary.data_quality_findings ??
    [];

  const hasMetricFindings =
    metricFindings.length > 0;

  const hasDataQualityFindings =
    dataQualityFindings.length > 0;


  return (
    <section className="rounded-xl border bg-white">

      <div className="border-b px-6 py-4">

        <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
          Version comparison
        </p>

        <h3 className="mt-1 text-lg font-semibold">
          Changes since v{changeSummary.previous_version}
        </h3>

        <p className="mt-2 text-sm leading-6 text-gray-600">
          {changeSummary.overview}
        </p>

      </div>


      {!hasMetricFindings &&
        !hasDataQualityFindings && (

          <div className="p-6 text-sm text-gray-500">
            No meaningful changes were detected.
          </div>

        )}


      {hasDataQualityFindings && (

        <ChangeFindingSection
          title="Data quality changes"
          description={
            changeSummary.data_quality_overview ??
            "Meaningful shifts in source data quality and structure."
          }
          findings={dataQualityFindings}
        />

      )}


      {hasMetricFindings && (

        <ChangeFindingSection
          title="Metric changes"
          description="Meaningful shifts in product KPIs compared with the prior version."
          findings={metricFindings}
          borderedTop={hasDataQualityFindings}
        />

      )}

    </section>

  );

}


function ChangeFindingSection({
  title,
  description,
  findings,
  borderedTop = false,
}: {
  title: string;
  description: string;
  findings: ProductChangeFinding[];
  borderedTop?: boolean;
}) {

  return (
    <div
      className={
        borderedTop
          ? "border-t"
          : ""
      }
    >

      <div className="border-b bg-gray-50 px-6 py-3">

        <h4 className="text-sm font-semibold text-gray-950">
          {title}
        </h4>

        <p className="mt-1 text-sm text-gray-600">
          {description}
        </p>

      </div>


      <div className="divide-y">

        {findings.map((finding) => (

          <ChangeFindingRow
            key={finding.id}
            finding={finding}
          />

        ))}

      </div>

    </div>

  );

}


function ChangeFindingRow({
  finding,
}: {
  finding: ProductChangeFinding;
}) {

  const severity =
    String(
      finding.severity ?? "low"
    ).toLowerCase();

  const severityClass =
    SEVERITY_STYLES[severity] ??
    SEVERITY_STYLES.low;


  return (
    <div className="px-6 py-4">

      <div className="flex flex-wrap items-center gap-2">

        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${severityClass}`}
        >
          {severity}
        </span>

        {finding.direction && (

          <span className="text-xs capitalize text-gray-500">
            {finding.direction}
          </span>

        )}

        {finding.relative_change_percent != null && (

          <span className="text-xs text-gray-500">
            {finding.relative_change_percent > 0 ? "+" : ""}
            {finding.relative_change_percent.toFixed(1)}%
          </span>

        )}

      </div>

      <p className="mt-2 font-medium text-gray-950">
        {finding.title}
      </p>

      <p className="mt-1 text-sm leading-6 text-gray-600">
        {finding.message}
      </p>

    </div>

  );

}
