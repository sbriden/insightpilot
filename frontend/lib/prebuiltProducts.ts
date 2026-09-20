import {
  PRODUCT_TYPE_LABELS,
  PRODUCT_TYPE_NATIVE,
  ProductType,
} from "@/lib/productTypes";

/**
 * Presentation catalog for InsightPilot-maintained
 * (native) products. product_type is the model
 * field; this list only supplies UI routing / labels
 * for products that have a branded entry page.
 */
export interface NativeProduct {
  id: string;
  product_type: typeof PRODUCT_TYPE_NATIVE;
  name: string;
  description: string;
  badge: string;
  href: string;
  sourceLabel: string;
  domainLabel: string;
}

/** @deprecated Prefer NativeProduct */
export type PrebuiltProduct = NativeProduct;

/** @deprecated Prefer product.id with product_type */
export type PrebuiltProductKind = "fantasy_football";


export const NATIVE_PRODUCTS: NativeProduct[] = [
  {
    id: "fantasy_football",
    product_type: PRODUCT_TYPE_NATIVE,
    name: "Fantasy Football",
    description:
      "InsightPilot-native fantasy football analyses over nflverse-backed data.",
    badge: PRODUCT_TYPE_LABELS.native,
    href: "/products/fantasy-football",
    sourceLabel: "nflverse",
    domainLabel: "Player Overview",
  },
];

/** @deprecated Prefer NATIVE_PRODUCTS */
export const PREBUILT_PRODUCTS = NATIVE_PRODUCTS;

export const NATIVE_DEFINITION_IDS: ReadonlySet<string> =
  new Set(
    NATIVE_PRODUCTS.map(
      (product) => product.id
    )
  );


export function getNativeProduct(
  id: string
): NativeProduct | undefined {

  return NATIVE_PRODUCTS.find(
    (product) => product.id === id
  );

}

/** @deprecated Prefer getNativeProduct */
export function getPrebuiltProduct(
  id: string
): NativeProduct | undefined {

  return getNativeProduct(id);

}


export function productTypeBadge(
  productType: ProductType
): string {

  return PRODUCT_TYPE_LABELS[productType];

}
