"use client";



import Link from "next/link";



import ProductWorkspace from "@/components/products/ProductWorkspace";

import ProductHealthBadge from "@/components/products/ProductHealthBadge";



import {

  DataProduct,

} from "@/types/report";





interface ProductAnalysisResultProps {

  product: DataProduct;

}





export default function ProductAnalysisResult({

  product,

}: ProductAnalysisResultProps) {



  const dashboards =

    product.dashboards ?? [];



  const completedIds = new Set(

    (

      product.metadata

        ?.completed_analysis_ids as

          string[] | undefined

    ) ??

    dashboards.map(

      (dashboard) => dashboard.id

    )

  );



  return (

    <div className="space-y-8">



      <div className="rounded-xl border bg-white p-6">



        <div className="flex flex-wrap items-start justify-between gap-4">



          <div className="max-w-2xl">



            <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">

              Data Product

            </p>



            <h2 className="mt-1 text-2xl font-semibold">

              {product.name}

            </h2>



            <p className="mt-2 text-sm leading-6 text-gray-600">

              {product.description}

            </p>



            <p className="mt-3 text-sm text-gray-500">

              Saved as version {product.version}.

              You can reopen this result later without

              uploading again.

            </p>



            <Link

              href={`/products/${encodeURIComponent(

                product.definition_id ??

                product.id

              )}`}

              className="mt-3 inline-block text-sm font-medium text-gray-900 underline underline-offset-4"

            >

              Open saved product

            </Link>



          </div>



          <div className="text-right">

            <div className="flex justify-end">
              <ProductHealthBadge
                product={product}
                showPopover
                popoverSize="compact"
              />
            </div>

            <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-gray-400">

              Version

            </p>



            <p className="mt-1 text-2xl font-bold">

              v{product.version}

            </p>



            <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-gray-400">

              Field coverage

            </p>



            <p className="mt-1 text-2xl font-bold">

              {product.coverage}%

            </p>



            <p className="text-xs capitalize text-gray-500">

              {product.status}

            </p>



          </div>



        </div>



        {product.analyses.length > 0 && (



          <div className="mt-6 flex flex-wrap gap-2">



            {product.analyses.map(

              (analysis) => {



                const complete =

                  completedIds.has(

                    analysis.id

                  );



                return (

                  <span

                    key={analysis.id}

                    className={`rounded-full px-3 py-1 text-xs ${

                      complete

                        ? "bg-gray-900 text-white"

                        : "bg-gray-100 text-gray-500"

                    }`}

                  >

                    {analysis.title}

                    {!complete && " · unavailable"}

                  </span>

                );



              }

            )}



          </div>



        )}



      </div>



      <ProductWorkspace

        product={product}

        dashboards={dashboards}

        showViewAllLink={false}

      />



    </div>

  );



}


