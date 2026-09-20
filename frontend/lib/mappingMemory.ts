import {
  DatasetField,
  FieldMapping,
  SemanticField,
} from "@/types/dataset";

import {
  normalizeFieldName,
} from "@/lib/fieldMapping";

import {
  getSavedFieldMappings,
  saveSavedFieldMappings,
} from "@/services/api";


export const MAPPING_MEMORY_PREFIX =
  "insightpilot_mappings_";


export interface SavedFieldMappings {
  datasetTypeId: string;
  uploadedColumns: string[];
  mappings: FieldMapping[];
  savedAt: string;
}


function storageKey(
  datasetTypeId: string
) {

  return (
    `${MAPPING_MEMORY_PREFIX}${datasetTypeId}`
  );

}


export function saveFieldMappings(
  datasetTypeId: string,
  uploadedFields: DatasetField[],
  mappings: FieldMapping[]
) {

  if (
    typeof window === "undefined"
  ) {
    return;
  }

  if (!datasetTypeId) {
    return;
  }

  const mapped =
    mappings.filter(
      mapping =>
        !!mapping.uploadedField
    );

  if (mapped.length === 0) {
    return;
  }

  const payload: SavedFieldMappings = {
    datasetTypeId,

    uploadedColumns:
      uploadedFields.map(
        field => field.name
      ),

    mappings,

    savedAt:
      new Date().toISOString(),
  };

  try {

    localStorage.setItem(
      storageKey(datasetTypeId),
      JSON.stringify(payload)
    );

  } catch (error) {

    console.warn(
      "Unable to save field mappings:",
      error
    );

  }

}


function cacheFieldMappingsLocally(
  payload: SavedFieldMappings
) {

  try {

    localStorage.setItem(
      storageKey(
        payload.datasetTypeId
      ),
      JSON.stringify(payload)
    );

  } catch (error) {

    console.warn(
      "Unable to cache field mappings locally:",
      error
    );

  }

}


function recordToSavedFieldMappings(
  datasetTypeId: string,
  record: {
    uploaded_columns?: string[];
    uploadedColumns?: string[];
    mappings: FieldMapping[];
    updated_at?: string | null;
    savedAt?: string;
  }
): SavedFieldMappings {

  return {
    datasetTypeId,

    uploadedColumns:
      record.uploaded_columns ??
      record.uploadedColumns ??
      [],

    mappings: record.mappings,

    savedAt:
      record.updated_at ??
      record.savedAt ??
      new Date().toISOString(),
  };

}


export async function loadFieldMappingsAsync(
  datasetTypeId: string
): Promise<SavedFieldMappings | null> {

  if (
    typeof window === "undefined"
  ) {
    return null;
  }

  if (!datasetTypeId) {
    return null;
  }

  try {

    const remote =
      await getSavedFieldMappings(
        datasetTypeId
      );

    if (remote) {

      const payload =
        recordToSavedFieldMappings(
          datasetTypeId,
          remote
        );

      cacheFieldMappingsLocally(
        payload
      );

      return payload;

    }

  } catch (error) {

    console.warn(
      "Unable to load field mappings from server:",
      error
    );

  }

  return loadFieldMappings(
    datasetTypeId
  );

}


export async function saveFieldMappingsAsync(
  datasetTypeId: string,
  uploadedFields: DatasetField[],
  mappings: FieldMapping[]
) {

  saveFieldMappings(
    datasetTypeId,
    uploadedFields,
    mappings
  );

  const mapped =
    mappings.filter(
      mapping =>
        !!mapping.uploadedField
    );

  if (mapped.length === 0) {
    return;
  }

  try {

    await saveSavedFieldMappings(
      datasetTypeId,
      {
        uploaded_columns:
          uploadedFields.map(
            field => field.name
          ),

        mappings,
      }
    );

  } catch (error) {

    console.warn(
      "Unable to save field mappings to server:",
      error
    );

  }

}


export function loadFieldMappings(
  datasetTypeId: string
): SavedFieldMappings | null {

  if (
    typeof window === "undefined"
  ) {
    return null;
  }

  if (!datasetTypeId) {
    return null;
  }

  try {

    const stored =
      localStorage.getItem(
        storageKey(datasetTypeId)
      );

    if (!stored) {
      return null;
    }

    const parsed =
      JSON.parse(
        stored
      ) as SavedFieldMappings;

    if (
      !parsed ||
      parsed.datasetTypeId !==
        datasetTypeId ||
      !Array.isArray(
        parsed.mappings
      )
    ) {
      return null;
    }

    return parsed;

  } catch {

    return null;

  }

}


function resolveUploadedColumn(
  savedUploadedField: string,
  uploadedFields: DatasetField[]
): string | null {

  const exact =
    uploadedFields.find(
      field =>
        field.name ===
        savedUploadedField
    );

  if (exact) {
    return exact.name;
  }

  const normalizedSaved =
    normalizeFieldName(
      savedUploadedField
    );

  const normalized =
    uploadedFields.find(
      field =>
        field.normalizedName ===
          normalizedSaved ||
        normalizeFieldName(
          field.name
        ) === normalizedSaved
    );

  return normalized?.name ?? null;

}


export function areMappingsCompatible(
  saved: SavedFieldMappings,
  uploadedFields: DatasetField[]
): boolean {

  const mapped =
    saved.mappings.filter(
      mapping =>
        !!mapping.uploadedField
    );

  if (mapped.length === 0) {
    return false;
  }

  return mapped.every(
    mapping =>
      resolveUploadedColumn(
        String(
          mapping.uploadedField
        ),
        uploadedFields
      ) !== null
  );

}


/*
 * Rebuild mappings for the current semantic
 * fields, preferring previously saved mappings
 * when the uploaded columns still match.
 */

export function reuseFieldMappings(
  saved: SavedFieldMappings,
  uploadedFields: DatasetField[],
  semanticFields: SemanticField[]
): FieldMapping[] | null {

  if (
    !areMappingsCompatible(
      saved,
      uploadedFields
    )
  ) {
    return null;
  }

  const savedByRequired = new Map(
    saved.mappings.map(
      mapping => [
        mapping.requiredField,
        mapping,
      ]
    )
  );

  const usedUploaded =
    new Set<string>();

  const reused: FieldMapping[] = [];

  for (
    const semantic
    of semanticFields
  ) {

    const previous =
      savedByRequired.get(
        semantic.field
      );

    if (
      !previous?.uploadedField
    ) {

      reused.push({
        requiredField:
          semantic.field,

        uploadedField: null,

        matchType: "unmapped",

        confidence: 0,

        required:
          semantic.required,

        valid: !semantic.required,
      });

      continue;

    }

    const resolved =
      resolveUploadedColumn(
        previous.uploadedField,
        uploadedFields
      );

    if (
      !resolved ||
      usedUploaded.has(resolved)
    ) {
      return null;
    }

    usedUploaded.add(resolved);

    reused.push({
      requiredField:
        semantic.field,

      uploadedField: resolved,

      matchType:
        resolved ===
        previous.uploadedField
          ? "reused"
          : "normalized",

      confidence: 1,

      required:
        semantic.required,

      valid: true,
    });

  }

  return reused;

}
