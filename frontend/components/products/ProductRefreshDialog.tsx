"use client";

import { useState } from "react";

import UploadCard from "@/components/upload/UploadCard";

import { useAnalysis } from "@/hooks/useAnalysis";

import { readDatasetFields } from "@/lib/readDatasetFields";

import {
  loadFieldMappingsAsync,
  reuseFieldMappings,
} from "@/lib/mappingMemory";

import { buildSemanticFields } from "@/lib/semanticFields";

import {
  getDatasetTypeDataProducts,
} from "@/services/api";

import {
  DataProductRequirement,
  FieldMapping,
} from "@/types/dataset";


interface Props {
  open: boolean;
  onClose: () => void;
  definitionIds: string[];
  productNames: string[];
  primaryDefinitionId: string;
  datasetTypeId?: string;
  onRefreshComplete?: (
    productId: string
  ) => void;
}


export default function ProductRefreshDialog({
  open,
  onClose,
  definitionIds,
  productNames,
  primaryDefinitionId,
  datasetTypeId = "sales",
  onRefreshComplete,
}: Props) {

  const {
    upload,
    analysisLoading,
  } = useAnalysis();

  const [file, setFile] =
    useState<File | null>(null);

  const [mappingLoading, setMappingLoading] =
    useState(false);

  const [fieldMappings, setFieldMappings] =
    useState<FieldMapping[]>([]);

  const [mappingReady, setMappingReady] =
    useState(false);

  const [mappingMessage, setMappingMessage] =
    useState<string | null>(null);

  const [error, setError] =
    useState<string | null>(null);


  if (!open) {
    return null;
  }


  function resetState() {

    setFile(null);
    setFieldMappings([]);
    setMappingReady(false);
    setMappingMessage(null);
    setError(null);

  }


  function handleClose() {

    resetState();
    onClose();

  }


  async function handleFileChange(
    nextFile: File | null
  ) {

    setFile(nextFile);
    setError(null);
    setMappingMessage(null);
    setMappingReady(false);
    setFieldMappings([]);

    if (!nextFile) {
      return;
    }

    try {

      setMappingLoading(true);

      const uploadedFields =
        await readDatasetFields(
          nextFile
        );

      const catalog =
        await getDatasetTypeDataProducts(
          datasetTypeId
        );

      const allRequirements =
        (catalog?.data_products ??
          []) as DataProductRequirement[];

      const productRequirements =
        definitionIds
          .map(
            id =>
              allRequirements.find(
                product =>
                  product.id === id
              )
          )
          .filter(
            (
              product
            ): product is DataProductRequirement =>
              !!product
          );

      if (
        productRequirements.length === 0
      ) {

        setError(
          "Unable to load field requirements for the associated products."
        );

        return;

      }

      const semanticFields =
        buildSemanticFields(
          productRequirements
        );

      const saved =
        await loadFieldMappingsAsync(
          datasetTypeId
        );

      const reused =
        saved
          ? reuseFieldMappings(
              saved,
              uploadedFields,
              semanticFields
            )
          : null;

      const mappings =
        reused ??
        semanticFields.map(
          field => ({
            requiredField:
              field.field,

            uploadedField: null,

            matchType: "unmapped" as const,

            confidence: 0,

            required:
              field.required,

            valid: !field.required,
          })
        );

      setFieldMappings(mappings);

      const blockedProducts =
        productRequirements
          .map(
            requirement => {

              const missingRequired =
                requirement.required_fields.filter(
                  field =>
                    !mappings.some(
                      mapping =>
                        mapping.requiredField === field &&
                        !!mapping.uploadedField
                    )
                );

              if (
                missingRequired.length === 0
              ) {
                return null;
              }

              return {
                name:
                  requirement.name,

                missingRequired,
              };

            }
          )
          .filter(
            Boolean
          ) as Array<{
            name: string;
            missingRequired: string[];
          }>;

      if (
        blockedProducts.length > 0
      ) {

        setMappingMessage(
          blockedProducts
            .map(
              item =>
                `${item.name}: missing ${item.missingRequired.join(", ")}`
            )
            .join("; ")
        );

        setMappingReady(false);

        return;

      }

      const productLabel =
        definitionIds.length === 1
          ? productNames[0]
          : `${definitionIds.length} data products`;

      setMappingMessage(
        `Field mappings loaded. Ready to refresh ${productLabel}.`
      );

      setMappingReady(true);

    } catch (uploadError) {

      console.error(
        "Failed to prepare refresh upload:",
        uploadError
      );

      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to prepare the dataset."
      );

    } finally {

      setMappingLoading(false);

    }

  }


  async function handleRefresh() {

    if (!file || !mappingReady) {
      return;
    }

    try {

      setError(null);

      const result =
        await upload(
          file,
          fieldMappings,
          definitionIds
        );

      const refreshedProduct =
        result.data_products?.find(
          product =>
            product.definition_id ===
              primaryDefinitionId ||
            product.id.startsWith(
              `${primaryDefinitionId}__`
            )
        );

      const refreshedCount =
        result.data_products?.length ??
        definitionIds.length;

      if (refreshedProduct?.id) {

        onRefreshComplete?.(
          refreshedProduct.id
        );

        resetState();
        onClose();

        return;

      }

      setMappingMessage(
        `Analysis completed for ${refreshedCount} product${refreshedCount === 1 ? "" : "s"}. Reloading...`
      );

      onRefreshComplete?.("");
      handleClose();

    } catch (refreshError) {

      console.error(
        "Failed to refresh products:",
        refreshError
      );

      setError(
        refreshError instanceof Error
          ? refreshError.message
          : "Unable to refresh these products."
      );

    }

  }


  const loading =
    mappingLoading ||
    analysisLoading;

  const refreshTargetLabel =
    definitionIds.length === 1
      ? productNames[0] ??
        "this product"
      : `${definitionIds.length} associated data products`;


  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">

      <div
        className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-xl border bg-white p-6 shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="refresh-data-title"
      >

        <div className="flex items-start justify-between gap-4">

          <div>

            <h2
              id="refresh-data-title"
              className="text-lg font-semibold"
            >
              Refresh data
            </h2>

            <p className="mt-1 text-sm text-gray-600">
              Upload a new or updated dataset to
              generate new versions for{" "}
              {refreshTargetLabel}. Saved field
              mappings are reused automatically.
            </p>

            {definitionIds.length > 1 && (

              <div className="mt-3 flex flex-wrap gap-2">

                {productNames.map(
                  (name) => (

                    <span
                      key={name}
                      className="rounded-full bg-gray-100 px-2.5 py-1 text-xs text-gray-600"
                    >
                      {name}
                    </span>

                  )
                )}

              </div>

            )}

          </div>

          <button
            type="button"
            onClick={handleClose}
            className="rounded-lg border px-3 py-1 text-sm text-gray-500 hover:bg-gray-50"
          >
            Close
          </button>

        </div>


        {error && (

          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3">

            <p className="text-sm text-red-700">
              {error}
            </p>

          </div>

        )}


        {mappingMessage && (

          <div
            className={`mt-4 rounded-lg border p-3 ${
              mappingReady
                ? "border-green-200 bg-green-50"
                : "border-amber-200 bg-amber-50"
            }`}
          >

            <p
              className={`text-sm ${
                mappingReady
                  ? "text-green-700"
                  : "text-amber-800"
              }`}
            >
              {mappingMessage}
            </p>

          </div>

        )}


        <div className="mt-4">

          <UploadCard
            file={file}
            loading={loading}
            onFileChange={
              handleFileChange
            }
          />

        </div>


        <div className="mt-4 flex flex-wrap justify-end gap-3">

          <button
            type="button"
            onClick={handleClose}
            className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-gray-50"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleRefresh}
            disabled={
              !file ||
              !mappingReady ||
              loading
            }
            className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {analysisLoading
              ? "Analyzing..."
              : "Upload and refresh"}
          </button>

        </div>

      </div>

    </div>

  );

}
