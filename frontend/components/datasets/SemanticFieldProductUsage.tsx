"use client";

import {
  DataProductRequirement,
  SemanticField,
} from "@/types/dataset";


export type ProductFieldUsage =
  | "required"
  | "optional"
  | "unused";


const USAGE_DOT: Record<
  ProductFieldUsage,
  string
> = {
  required: "bg-red-500",
  optional: "bg-amber-400",
  unused: "bg-gray-200",
};


const USAGE_LABEL: Record<
  ProductFieldUsage,
  string
> = {
  required: "Required",
  optional: "Optional",
  unused: "Not used",
};


export function getProductFieldUsage(
  semanticField: SemanticField,
  productId: string
): ProductFieldUsage {

  if (
    semanticField.requiredBy.includes(
      productId
    )
  ) {
    return "required";
  }

  if (
    semanticField.optionalFor.includes(
      productId
    )
  ) {
    return "optional";
  }

  return "unused";

}


interface ProductUsageProps {
  semanticField: SemanticField;

  products: DataProductRequirement[];
}


export function SemanticFieldProductUsage({
  semanticField,
  products,
}: ProductUsageProps) {

  if (
    products.length === 0
  ) {
    return (
      <p className="text-xs text-gray-400">
        No products
      </p>
    );
  }


  return (
    <ul className="space-y-1.5">

      {products.map(
        product => {

          const usage =
            getProductFieldUsage(
              semanticField,
              product.id
            );


          return (
            <li
              key={product.id}
              className="flex items-center gap-2"
              title={`${product.name}: ${USAGE_LABEL[usage]}`}
            >

              <span
                className={`h-2 w-2 shrink-0 rounded-full ${USAGE_DOT[usage]}`}
                aria-hidden
              />

              <span className="min-w-0 truncate text-xs text-gray-700">
                {product.name}
              </span>

            </li>
          );

        }
      )}

    </ul>
  );

}


export function SemanticFieldProductUsageLegend() {

  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">

      <span className="inline-flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-red-500" />
        Required
      </span>

      <span className="inline-flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-amber-400" />
        Optional
      </span>

      <span className="inline-flex items-center gap-1.5">
        <span className="h-2 w-2 rounded-full bg-gray-200" />
        Not used
      </span>

    </div>
  );

}
