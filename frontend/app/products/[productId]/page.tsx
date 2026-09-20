"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import ProductCustomizer from "@/components/products/ProductCustomizer";
import ProductRefreshDialog from "@/components/products/ProductRefreshDialog";
import ProductWorkspace from "@/components/products/ProductWorkspace";
import ProductVersionCoveragePanel from "@/components/products/ProductVersionCoveragePanel";
import ProductHealthBadge from "@/components/products/ProductHealthBadge";
import ExportReportButton from "@/components/products/ExportReportButton";
import ProductHeaderIconButton from "@/components/products/ProductHeaderIconButton";

import {
  RefreshCw,
  Save,
  SlidersHorizontal,
} from "lucide-react";

import {
  DataProduct,
  DataProductConfiguration,
} from "@/types/report";

import {
  getProductConfiguration,
  saveProductConfiguration,
} from "@/lib/dataProducts";

import {
  buildProductConfiguration,
} from "@/lib/buildProductConfiguration";

import {
  getDefinitionIdsForUploadBatch,
  groupProductsByDefinition,
  normalizeProduct,
  parseProductInstanceId,
} from "@/lib/productLineage";

import {
  getDataProduct,
  getDataProducts,
  getProductVersions,
  updateDataProduct,
} from "@/services/api";


export default function DataProductPage({
  params,
}: {
  params: Promise<{
    productId: string;
  }>;
}) {

  const [routeKey, setRouteKey] =
    useState<string>("");

  const [definitionId, setDefinitionId] =
    useState<string>("");

  const [versions, setVersions] =
    useState<DataProduct[]>([]);

  const [selectedVersionId, setSelectedVersionId] =
    useState<string>("");

  const [product, setProduct] =
    useState<DataProduct | null>(null);

  const [dashboards, setDashboards] =
    useState<any[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [saving, setSaving] =
    useState(false);

  const [
    configuration,
    setConfiguration,
  ] =
    useState<DataProductConfiguration | null>(
      null
    );

  const [
    showRefresh,
    setShowRefresh,
  ] =
    useState(false);

  const [
    supportedDefinitionIds,
    setSupportedDefinitionIds,
  ] =
    useState<string[]>([]);

  const [
    supportedProductNames,
    setSupportedProductNames,
  ] =
    useState<string[]>([]);

  const [
    showCustomizer,
    setShowCustomizer,
  ] =
    useState(false);


  function loadAssociatedProducts(
    referenceProduct: DataProduct,
    allProducts: DataProduct[]
  ) {

    const definitionIds =
      getDefinitionIdsForUploadBatch(
        allProducts,
        referenceProduct
      );

    const associatedGroups =
      groupProductsByDefinition(
        allProducts.filter(
          product =>
            definitionIds.includes(
              product.definition_id ??
              parseProductInstanceId(
                product.id
              ).definitionId
            )
        )
      );

    const names =
      definitionIds.map(
        id =>
          associatedGroups.find(
            group =>
              group.definitionId === id
          )?.name ??
          referenceProduct.name
      );

    setSupportedDefinitionIds(
      definitionIds
    );

    setSupportedProductNames(
      names
    );

  }


  const loadVersion =
    useCallback(
      async (
        versionId: string
      ) => {

        const result =
          await getDataProduct(
            versionId
          );

        if (!result) {
          return null;
        }

        const foundProduct =
          normalizeProduct(
            result
          ) as DataProduct;

        let productDashboards: any[] =
          Array.isArray(
            foundProduct.dashboards
          )
            ? foundProduct.dashboards
            : [];

        const savedConfiguration =
          getProductConfiguration(
            foundProduct.id
          );

        const productConfiguration =
          savedConfiguration ??
          buildProductConfiguration(
            foundProduct,
            productDashboards
          );

        setProduct(
          foundProduct
        );

        setDashboards(
          productDashboards
        );

        setConfiguration(
          productConfiguration
        );

        setSelectedVersionId(
          foundProduct.id
        );

        return foundProduct;

      },
      []
    );


  const loadProductLineage =
    useCallback(
      async (
        requestedKey: string,
        preferredVersionId?: string
      ) => {

        setLoading(true);
        setError(null);

        try {

          const parsed =
            parseProductInstanceId(
              requestedKey
            );

          const resolvedDefinitionId =
            parsed.isInstanceId
              ? parsed.definitionId
              : requestedKey;

          setDefinitionId(
            resolvedDefinitionId
          );

          let versionRows: DataProduct[] =
            [];

          try {

            const result =
              await getProductVersions(
                resolvedDefinitionId
              );

            versionRows =
              Array.isArray(result)
                ? result.map(
                    normalizeProduct
                  )
                : [];

          } catch (versionError) {

            /*
             * Fall back to a direct product load
             * for legacy rows without definition_id.
             */

            const direct =
              await getDataProduct(
                requestedKey
              );

            if (direct) {

              const normalized =
                normalizeProduct(
                  direct
                ) as DataProduct;

              versionRows = [normalized];

              setDefinitionId(
                normalized.definition_id ??
                parsed.definitionId
              );

            } else {

              throw versionError;

            }

          }

          if (
            versionRows.length === 0
          ) {

            setError(
              "Data product not found."
            );

            return;

          }

          setVersions(
            versionRows
          );

          const preferred =
            preferredVersionId ??
            (
              parsed.isInstanceId
                ? versionRows.find(
                    row =>
                      row.id === requestedKey
                  )?.id
                : undefined
            ) ??
            versionRows[0]?.id;

          if (!preferred) {

            setError(
              "Data product not found."
            );

            return;

          }

          const loadedProduct =
            await loadVersion(
              preferred
            );

          if (loadedProduct) {

            try {

              const allProducts =
                await getDataProducts();

              loadAssociatedProducts(
                loadedProduct,
                Array.isArray(
                  allProducts
                )
                  ? allProducts.map(
                      normalizeProduct
                    )
                  : []
              );

            } catch (associatedError) {

              console.warn(
                "Unable to load associated products:",
                associatedError
              );

              loadAssociatedProducts(
                loadedProduct,
                [loadedProduct]
              );

            }

          }

        } catch (loadError) {

          console.error(
            "Failed to load data product:",
            loadError
          );

          setError(
            loadError instanceof Error
              ? loadError.message
              : "Unable to load data product."
          );

        } finally {

          setLoading(false);

        }

      },
      [loadVersion]
    );


  useEffect(() => {

    async function init() {

      const {
        productId,
      } = await params;

      setRouteKey(productId);

      await loadProductLineage(
        productId
      );

    }

    init();

  }, [params, loadProductLineage]);


  async function handleVersionChange(
    versionId: string
  ) {

    if (
      versionId === selectedVersionId
    ) {
      return;
    }

    try {

      setLoading(true);
      setError(null);

      await loadVersion(
        versionId
      );

    } catch (versionError) {

      console.error(
        "Failed to switch version:",
        versionError
      );

      setError(
        versionError instanceof Error
          ? versionError.message
          : "Unable to load that version."
      );

    } finally {

      setLoading(false);

    }

  }


  async function handleRefreshComplete(
    newProductId?: string
  ) {

    await loadProductLineage(
      definitionId || routeKey,
      newProductId || undefined
    );

  }


  function handleSaveConfiguration(
    nextConfiguration: DataProductConfiguration
  ) {

    saveProductConfiguration(
      nextConfiguration
    );

    setConfiguration(
      nextConfiguration
    );

    setShowCustomizer(
      false
    );

  }


  async function handleSaveProduct() {

    if (!product) {
      return;
    }


    try {

      setSaving(true);
      setError(null);

      const productPayload = {

        id:
          product.id,

        name:
          configuration?.name ??
          product.name,

        description:
          configuration?.description ??
          product.description,

        business_purpose:
          product.business_purpose ??
          null,

        source_dataset:
          product.source_dataset ??
          null,

        status:
          product.status,

        coverage:
          Number(
            product.coverage ?? 0
          ),

        version:
          Number(
            product.version ?? 1
          ),

        analyses:
          product.analyses ?? [],

        metrics:
          product.metrics ?? [],

        insights:
          product.insights ?? [],

        metadata:
          product.metadata ?? {},

      };

      const updatedProduct =
        await updateDataProduct(
          product.id,
          productPayload
        );

      if (updatedProduct) {

        setProduct(
          normalizeProduct(
            updatedProduct
          ) as DataProduct
        );

      }

    } catch (saveError) {

      console.error(
        "Failed to update data product:",
        saveError
      );

      setError(
        saveError instanceof Error
          ? saveError.message
          : "Unable to save data product."
      );

    } finally {

      setSaving(false);

    }

  }


  if (loading && !product) {

    return (

      <main className="min-h-screen p-10">

        <Link
          href="/"
          className="text-sm text-gray-500"
        >
          ← Data Products
        </Link>

        <p className="mt-8 text-gray-500">
          Loading data product...
        </p>

      </main>

    );

  }


  if (!product) {

    return (

      <main className="min-h-screen p-10">

        <Link
          href="/"
          className="text-sm text-gray-500"
        >
          ← Back to Data Products
        </Link>


        <h1 className="mt-8 text-2xl font-bold">
          Data Product Not Found
        </h1>


        <p className="mt-2 text-gray-600">
          {error ??
            "The requested data product could not be found."}
        </p>

      </main>

    );

  }


  const selectedAnalysisIds =
    configuration?.selectedAnalyses ?? [];


  const selectedDashboards =
    dashboards.filter(
      (dashboard) =>
        selectedAnalysisIds.includes(
          dashboard.id
        )
    );


  const latestVersion =
    versions[0]?.version ??
    product.version;


  return (

    <main className="min-h-screen p-10">

      <Link
        href="/"
        className="text-sm text-gray-500 hover:underline"
      >
        ← Data Products
      </Link>


      {error && (

        <div className="mt-6 rounded-lg border border-red-200 bg-red-50 p-4">

          <p className="text-sm text-red-700">
            {error}
          </p>

        </div>

      )}


      <div className="mt-8">

        <div className="flex flex-wrap items-start justify-between gap-6">

          <div>

            <div className="flex flex-wrap items-center gap-3">

              <h1 className="text-4xl font-bold">
                {configuration?.name ??
                  product.name}
              </h1>


              <StatusBadge
                status={product.status}
              />


              <ProductHealthBadge
                product={product}
                showPopover
                popoverSize="full"
              />

            </div>


            <p className="mt-4 max-w-3xl text-gray-600">

              {configuration?.description ??
                product.description}

            </p>

          </div>


          <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">

            <ProductVersionCoveragePanel
              versions={versions}
              selectedVersionId={
                selectedVersionId
              }
              currentVersion={
                product.version
              }
              coverage={product.coverage}
              latestVersion={latestVersion}
              changeSummary={
                product.change_summary
              }
              onVersionChange={
                handleVersionChange
              }
              formatVersionDate={
                formatVersionDate
              }
            />

            <ExportReportButton
              product={product}
            />

            {definitionId && (

              <ProductHeaderIconButton
                label="Refresh data"
                icon={RefreshCw}
                onClick={() =>
                  setShowRefresh(true)
                }
              />

            )}

            <ProductHeaderIconButton
              label="Customize product"
              icon={SlidersHorizontal}
              onClick={() =>
                setShowCustomizer(true)
              }
            />

            <ProductHeaderIconButton
              label={
                saving
                  ? "Saving product..."
                  : "Save product"
              }
              icon={Save}
              variant="default"
              loading={saving}
              disabled={saving}
              onClick={handleSaveProduct}
            />

          </div>

        </div>


        {product.business_purpose && (

          <div className="mt-6 max-w-3xl">

            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
              Business Purpose
            </p>


            <p className="mt-2 text-sm leading-6 text-gray-600">
              {product.business_purpose}
            </p>

          </div>

        )}


        <div className="mt-6 flex flex-wrap gap-3">

          <span className="rounded-full border px-3 py-1 text-xs text-gray-600">

            {product.analyses.length}{" "}
            {product.analyses.length === 1
              ? "analysis"
              : "analyses"}

          </span>


          <span className="rounded-full border px-3 py-1 text-xs text-gray-600">

            {(product.metrics ?? []).length}{" "}
            {(product.metrics ?? []).length === 1
              ? "KPI"
              : "KPIs"}

          </span>


          <span className="rounded-full border px-3 py-1 text-xs text-gray-600">

            {(product.insights ?? []).length}{" "}
            {(product.insights ?? []).length === 1
              ? "insight"
              : "insights"}

          </span>


          <span className="rounded-full border px-3 py-1 text-xs text-gray-600">

            v{product.version}

          </span>

        </div>

      </div>


      <div className="mt-8">

        <ProductWorkspace
          product={product}
          dashboards={dashboards}
          visibleDashboards={
            selectedDashboards
          }
        />

      </div>


      {definitionId && (

        <ProductRefreshDialog
          open={showRefresh}
          onClose={() =>
            setShowRefresh(false)
          }
          definitionIds={
            supportedDefinitionIds.length > 0
              ? supportedDefinitionIds
              : [definitionId]
          }
          productNames={
            supportedProductNames.length > 0
              ? supportedProductNames
              : [product.name]
          }
          primaryDefinitionId={
            definitionId
          }
          onRefreshComplete={
            handleRefreshComplete
          }
        />

      )}


      {showCustomizer &&
        configuration && (

          <ProductCustomizer
            configuration={
              configuration
            }
            dashboards={
              dashboards
            }
            onSave={
              handleSaveConfiguration
            }
            onClose={() =>
              setShowCustomizer(false)
            }
          />

        )}

    </main>

  );

}


function formatVersionDate(
  version: {
    updated_at?: string;
    created_at?: string;
  }
) {

  const timestamp =
    version.updated_at ??
    version.created_at;

  if (!timestamp) {
    return "";
  }

  const parsed =
    Date.parse(timestamp);

  if (Number.isNaN(parsed)) {
    return "";
  }

  return ` — ${new Date(parsed).toLocaleDateString()}`;

}


function StatusBadge({
  status,
}: {
  status: string;
}) {

  const normalizedStatus =
    String(
      status ?? "unknown"
    ).toLowerCase();


  const labels: Record<
    string,
    string
  > = {

    ready:
      "Ready",

    partial:
      "Partial",

    limited:
      "Limited",

    draft:
      "Draft",

    archived:
      "Archived",

    unknown:
      "Unknown",

  };


  const styles: Record<
    string,
    string
  > = {

    ready:
      "bg-green-100 text-green-700",

    partial:
      "bg-yellow-100 text-yellow-700",

    limited:
      "bg-orange-100 text-orange-700",

    draft:
      "bg-gray-100 text-gray-700",

    archived:
      "bg-gray-100 text-gray-500",

    unknown:
      "bg-gray-100 text-gray-700",

  };


  return (

    <span
      className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${
        styles[
          normalizedStatus
        ] ??
        styles.unknown
      }`}
    >

      {
        labels[
          normalizedStatus
        ] ??
        "Unknown"
      }

    </span>

  );

}
