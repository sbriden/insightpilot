"use client";

import Link from "next/link";
import { useMemo } from "react";

import ProductWorkspace from "@/components/products/ProductWorkspace";
import {
  getNativeProduct,
} from "@/lib/prebuiltProducts";
import {
  SPORTS_BETTING_ANALYSES,
} from "@/lib/sportsBettingAnalyses";
import {
  PRODUCT_TYPE_NATIVE,
} from "@/lib/productTypes";
import {
  AnalysisDashboard,
  DataProductAnalysis,
} from "@/types/report";

const native = getNativeProduct("sports_betting");

const DEFAULT_ANALYSES: DataProductAnalysis[] =
  SPORTS_BETTING_ANALYSES.map((analysis) => ({
    id: analysis.id,
    title: analysis.title,
    description: analysis.description,
  }));

function placeholderDashboard(
  analysis: DataProductAnalysis
): AnalysisDashboard {
  return {
    id: analysis.id,
    title: analysis.title,
    summary: analysis.description ?? "",
    metrics: [],
    visualizations: [],
    insights: [],
    actions: [],
    datasets: {},
  };
}

export default function SportsBettingPage() {
  const workspaceProduct = useMemo(
    () => ({
      name: native?.name ?? "Sports Betting",
      description:
        native?.description
        ?? "Analyze NFL markets and InsightPilot model differences.",
      business_purpose:
        "Sports betting market analysis over InsightPilot projections.",
      product_type: PRODUCT_TYPE_NATIVE,
      analyses: DEFAULT_ANALYSES,
      metrics: [],
      insights: [],
      promoted_insights: [],
      insight_initial_results: undefined,
      dashboards: DEFAULT_ANALYSES.map(placeholderDashboard),
      change_summary: null,
      executive_summary: null,
      executive_brief: null,
    }),
    []
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link
            href="/"
            className="text-sm text-gray-500 hover:text-gray-800"
          >
            ← Products
          </Link>
          <div className="mt-3 flex items-center gap-3">
            <h1 className="text-3xl font-semibold tracking-tight text-gray-900">
              {native?.name ?? "Sports Betting"}
            </h1>
            <span className="rounded-full bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-700 ring-1 ring-teal-200">
              {native?.badge ?? "Native"}
            </span>
          </div>
          <p className="mt-2 max-w-3xl text-sm text-gray-600">
            Analyze today&apos;s games, compare market prices with
            InsightPilot projections, and evaluate betting
            opportunities across major NFL markets.
          </p>
        </div>
      </div>

      <div className="mt-8">
        <ProductWorkspace
          product={workspaceProduct}
          dashboards={workspaceProduct.dashboards ?? []}
          showViewAllLink={false}
          initialTab="analyses"
        />
      </div>
    </div>
  );
}
