"use client";

import {
  EvidenceMetric,
  INSIGHT_TIER_LABELS,
  PromotedInsight,
  ShowEvidence,
  StructuredEvidence,
} from "@/types/report";
import { sortPromotedInsights } from "@/lib/insightModel";
import { resolveInsightLayers } from "@/lib/insightLayers";
import InsightLayerStack from "@/components/products/InsightLayerStack";


interface Props {
  insights?: PromotedInsight[];
  analysisType?: string;
  showHeader?: boolean;
}


function formatValue(
  value: unknown
): string {

  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  if (typeof value === "number") {

    if (!Number.isFinite(value)) {
      return "—";
    }

    if (
      Math.abs(value) > 0 &&
      Math.abs(value) < 1
    ) {
      return `${(value * 100).toFixed(1)}%`;
    }

    if (Number.isInteger(value)) {
      return value.toLocaleString();
    }

    return value.toLocaleString(
      undefined,
      {
        maximumFractionDigits: 3,
      }
    );

  }

  return String(value);

}


function formatEvidenceValue(
  metric: EvidenceMetric
): string {

  const value = metric.value;
  const unit = metric.unit;

  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  if (typeof value === "number" && Number.isFinite(value)) {

    if (unit === "ratio") {
      return `${(value * 100).toFixed(1)}%`;
    }

    if (unit === "currency") {
      return `$${value.toLocaleString(
        undefined,
        {
          maximumFractionDigits: 0,
        }
      )}`;
    }

    if (unit === "count") {
      return value.toLocaleString();
    }

  }

  return formatValue(value);

}


function normalizeEvidence(
  evidence: PromotedInsight["evidence"]
): StructuredEvidence {

  if (
    evidence &&
    typeof evidence === "object" &&
    Array.isArray(evidence.metrics)
  ) {
    return evidence;
  }

  if (typeof evidence === "string") {
    return {
      metrics: [],
      summary: evidence,
    };
  }

  return {
    metrics: [],
    summary: "",
  };

}


function resolveShowEvidence(
  evidence: StructuredEvidence
): ShowEvidence {
  if (evidence.show_evidence) {
    return evidence.show_evidence;
  }

  return {
    summary: {
      headline: evidence.summary ?? "",
      metric: evidence.metric,
      observed_value: evidence.observed_value,
      baseline: evidence.baseline,
      comparison: evidence.comparison,
      difference: evidence.difference,
      percentage_change: evidence.percentage_change,
      population: evidence.population,
      key_numbers: evidence.metrics ?? [],
    },
    breakdown: {
      level: evidence.level,
      levels_present: evidence.levels_present ?? [],
      dimension: evidence.relevant_dimensions?.[0] ?? null,
      dimensions: evidence.relevant_dimensions ?? [],
      entities: evidence.entities ?? evidence.breakdown ?? [],
      aggregate: {
        columns: ["label", "current", "previous", "change", "change_pct"],
        rows: evidence.aggregate_rows ?? [],
      },
      distribution: {
        dimension: evidence.relevant_dimensions?.[0] ?? null,
        buckets: evidence.distribution ?? [],
      },
      records: evidence.records ?? [],
    },
    methodology: {
      steps: evidence.methodology ?? [],
      calculation: evidence.calculation,
    },
    source: {
      dataset: evidence.source_dataset,
      dataset_id: evidence.source_dataset_id,
      columns: evidence.source_columns ?? [],
      filters: evidence.filters ?? [],
    },
    data_quality: evidence.data_quality ?? {
      issues: [],
      notes: [],
      affects_reliability: false,
      has_limitations: false,
    },
  };
}


function formatRatio(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }
  return `${(value * 100).toFixed(1)}%`;
}


function formatConfidence(
  value: number | string | null | undefined
): string {

  if (typeof value === "string" && value.trim()) {
    return value.trim().toLowerCase();
  }

  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "—";
  }

  return `${Math.round(value * 100)}%`;

}


export default function PromotedInsightsPanel({
  insights = [],
  analysisType,
  showHeader = true,
}: Props) {

  const rankedInsights = sortPromotedInsights(insights);

  if (rankedInsights.length === 0) {

    return (
      <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-500">
        No insights were generated for this analysis.
      </div>
    );

  }


  return (
    <div className="overflow-hidden rounded-xl border border-gray-200">

      {showHeader ? (

        <div className="border-b border-gray-100 bg-gray-50 px-4 py-3">

          <p className="text-sm font-medium text-gray-950">
            Insights
            {analysisType ? (
              <span className="ml-2 font-normal text-gray-500">
                ({analysisType})
              </span>
            ) : null}
          </p>

          <p className="mt-1 text-xs text-gray-500">
            Each insight keeps Fact, Interpretation, and Recommendation
            separate so deterministic observations stay distinct from
            AI meaning and next actions.
          </p>

        </div>

      ) : null}


      <div className="divide-y divide-gray-100 bg-white">

        {rankedInsights.map((insight, index) => {

          const scoreTotal =
            typeof insight.scoring?.total === "number"
              ? insight.scoring.total
              : null;
          const layers = resolveInsightLayers(insight);

          return (

            <article
              key={`${insight.insight_id}-${index}`}
              className="px-4 py-4"
            >

              <div className="flex flex-wrap items-start justify-between gap-3">

                <div>

                  <h4 className="font-medium text-gray-950">
                    {insight.title}
                  </h4>

                  <p className="mt-1 text-xs text-gray-500">
                    {INSIGHT_TIER_LABELS[insight.tier] ??
                      insight.tier ??
                      "Tier 2 — Important"}
                    {" · "}
                    {insight.category}
                    {" · "}
                    {insight.insight_type}
                    {" · "}
                    {insight.analysis_type}
                    {" · "}
                    importance{" "}
                    {formatConfidence(insight.importance)}
                    {" · "}
                    confidence {formatConfidence(insight.confidence)}
                    {scoreTotal !== null
                      ? ` · score ${scoreTotal.toFixed(1)}`
                      : ""}
                    {insight.redundancy &&
                    insight.redundancy.cluster_size > 1
                      ? ` · ${insight.redundancy.cluster_size - 1} related suppressed`
                      : ""}
                  </p>

                </div>

                <div className="text-right text-xs text-gray-500">
                  <div>
                    Metric: {insight.metric}
                  </div>
                  <div className="mt-1">
                    Observed {formatValue(insight.observed_value)}
                    {insight.baseline !== null &&
                    insight.baseline !== undefined
                      ? ` · baseline ${formatValue(insight.baseline)}`
                      : ""}
                    {insight.magnitude !== null &&
                    insight.magnitude !== undefined
                      ? ` · Δ ${formatValue(insight.magnitude)}`
                      : ""}
                  </div>
                </div>

              </div>

              <div className="mt-3">
                <InsightLayerStack
                  layers={layers}
                  variant="full"
                  afterFact={(() => {
                const evidence =
                  normalizeEvidence(insight.evidence);
                const show = resolveShowEvidence(evidence);
                const keyNumbers =
                  show.summary.key_numbers ?? [];
                const entities =
                  show.breakdown.entities ?? [];
                const aggregateRows =
                  show.breakdown.aggregate?.rows ?? [];
                const distributionBuckets =
                  show.breakdown.distribution?.buckets ?? [];
                const recordRefs =
                  show.breakdown.records ?? [];
                const steps =
                  show.methodology.steps ?? [];
                const calculation =
                  show.methodology.calculation;
                const columns = show.source.columns ?? [];
                const filters = show.source.filters ?? [];
                const dq = show.data_quality;
                const dqIssues = dq?.issues ?? [];
                const dqNotes = dq?.notes ?? [];
                const hasDataQuality =
                  Boolean(dq?.has_limitations) ||
                  dqIssues.length > 0 ||
                  dqNotes.length > 0;
                const hasCalculation = Boolean(
                  calculation &&
                    (calculation.measure ||
                      calculation.aggregation ||
                      calculation.grouping ||
                      calculation.top_n != null ||
                      calculation.comparison)
                );

                const hasStructured =
                  keyNumbers.length > 0 ||
                  entities.length > 0 ||
                  aggregateRows.length > 0 ||
                  distributionBuckets.length > 0 ||
                  recordRefs.length > 0 ||
                  steps.length > 0 ||
                  hasCalculation ||
                  columns.length > 0 ||
                  filters.length > 0 ||
                  Boolean(show.source.dataset) ||
                  hasDataQuality;

                if (!hasStructured) {
                  return show.summary.headline &&
                    show.summary.headline !== insight.finding ? (
                    <p className="mt-2 text-sm text-gray-600">
                      Evidence: {show.summary.headline}
                    </p>
                  ) : null;
                }

                return (
                  <div className="mt-3 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                      Show evidence
                    </p>

                    {keyNumbers.length > 0 ? (
                      <div className="mt-2">
                        <p className="text-xs font-medium text-gray-600">
                          Summary
                        </p>
                        <dl className="mt-1 grid gap-1 text-sm text-gray-800 sm:grid-cols-2">
                          {keyNumbers.map((metric) => (
                            <div
                              key={metric.key}
                              className="flex justify-between gap-3"
                            >
                              <dt className="text-gray-500">
                                {metric.label}
                              </dt>
                              <dd className="font-medium tabular-nums">
                                {formatEvidenceValue(metric)}
                              </dd>
                            </div>
                          ))}
                        </dl>
                      </div>
                    ) : null}

                    {aggregateRows.length > 0 ? (
                      <div className="mt-2 border-t border-gray-200 pt-2">
                        <p className="text-xs font-medium text-gray-600">
                          Breakdown · aggregate
                          {show.breakdown.dimension
                            ? ` · ${show.breakdown.dimension}`
                            : ""}
                        </p>
                        <div className="mt-1 overflow-x-auto">
                          <table className="w-full text-left text-sm text-gray-800">
                            <thead className="text-xs text-gray-500">
                              <tr>
                                <th className="py-1 pr-3 font-medium">
                                  {show.breakdown.dimension
                                    ? show.breakdown.dimension
                                    : "Group"}
                                </th>
                                <th className="py-1 pr-3 font-medium">
                                  Current
                                </th>
                                <th className="py-1 pr-3 font-medium">
                                  Previous
                                </th>
                                <th className="py-1 font-medium">
                                  Change
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              {aggregateRows.slice(0, 8).map((row, rowIndex) => (
                                <tr
                                  key={`${row.id ?? row.label}-${rowIndex}`}
                                >
                                  <td className="py-1 pr-3 text-gray-500">
                                    {row.label}
                                  </td>
                                  <td className="py-1 pr-3 font-medium tabular-nums">
                                    {formatEvidenceValue({
                                      key: "current",
                                      label: "Current",
                                      value: row.current ?? null,
                                      unit: row.unit,
                                    })}
                                  </td>
                                  <td className="py-1 pr-3 font-medium tabular-nums">
                                    {formatEvidenceValue({
                                      key: "previous",
                                      label: "Previous",
                                      value: row.previous ?? null,
                                      unit: row.unit,
                                    })}
                                  </td>
                                  <td className="py-1 font-medium tabular-nums">
                                    {typeof row.change_pct === "number"
                                      ? formatRatio(row.change_pct)
                                      : formatEvidenceValue({
                                          key: "change",
                                          label: "Change",
                                          value: row.change ?? null,
                                          unit: row.unit,
                                        })}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : null}

                    {entities.length > 0 ? (
                      <div className="mt-2 border-t border-gray-200 pt-2">
                        <p className="text-xs font-medium text-gray-600">
                          Breakdown · entity
                          {show.breakdown.dimension
                            ? ` · ${show.breakdown.dimension}`
                            : ""}
                        </p>
                        <ul className="mt-1 space-y-1 text-sm text-gray-800">
                          {entities.slice(0, 8).map((entity, entityIndex) => (
                            <li
                              key={`${entity.id ?? entity.label}-${entityIndex}`}
                              className="flex justify-between gap-3"
                            >
                              <span className="text-gray-500">
                                {entity.label}
                              </span>
                              <span className="font-medium tabular-nums">
                                {formatEvidenceValue({
                                  key: entity.id ?? entity.label,
                                  label: entity.label,
                                  value: entity.value ?? null,
                                  unit: entity.unit,
                                })}
                                {typeof entity.share === "number"
                                  ? ` (${formatRatio(entity.share)})`
                                  : ""}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    {distributionBuckets.length > 0 ? (
                      <div className="mt-2 border-t border-gray-200 pt-2">
                        <p className="text-xs font-medium text-gray-600">
                          Breakdown · distribution
                          {show.breakdown.distribution?.dimension ||
                          show.breakdown.dimension
                            ? ` · ${
                                show.breakdown.distribution?.dimension ||
                                show.breakdown.dimension
                              }`
                            : ""}
                        </p>
                        <ul className="mt-1 space-y-1 text-sm text-gray-800">
                          {distributionBuckets
                            .slice(0, 8)
                            .map((bucket, bucketIndex) => (
                              <li
                                key={`${bucket.id ?? bucket.label}-${bucketIndex}`}
                                className="flex justify-between gap-3"
                              >
                                <span className="text-gray-500">
                                  {bucket.label}
                                </span>
                                <span className="font-medium tabular-nums">
                                  {formatEvidenceValue({
                                    key: bucket.id ?? bucket.label,
                                    label: bucket.label,
                                    value: bucket.value ?? null,
                                    unit: bucket.unit,
                                  })}
                                  {typeof bucket.share === "number"
                                    ? ` (${formatRatio(bucket.share)})`
                                    : ""}
                                </span>
                              </li>
                            ))}
                        </ul>
                      </div>
                    ) : null}

                    {recordRefs.length > 0 ? (
                      <div className="mt-2 border-t border-gray-200 pt-2">
                        <p className="text-xs font-medium text-gray-600">
                          Breakdown · records
                        </p>
                        <ul className="mt-1 space-y-1 text-sm text-gray-800">
                          {recordRefs.slice(0, 8).map((record, recordIndex) => (
                            <li
                              key={`${record.record_id ?? record.label ?? recordIndex}`}
                              className="text-gray-500"
                            >
                              {record.label ||
                                record.record_id ||
                                Object.entries(record.keys ?? {})
                                  .map(([key, value]) => `${key}=${String(value)}`)
                                  .join(", ") ||
                                "Record"}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}

                    {steps.length > 0 || hasCalculation ? (
                      <div className="mt-2 border-t border-gray-200 pt-2">
                        <p className="text-xs font-medium text-gray-600">
                          Methodology
                        </p>
                        {hasCalculation ? (
                          <p className="mt-1 text-xs text-gray-500">
                            {[
                              calculation?.measure
                                ? `Measure: ${calculation.measure}`
                                : null,
                              calculation?.aggregation
                                ? `Aggregation: ${calculation.aggregation}`
                                : null,
                              calculation?.grouping
                                ? `Grouping: ${
                                    Array.isArray(calculation.grouping)
                                      ? calculation.grouping.join(", ")
                                      : calculation.grouping
                                  }`
                                : null,
                              calculation?.ranking
                                ? `Ranking: ${calculation.ranking}`
                                : null,
                              calculation?.top_n != null
                                ? `Top N: ${calculation.top_n}`
                                : null,
                              calculation?.comparison
                                ? `Comparison: ${calculation.comparison}`
                                : null,
                            ]
                              .filter(Boolean)
                              .join(" · ")}
                          </p>
                        ) : null}
                        {steps.length > 0 ? (
                          <p className="mt-1 text-xs text-gray-500">
                            {steps.join(" → ")}
                          </p>
                        ) : null}
                      </div>
                    ) : null}

                    {columns.length > 0 ||
                    filters.length > 0 ||
                    show.source.dataset ? (
                      <div className="mt-2 border-t border-gray-200 pt-2">
                        <p className="text-xs font-medium text-gray-600">
                          Source
                        </p>
                        <p className="mt-1 text-xs text-gray-500">
                          {[
                            show.source.dataset
                              ? `Dataset: ${show.source.dataset}`
                              : null,
                            columns.length > 0
                              ? `Columns: ${columns.join(", ")}`
                              : null,
                            filters.length > 0
                              ? `Filters: ${filters
                                  .map(
                                    (item) =>
                                      item.label ||
                                      item.expression ||
                                      "filter"
                                  )
                                  .join("; ")}`
                              : null,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </p>
                      </div>
                    ) : null}

                    {hasDataQuality ? (
                      <div className="mt-2 border-t border-gray-200 pt-2">
                        <p className="text-xs font-medium text-gray-600">
                          Data quality
                          {dq?.affects_reliability
                            ? " · may affect reliability"
                            : ""}
                        </p>
                        {dqIssues.length > 0 ? (
                          <ul className="mt-1 space-y-1 text-sm text-gray-800">
                            {dqIssues.map((issue, issueIndex) => (
                              <li
                                key={`${issue.type}-${issue.field ?? issue.label}-${issueIndex}`}
                                className="text-gray-600"
                              >
                                {issue.description ||
                                  [
                                    issue.label,
                                    issue.field
                                      ? `(${issue.field})`
                                      : null,
                                    typeof issue.rate === "number"
                                      ? formatRatio(issue.rate)
                                      : typeof issue.count === "number"
                                        ? `${issue.count.toLocaleString()} records`
                                        : null,
                                  ]
                                    .filter(Boolean)
                                    .join(" · ")}
                              </li>
                            ))}
                          </ul>
                        ) : null}
                        {dqNotes.length > 0 ? (
                          <p className="mt-1 text-xs text-gray-500">
                            {dqNotes.join(" · ")}
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                );
              })()}
                />
              </div>

              {insight.dimensions?.length ||
              insight.source_columns?.length ? (

                <p className="mt-3 text-xs text-gray-500">
                  {insight.dimensions?.length
                    ? `Dimensions: ${insight.dimensions.join(", ")}`
                    : null}
                  {insight.dimensions?.length &&
                  insight.source_columns?.length
                    ? " · "
                    : null}
                  {insight.source_columns?.length
                    ? `Source columns: ${insight.source_columns.join(", ")}`
                    : null}
                </p>

              ) : null}

            </article>

          );

        })}

      </div>

    </div>
  );

}
