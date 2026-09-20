import { DataProduct } from "@/types/report";

import {
  NATIVE_DEFINITION_IDS,
} from "@/lib/prebuiltProducts";

import {
  resolveProductType,
} from "@/lib/productTypes";


export interface ParsedProductInstanceId {
  definitionId: string;
  datasetIdentity: string | null;
  version: number | null;
  isInstanceId: boolean;
}


export interface ProductGroup {
  definitionId: string;
  name: string;
  description: string;
  latest: DataProduct;
  versions: DataProduct[];
  versionCount: number;
}


const INSTANCE_ID_PATTERN =
  /^(.+)__([a-f0-9]{32})__v(\d+)$/i;


export function parseProductInstanceId(
  value: string
): ParsedProductInstanceId {

  const match =
    value.match(
      INSTANCE_ID_PATTERN
    );

  if (!match) {

    return {
      definitionId: value,
      datasetIdentity: null,
      version: null,
      isInstanceId: false,
    };

  }

  return {
    definitionId: match[1],
    datasetIdentity: match[2],
    version: Number(match[3]),
    isInstanceId: true,
  };

}


export function resolveDefinitionId(
  product: DataProduct
): string {

  if (product.definition_id) {
    return product.definition_id;
  }

  const parsed =
    parseProductInstanceId(
      product.id
    );

  return parsed.definitionId;

}


export function groupProductsByDefinition(
  products: DataProduct[]
): ProductGroup[] {

  const groups =
    new Map<
      string,
      DataProduct[]
    >();


  for (const product of products) {

    const key =
      resolveDefinitionId(
        product
      );

    const existing =
      groups.get(key) ?? [];

    existing.push(product);

    groups.set(
      key,
      existing
    );

  }


  return Array.from(
    groups.entries()
  )
    .map(
      ([
        definitionId,
        versions,
      ]) => {

        const sorted =
          [...versions].sort(
            (left, right) => {

              const versionDelta =
                (
                  Number(
                    right.version ?? 0
                  )
                  -
                  Number(
                    left.version ?? 0
                  )
                );

              if (
                versionDelta !== 0
              ) {
                return versionDelta;
              }

              const rightUpdated =
                Date.parse(
                  right.updated_at ??
                  right.created_at ??
                  ""
                ) || 0;

              const leftUpdated =
                Date.parse(
                  left.updated_at ??
                  left.created_at ??
                  ""
                ) || 0;

              return (
                rightUpdated -
                leftUpdated
              );

            }
          );

        const latest =
          sorted[0];

        return {
          definitionId,

          name:
            latest.name,

          description:
            latest.description,

          latest,

          versions: sorted,

          versionCount:
            sorted.length,

        };

      }
    )
    .sort(
      (left, right) => {

        const rightUpdated =
          Date.parse(
            right.latest.updated_at ??
            right.latest.created_at ??
            ""
          ) || 0;

        const leftUpdated =
          Date.parse(
            left.latest.updated_at ??
            left.latest.created_at ??
            ""
          ) || 0;

        return (
          rightUpdated -
          leftUpdated
        );

      }
    );

}


export function normalizeProduct(
  product: any
): DataProduct {

  const analyses =
    Array.isArray(product?.analyses)
      ? product.analyses
      : [];


  const metrics =
    Array.isArray(product?.metrics)
      ? product.metrics
      : [];


  const insights =
    Array.isArray(product?.insights)
      ? product.insights
      : [];


  const dashboards =
    Array.isArray(product?.dashboards)
      ? product.dashboards
      : [];


  return {

    ...product,

    id:
      String(
        product?.id ?? ""
      ),

    name:
      String(
        product?.name ??
        "Unnamed Data Product"
      ),

    description:
      String(
        product?.description ??
        ""
      ),

    product_type: resolveProductType(
      {
        product_type:
          product?.product_type,
        definition_id:
          product?.definition_id
            ? String(
                product.definition_id
              )
            : undefined,
        id: String(product?.id ?? ""),
      },
      NATIVE_DEFINITION_IDS
    ),

    status:
      String(
        product?.status ??
        "unknown"
      ),

    coverage:
      Number(
        product?.coverage ?? 0
      ),

    version:
      Number(
        product?.version ?? 1
      ),

    analyses,

    metrics,

    insights,

    dashboards,

    change_summary:
      product?.change_summary ?? null,

    executive_summary:
      product?.executive_summary ?? null,

    health:
      product?.health ?? null,

    definition_id:
      product?.definition_id
        ? String(
            product.definition_id
          )
        : undefined,

    dataset_identity:
      product?.dataset_identity
        ? String(
            product.dataset_identity
          )
        : undefined,

    previous_product_id:
      product?.previous_product_id ??
      null,

    metadata:
      product?.metadata ?? {},

    created_at:
      product?.created_at,

    updated_at:
      product?.updated_at,

  } as DataProduct;

}


export interface DatasetGroup {
  uploadBatchId: string;
  classificationType: string;
  dataQualityScore: number;
  rows: number;
  columns: number;
  missingPercentage: number | null;
  duplicateCount: number | null;
  updatedAt: string;
  supportedProducts: Array<{
    definitionId: string;
    name: string;
    status: string;
    coverage: number;
    version: number;
    productId: string;
  }>;
}


function resolveUploadBatchId(
  product: DataProduct
): string {

  const batchId =
    product.metadata?.upload_batch_id;

  if (
    typeof batchId === "string" &&
    batchId.length > 0
  ) {
    return batchId;
  }

  if (product.created_at) {
    return product.created_at.slice(0, 19);
  }

  return product.id;

}


export function groupProductsByUploadBatch(
  products: DataProduct[]
): DatasetGroup[] {

  const batches =
    new Map<
      string,
      DataProduct[]
    >();


  for (const product of products) {

    const key =
      resolveUploadBatchId(
        product
      );

    const existing =
      batches.get(key) ?? [];

    existing.push(product);

    batches.set(
      key,
      existing
    );

  }


  return Array.from(
    batches.entries()
  )
    .map(
      ([
        uploadBatchId,
        batchProducts,
      ]) => {

        const sorted =
          [...batchProducts].sort(
            (left, right) => {

              const rightUpdated =
                Date.parse(
                  right.updated_at ??
                  right.created_at ??
                  ""
                ) || 0;

              const leftUpdated =
                Date.parse(
                  left.updated_at ??
                  left.created_at ??
                  ""
                ) || 0;

              return (
                rightUpdated -
                leftUpdated
              );

            }
          );

        const reference =
          sorted[0];

        const metadata =
          reference.metadata ?? {};

        const productGroups =
          groupProductsByDefinition(
            batchProducts
          );

        return {
          uploadBatchId,

          classificationType:
            String(
              metadata.classification_type ??
              "Unknown dataset"
            ),

          dataQualityScore:
            Number(
              metadata.data_quality_score ??
              0
            ),

          rows:
            Number(
              metadata.dataset_rows ??
              0
            ),

          columns:
            Number(
              metadata.dataset_columns ??
              0
            ),

          missingPercentage:
            metadata.missing_percentage ==
            null
              ? null
              : Number(
                  metadata.missing_percentage
                ),

          duplicateCount:
            metadata.duplicate_count ==
            null
              ? null
              : Number(
                  metadata.duplicate_count
                ),

          updatedAt:
            reference.updated_at ??
            reference.created_at ??
            "",

          supportedProducts:
            productGroups.map(
              (group) => ({
                definitionId:
                  group.definitionId,

                name:
                  group.name,

                status:
                  group.latest.status,

                coverage:
                  group.latest.coverage,

                version:
                  group.latest.version,

                productId:
                  group.latest.id,
              })
            ),

        };

      }
    )
    .sort(
      (left, right) => {

        const rightUpdated =
          Date.parse(
            right.updatedAt
          ) || 0;

        const leftUpdated =
          Date.parse(
            left.updatedAt
          ) || 0;

        return (
          rightUpdated -
          leftUpdated
        );

      }
    );

}


export function getDefinitionIdsForUploadBatch(
  products: DataProduct[],
  referenceProduct: DataProduct
): string[] {

  const batchId =
    resolveUploadBatchId(
      referenceProduct
    );

  const definitionIds =
    new Set<string>();

  for (const product of products) {

    if (
      resolveUploadBatchId(
        product
      ) !== batchId
    ) {
      continue;
    }

    definitionIds.add(
      resolveDefinitionId(
        product
      )
    );

  }

  if (
    definitionIds.size === 0
  ) {
    definitionIds.add(
      resolveDefinitionId(
        referenceProduct
      )
    );
  }

  return Array.from(
    definitionIds
  );

}


export function getSelectedProductForGroup(
  group: ProductGroup,
  selectedVersionId?: string
): DataProduct {

  if (!selectedVersionId) {
    return group.latest;
  }

  return (
    group.versions.find(
      version =>
        version.id ===
        selectedVersionId
    ) ?? group.latest
  );

}
