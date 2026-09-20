"use client";

import {
  FieldMapping as FieldMappingType,
} from "@/types/dataset";


interface Props {

  mappings: FieldMappingType[];

  uploadedFields: string[];

  onChange: (
    requiredField: string,
    uploadedField: string | null
  ) => void;

}


export default function FieldMapping({
  mappings,
  uploadedFields,
  onChange,
}: Props) {

  return (

    <div className="space-y-4">

      {mappings.map((mapping) => (

        <div
          key={mapping.requiredField}
          className="rounded-xl border bg-white p-5"
        >

          <div className="flex items-start justify-between gap-4">

            <div>

              <div className="flex items-center gap-2">

                <p className="font-medium">
                  {mapping.requiredField}
                </p>

                {mapping.required && (

                  <span className="rounded-full bg-red-50 px-2 py-1 text-xs text-red-600">
                    Required
                  </span>

                )}

                {!mapping.required && (

                  <span className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-500">
                    Optional
                  </span>

                )}

              </div>

              <p className="mt-1 text-xs text-gray-500">
                Map this requirement to a column
                in your uploaded dataset.
              </p>

            </div>


            <MatchBadge
              mapping={mapping}
            />

          </div>


          <div className="mt-4">

            <select
              value={
                mapping.uploadedField ?? ""
              }
              onChange={(event) => {

                onChange(
                  mapping.requiredField,
                  event.target.value || null
                );

              }}
              className="w-full rounded-lg border px-3 py-2 text-sm"
            >

              <option value="">
                -- Not mapped --
              </option>

              {uploadedFields.map(
                (field) => (

                  <option
                    key={field}
                    value={field}
                  >
                    {field}
                  </option>

                )
              )}

            </select>

          </div>

        </div>

      ))}

    </div>
  );
}


function MatchBadge({
  mapping,
}: {
  mapping: FieldMappingType;
}) {

  if (!mapping.uploadedField) {

    return (
      <span className="rounded-full bg-red-50 px-2 py-1 text-xs text-red-600">
        Missing
      </span>
    );
  }


  if (mapping.matchType === "manual") {

    return (
      <span className="rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-600">
        Manual
      </span>
    );
  }


  if (mapping.confidence >= 0.9) {

    return (
      <span className="rounded-full bg-green-50 px-2 py-1 text-xs text-green-600">
        Strong match
      </span>
    );
  }


  return (
    <span className="rounded-full bg-yellow-50 px-2 py-1 text-xs text-yellow-700">
      Review
    </span>
  );
}