import {
  DatasetField,
  FieldMapping,
  SemanticField,
} from "@/types/dataset";


/*
 * ---------------------------------------------------------------------------
 * Normalize field name
 * ---------------------------------------------------------------------------
 *
 * Normalize common naming differences so that:
 *
 * customer_id
 * Customer ID
 * customer-id
 * CUSTOMER_ID
 *
 * all become:
 *
 * customerid
 */

export function normalizeFieldName(
  value: string
): string {

  return String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");

}


/*
 * ---------------------------------------------------------------------------
 * Calculate similarity
 * ---------------------------------------------------------------------------
 *
 * Lightweight fuzzy matching.
 */

function similarity(
  source: string,
  target: string
): number {

  if (!source || !target) {
    return 0;
  }


  /*
   * Exact match.
   */

  if (source === target) {
    return 1;
  }


  /*
   * One value contains the other.
   *
   * Example:
   *
   * customerid
   * customeridentifier
   */

  if (
    source.includes(target) ||
    target.includes(source)
  ) {

    return 0.85;

  }


  /*
   * Compare individual words.
   *
   * This is mainly useful when the original
   * field names still contain separators.
   */

  const sourceWords =
    source.split(/[_\s-]+/);

  const targetWords =
    target.split(/[_\s-]+/);


  const matches =
    sourceWords.filter(
      word =>
        targetWords.includes(word)
    ).length;


  const denominator =
    Math.max(
      sourceWords.length,
      targetWords.length
    );


  if (denominator === 0) {
    return 0;
  }


  return matches / denominator;

}


/*
 * ---------------------------------------------------------------------------
 * Automatically map uploaded fields to shared semantic fields
 * ---------------------------------------------------------------------------
 *
 * IMPORTANT:
 *
 * This function is now product-independent.
 *
 * Previously:
 *
 * uploadedFields
 *      ↓
 * selected product
 *      ↓
 * product required/optional fields
 *
 * Now:
 *
 * uploadedFields
 *      ↓
 * semantic fields for dataset type
 *      ↓
 * shared mappings
 *
 * A semantic field is mapped exactly once and that mapping can subsequently
 * be used by every data product associated with the dataset type.
 */

export function mapDatasetFields(
  uploadedFields: DatasetField[],
  semanticFields: SemanticField[]
): FieldMapping[] {

  if (
    !Array.isArray(uploadedFields) ||
    !Array.isArray(semanticFields)
  ) {

    return [];

  }


  return semanticFields.map(
    semanticField => {

      const normalizedSemanticField =
        normalizeFieldName(
          semanticField.field
        );


      /*
       * --------------------------------------------------
       * 1. Exact normalized match
       * --------------------------------------------------
       *
       * Example:
       *
       * Uploaded:
       * customer_id
       *
       * Semantic:
       * customer_id
       */

      const exactMatch =
        uploadedFields.find(
          field =>
            normalizeFieldName(
              field.name
            ) ===
            normalizedSemanticField
        );


      if (exactMatch) {

        return {

          requiredField:
            semanticField.field,

          uploadedField:
            exactMatch.name,

          confidence:
            1,

          matchType:
            "exact",

          required:
            semanticField.required,

          valid:
            true,

        };

      }


      /*
       * --------------------------------------------------
       * 2. Fuzzy match
       * --------------------------------------------------
       */

      let bestField:
        DatasetField | null =
        null;

      let bestScore = 0;


      for (
        const field of uploadedFields
      ) {

        const normalizedUploadedField =
          normalizeFieldName(
            field.name
          );


        const score =
          similarity(
            normalizedUploadedField,
            normalizedSemanticField
          );


        if (
          score > bestScore
        ) {

          bestScore =
            score;

          bestField =
            field;

        }

      }


      /*
       * Only accept fuzzy matches above
       * the existing confidence threshold.
       */

      if (
        bestField &&
        bestScore >= 0.65
      ) {

        return {

          requiredField:
            semanticField.field,

          uploadedField:
            bestField.name,

          confidence:
            bestScore,

          matchType:
            bestScore >= 0.85
              ? "normalized"
              : "fuzzy",

          required:
            semanticField.required,

          valid:
            true,

        };

      }


      /*
       * --------------------------------------------------
       * 3. No match
       * --------------------------------------------------
       */

      return {

        requiredField:
          semanticField.field,

        uploadedField:
          null,

        confidence:
          0,

        matchType:
          "missing",

        required:
          semanticField.required,

        valid:
          false,

      };

    }
  );

}


/*
 * ---------------------------------------------------------------------------
 * Calculate mapping coverage
 * ---------------------------------------------------------------------------
 *
 * This represents coverage across the shared semantic field set.
 *
 * Product-specific coverage will be calculated later from the same mappings.
 */

export function calculateMappingCoverage(
  mappings: FieldMapping[]
): number {

  if (
    !Array.isArray(mappings) ||
    mappings.length === 0
  ) {

    return 0;

  }


  const mapped =
    mappings.filter(
      mapping =>
        !!mapping.uploadedField
    ).length;


  return Math.round(
    (mapped / mappings.length) *
      100
  );

}


/*
 * ---------------------------------------------------------------------------
 * Calculate required-field coverage
 * ---------------------------------------------------------------------------
 *
 * This is useful for determining whether the shared dataset mapping is
 * complete enough to proceed.
 *
 * Only semantic fields marked as required are considered.
 */

export function calculateRequiredMappingCoverage(
  mappings: FieldMapping[]
): number {

  if (
    !Array.isArray(mappings)
  ) {

    return 0;

  }


  const requiredMappings =
    mappings.filter(
      mapping =>
        mapping.required
    );


  if (
    requiredMappings.length === 0
  ) {

    return 100;

  }


  const mappedRequired =
    requiredMappings.filter(
      mapping =>
        !!mapping.uploadedField
    );


  return Math.round(
    (mappedRequired.length /
      requiredMappings.length) *
      100
  );

}


/*
 * ---------------------------------------------------------------------------
 * Get missing required semantic fields
 * ---------------------------------------------------------------------------
 */

export function getMissingRequiredFields(
  mappings: FieldMapping[]
): string[] {

  if (
    !Array.isArray(mappings)
  ) {

    return [];

  }


  return mappings
    .filter(
      mapping =>
        mapping.required &&
        !mapping.uploadedField
    )
    .map(
      mapping =>
        mapping.requiredField
    );

}


/*
 * ---------------------------------------------------------------------------
 * Get mapped semantic fields
 * ---------------------------------------------------------------------------
 */

export function getMappedFields(
  mappings: FieldMapping[]
): string[] {

  if (
    !Array.isArray(mappings)
  ) {

    return [];

  }


  return mappings
    .filter(
      mapping =>
        !!mapping.uploadedField
    )
    .map(
      mapping =>
        mapping.requiredField
    );

}