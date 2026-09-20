"use client";

import {
  CandidateFinding,
  FindingProvenance,
} from "@/types/report";


interface Props {
  findings?: CandidateFinding[];
  analysisType?: string;
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

    if (
      !Number.isFinite(value)
    ) {
      return "—";
    }

    if (
      Math.abs(value) > 0 &&
      Math.abs(value) < 1
    ) {
      return `${(value * 100).toFixed(1)}%`;
    }

    if (
      Number.isInteger(value)
    ) {
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


function formatMagnitude(
  finding: CandidateFinding
): string {

  if (
    finding.magnitude === null ||
    finding.magnitude === undefined
  ) {
    return "—";
  }

  const value =
    finding.magnitude;

  const unit =
    finding.magnitude_unit;

  if (unit === "ratio") {
    const sign =
      value > 0 ? "+" : "";
    return `${sign}${(value * 100).toFixed(1)} pp`;
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

  return formatValue(value);

}


function formatConfidence(
  value: number | string | null | undefined
): string {

  if (typeof value === "string" && value.trim()) {
    return value.trim().toLowerCase();
  }

  if (
    typeof value !== "number" ||
    !Number.isFinite(value)
  ) {
    return "—";
  }

  return `${Math.round(value * 100)}%`;

}


function formatList(
  values?: string[] | null
): string {

  if (
    !values ||
    values.length === 0
  ) {
    return "—";
  }

  return values.join(", ");

}


function resolveProvenance(
  finding: CandidateFinding
): FindingProvenance {

  if (
    finding.provenance
  ) {
    return finding.provenance;
  }

  return {
    source_columns:
      finding.source_columns ?? [],
    dimensions:
      finding.relevant_dimensions ?? [],
    filters:
      finding.filters ?? [],
    calculations:
      finding.calculations ?? [],
    row_scope: null,
    input_values: {},
  };

}


function ProvenanceCell({
  finding,
}: {
  finding: CandidateFinding;
}) {

  const provenance =
    resolveProvenance(finding);

  const filters =
    provenance.filters ?? [];

  const calculations =
    provenance.calculations ?? [];

  return (
    <div className="max-w-md space-y-2 text-xs text-gray-700">

      <div>
        <div className="font-semibold text-gray-500">
          Columns
        </div>
        <div className="font-mono">
          {formatList(
            provenance.source_columns
          )}
        </div>
      </div>

      <div>
        <div className="font-semibold text-gray-500">
          Dimensions
        </div>
        <div>
          {formatList(
            provenance.dimensions
          )}
        </div>
      </div>

      <div>
        <div className="font-semibold text-gray-500">
          Filters
        </div>
        {filters.length === 0 ? (
          <div>—</div>
        ) : (
          <ul className="list-disc pl-4">
            {filters.map(
              (filter, index) => (
                <li key={`${finding.id}-filter-${index}`}>
                  {filter.label ||
                    [
                      filter.field,
                      filter.op,
                      filter.value != null
                        ? String(filter.value)
                        : null,
                    ]
                      .filter(Boolean)
                      .join(" ") ||
                    filter.expression ||
                    "—"}
                </li>
              )
            )}
          </ul>
        )}
      </div>

      <div>
        <div className="font-semibold text-gray-500">
          Calculations
        </div>
        {calculations.length === 0 ? (
          <div>—</div>
        ) : (
          <ol className="list-decimal pl-4">
            {calculations.map(
              (step, index) => (
                <li key={`${finding.id}-calc-${index}`}>
                  {step}
                </li>
              )
            )}
          </ol>
        )}
      </div>

      {provenance.row_scope ? (
        <div>
          <div className="font-semibold text-gray-500">
            Row scope
          </div>
          <div>
            {provenance.row_scope}
          </div>
        </div>
      ) : null}

    </div>
  );

}


export default function CandidateFindingsPanel({
  findings = [],
  analysisType,
}: Props) {

  if (
    findings.length === 0
  ) {

    return (
      <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-500">
        No candidate findings were emitted for this analysis.
      </div>
    );

  }


  return (
    <div className="overflow-hidden rounded-xl border border-gray-200">

      <div className="border-b border-gray-100 bg-gray-50 px-4 py-3">

        <p className="text-sm font-medium text-gray-950">
          Candidate findings
          {analysisType ? (
            <span className="ml-2 font-normal text-gray-500">
              ({analysisType})
            </span>
          ) : null}
        </p>

        <p className="mt-1 text-xs text-gray-500">
          Traceable deterministic observations — each finding
          retains the columns, filters, dimensions, and
          calculations that produced it.
        </p>

      </div>


      <div className="overflow-x-auto">

        <table className="min-w-full text-left text-sm">

          <thead className="bg-white text-xs font-semibold uppercase tracking-wide text-gray-500">

            <tr>

              <th className="px-4 py-3">
                Finding
              </th>

              <th className="px-4 py-3">
                Metric
              </th>

              <th className="px-4 py-3 text-right">
                Observed
              </th>

              <th className="px-4 py-3 text-right">
                Baseline
              </th>

              <th className="px-4 py-3 text-right">
                Magnitude
              </th>

              <th className="px-4 py-3">
                Evidence
              </th>

              <th className="px-4 py-3">
                Data provenance
              </th>

            </tr>

          </thead>


          <tbody className="divide-y divide-gray-100 bg-white">

            {findings.map(
              (finding, index) => (

                <tr
                  key={`${finding.id}-${index}`}
                  className="align-top hover:bg-gray-50"
                >

                  <td className="px-4 py-3">

                    <div className="font-medium text-gray-950">
                      {finding.title ||
                        finding.rule_id ||
                        finding.id}
                    </div>

                    <div className="mt-1 text-xs text-gray-500">
                      importance{" "}
                      {finding.importance ??
                        finding.severity ??
                        "—"}
                      {" · "}
                      confidence{" "}
                      {formatConfidence(
                        finding.confidence
                      )}
                      {" · "}
                      {finding.analysis_type}
                    </div>

                  </td>

                  <td className="px-4 py-3 font-mono text-xs text-gray-700">
                    {finding.metric}
                    {finding.comparison ? (
                      <div className="mt-1 text-gray-500">
                        {finding.comparison}
                      </div>
                    ) : null}
                  </td>

                  <td className="px-4 py-3 text-right font-medium text-gray-950">
                    {formatValue(
                      finding.observed_value
                    )}
                  </td>

                  <td className="px-4 py-3 text-right text-gray-700">
                    {formatValue(
                      finding.baseline
                    )}
                  </td>

                  <td className="px-4 py-3 text-right text-gray-700">
                    {formatMagnitude(
                      finding
                    )}
                  </td>

                  <td className="max-w-xs px-4 py-3 text-gray-700">
                    {finding.evidence || "—"}
                  </td>

                  <td className="px-4 py-3">
                    <ProvenanceCell
                      finding={finding}
                    />
                  </td>

                </tr>

              )
            )}

          </tbody>

        </table>

      </div>

    </div>
  );

}
