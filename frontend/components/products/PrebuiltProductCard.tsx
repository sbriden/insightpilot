"use client";

import Link from "next/link";

import {
  NativeProduct,
} from "@/lib/prebuiltProducts";


interface PrebuiltProductCardProps {
  product: NativeProduct;
}


export default function PrebuiltProductCard({
  product,
}: PrebuiltProductCardProps) {

  return (

    <div className="relative flex flex-col overflow-hidden rounded-xl border border-teal-200 bg-gradient-to-br from-teal-50/80 via-white to-white p-6 shadow-[inset_4px_0_0_0_#0f766e]">

      <div className="flex items-start justify-between gap-4">

        <div className="min-w-0">

          <div className="flex flex-wrap items-center gap-2">

            <h2 className="font-semibold text-gray-900">
              {product.name}
            </h2>

            <span className="rounded-md bg-teal-700 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-white">
              {product.badge}
            </span>

          </div>

          <p className="mt-2 text-sm leading-6 text-gray-600">
            {product.description}
          </p>

        </div>

      </div>


      <div className="mt-4 flex flex-wrap gap-2">

        <span className="rounded-full bg-teal-100 px-3 py-1 text-xs text-teal-900">
          {product.sourceLabel}
        </span>

        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-700">
          {product.domainLabel}
        </span>

        <span className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-700">
          Ready to explore
        </span>

      </div>


      <div className="mt-6 border-t border-teal-100 pt-5">

        <Link
          href={product.href}
          className="text-sm font-medium text-teal-900 hover:underline"
        >
          Open product →
        </Link>

      </div>

    </div>

  );

}
