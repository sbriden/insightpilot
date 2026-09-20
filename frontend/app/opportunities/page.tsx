"use client";

import { useState } from "react";
import Link from "next/link";

import CollapsibleProductGroup from "@/components/products/CollapsibleProductGroup";
import ProductOpportunitiesTable from "@/components/products/ProductOpportunitiesTable";

import { useSavedProducts } from "@/hooks/useSavedProducts";

import {
  extractTopOpportunities,
} from "@/lib/productOpportunities";

import {
  countOpportunitiesByPriority,
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


function getProductOpportunities(
  product: DataProduct
) {

  return extractTopOpportunities(
    product.dashboards ?? [],
    product.insights ?? [],
    100
  );

}


export default function OpportunitiesPage() {

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
        Opportunities
      </h1>

      <p className="mt-2 text-gray-600">
        Recommended actions grouped by data product.
        Expand a product to review opportunities in detail.
      </p>

      {error ? (

        <div className="mt-8 rounded-xl border bg-white p-6 text-sm text-red-600">
          {error}
        </div>

      ) : groups.length === 0 ? (

        <div className="mt-8 rounded-xl border bg-white p-6 text-sm text-gray-500">

          <p>
            No saved data products yet. Create a
            data product to identify opportunities.
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

            const opportunities =
              getProductOpportunities(
                activeProduct
              );

            const priorityCounts =
              countOpportunitiesByPriority(
                opportunities
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
                emptyLabel="No opportunities"
              >
                {(product) => (

                  <ProductOpportunitiesTable
                    opportunities={
                      getProductOpportunities(
                        product
                      )
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
