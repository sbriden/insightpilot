"use client";

import {
  useState,
} from "react";

import {
  ProductChangeFinding,
  ProductChangeSummary,
} from "@/types/report";


type ChangeTab =
  | "data_quality"
  | "metrics";


interface Props {
  changeSummary: ProductChangeSummary;
  onClose: () => void;
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


export default function VersionComparisonModal({
  changeSummary,
  onClose,
}: Props) {

  const metricCount =
    changeSummary.finding_count ?? 0;

  const dataQualityCount =
    changeSummary.data_quality_finding_count ??
    changeSummary.data_quality_findings?.length ??
    0;

  const totalFindings =
    metricCount + dataQualityCount;


  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >

      <div
        className="flex max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl"
        onClick={(event) =>
          event.stopPropagation()
        }
        role="dialog"
        aria-modal="true"
        aria-labelledby="version-comparison-title"
      >

        <div className="shrink-0 border-b px-6 py-5">

          <div className="flex items-start justify-between gap-4">

            <div>

              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                Version comparison
              </p>

              <h2
                id="version-comparison-title"
                className="mt-1 text-xl font-semibold text-gray-950"
              >
                v{changeSummary.previous_version} → v{changeSummary.current_version}
              </h2>

              <p className="mt-2 text-sm leading-6 text-gray-600">
                {changeSummary.overview}
              </p>

              {totalFindings > 0 && (

                <p className="mt-2 text-sm text-gray-500">
                  {totalFindings} meaningful change
                  {totalFindings === 1 ? "" : "s"} detected
                </p>

              )}

            </div>


            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
            >
              Close
            </button>

          </div>

        </div>


        <ChangeSummaryDetails
          changeSummary={changeSummary}
        />

      </div>

    </div>

  );

}


function ChangeSummaryDetails({
  changeSummary,
}: {
  changeSummary: ProductChangeSummary;
}) {

  const metricFindings =
    changeSummary.findings ?? [];

  const dataQualityFindings =
    changeSummary.data_quality_findings ??
    [];

  const hasMetricFindings =
    metricFindings.length > 0;

  const hasDataQualityFindings =
    dataQualityFindings.length > 0;

  const showTabs =
    hasMetricFindings &&
    hasDataQualityFindings;

  const [
    activeTab,
    setActiveTab,
  ] = useState<ChangeTab>(
    () =>
      hasDataQualityFindings
        ? "data_quality"
        : "metrics"
  );


  if (
    !hasMetricFindings &&
    !hasDataQualityFindings
  ) {

    return (
      <div className="px-6 py-8 text-sm text-gray-500">
        No meaningful changes were detected.
      </div>
    );

  }


  const activeConfig =
    activeTab === "data_quality"
      ? {
          title: "Data quality changes",
          description:
            changeSummary.data_quality_overview ??
            "Meaningful shifts in source data quality and structure.",
          findings: dataQualityFindings,
        }
      : {
          title: "Metric changes",
          description:
            "Meaningful shifts in product KPIs compared with the prior version.",
          findings: metricFindings,
        };


  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden bg-gray-50/50">

      {showTabs && (

        <div
          className="shrink-0 border-b border-gray-200 bg-white px-6 py-3"
          role="tablist"
          aria-label="Version comparison sections"
        >

          <div className="flex flex-wrap gap-2">

            <ChangeTabButton
              id="data_quality"
              label="Data quality"
              count={dataQualityFindings.length}
              selected={activeTab === "data_quality"}
              onSelect={() =>
                setActiveTab("data_quality")
              }
            />

            <ChangeTabButton
              id="metrics"
              label="Metrics"
              count={metricFindings.length}
              selected={activeTab === "metrics"}
              onSelect={() =>
                setActiveTab("metrics")
              }
            />

          </div>

        </div>

      )}


      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">

        <div className="shrink-0 border-b border-gray-200 bg-gray-50 px-6 py-3">

          <h4 className="text-sm font-semibold text-gray-950">
            {activeConfig.title}
          </h4>

          <p className="mt-1 text-sm text-gray-600">
            {activeConfig.description}
          </p>

        </div>


        <ChangeFindingsTable
          findings={activeConfig.findings}
        />

      </div>

    </div>

  );

}


function ChangeTabButton({
  id,
  label,
  count,
  selected,
  onSelect,
}: {
  id: string;
  label: string;
  count: number;
  selected: boolean;
  onSelect: () => void;
}) {

  return (
    <button
      type="button"
      id={`version-tab-${id}`}
      role="tab"
      aria-selected={selected}
      aria-controls={`version-panel-${id}`}
      onClick={onSelect}
      className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
        selected
          ? "bg-gray-900 text-white"
          : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
      }`}
    >

      {label}

      {count > 0 && (

        <span
          className={`rounded-full px-2 py-0.5 text-xs ${
            selected
              ? "bg-white/15 text-white"
              : "bg-gray-100 text-gray-600"
          }`}
        >
          {count}
        </span>

      )}

    </button>

  );

}


function ChangeFindingsTable({
  findings,
}: {
  findings: ProductChangeFinding[];
}) {

  const cellPadding =
    "px-4 py-3";

  if (findings.length === 0) {

    return (
      <div className="px-6 py-8 text-sm text-gray-500">
        No changes in this category.
      </div>
    );

  }


  return (
    <div className="min-h-0 flex-1 overflow-y-auto overflow-x-auto bg-white">

      <table className="min-w-full divide-y divide-gray-200 text-sm">

        <thead className="sticky top-0 z-10 bg-gray-50 shadow-sm">

          <tr>

            <th className={`${cellPadding} text-left text-xs font-semibold uppercase tracking-wide text-gray-500`}>
              Severity
            </th>

            <th className={`${cellPadding} text-left text-xs font-semibold uppercase tracking-wide text-gray-500`}>
              Category
            </th>

            <th className={`${cellPadding} text-left text-xs font-semibold uppercase tracking-wide text-gray-500`}>
              Change
            </th>

            <th className={`${cellPadding} text-left text-xs font-semibold uppercase tracking-wide text-gray-500`}>
              Direction
            </th>

            <th className={`${cellPadding} text-left text-xs font-semibold uppercase tracking-wide text-gray-500`}>
              Delta
            </th>

            <th className={`${cellPadding} text-left text-xs font-semibold uppercase tracking-wide text-gray-500`}>
              Detail
            </th>

          </tr>

        </thead>


        <tbody className="divide-y divide-gray-100 bg-white">

          {findings.map((finding) => (

            <ChangeFindingTableRow
              key={finding.id}
              finding={finding}
              cellPadding={cellPadding}
            />

          ))}

        </tbody>

      </table>

    </div>

  );

}


function ChangeFindingTableRow({
  finding,
  cellPadding,
}: {
  finding: ProductChangeFinding;
  cellPadding: string;
}) {

  const severity =
    String(
      finding.severity ?? "low"
    ).toLowerCase();

  const severityClass =
    SEVERITY_STYLES[severity] ??
    SEVERITY_STYLES.low;

  const category =
    finding.category ??
    finding.metric_name ??
    "—";

  const direction =
    finding.direction
      ? finding.direction.charAt(0).toUpperCase() +
        finding.direction.slice(1)
      : "—";


  return (
    <tr className="align-top hover:bg-gray-50">

      <td className={cellPadding}>

        <span
          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${severityClass}`}
        >
          {severity}
        </span>

      </td>

      <td className={`${cellPadding} text-gray-600`}>
        {category}
      </td>

      <td className={`${cellPadding} font-medium text-gray-950`}>
        {finding.title}
      </td>

      <td className={`${cellPadding} capitalize text-gray-600`}>
        {direction}
      </td>

      <td className={`${cellPadding} text-gray-900`}>
        {formatFindingDelta(finding)}
      </td>

      <td className={`${cellPadding} text-gray-700`}>
        {finding.message}
      </td>

    </tr>

  );

}


function formatFindingDelta(
  finding: ProductChangeFinding
): string {

  if (
    finding.relative_change_percent != null
  ) {

    const sign =
      finding.relative_change_percent > 0
        ? "+"
        : "";

    return `${sign}${finding.relative_change_percent.toFixed(1)}%`;

  }

  if (
    finding.previous_value != null &&
    finding.current_value != null
  ) {

    return `${formatMetricValue(finding.previous_value, finding.unit)} → ${formatMetricValue(finding.current_value, finding.unit)}`;

  }

  if (
    finding.absolute_change != null
  ) {

    const sign =
      finding.absolute_change > 0
        ? "+"
        : "";

    return `${sign}${formatMetricValue(finding.absolute_change, finding.unit)}`;

  }

  return "—";

}


function formatMetricValue(
  value: number,
  unit?: string
): string {

  const formatted =
    Number.isInteger(value)
      ? value.toLocaleString()
      : value.toLocaleString(
          undefined,
          {
            maximumFractionDigits: 2,
          }
        );

  if (!unit) {
    return formatted;
  }

  if (unit === "%") {
    return `${formatted}%`;
  }

  if (unit === "$") {
    return `$${formatted}`;
  }

  return `${formatted} ${unit}`;

}
