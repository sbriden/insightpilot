"use client";


interface Props {

  requiredCoverage: number;

  overallCoverage: number;

  missingRequiredFields: string[];

  availableOptionalFields: string[];

}


export default function MappingCoverage({
  requiredCoverage,
  overallCoverage,
  missingRequiredFields,
  availableOptionalFields,
}: Props) {

  const canAnalyze =
    missingRequiredFields.length === 0;


  return (

    <div className="space-y-6">

      {/* Required coverage */}

      <div className="rounded-xl border bg-white p-6">

        <div className="flex justify-between">

          <div>

            <p className="text-sm font-medium">
              Required field coverage
            </p>

            <p className="mt-1 text-xs text-gray-500">
              Required fields determine whether
              the product can be analyzed.
            </p>

          </div>

          <p className="text-2xl font-bold">
            {requiredCoverage}%
          </p>

        </div>


        <div className="mt-4 h-2 overflow-hidden rounded-full bg-gray-100">

          <div
            className="h-full rounded-full bg-gray-900"
            style={{
              width: `${requiredCoverage}%`,
            }}
          />

        </div>


        {canAnalyze ? (

          <p className="mt-4 text-sm text-green-600">
            All required fields are mapped.
          </p>

        ) : (

          <div className="mt-4">

            <p className="text-sm font-medium text-red-600">
              Missing required fields
            </p>

            <div className="mt-2 flex flex-wrap gap-2">

              {missingRequiredFields.map(
                (field) => (

                  <span
                    key={field}
                    className="rounded-full bg-red-50 px-3 py-1 text-xs text-red-600"
                  >
                    {field}
                  </span>

                )
              )}

            </div>

          </div>

        )}

      </div>


      {/* Overall coverage */}

      <div className="rounded-xl border bg-white p-6">

        <div className="flex justify-between">

          <div>

            <p className="text-sm font-medium">
              Product coverage
            </p>

            <p className="mt-1 text-xs text-gray-500">
              Additional fields can unlock
              additional analysis.
            </p>

          </div>

          <p className="text-2xl font-bold">
            {overallCoverage}%
          </p>

        </div>


        <div className="mt-4 h-2 overflow-hidden rounded-full bg-gray-100">

          <div
            className="h-full rounded-full bg-gray-900"
            style={{
              width: `${overallCoverage}%`,
            }}
          />

        </div>


        {availableOptionalFields.length > 0 && (

          <div className="mt-5">

            <p className="text-sm font-medium">
              Additional analysis enabled
            </p>

            <p className="mt-1 text-xs text-gray-500">
              Your dataset contains these optional
              fields.
            </p>

            <div className="mt-3 flex flex-wrap gap-2">

              {availableOptionalFields.map(
                (field) => (

                  <span
                    key={field}
                    className="rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-600"
                  >
                    {field}
                  </span>

                )
              )}

            </div>

          </div>

        )}

      </div>

    </div>
  );
}