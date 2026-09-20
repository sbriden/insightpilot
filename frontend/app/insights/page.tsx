"use client";

import { useState } from "react";
import Link from "next/link";

import CollapsibleProductGroup from "@/components/products/CollapsibleProductGroup";
import ProductInsightsTable from "@/components/products/ProductInsightsTable";

import { useSavedProducts } from "@/hooks/useSavedProducts";

import {
  countInsightsByPriority,
} from "@/lib/prioritySummary";

import {
  ProductGroup,
} from "@/lib/productLineage";

import {
  DataProduct,
} from "@/types/report";


function resolveActiveProduct(
  group: ProductGroup,
  selectedVersionId?: string
): DataProduct {

  const activeVersionId =
    selectedVersionId ??
    group.latest.id;

  return (
    group.versions.find(
      version =>
        version.id === activeVersionId
    ) ?? group.latest
  );

}


export default function InsightsPage() {

  const {
    groups,
    loaded,
    error,
  } = useSavedProducts();

  const [
    selectedVersions,
    setSelectedVersions,
  ] =
    useState<
      Record<string, string>
    >({});


  function handleVersionChange(
    definitionId: string,
    versionId: string
  ) {

    setSelectedVersions(
      current => ({
        ...current,
        [definitionId]: versionId,
      })
    );

  }


  if (!loaded) {
    return null;
  }


  return (
    <div className="mx-auto max-w-7xl">

      <h1 className="text-3xl font-bold">
        Insights
      </h1>

      <p className="mt-2 text-gray-600">
        Each insight separates Fact, Interpretation, and Recommendation
        so observations stay distinct from meaning and next actions.
      </p>

      {error ? (

        <div className="mt-8 rounded-xl border bg-white p-6 text-sm text-red-600">
          {error}
        </div>

      ) : groups.length === 0 ? (

        <div className="mt-8 rounded-xl border bg-white p-6 text-sm text-gray-500">

          <p>
            No saved data products yet. Create a
            data product to generate insights.
          </p>

          <Link
            href="/create"
            className="mt-4 inline-block text-sm font-medium text-gray-900 underline underline-offset-4"
          >
            Create data product
          </Link>

        </div>

      ) : (

        <div className="mt-8 space-y-4">

          {groups.map((group) => {

            const activeProduct =
              resolveActiveProduct(
                group,
                selectedVersions[
                  group.definitionId
                ]
              );

            const priorityCounts =
              countInsightsByPriority(
                activeProduct.insights
              );

            return (

              <CollapsibleProductGroup
                key={group.definitionId}
                group={group}
                selectedVersionId={
                  selectedVersions[
                    group.definitionId
                  ]
                }
                onVersionChange={(
                  versionId
                ) =>
                  handleVersionChange(
                    group.definitionId,
                    versionId
                  )
                }
                priorityCounts={
                  priorityCounts
                }
                emptyLabel="No insights"
              >
                {(product) => (

                  <ProductInsightsTable
                    insights={
                      product.insights
                    }
                  />

                )}
              </CollapsibleProductGroup>

            );

          })}

        </div>

      )}

    </div>
  );

}
