import { DataProduct } from "@/types/report";

/**
 * Origin of a data product.
 *
 * user_created — built from a user's dataset
 *   (e.g. upload sales → Customer Intelligence)
 * native — defined and maintained by InsightPilot
 *   (e.g. Fantasy Football)
 */
export type ProductType =
  | "user_created"
  | "native";

export const PRODUCT_TYPE_USER_CREATED:
  ProductType = "user_created";

export const PRODUCT_TYPE_NATIVE:
  ProductType = "native";

/** Legacy persisted value before the native rename. */
const LEGACY_PRE_CANNED = "pre_canned";

export const PRODUCT_TYPE_LABELS: Record<
  ProductType,
  string
> = {
  user_created: "User-created",
  native: "Native",
};


export function isProductType(
  value: unknown
): value is ProductType {

  return (
    value === PRODUCT_TYPE_USER_CREATED
    || value === PRODUCT_TYPE_NATIVE
  );

}


/**
 * Resolve product_type from a persisted instance,
 * falling back to known native definition ids
 * for legacy rows that predate the field.
 */
export function resolveProductType(
  product: Pick<
    DataProduct,
    "product_type" | "definition_id" | "id"
  > & {
    product_type?: string | null;
  },
  nativeDefinitionIds: ReadonlySet<string> = (
    new Set()
  )
): ProductType {

  if (isProductType(product.product_type)) {
    return product.product_type;
  }

  if (product.product_type === LEGACY_PRE_CANNED) {
    return PRODUCT_TYPE_NATIVE;
  }

  const definitionId =
    product.definition_id
    || product.id
    || "";

  if (
    definitionId
    && (
      nativeDefinitionIds.has(definitionId)
      || [...nativeDefinitionIds].some(
        (id) =>
          definitionId === id
          || definitionId.startsWith(`${id}__`)
      )
    )
  ) {
    return PRODUCT_TYPE_NATIVE;
  }

  return PRODUCT_TYPE_USER_CREATED;

}


export function isNativeProduct(
  product: Pick<
    DataProduct,
    "product_type" | "definition_id" | "id"
  >,
  nativeDefinitionIds: ReadonlySet<string> = (
    new Set()
  )
): boolean {

  return (
    resolveProductType(
      product,
      nativeDefinitionIds
    ) === PRODUCT_TYPE_NATIVE
  );

}
