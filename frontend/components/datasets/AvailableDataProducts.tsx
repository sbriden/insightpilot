"use client";

import { DataProduct } from "@/types/report";


interface AvailableDataProductsProps {
  products: DataProduct[];
}


export default function AvailableDataProducts({
  products,
}: AvailableDataProductsProps) {

  if (products.length === 0) {

    return (
      <div className="mt-8 rounded-xl border p-6">

        <h3 className="font-semibold">
          No data products available yet
        </h3>

        <p className="mt-2 text-sm text-gray-500">
          InsightPilot does not currently
          have data products configured for
          this dataset type.
        </p>

      </div>
    );

  }


  return (
    <section className="mt-10">

      <div className="mb-5">

        <h2 className="text-xl font-semibold">
          Available Data Products
        </h2>

        <p className="mt-2 text-sm text-gray-600">
          These analytical products can be
          created from this type of data.
        </p>

      </div>


      <div className="grid gap-4 md:grid-cols-2">

        {products.map(
          (product) => (

            <div
              key={product.id}
              className="rounded-xl border bg-white p-5"
            >

              <h3 className="font-semibold">
                {product.name}
              </h3>

              <p className="mt-2 text-sm leading-6 text-gray-600">
                {product.description}
              </p>


              <div className="mt-4">

                <span className="rounded-full bg-gray-100 px-3 py-1 text-xs">
                  Data product
                </span>

              </div>

            </div>

          )
        )}

      </div>

    </section>
  );
}