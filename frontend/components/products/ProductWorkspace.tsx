"use client";

import {
  useMemo,
  useState,
  type ReactNode,
} from "react";

import ProductAnalysisTabs from "@/components/products/ProductAnalysisTabs";
import ProductExecutiveSummary from "@/components/products/ProductExecutiveSummary";
import ProductInsightExecutiveBrief from "@/components/products/ProductInsightExecutiveBrief";
import PromotedInsightsPanel from "@/components/products/PromotedInsightsPanel";
import ProductKPIs from "@/components/products/ProductKPIs";
import ProductTopOpportunities from "@/components/products/ProductTopOpportunities";
import RecommendedInsightCards from "@/components/products/RecommendedInsightCards";

import {
  normalizeInsights,
  normalizePriority,
} from "@/lib/insightModel";

import {
  resolveRecommendedInsights,
} from "@/lib/productExecutiveSummary";

import {
  AnalysisDashboard,
  DataProduct,
  DataProductAnalysis,
} from "@/types/report";


type BuiltinWorkspaceTab =
  | "overview"
  | "insights"
  | "analyses";

type WorkspaceTab =
  | BuiltinWorkspaceTab
  | string;

export interface ProductWorkspaceExtraTab {
  id: string;
  label: string;
  count?: number;
  content: ReactNode;
}


interface Props {
  product: Pick<
    DataProduct,
    | "name"
    | "business_purpose"
    | "description"
    | "analyses"
    | "metrics"
    | "insights"
    | "promoted_insights"
    | "insight_initial_results"
    | "dashboards"
    | "change_summary"
    | "executive_summary"
    | "executive_brief"
  >;
  dashboards?: AnalysisDashboard[];
  visibleDashboards?: AnalysisDashboard[];
  showViewAllLink?: boolean;
  initialTab?: WorkspaceTab;
  extraTabs?: ProductWorkspaceExtraTab[];
  onTabChange?: (tabId: WorkspaceTab) => void;
}


export default function ProductWorkspace({
  product,
  dashboards = product.dashboards ?? [],
  visibleDashboards,
  showViewAllLink = true,
  initialTab = "overview",
  extraTabs = [],
  onTabChange,
}: Props) {

  const [
    activeTab,
    setActiveTab,
  ] = useState<WorkspaceTab>(
    initialTab
  );

  const analysisDashboards =
    visibleDashboards ??
    dashboards;

  const insights =
    product.insights ?? [];

  const promotedInsights =
    product.promoted_insights ?? [];

  const initialResults =
    product.insight_initial_results;

  const recommendedInsights =
    resolveRecommendedInsights(product);

  const executiveBrief =
    product.executive_brief ??
    initialResults?.executive_brief ??
    null;

  const normalizedInsights =
    normalizeInsights(insights);

  const highPriorityCount =
    normalizedInsights.filter(
      insight =>
        normalizePriority(
          insight.priority
        ) === "high"
    ).length;

  const insightsTabCount =
    initialResults?.recommended_count ??
    recommendedInsights.length;

  const activeExtraTab =
    extraTabs.find(
      (tab) => tab.id === activeTab
    );

  const tabs =
    useMemo(
      () => [

        {
          id: "overview" as const,
          label: "Overview",
        },

        {
          id: "insights" as const,
          label: "Insights",
          count: insightsTabCount,
          emphasis:
            highPriorityCount > 0 ||
            recommendedInsights.length > 0,
        },

        {
          id: "analyses" as const,
          label: "Analyses",
          count:
            product.analyses?.length ??
            analysisDashboards.length,
        },

        ...extraTabs.map(
          (tab) => ({
            id: tab.id,
            label: tab.label,
            count: tab.count,
          })
        ),

      ],
      [
        insightsTabCount,
        recommendedInsights.length,
        highPriorityCount,
        product.analyses,
        analysisDashboards.length,
        extraTabs,
      ]
    );


  return (
    <div>

      <nav
        className="sticky top-0 z-20 -mx-1 rounded-2xl border border-gray-200 bg-white/95 px-2 py-2 shadow-sm backdrop-blur"
        aria-label="Product sections"
      >

        <div className="flex flex-wrap gap-2">

          {tabs.map(
            (tab) => {

              const selected =
                activeTab === tab.id;

              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => {
                    setActiveTab(tab.id);
                    onTabChange?.(tab.id);
                  }}
                  className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-colors ${
                    selected
                      ? "bg-gray-900 text-white"
                      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                  }`}
                >

                  {tab.label}

                  {tab.count !== undefined &&
                    tab.count > 0 && (

                      <span
                        className={`rounded-full px-2 py-0.5 text-xs ${
                          selected
                            ? "bg-white/15 text-white"
                            : tab.emphasis
                              ? "bg-red-100 text-red-700"
                              : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {tab.count}
                      </span>

                    )}

                </button>
              );

            }
          )}

        </div>

      </nav>


      <div className="mt-6">

        {activeTab === "overview" && (

          <div className="space-y-6">

            <ProductInsightExecutiveBrief
              brief={executiveBrief}
              embedded
            />

            <ProductExecutiveSummary
              product={product}
              embedded
            />

            <ProductKPIs
              metrics={product.metrics}
              productName={product.name}
              embedded
            />

            <ProductTopOpportunities
              productName={product.name}
              dashboards={dashboards}
              insights={insights}
              showViewAllLink={
                showViewAllLink
              }
              embedded
            />

          </div>

        )}


        {activeTab === "insights" && (

          <section className="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">

            <div className="border-b border-gray-100 bg-gray-50 px-6 py-5">

              <h2 className="text-lg font-semibold text-gray-950">
                Insights
              </h2>

              <p className="mt-1 text-sm text-gray-600">
                {initialResults?.headline ??
                  "Each insight separates Fact, Interpretation, and Recommendation."}
              </p>

              {initialResults ? (
                <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                  <span>
                    Total discovered:{" "}
                    {initialResults.total_discovered}
                  </span>
                  <span>
                    Tier 1: {initialResults.tier_counts.tier_1}
                  </span>
                  <span>
                    Tier 2: {initialResults.tier_counts.tier_2}
                  </span>
                  <span>
                    Tier 3: {initialResults.tier_counts.tier_3}
                  </span>
                  <span>
                    Recommended:{" "}
                    {initialResults.recommended_count}
                  </span>
                </div>
              ) : null}

            </div>

            <div className="p-4 space-y-4">

              {recommendedInsights.length > 0 ? (
                <PromotedInsightsPanel
                  insights={recommendedInsights}
                  showHeader={false}
                />
              ) : (
                <RecommendedInsightCards
                  insights={recommendedInsights}
                />
              )}

              {promotedInsights.length >
              recommendedInsights.length ? (
                <details className="rounded-xl border border-gray-200 bg-white px-4 py-3">
                  <summary className="cursor-pointer text-sm font-medium text-gray-800">
                    View all {promotedInsights.length} insights
                  </summary>
                  <div className="mt-3">
                    <PromotedInsightsPanel
                      insights={promotedInsights}
                      showHeader={false}
                    />
                  </div>
                </details>
              ) : null}

            </div>

          </section>

        )}


        {activeTab === "analyses" && (

          <ProductAnalysisTabs
            analyses={
              product.analyses as
                | Array<
                    string | DataProductAnalysis
                  >
                | undefined
            }
            dashboards={
              analysisDashboards
            }
          />

        )}

        {activeExtraTab
          ? activeExtraTab.content
          : null}

      </div>

    </div>

  );

}
