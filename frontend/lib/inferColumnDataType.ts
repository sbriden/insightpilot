/*
 * Infer a column data type from its name and an optional sample value.
 */

const DATE_PATTERNS = [
  /^\d{4}-\d{2}-\d{2}/,
  /^\d{1,2}\/\d{1,2}\/\d{2,4}/,
  /^\d{4}\/\d{2}\/\d{2}/,
];

const INTEGER_PATTERN = /^-?\d+$/;

const DECIMAL_PATTERN = /^-?\d+(\.\d+)?$/;

const BOOLEAN_VALUES = new Set([
  "true",
  "false",
  "yes",
  "no",
  "0",
  "1",
]);

export function inferColumnDataType(
  columnName: string,
  sampleValue?: string
): string {

  const normalizedName = String(columnName ?? "")
    .toLowerCase();

  const trimmedSample = String(sampleValue ?? "").trim();


  if (trimmedSample) {

    if (DATE_PATTERNS.some(pattern => pattern.test(trimmedSample))) {
      return "date";
    }

    if (BOOLEAN_VALUES.has(trimmedSample.toLowerCase())) {
      return "boolean";
    }

    if (INTEGER_PATTERN.test(trimmedSample)) {
      return "integer";
    }

    if (DECIMAL_PATTERN.test(trimmedSample)) {
      return "number";
    }

    return "string";

  }


  if (
    /date|time|timestamp|datetime|month|year|week|period/.test(
      normalizedName
    )
  ) {
    return "date";
  }

  if (
    /revenue|amount|price|cost|profit|margin|value|sales|income|total/.test(
      normalizedName
    )
  ) {
    return "number";
  }

  if (
    /quantity|qty|count|units|volume|number|num/.test(
      normalizedName
    )
  ) {
    return "number";
  }

  if (
    /id|key|code|sku|uuid|guid/.test(
      normalizedName
    )
  ) {
    return "string";
  }

  if (
    /status|flag|active|enabled/.test(
      normalizedName
    )
  ) {
    return "string";
  }

  return "string";

}
