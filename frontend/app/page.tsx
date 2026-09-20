"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { DataProduct } from "@/types/report";

import ProductHealthBadge from "@/components/products/ProductHealthBadge";
import PrebuiltProductCard from "@/components/products/PrebuiltProductCard";

import {
  getDataProducts,
} from "@/services/api";

import {
  groupProductsByDefinition,
  normalizeProduct,
  ProductGroup,
} from "@/lib/productLineage";

import {
  NATIVE_DEFINITION_IDS,
  NATIVE_PRODUCTS,
} from "@/lib/prebuiltProducts";

import {
  isNativeProduct,
} from "@/lib/productTypes";


export default function DataProductsHomePage() {

  const [groups, setGroups] =
    useState<ProductGroup[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);


  useEffect(() => {

    async function loadProducts() {

      try {

        setLoading(true);
        setError(null);

        const result =
          await getDataProducts();

        const normalized =
          Array.isArray(result)
            ? result.map(
                normalizeProduct
              )
            : [];

        setGroups(
          groupProductsByDefinition(
            normalized
          ).filter(
            (group) =>
              !isNativeProduct(
                group.latest,
                NATIVE_DEFINITION_IDS
              )
          )
        );

      } catch (loadError) {

        console.error(
          "Failed to load products:",
          loadError
        );

        setError(
          "Unable to load data products."
        );

      } finally {

        setLoading(false);

      }

    }

    loadProducts();

  }, []);


  if (loading) {

    return (
      <main className="mx-auto min-h-screen max-w-7xl">

        <h1 className="text-3xl font-bold">
          Data Products
        </h1>

        <p className="mt-4 text-gray-500">
          Loading data products...
        </p>

      </main>
    );

  }


  if (error) {

    return (
      <main className="mx-auto min-h-screen max-w-7xl">

        <h1 className="text-3xl font-bold">
          Data Products
        </h1>

        <div className="mt-6 rounded-lg border bg-white p-6">

          <p className="text-red-600">
            {error}
          </p>

          <button
            onClick={() =>
              window.location.reload()
            }
            className="mt-4 rounded-lg border px-4 py-2 text-sm font-medium hover:bg-gray-50"
          >
            Try again
          </button>

        </div>

      </main>
    );

  }


  return (

    <main className="mx-auto min-h-screen max-w-7xl">

      <div className="mb-8">

        <div className="flex flex-wrap items-start justify-between gap-4">

          <div>

            <h1 className="text-3xl font-bold">
              Data Products
            </h1>

            <p className="mt-2 max-w-2xl text-gray-600">
              Explore included pre-built products, or open
              your saved analytical products to review
              results, switch versions, and refresh data.
            </p>

          </div>


          <div className="flex flex-wrap items-center gap-3">

            {groups.length > 0 && (

              <span className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-600">
                {groups.length}{" "}
                {groups.length === 1
                  ? "product"
                  : "products"}
              </span>

            )}

            <Link
              href="/create"
              className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
            >
              Create data product
            </Link>

          </div>

        </div>

      </div>


      <section className="mb-10">

        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">

          <div>

            <h2 className="text-lg font-semibold text-gray-900">
              Native products
            </h2>

            <p className="mt-1 text-sm text-gray-500">
              InsightPilot-maintained products with curated sources — no upload required.
            </p>

          </div>

          <span className="rounded-full bg-teal-100 px-3 py-1 text-xs font-medium text-teal-900">
            {NATIVE_PRODUCTS.length} included
          </span>

        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">

          {NATIVE_PRODUCTS.map(
            (product) => (

              <PrebuiltProductCard
                key={product.id}
                product={product}
              />

            )
          )}

        </div>

      </section>


      <section>

        <div className="mb-4 flex flex-wrap items-end justify-between gap-3">

          <div>

            <h2 className="text-lg font-semibold text-gray-900">
              User-created products
            </h2>

            <p className="mt-1 text-sm text-gray-500">
              Analytical products you created from your datasets.
            </p>

          </div>

        </div>

        {groups.length === 0 ? (

          <EmptyState />

        ) : (

          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">

            {groups.map(
              (group) => (

                <ProductGroupCard
                  key={
                    group.definitionId
                  }
                  group={group}
                />

              )
            )}

          </div>

        )}

      </section>

    </main>

  );

}


function ProductGroupCard({
  group,
}: {
  group: ProductGroup;
}) {

  const product =
    group.latest;

  const analyses =
    Array.isArray(product.analyses)
      ? product.analyses
      : [];

  const metrics =
    Array.isArray(product.metrics)
      ? product.metrics
      : [];

  const insights =
    Array.isArray(product.insights)
      ? product.insights
      : [];


  return (

    <div className="flex flex-col rounded-xl border bg-white p-6">

      <div className="flex items-start justify-between gap-4">

        <div>

          <h2 className="font-semibold">
            {group.name}
          </h2>

          <p className="mt-2 text-sm leading-6 text-gray-600">
            {group.description}
          </p>

        </div>

        <div className="flex shrink-0 items-center gap-2">

          <StatusBadge
            status={product.status}
          />

          <ProductHealthBadge
            product={product}
            showLabel={false}
            showPopover
            popoverSize="compact"
            align="right"
          />

        </div>

      </div>


      <div className="mt-4 flex flex-wrap gap-2">

        <span className="rounded-full bg-gray-900 px-3 py-1 text-xs text-white">
          Latest v{product.version}
        </span>

        {group.versionCount > 1 && (

          <span className="rounded-full bg-gray-100 px-3 py-1 text-xs">
            {group.versionCount} versions
          </span>

        )}

        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs">

          {analyses.length}{" "}
          {analyses.length === 1
            ? "analysis"
            : "analyses"}

        </span>


        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs">

          {metrics.length}{" "}
          {metrics.length === 1
            ? "KPI"
            : "KPIs"}

        </span>


        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs">

          {insights.length}{" "}
          {insights.length === 1
            ? "insight"
            : "insights"}

        </span>

        {product.change_summary?.has_meaningful_changes && (

          <span className="rounded-full bg-gray-900 px-3 py-1 text-xs text-white">
            {product.change_summary.finding_count}{" "}
            change
            {product.change_summary.finding_count === 1
              ? ""
              : "s"}
          </span>

        )}

      </div>


      <div className="mt-6">

        <div className="mb-2 flex justify-between text-xs">

          <span className="text-gray-500">
            Field coverage
          </span>

          <span className="font-medium">
            {product.coverage}%
          </span>

        </div>


        <div className="h-2 overflow-hidden rounded-full bg-gray-100">

          <div
            className="h-full rounded-full bg-gray-900"
            style={{
              width:
                `${Math.min(
                  Math.max(
                    Number(
                      product.coverage ?? 0
                    ),
                    0
                  ),
                  100
                )}%`,
            }}
          />

        </div>

      </div>


      <div className="mt-6">

        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
          Included Analysis
        </p>


        {analyses.length === 0 ? (

          <p className="mt-3 text-sm text-gray-400">
            No analysis defined.
          </p>

        ) : (

          <div className="mt-3 flex flex-wrap gap-2">

            {analyses.map(
              (
                analysis,
                index
              ) => {

                const id =
                  typeof analysis === "string"
                    ? analysis
                    : analysis?.id ??
                      `analysis-${index}`;


                const title =
                  formatAnalysisName(
                    analysis
                  );


                return (

                  <span
                    key={`${id}-${index}`}
                    className="rounded-md bg-gray-100 px-2 py-1 text-xs text-gray-600"
                  >
                    {title}
                  </span>

                );

              }
            )}

          </div>

        )}

      </div>


      <div className="mt-6 border-t pt-5">

        <Link
          href={`/products/${encodeURIComponent(group.definitionId)}`}
          className="text-sm font-medium hover:underline"
        >
          Explore product →
        </Link>

      </div>

    </div>

  );

}


function StatusBadge({
  status,
}: {
  status: DataProduct["status"];
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
      className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${
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


function EmptyState() {

  return (

    <div className="rounded-xl border bg-white p-10 text-center">

      <h2 className="text-lg font-semibold">
        No custom products yet
      </h2>


      <p className="mx-auto mt-2 max-w-md text-sm text-gray-500">
        Create a product from your own data, or open a
        pre-built product above to get started.
      </p>


      <Link
        href="/create"
        className="mt-5 inline-block rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
      >
        Create data product
      </Link>

    </div>

  );

}


function formatAnalysisName(
  value:
    | string
    | {
        id?: string;
        title?: string;
      }
    | null
    | undefined
) {

  if (!value) {

    return "Unknown";

  }


  const name =
    typeof value === "string"
      ? value
      : value.title ||
        value.id ||
        "Unknown";


  return String(name)
    .replaceAll(
      "_",
      " "
    )
    .replace(
      /\b\w/g,
      (char) =>
        char.toUpperCase()
    );

}
