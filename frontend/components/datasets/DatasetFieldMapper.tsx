"use client";

import {
  DataProductRequirement,
  DatasetField,
  FieldMapping,
  SemanticField,
} from "@/types/dataset";

import {
  SemanticFieldProductUsage,
  SemanticFieldProductUsageLegend,
} from "@/components/datasets/SemanticFieldProductUsage";

import SemanticFieldDetails from "@/components/datasets/SemanticFieldDetails";

interface Props {
  product: DataProductRequirement;

  uploadedFields: DatasetField[];

  mappings: FieldMapping[];

  onChange: (
    requiredField: string,
    uploadedField: string | null
  ) => void;

  onContinue: (
    mappings: FieldMapping[]
  ) => void;

  onBack: () => void;

  semanticFields?: SemanticField[];

  availableProducts?: DataProductRequirement[];

  embedded?: boolean;

  hideActions?: boolean;
}

export default function DatasetFieldMapper({
  product,
  uploadedFields,
  mappings,
  onChange,
  onContinue,
  onBack,
  semanticFields = [],
  availableProducts = [],
  embedded = false,
  hideActions = false,
}: Props) {
  /*
   * -------------------------------------------------------------------------
   * IMPORTANT ARCHITECTURAL RULE
   * -------------------------------------------------------------------------
   *
   * There are NO globally required fields at the dataset mapping level.
   *
   * A field may be:
   *
   *   - required by Product A
   *   - optional for Product B
   *   - unused by Product C
   *
   * Therefore the mapper must NEVER prevent the user from continuing because
   * a semantic field is unmapped.
   *
   * Product-specific requirements are evaluated after this screen.
   */

  const safeMappings = Array.isArray(mappings)
    ? mappings
    : [];

  /*
   * Dataset-level mapping statistics.
   */

  const mappedCount =
    safeMappings.filter(
      (mapping) =>
        !!mapping.uploadedField
    ).length;

  const totalCount =
    safeMappings.length;

  const mappingCoverage =
    totalCount === 0
      ? 0
      : Math.round(
          (mappedCount / totalCount) * 100
        );

  /*
   * The Continue button should only depend on whether mappings exist.
   *
   * It should NOT depend on whether every field is mapped.
   */

  const canContinue =
    safeMappings.length > 0;

  /*
   * Determine which semantic field information belongs to each mapping.
   *
   * This lets us show product-specific context without making the field
   * globally required.
   */

  function getSemanticField(
    fieldName: string
  ): SemanticField | undefined {
    return semanticFields.find(
      (field) =>
        field.field === fieldName
    );
  }

  /*
   * Helper to determine which uploaded columns are already being used.
   *
   * This prevents one uploaded column from accidentally being mapped to
   * multiple semantic fields.
   */

  function getAvailableFields(
    currentMapping: FieldMapping
  ) {
    const usedFields =
      safeMappings
        .filter(
          (mapping) =>
            mapping.requiredField !==
              currentMapping.requiredField &&
            !!mapping.uploadedField
        )
        .map(
          (mapping) =>
            mapping.uploadedField
        );

    return uploadedFields.filter(
      (field) =>
        !usedFields.includes(field.name) ||
        field.name ===
          currentMapping.uploadedField
    );
  }

  /*
   * -------------------------------------------------------------------------
   * Mapping Row
   * -------------------------------------------------------------------------
   */

  function MappingRow({
    mapping,
  }: {
    mapping: FieldMapping;
  }) {
    const availableFields =
      getAvailableFields(mapping);

    const semanticField =
      getSemanticField(
        mapping.requiredField
      );

    return (
      <div className="grid gap-4 px-6 py-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,0.9fr)]">

        {/* Semantic field */}

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 lg:hidden">
            Semantic Field
          </p>

          <div className="mt-2 lg:mt-0">
            <SemanticFieldDetails
              fieldName={
                mapping.requiredField
              }
              semanticField={
                semanticField
              }
            />
          </div>
        </div>

        {/* Uploaded field */}

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 lg:hidden">
            Uploaded Column
          </p>

          <select
            value={
              mapping.uploadedField ?? ""
            }
            onChange={(event) =>
              onChange(
                mapping.requiredField,
                event.target.value || null
              )
            }
            className={`mt-2 w-full rounded-lg border px-3 py-2 text-sm lg:mt-0 ${
              mapping.uploadedField
                ? "border-gray-300 bg-white"
                : "border-gray-300 bg-gray-50"
            }`}
          >
            <option value="">
              — Not mapped —
            </option>

            {availableFields.map(
              (field) => (
                <option
                  key={field.name}
                  value={field.name}
                >
                  {field.name}
                </option>
              )
            )}
          </select>

          {/* Mapping status */}

          <div className="mt-2">
            {!mapping.uploadedField && (
              <span className="text-xs text-gray-500">
                Not mapped
              </span>
            )}

            {mapping.uploadedField &&
              mapping.matchType ===
                "exact" && (
                <span className="text-xs text-green-600">
                  ✓ Exact match
                </span>
              )}

            {mapping.uploadedField &&
              mapping.matchType ===
                "normalized" && (
                <span className="text-xs text-green-600">
                  ✓ Strong match
                </span>
              )}

            {mapping.uploadedField &&
              mapping.matchType ===
                "fuzzy" && (
                <span className="text-xs text-yellow-600">
                  ⚠ Suggested match
                </span>
              )}

            {mapping.uploadedField &&
              mapping.matchType ===
                "manual" && (
                <span className="text-xs text-blue-600">
                  ✓ Manually mapped
                </span>
              )}
          </div>
        </div>

        {/* Product usage */}

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 lg:hidden">
            Data Products
          </p>

          <div className="mt-2 lg:mt-0">
            {semanticField ? (
              <SemanticFieldProductUsage
                semanticField={
                  semanticField
                }
                products={
                  availableProducts
                }
              />
            ) : (
              <p className="text-xs text-gray-400">
                —
              </p>
            )}
          </div>
        </div>

      </div>
    );
  }

  return (
    <div className="space-y-6">

      {!embedded && (

      <>
      {/* -------------------------------------------------------------------
          Header
          ------------------------------------------------------------------- */}

      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-gray-400">
          Field Mapping
        </p>

        <h2 className="mt-1 text-2xl font-semibold">
          Map your dataset
        </h2>

        <p className="mt-2 max-w-2xl text-sm text-gray-600">
          InsightPilot automatically matched
          your uploaded columns to shared
          semantic fields. Review the matches
          below and map any fields you want to
          make available for analysis.
        </p>
      </div>
      </>
      )}


      {/* -------------------------------------------------------------------
          Dataset Mapping Summary
          ------------------------------------------------------------------- */}

      <div className="rounded-xl border bg-white p-6">

        <div className="flex items-center justify-between">

          <div>
            <p className="text-sm text-gray-500">
              Dataset field coverage
            </p>

            <p className="mt-1 text-3xl font-bold">
              {mappingCoverage}%
            </p>
          </div>

          <div className="text-right">

            <p className="text-sm text-gray-500">
              Fields mapped
            </p>

            <p className="mt-1 font-medium">
              {mappedCount} of{" "}
              {totalCount}
            </p>

          </div>

        </div>

        <div className="mt-4 h-2 overflow-hidden rounded-full bg-gray-100">

          <div
            className="h-full rounded-full bg-gray-900 transition-all"
            style={{
              width: `${mappingCoverage}%`,
            }}
          />

        </div>

        <p className="mt-4 text-sm text-gray-500">
          You can continue with unmapped
          fields. Required fields are evaluated
          separately for each data product.
        </p>

      </div>


      {/* -------------------------------------------------------------------
          Fields
          ------------------------------------------------------------------- */}

      <div className="rounded-xl border bg-white">

        <div className="border-b px-6 py-4">

          <h3 className="font-semibold">
            Dataset Fields
          </h3>

          <p className="mt-1 text-sm text-gray-500">
            Map the uploaded columns to the
            semantic fields used by InsightPilot.
          </p>

          {availableProducts.length > 0 && (
            <div className="mt-3">
              <SemanticFieldProductUsageLegend />
            </div>
          )}

        </div>

        {safeMappings.length > 0 && (
          <div className="hidden border-b bg-gray-50 px-6 py-3 lg:grid lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,0.9fr)] lg:gap-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Semantic Field
            </p>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Uploaded Column
            </p>
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              Data Products
            </p>
          </div>
        )}

        <div className="divide-y">

          {safeMappings.length === 0 ? (

            <div className="px-6 py-8 text-center">

              <p className="text-sm text-gray-500">
                No semantic fields were detected.
              </p>

            </div>

          ) : (

            safeMappings.map(
              (mapping) => (
                <MappingRow
                  key={
                    mapping.requiredField
                  }
                  mapping={mapping}
                />
              )
            )

          )}

        </div>

      </div>


      {/* -------------------------------------------------------------------
          Product Requirement Explanation
          ------------------------------------------------------------------- */}

      <div className="rounded-xl border bg-gray-50 p-5">

        <p className="text-sm font-medium">
          How field requirements work
        </p>

        <p className="mt-1 text-sm text-gray-600">
          A field may be required for one analytical
          product, optional for another, or not used at
          all. The colored indicators in the Data
          Products column show how each field applies.
        </p>

      </div>


      {/* -------------------------------------------------------------------
          Actions
          ------------------------------------------------------------------- */}

      {!hideActions && (

      <div className="flex items-center justify-between">

        <button
          type="button"
          onClick={onBack}
          className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-gray-50"
        >
          ← Back
        </button>

        <button
          type="button"
          onClick={() =>
            onContinue(
              safeMappings
            )
          }
          disabled={!canContinue}
          className="rounded-lg bg-gray-900 px-5 py-2 text-sm font-medium text-white transition hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Continue →
        </button>

      </div>

      )}

    </div>
  );
}