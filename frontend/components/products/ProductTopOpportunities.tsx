"use client";

import {
  useState,
} from "react";

import {
  AnalysisDashboard,
  DataProductInsight,
} from "@/types/report";

import {
  extractTopOpportunities,
  formatOpportunityValue,
  RankedProductOpportunity,
} from "@/lib/productOpportunities";

import ProductOpportunitiesModal from "@/components/products/ProductOpportunitiesModal";


interface Props {
  productName?: string;
  dashboards?: AnalysisDashboard[];
  insights?: DataProductInsight[];
  limit?: number;
  showViewAllLink?: boolean;
  embedded?: boolean;
}


export default function ProductTopOpportunities({
  productName = "This product",
  dashboards = [],
  insights = [],
  limit = 5,
  showViewAllLink = true,
  embedded = false,
}: Props) {

  const [
    modalOpen,
    setModalOpen,
  ] = useState(false);

  const opportunities =
    extractTopOpportunities(
      dashboards,
      insights,
      limit
    );

  const allOpportunities =
    extractTopOpportunities(
      dashboards,
      insights,
      100
    );


  return (
    <>
      <section className={`overflow-hidden rounded-2xl border border-gray-900 bg-gray-900 text-white shadow-lg ${embedded ? "" : "mt-12"}`}>

        <div className="border-b border-white/10 px-6 py-5">

          <div className="flex flex-wrap items-start justify-between gap-4">

            <div>

              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-gray-400">
                Top Opportunities
              </p>

              <h2 className="mt-2 text-2xl font-semibold">
                Highest-impact actions from this analysis
              </h2>

              <p className="mt-2 max-w-3xl text-sm leading-6 text-gray-300">
                The most important opportunities identified
                across the analyses powering this data product.
              </p>

            </div>


            {showViewAllLink &&
              allOpportunities.length > 0 && (

                <button
                  type="button"
                  onClick={() =>
                    setModalOpen(true)
                  }
                  className="rounded-lg border border-white/20 px-4 py-2 text-sm font-medium text-white hover:bg-white/10"
                >
                  View all opportunities
                </button>

              )}

          </div>

        </div>


        {opportunities.length === 0 ? (

          <div className="px-6 py-8 text-sm text-gray-300">
            No ranked opportunities were identified for
            this product yet. Run or refresh the analysis
            to surface actionable findings.
          </div>

        ) : (

          <div className="grid gap-px bg-white/10 md:grid-cols-2 xl:grid-cols-3">

            {opportunities.map(
              (
                opportunity,
                index
              ) => (

                <OpportunityCard
                  key={
                    opportunity.id
                  }
                  rank={index + 1}
                  opportunity={
                    opportunity
                  }
                />

              )
            )}

          </div>

        )}

      </section>


      {modalOpen && (

        <ProductOpportunitiesModal
          productName={productName}
          opportunities={allOpportunities}
          onClose={() =>
            setModalOpen(false)
          }
        />

      )}

    </>
  );

}


function OpportunityCard({
  rank,
  opportunity,
}: {
  rank: number;
  opportunity: RankedProductOpportunity;
}) {

  const value =
    formatOpportunityValue(
      opportunity.potential
    );


  return (
    <article className="flex h-full flex-col bg-gray-900 px-6 py-5">

      <div className="flex items-start justify-between gap-3">

        <div className="flex items-center gap-3">

          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-sm font-bold text-gray-900">
            {rank}
          </span>

          <span
            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${
              opportunity.priority === "high"
                ? "bg-green-400/20 text-green-200"
                : opportunity.priority === "medium"
                ? "bg-yellow-400/20 text-yellow-100"
                : "bg-white/10 text-gray-300"
            }`}
          >
            {opportunity.priority} priority
          </span>

        </div>


        {value && (

          <p className="text-right text-lg font-semibold text-white">
            {value}
          </p>

        )}

      </div>


      <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-gray-400">
        {opportunity.type}
      </p>

      <h3 className="mt-2 text-lg font-semibold leading-7 text-white">
        {opportunity.label}
      </h3>

      {opportunity.detail && (

        <p className="mt-2 text-sm leading-6 text-gray-300">
          {opportunity.detail}
        </p>

      )}

      <p className="mt-auto pt-4 text-xs text-gray-400">
        From {opportunity.source}
      </p>

    </article>

  );

}
