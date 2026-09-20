import {
  DataProductRequirement,
  SemanticField,
} from "@/types/dataset";

import {
  resolveSemanticFieldMetadata,
} from "@/lib/semanticFieldCatalog";


/*
 * ---------------------------------------------------------------------------
 * Build shared semantic fields
 * ---------------------------------------------------------------------------
 *
 * Creates the union of all required and optional fields across the products
 * associated with a dataset type.
 *
 * Example:
 *
 * Customer Intelligence:
 *
 *   required:
 *     customer_id
 *     revenue
 *     product_id
 *     transaction_date
 *
 *   optional:
 *     customer_name
 *     customer_segment
 *     cost
 *
 *
 * Product Performance:
 *
 *   required:
 *     product_id
 *     revenue
 *     transaction_date
 *
 *   optional:
 *     product_name
 *     product_category
 *     quantity
 *     cost
 *
 *
 * The resulting semantic field list contains each field only once.
 */

export function buildSemanticFields(
  products: DataProductRequirement[]
): SemanticField[] {

  if (!Array.isArray(products)) {
    return [];
  }


  /*
   * Use a Map so each semantic field only appears once.
   *
   * The key is the normalized field name.
   */

  const fields =
    new Map<
      string,
      SemanticField
    >();


  /*
   * Process each product.
   */

  for (const product of products) {

    if (!product) {
      continue;
    }


    /*
     * --------------------------------------------------
     * Required fields
     * --------------------------------------------------
     */

    const requiredFields =
      Array.isArray(
        product.required_fields
      )
        ? product.required_fields
        : [];


    for (
      const field of requiredFields
    ) {

      addField(
        fields,
        field,
        product,
        true
      );

    }


    /*
     * --------------------------------------------------
     * Optional fields
     * --------------------------------------------------
     */

    const optionalFields =
      Array.isArray(
        product.optional_fields
      )
        ? product.optional_fields
        : [];


    for (
      const field of optionalFields
    ) {

      addField(
        fields,
        field,
        product,
        false
      );

    }

  }


  /*
   * Return the semantic fields as an array.
   */

  return Array.from(
    fields.values()
  );

}


/*
 * ---------------------------------------------------------------------------
 * Add a field to the semantic field map
 * ---------------------------------------------------------------------------
 */

function applyFieldMetadata(
  field: string,
  fallbackDefinition?: string
): Pick<
  SemanticField,
  | "definition"
  | "keyRelationships"
  | "typicalBusinessQuestions"
> {

  const metadata =
    resolveSemanticFieldMetadata(
      field,
      fallbackDefinition
    );


  return {
    definition:
      metadata.definition,
    keyRelationships:
      metadata.keyRelationships,
    typicalBusinessQuestions:
      metadata.typicalBusinessQuestions,
  };

}


function addField(
  fields: Map<
    string,
    SemanticField
  >,
  field: string,
  product: DataProductRequirement,
  required: boolean
) {

  if (!field) {
    return;
  }


  /*
   * Normalize the field name so that:
   *
   * customer_id
   * Customer ID
   * customer-id
   *
   * are treated as the same semantic field.
   */

  const normalized =
    normalizeSemanticField(
      field
    );


  const existing =
    fields.get(normalized);


  /*
   * --------------------------------------------------
   * Field does not exist yet
   * --------------------------------------------------
   */

  if (!existing) {

    const opportunityDescription =
      product.field_opportunities?.find(
        entry =>
          normalizeSemanticField(
            entry.field
          ) === normalized
      )?.description?.trim();

    const metadata =
      applyFieldMetadata(
        field,
        opportunityDescription
      );

    fields.set(
      normalized,
      {

        field,

        ...metadata,

        required,

        requiredBy:
          required
            ? [product.id]
            : [],

        optionalFor:
          required
            ? []
            : [product.id],

        usedByProducts:
          [product.id],

        analyses:
          [...(
            product.analyses ?? []
          )],

      }
    );


    return;

  }


  /*
   * --------------------------------------------------
   * Field already exists
   * --------------------------------------------------
   *
   * This is where the shared semantic model becomes
   * important.
   *
   * If one product requires a field and another product
   * treats it as optional, the field is considered
   * REQUIRED at the dataset-type level.
   *
   * Example:
   *
   * customer_id
   *
   * Customer Intelligence → required
   * Product Performance    → optional
   *
   * Dataset mapping should still identify customer_id
   * as a required semantic field because at least one
   * available product requires it.
   */


  if (
    !existing.usedByProducts.includes(
      product.id
    )
  ) {

    existing.usedByProducts.push(
      product.id
    );

  }


  if (
    !existing.definition?.trim() ||
    !existing.keyRelationships?.trim()
  ) {

    const opportunityDescription =
      product.field_opportunities?.find(
        entry =>
          normalizeSemanticField(
            entry.field
          ) === normalized
      )?.description?.trim();

    const metadata =
      applyFieldMetadata(
        field,
        opportunityDescription
      );


    if (
      !existing.definition?.trim()
    ) {
      existing.definition =
        metadata.definition;
    }

    if (
      !existing.keyRelationships?.trim()
    ) {
      existing.keyRelationships =
        metadata.keyRelationships;
    }

    if (
      !existing.typicalBusinessQuestions?.length
    ) {
      existing.typicalBusinessQuestions =
        metadata.typicalBusinessQuestions;
    }

  }


  /*
   * Required relationship.
   */

  if (required) {

    existing.required = true;


    if (
      !existing.requiredBy.includes(
        product.id
      )
    ) {

      existing.requiredBy.push(
        product.id
      );

    }


    /*
     * If the same product previously listed the
     * field as optional, remove it from optionalFor.
     */

    existing.optionalFor =
      existing.optionalFor.filter(
        productId =>
          productId !== product.id
      );

  }


  /*
   * Optional relationship.
   */

  else {

    /*
     * Only treat it as optional for this product
     * if that product does not already require it.
     */

    if (
      !existing.requiredBy.includes(
        product.id
      ) &&
      !existing.optionalFor.includes(
        product.id
      )
    ) {

      existing.optionalFor.push(
        product.id
      );

    }

  }


  /*
   * --------------------------------------------------
   * Analyses
   * --------------------------------------------------
   *
   * Combine all analyses that use this semantic field.
   */

  for (
    const analysis of
      product.analyses ?? []
  ) {

    if (
      !existing.analyses.includes(
        analysis
      )
    ) {

      existing.analyses.push(
        analysis
      );

    }

  }

}


/*
 * ---------------------------------------------------------------------------
 * Normalize semantic field names
 * ---------------------------------------------------------------------------
 */

function normalizeSemanticField(
  value: string
): string {

  return String(value ?? "")
    .toLowerCase()
    .replace(
      /[^a-z0-9]/g,
      ""
    );

}