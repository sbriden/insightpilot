"use client";

import { useState } from "react";

import {
  DatasetAnalysis,
} from "@/types/report";

import ProductAnalysisResult from "@/components/report/ProductAnalysisResult";
import SemanticUnderstandingDebug from "@/components/report/SemanticUnderstandingDebug";


interface AnalysisResultsProps {
  result: DatasetAnalysis;
}


export default function AnalysisResults({
  result,
}: AnalysisResultsProps) {

  const products =
    result.data_products ?? [];

  const [
    selectedProductId,
    setSelectedProductId,
  ] =
    useState(
      products[0]?.id ?? ""
    );

  const selectedProduct =
    products.find(
      (product) =>
        product.id === selectedProductId
    ) ?? products[0];

  const summary =
    result.profile?.summary;

  return (
    <div className="mx-auto max-w-7xl space-y-8">

      <div>

        <h1 className="text-3xl font-bold">
          Analysis results
        </h1>

        <p className="mt-2 text-gray-600">
          Each selected data product is saved so you
          can reopen it later from Data Products
          without uploading again.
        </p>

      </div>

      <SemanticUnderstandingDebug
        understanding={
          result.semantic_understanding
        }
      />

      {summary && (

        <section>

          <SectionTitle
            title="Dataset health"
            description="Shared quality and scale of the uploaded file. This is not product-specific."
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">

            <MetricCard
              title="Data Quality"
              value={`${summary.data_quality_score}%`}
            />

            <MetricCard
              title="Rows"
              value={summary.rows.toLocaleString()}
            />

            <MetricCard
              title="Columns"
              value={summary.columns.toLocaleString()}
            />

          </div>

        </section>

      )}

      {products.length === 0 ? (

        <div className="rounded-xl border bg-white p-6 text-sm text-gray-500">
          No data products were generated for this analysis.
        </div>

      ) : (

        <section className="space-y-6">

          <SectionTitle
            title="Selected data products"
            description="Open one product at a time to see only that product’s metrics, insights, and analyses."
          />

          {products.length > 1 && (

            <div className="flex flex-wrap gap-2">

              {products.map(
                (product) => {

                  const active =
                    product.id ===
                    selectedProduct?.id;

                  return (
                    <button
                      key={product.id}
                      type="button"
                      onClick={() =>
                        setSelectedProductId(
                          product.id
                        )
                      }
                      className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                        active
                          ? "bg-gray-900 text-white"
                          : "border bg-white text-gray-600 hover:border-gray-400"
                      }`}
                    >
                      {product.name}
                    </button>
                  );

                }
              )}

            </div>

          )}

          {selectedProduct && (

            <ProductAnalysisResult
              product={selectedProduct}
            />

          )}

        </section>

      )}

    </div>
  );

}


function SectionTitle({
  title,
  description,
}: {
  title: string;
  description: string;
}) {

  return (
    <div className="mb-4">

      <h2 className="text-xl font-semibold">
        {title}
      </h2>

      <p className="mt-1 text-sm text-gray-500">
        {description}
      </p>

    </div>
  );

}


function MetricCard({
  title,
  value,
}: {
  title: string;
  value: string;
}) {

  return (
    <div className="rounded-xl border bg-white p-5">

      <p className="text-sm text-gray-500">
        {title}
      </p>

      <p className="mt-2 text-2xl font-bold">
        {value}
      </p>

    </div>
  );

}
