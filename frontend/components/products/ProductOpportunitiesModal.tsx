"use client";

import ProductOpportunitiesTable from "@/components/products/ProductOpportunitiesTable";

import {
  RankedProductOpportunity,
} from "@/lib/productOpportunities";


interface Props {
  productName: string;
  opportunities: RankedProductOpportunity[];
  onClose: () => void;
}


export default function ProductOpportunitiesModal({
  productName,
  opportunities,
  onClose,
}: Props) {

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >

      <div
        className="flex max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl"
        onClick={(event) =>
          event.stopPropagation()
        }
        role="dialog"
        aria-modal="true"
        aria-labelledby="product-opportunities-title"
      >

        <div className="border-b px-6 py-5">

          <div className="flex items-start justify-between gap-4">

            <div>

              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                Product opportunities
              </p>

              <h2
                id="product-opportunities-title"
                className="mt-1 text-xl font-semibold text-gray-950"
              >
                {productName}
              </h2>

              <p className="mt-2 text-sm text-gray-600">
                {opportunities.length} opportunit
                {opportunities.length === 1 ? "y" : "ies"} identified across this product&apos;s analyses.
              </p>

            </div>


            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
            >
              Close
            </button>

          </div>

        </div>


        <div className="overflow-y-auto">

          <ProductOpportunitiesTable
            opportunities={opportunities}
          />

        </div>

      </div>

    </div>

  );

}
