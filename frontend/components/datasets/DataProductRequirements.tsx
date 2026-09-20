"use client";

import {
  useState,
} from "react";

import {
  ChevronDown,
} from "lucide-react";

import {
  DataProductRequirement,
  DataCoverageResult,
  FieldOpportunity,
} from "@/types/dataset";

import {
  cn,
} from "@/lib/utils";


interface Props {
  products: DataProductRequirement[];
  selectedProductIds: string[];
  onSelect?: (
    product: DataProductRequirement
  ) => void;
  productCoverage?: Record<
    string,
    DataCoverageResult
  >;
}


export default function DataProductRequirements({
  products,
  selectedProductIds,
  onSelect,
  productCoverage = {},
}: Props) {

  const [
    expandedProductIds,
    setExpandedProductIds,
  ] = useState<
    Set<string>
  >(new Set());


  if (products.length === 0) {

    return (
      <div className="rounded-xl border bg-white p-6">
        <p className="text-sm text-gray-500">
          No data products are currently available
          for this dataset type.
        </p>
      </div>
    );

  }


  function toggleExpanded(
    productId: string
  ) {

    setExpandedProductIds(
      current => {

        const next =
          new Set(current);

        if (
          next.has(productId)
        ) {
          next.delete(productId);
        } else {
          next.add(productId);
        }

        return next;

      }
    );

  }


  return (
    <div className="overflow-hidden rounded-xl border bg-white divide-y divide-gray-100">

      {products.map((product) => {

        const isSelected =
          selectedProductIds.includes(
            product.id
          );

        const isExpanded =
          expandedProductIds.has(
            product.id
          );

        const coverage =
          productCoverage[product.id];

        const canAnalyze =
          coverage?.can_analyze ?? false;

        const coveragePercent =
          coverage?.coverage_percent ?? 0;

        const requiredCoveragePercent =
          coverage?.required_coverage_percent ??
          (
            coverage?.metadata
              ?.required_field_count
              ? Math.round(
                  (
                    (
                      coverage.metadata
                        .mapped_required_count ??
                      0
                    ) /
                    coverage.metadata
                      .required_field_count
                  ) * 100
                )
              : 0
          );

        const mappedRequired =
          coverage?.metadata
            ?.mapped_required_count ?? 0;

        const requiredCount =
          coverage?.metadata
            ?.required_field_count ?? 0;

        const availableOptional =
          coverage?.metadata
            ?.available_optional_count ?? 0;

        const optionalCount =
          coverage?.metadata
            ?.optional_field_count ?? 0;

        const opportunities =
          coverage?.opportunities ?? [];

        const requiredMissing =
          opportunities.filter(
            item =>
              coverage?.missing_required_fields?.includes(
                item.field
              )
          );

        const optionalMissing =
          opportunities.filter(
            item =>
              coverage?.missing_optional_fields?.includes(
                item.field
              )
          );


        return (
          <article
            key={product.id}
            className={cn(
              "transition-colors",
              isSelected &&
                "bg-gray-50/80"
            )}
          >

            <div className="flex items-center gap-3 px-4 py-3">

              <button
                type="button"
                disabled={
                  !!coverage &&
                  !canAnalyze
                }
                onClick={() => {
                  if (
                    coverage &&
                    !canAnalyze
                  ) {
                    return;
                  }

                  onSelect?.(product);

                }}
                className={cn(
                  "flex min-w-0 flex-1 items-center gap-3 text-left",
                  coverage &&
                    !canAnalyze
                    ? "cursor-not-allowed opacity-75"
                    : "cursor-pointer"
                )}
              >

                <span
                  className={cn(
                    "flex size-4 shrink-0 items-center justify-center rounded border text-[10px] font-bold",
                    isSelected
                      ? "border-gray-900 bg-gray-900 text-white"
                      : coverage &&
                          !canAnalyze
                        ? "border-gray-200 bg-gray-100"
                        : "border-gray-300 bg-white"
                  )}
                >
                  {isSelected
                    ? "✓"
                    : ""}
                </span>


                <div className="min-w-0 flex-1">

                  <div className="flex flex-wrap items-center gap-2">

                    <h3 className="truncate text-sm font-semibold text-gray-950">
                      {product.name}
                    </h3>


                    {isSelected && (

                      <span className="rounded-full bg-gray-900 px-2 py-0.5 text-[10px] font-medium text-white">
                        Selected
                      </span>

                    )}


                    {coverage &&
                      !canAnalyze && (

                        <span className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-medium text-red-600">
                          Missing required data
                        </span>

                      )}


                    {coverage &&
                      canAnalyze && (

                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-[10px] font-medium",
                            coveragePercent === 100
                              ? "bg-green-50 text-green-700"
                              : "bg-amber-50 text-amber-800"
                          )}
                        >
                          {coveragePercent === 100
                            ? "Fully supported"
                            : "Partially supported"}
                        </span>

                      )}

                  </div>


                  {!isExpanded && (

                    <p className="mt-0.5 line-clamp-1 text-xs text-gray-500">
                      {product.description}
                    </p>

                  )}

                </div>


                {coverage && (

                  <div className="hidden shrink-0 text-right sm:block">

                    <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
                      Coverage
                    </p>

                    <p className="text-sm font-bold text-gray-950">
                      {coveragePercent}%
                    </p>

                  </div>

                )}

              </button>


              <button
                type="button"
                onClick={() =>
                  toggleExpanded(
                    product.id
                  )
                }
                aria-expanded={
                  isExpanded
                }
                aria-label={
                  isExpanded
                    ? `Collapse details for ${product.name}`
                    : `Expand details for ${product.name}`
                }
                className="flex size-8 shrink-0 items-center justify-center rounded-lg border text-gray-500 hover:bg-gray-50 hover:text-gray-800"
              >

                <ChevronDown
                  className={cn(
                    "size-4 transition-transform",
                    isExpanded &&
                      "rotate-180"
                  )}
                  aria-hidden
                />

              </button>

            </div>


            {coverage && (

              <div className="px-4 pb-3">

                <div className="h-1.5 overflow-hidden rounded-full bg-gray-100">

                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      !canAnalyze
                        ? "bg-red-500"
                        : coveragePercent === 100
                          ? "bg-green-600"
                          : "bg-amber-500"
                    )}
                    style={{
                      width: `${Math.min(
                        Math.max(
                          coveragePercent,
                          0
                        ),
                        100
                      )}%`,
                    }}
                  />

                </div>

              </div>

            )}


            {isExpanded && (

              <ProductRequirementDetails
                product={product}
                coverage={coverage}
                canAnalyze={canAnalyze}
                coveragePercent={
                  coveragePercent
                }
                requiredCoveragePercent={
                  requiredCoveragePercent
                }
                mappedRequired={
                  mappedRequired
                }
                requiredCount={
                  requiredCount
                }
                availableOptional={
                  availableOptional
                }
                optionalCount={
                  optionalCount
                }
                requiredMissing={
                  requiredMissing
                }
                optionalMissing={
                  optionalMissing
                }
              />

            )}

          </article>
        );

      })}

    </div>

  );

}


function ProductRequirementDetails({
  product,
  coverage,
  canAnalyze,
  coveragePercent,
  requiredCoveragePercent,
  mappedRequired,
  requiredCount,
  availableOptional,
  optionalCount,
  requiredMissing,
  optionalMissing,
}: {
  product: DataProductRequirement;
  coverage?: DataCoverageResult;
  canAnalyze: boolean;
  coveragePercent: number;
  requiredCoveragePercent: number;
  mappedRequired: number;
  requiredCount: number;
  availableOptional: number;
  optionalCount: number;
  requiredMissing: FieldOpportunity[];
  optionalMissing: FieldOpportunity[];
}) {

  return (
    <div className="border-t border-gray-100 px-4 py-4">

      <p className="text-sm leading-6 text-gray-600">
        {product.description}
      </p>


      {coverage && (

        <div className="mt-4 rounded-lg bg-gray-50 p-3">

          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-gray-600">

            <span>
              Required:{" "}
              <span className="font-medium text-gray-800">
                {mappedRequired}
              </span>
              {" / "}
              <span className="font-medium text-gray-800">
                {requiredCount}
              </span>
              {requiredCount > 0 && (
                <span className="text-gray-400">
                  {" "}
                  ({requiredCoveragePercent}%)
                </span>
              )}
            </span>

            <span>
              Optional:{" "}
              <span className="font-medium text-gray-800">
                {availableOptional}
              </span>
              {" / "}
              <span className="font-medium text-gray-800">
                {optionalCount}
              </span>
            </span>

            <span className="font-medium text-gray-800">
              {coveragePercent}% total coverage
            </span>

          </div>

        </div>

      )}


      <div className="mt-4">

        <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
          Required fields
        </p>

        {product.required_fields.length === 0 ? (

          <p className="mt-2 text-sm text-gray-500">
            No required fields.
          </p>

        ) : (

          <div className="mt-2 flex flex-wrap gap-1.5">

            {product.required_fields.map(
              field => {

                const isMapped =
                  coverage?.mapped_required_fields?.includes(
                    field
                  ) ?? false;

                return (
                  <span
                    key={field}
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[11px]",
                      isMapped
                        ? "bg-green-100 text-green-700"
                        : "bg-red-50 text-red-600"
                    )}
                  >
                    {isMapped
                      ? `✓ ${field}`
                      : `✕ ${field}`}
                  </span>
                );

              }
            )}

          </div>

        )}

      </div>


      {requiredMissing.length > 0 && (

        <div className="mt-4 rounded-lg border border-red-100 bg-red-50 p-3">

          <p className="text-sm font-medium text-red-700">
            Required data missing
          </p>

          <div className="mt-2 space-y-2">

            {requiredMissing.map(
              opportunity => (

                <OpportunityCard
                  key={
                    opportunity.field
                  }
                  opportunity={
                    opportunity
                  }
                  tone="required"
                />

              )
            )}

          </div>

        </div>

      )}


      {product.optional_fields.length > 0 && (

        <div className="mt-4">

          <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
            Optional fields
          </p>

          <div className="mt-2 flex flex-wrap gap-1.5">

            {product.optional_fields.map(
              field => {

                const isAvailable =
                  coverage?.available_optional_fields?.includes(
                    field
                  ) ?? false;

                return (
                  <span
                    key={field}
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[11px]",
                      isAvailable
                        ? "bg-green-50 text-green-700"
                        : "border bg-white text-gray-500"
                    )}
                  >
                    {isAvailable
                      ? `✓ ${field}`
                      : field}
                  </span>
                );

              }
            )}

          </div>

        </div>

      )}


      {optionalMissing.length > 0 && (

        <div className="mt-4 rounded-lg border border-amber-100 bg-amber-50 p-3">

          <p className="text-sm font-medium text-amber-800">
            Add fields to unlock more
          </p>

          <div className="mt-2 space-y-2">

            {optionalMissing.map(
              opportunity => (

                <OpportunityCard
                  key={
                    opportunity.field
                  }
                  opportunity={
                    opportunity
                  }
                  tone="optional"
                />

              )
            )}

          </div>

        </div>

      )}


      <div className="mt-4">

        <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
          Dataset grain
        </p>

        <code className="mt-1 inline-block rounded bg-gray-50 px-2 py-1 text-xs">
          {product.grain}
        </code>

      </div>


      {product.analyses.length > 0 && (

        <div className="mt-4">

          <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
            Included analyses
          </p>

          <div className="mt-2 flex flex-wrap gap-1.5">

            {product.analyses.map(
              analysis => (

                <span
                  key={analysis}
                  className="rounded bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600"
                >
                  {formatLabel(analysis)}
                </span>

              )
            )}

          </div>

        </div>

      )}


      {coverage && (

        <div className="mt-4 border-t border-gray-100 pt-3">

          {canAnalyze ? (

            <p className="text-sm font-medium text-green-700">
              Ready to analyze
              {coveragePercent < 100
                ? " — more fields will deepen results"
                : ""}
            </p>

          ) : (

            <p className="text-sm text-red-600">
              This product cannot be analyzed with the
              current dataset. Map the missing required
              fields to make it available.
            </p>

          )}

        </div>

      )}

    </div>

  );

}


function OpportunityCard({
  opportunity,
  tone,
}: {
  opportunity: FieldOpportunity;
  tone: "required" | "optional";
}) {

  const analyses =
    opportunity.analyses ?? [];

  const metrics =
    opportunity.metrics ?? [];


  return (
    <div
      className={cn(
        "rounded-lg bg-white p-2.5",
        tone === "required"
          ? "border border-red-100"
          : "border border-amber-100"
      )}
    >

      <div className="flex flex-wrap items-center gap-2">

        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-[11px] font-medium",
            tone === "required"
              ? "bg-red-50 text-red-700"
              : "bg-amber-100 text-amber-800"
          )}
        >
          {opportunity.field}
        </span>

        {opportunity.priority && (

          <span className="text-[10px] uppercase tracking-wide text-gray-400">
            {opportunity.priority} priority
          </span>

        )}

      </div>


      {opportunity.description && (

        <p className="mt-1.5 text-xs leading-5 text-gray-600">
          {opportunity.description}
        </p>

      )}


      {(analyses.length > 0 ||
        metrics.length > 0) && (

        <div className="mt-2 space-y-1.5">

          {analyses.length > 0 && (

            <div className="flex flex-wrap gap-1">

              {analyses.map(
                analysis => (

                  <span
                    key={analysis}
                    className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-700"
                  >
                    {formatLabel(analysis)}
                  </span>

                )
              )}

            </div>

          )}

          {metrics.length > 0 && (

            <div className="flex flex-wrap gap-1">

              {metrics.map(
                metric => (

                  <span
                    key={metric}
                    className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-700"
                  >
                    {metric}
                  </span>

                )
              )}

            </div>

          )}

        </div>

      )}

    </div>

  );

}


function formatLabel(
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
