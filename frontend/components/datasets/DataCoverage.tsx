"use client";

import {
  DataCoverageResult,
} from "@/types/dataset";


interface Props {
  result: DataCoverageResult;
}


export default function DataCoverage({
  result,
}: Props) {

  /*
   * --------------------------------
   * Safely extract result values
   * --------------------------------
   */

  const requiredFields =
    result.required_fields ?? [];

  const mappedRequiredFields =
    result.mapped_required_fields ?? [];

  const missingRequiredFields =
    result.missing_required_fields ?? [];

  const availableOptionalFields =
    result.available_optional_fields ?? [];

  const missingOptionalFields =
    result.missing_optional_fields ?? [];

  const opportunities =
    result.opportunities ?? [];


  /*
   * --------------------------------
   * Calculate required coverage
   * --------------------------------
   */

  const requiredFieldCount =
    result.metadata?.required_field_count ??
    requiredFields.length;

  const mappedRequiredCount =
    result.metadata?.mapped_required_count ??
    mappedRequiredFields.length;


  const requiredCoverage =
    requiredFieldCount === 0
      ? 100
      : Math.round(
          (mappedRequiredCount /
            requiredFieldCount) *
            100
        );


  /*
   * --------------------------------
   * Calculate product coverage
   *
   * Required + optional fields
   * --------------------------------
   */

  const optionalFieldCount =
    result.metadata?.optional_field_count ??
    (
      availableOptionalFields.length +
      missingOptionalFields.length
    );

  const availableOptionalCount =
    result.metadata?.available_optional_count ??
    availableOptionalFields.length;


  const totalProductFields =
    requiredFieldCount +
    optionalFieldCount;


  const totalAvailableFields =
    mappedRequiredCount +
    availableOptionalCount;


  const productCoverage =
    totalProductFields === 0
      ? 100
      : Math.round(
          (totalAvailableFields /
            totalProductFields) *
            100
        );


  /*
   * --------------------------------
   * Debug
   * --------------------------------
   */

  console.log(
    "DataCoverage rendering:",
    {
      requiredFieldCount,
      mappedRequiredCount,
      requiredCoverage,
      optionalFieldCount,
      availableOptionalCount,
      totalProductFields,
      totalAvailableFields,
      productCoverage,
      resultCoverage:
        result.coverage_percent,
    }
  );


  /*
   * --------------------------------
   * Opportunity lookup
   * --------------------------------
   */

  function getOpportunity(
    field: string
  ) {

    if (!Array.isArray(opportunities)) {
      return null;
    }

    return (
      opportunities.find(
        opportunity =>
          opportunity.field === field
      ) ?? null
    );

  }


  return (

    <div className="space-y-6">


      {/* ================================= */}
      {/* Coverage Summary */}
      {/* ================================= */}

      <div className="grid gap-6 md:grid-cols-2">


        {/* Required Coverage */}

        <div className="rounded-xl border bg-white p-6">

          <div className="flex items-start justify-between">

            <div>

              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                Required Data Coverage
              </p>

              <p className="mt-2 text-3xl font-bold">
                {requiredCoverage}%
              </p>

              <p className="mt-2 text-sm text-gray-500">
                {mappedRequiredCount} of{" "}
                {requiredFieldCount} required fields
                are mapped.
              </p>

            </div>


            <div className="text-right">

              <p className="text-xs uppercase tracking-wide text-gray-400">
                Status
              </p>

              <p
                className={`mt-1 text-sm font-semibold ${
                  requiredCoverage === 100
                    ? "text-green-600"
                    : requiredCoverage >= 75
                    ? "text-yellow-600"
                    : "text-red-600"
                }`}
              >
                {requiredCoverage === 100
                  ? "Ready"
                  : requiredCoverage >= 75
                  ? "Mostly Ready"
                  : "More Data Needed"}
              </p>

            </div>

          </div>


          {/* Required progress */}

          <div className="mt-5">

            <div className="mb-2 flex items-center justify-between text-xs text-gray-500">

              <span>
                Required fields
              </span>

              <span className="font-semibold text-gray-700">
                {requiredCoverage}%
              </span>

            </div>


            <div className="h-3 w-full overflow-hidden rounded-full bg-gray-100">

              <div
                className="h-full rounded-full bg-gray-900 transition-all"
                style={{
                  width: `${Math.min(
                    Math.max(
                      requiredCoverage,
                      0
                    ),
                    100
                  )}%`,
                }}
              />

            </div>

          </div>

        </div>


        {/* Product Coverage */}

        <div className="rounded-xl border bg-white p-6">

          <div className="flex items-start justify-between">

            <div>

              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                Product Coverage
              </p>

              <p className="mt-2 text-3xl font-bold">
                {productCoverage}%
              </p>

              <p className="mt-2 text-sm text-gray-500">
                {totalAvailableFields} of{" "}
                {totalProductFields} product fields
                are available.
              </p>

            </div>


            <div className="text-right">

              <p className="text-xs uppercase tracking-wide text-gray-400">
                Coverage
              </p>

              <p className="mt-1 text-sm font-semibold text-gray-700">
                {productCoverage}%
              </p>

            </div>

          </div>


          {/* Product progress */}

          <div className="mt-5">

            <div className="mb-2 flex items-center justify-between text-xs text-gray-500">

              <span>
                Required + optional
              </span>

              <span className="font-semibold text-gray-700">
                {productCoverage}%
              </span>

            </div>


            <div className="h-3 w-full overflow-hidden rounded-full bg-gray-100">

              <div
                className="h-full rounded-full bg-gray-900 transition-all"
                style={{
                  width: `${Math.min(
                    Math.max(
                      productCoverage,
                      0
                    ),
                    100
                  )}%`,
                }}
              />

            </div>

          </div>

        </div>

      </div>


      {/* ================================= */}
      {/* Missing Required Fields */}
      {/* ================================= */}

      {missingRequiredFields.length > 0 && (

        <div className="rounded-xl border border-red-200 bg-red-50 p-6">

          <p className="text-xs font-semibold uppercase tracking-wide text-red-500">
            Required Data
          </p>

          <h3 className="mt-1 font-semibold text-red-900">
            Required fields are missing
          </h3>

          <p className="mt-1 text-sm text-red-700">
            These fields are required before this
            data product can be fully analyzed.
          </p>


          <div className="mt-4 space-y-2">

            {missingRequiredFields.map(
              field => (

                <div
                  key={field}
                  className="flex items-center gap-3 rounded-lg bg-white px-4 py-3"
                >

                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-red-100 text-xs font-bold text-red-600">
                    !
                  </span>

                  <span className="text-sm font-medium text-red-800">
                    {field}
                  </span>

                </div>

              )
            )}

          </div>

        </div>

      )}


      {/* ================================= */}
      {/* Available Optional Fields */}
      {/* ================================= */}

      {availableOptionalFields.length > 0 && (

        <div className="rounded-xl border bg-white p-6">

          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            Additional Data Available
          </p>

          <h3 className="mt-1 font-semibold">
            Your dataset contains additional fields
          </h3>

          <p className="mt-1 text-sm text-gray-500">
            These fields can support analysis beyond
            the core data product.
          </p>


          <div className="mt-4 flex flex-wrap gap-2">

            {availableOptionalFields.map(
              field => (

                <span
                  key={field}
                  className="rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-700"
                >
                  ✓ {field}
                </span>

              )
            )}

          </div>

        </div>

      )}


      {/* ================================= */}
      {/* Missing Optional Fields */}
      {/* ================================= */}

      {missingOptionalFields.length > 0 && (

        <div className="rounded-xl border bg-white p-6">

          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            Increase Data Coverage
          </p>

          <h3 className="mt-1 text-lg font-semibold">
            Add fields to unlock more analysis
          </h3>

          <p className="mt-2 max-w-2xl text-sm text-gray-600">
            Your current dataset supports the core
            analysis, but adding the fields below
            could allow InsightPilot to perform
            additional analysis.
          </p>


          <div className="mt-5 space-y-3">

            {missingOptionalFields.map(
              field => {

                const opportunity =
                  getOpportunity(field);


                return (

                  <div
                    key={field}
                    className="rounded-xl border bg-gray-50 p-5"
                  >

                    <div className="flex items-start justify-between gap-4">

                      <div>

                        <p className="font-semibold">
                          {field}
                        </p>

                        {opportunity?.description && (

                          <p className="mt-1 text-sm leading-6 text-gray-600">
                            {
                              opportunity.description
                            }
                          </p>

                        )}

                      </div>


                      {opportunity?.priority && (

                        <PriorityBadge
                          priority={
                            opportunity.priority
                          }
                        />

                      )}

                    </div>


                    {opportunity &&
                      opportunity.analyses?.length >
                        0 && (

                        <div className="mt-4">

                          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                            Unlocks
                          </p>

                          <div className="mt-2 flex flex-wrap gap-2">

                            {opportunity.analyses.map(
                              analysis => (

                                <span
                                  key={analysis}
                                  className="rounded-md bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm"
                                >
                                  {formatAnalysisName(
                                    analysis
                                  )}
                                </span>

                              )
                            )}

                          </div>

                        </div>

                      )}

                  </div>

                );

              }
            )}

          </div>

        </div>

      )}


      {/* ================================= */}
      {/* Everything Available */}
      {/* ================================= */}

      {missingRequiredFields.length === 0 &&
        missingOptionalFields.length === 0 && (

          <div className="rounded-xl border border-green-200 bg-green-50 p-6">

            <div className="flex items-start gap-3">

              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-green-100 font-semibold text-green-700">
                ✓
              </div>

              <div>

                <h3 className="font-semibold text-green-900">
                  Your dataset has excellent coverage
                </h3>

                <p className="mt-1 text-sm leading-6 text-green-700">
                  All required and optional fields
                  for this data product are available.
                  No additional fields are currently
                  needed to unlock the available
                  analysis.
                </p>

              </div>

            </div>

          </div>

        )}

    </div>

  );

}


/*
 * --------------------------------
 * Priority badge
 * --------------------------------
 */

function PriorityBadge({
  priority,
}: {
  priority: string;
}) {

  const normalized =
    priority.toLowerCase();


  let className =
    "bg-gray-100 text-gray-600";


  if (
    normalized === "high" ||
    normalized === "critical"
  ) {

    className =
      "bg-red-100 text-red-700";

  } else if (
    normalized === "medium"
  ) {

    className =
      "bg-yellow-100 text-yellow-700";

  } else if (
    normalized === "low"
  ) {

    className =
      "bg-green-100 text-green-700";

  }


  return (

    <span
      className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${className}`}
    >
      {priority}
    </span>

  );

}


/*
 * --------------------------------
 * Analysis name formatter
 * --------------------------------
 */

function formatAnalysisName(
  value: string
) {

  return value
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      char =>
        char.toUpperCase()
    );

}