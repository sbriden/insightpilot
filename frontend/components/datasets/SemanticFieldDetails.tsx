"use client";

import {
  useId,
} from "react";

import {
  Info,
} from "lucide-react";

import {
  SemanticField,
} from "@/types/dataset";

import {
  resolveSemanticFieldMetadata,
} from "@/lib/semanticFieldCatalog";


interface Props {
  fieldName: string;

  semanticField?: SemanticField;
}


export default function SemanticFieldDetails({
  fieldName,
  semanticField,
}: Props) {

  const metadata =
    resolveSemanticFieldMetadata(
      fieldName,
      semanticField?.definition
    );


  const keyRelationships =
    semanticField?.keyRelationships ??
    metadata.keyRelationships;

  const typicalBusinessQuestions =
    semanticField?.typicalBusinessQuestions ??
    metadata.typicalBusinessQuestions ??
    [];


  const hasExtraInfo =
    !!keyRelationships ||
    typicalBusinessQuestions.length > 0;


  return (
    <div>

      <div className="flex items-center gap-1.5">

        <p className="font-medium text-gray-950">
          {fieldName}
        </p>

        {hasExtraInfo && (

          <SemanticFieldInfoPopover
            keyRelationships={
              keyRelationships
            }
            typicalBusinessQuestions={
              typicalBusinessQuestions
            }
          />

        )}

      </div>


      <p className="mt-2 text-sm leading-6 text-gray-600">
        {metadata.definition}
      </p>

    </div>
  );

}


function SemanticFieldInfoPopover({
  keyRelationships,
  typicalBusinessQuestions,
}: {
  keyRelationships?: string;
  typicalBusinessQuestions: string[];
}) {

  const tooltipId =
    useId();


  return (
    <div className="group relative inline-flex">

      <button
        type="button"
        aria-label="Show field relationships and business questions"
        aria-describedby={
          tooltipId
        }
        className="inline-flex h-5 w-5 items-center justify-center rounded-full text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-1"
      >

        <Info
          className="h-3.5 w-3.5"
          aria-hidden
        />

      </button>


      <div
        id={tooltipId}
        role="tooltip"
        className="pointer-events-none absolute left-full top-0 z-50 pl-2 opacity-0 transition-opacity group-hover:pointer-events-auto group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:opacity-100"
      >

        <div className="w-80 rounded-lg border border-gray-200 bg-white p-4 shadow-lg">

          {keyRelationships && (

            <div>

              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                Key relationships
              </p>

              <p className="mt-1 text-sm leading-6 text-gray-700">
                {keyRelationships}
              </p>

            </div>

          )}


          {typicalBusinessQuestions.length > 0 && (

            <div
              className={
                keyRelationships
                  ? "mt-4"
                  : ""
              }
            >

              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                Typical business questions
              </p>

              <ul className="mt-1 list-disc space-y-1 pl-4 text-sm leading-6 text-gray-700">

                {typicalBusinessQuestions.map(
                  question => (

                    <li
                      key={
                        question
                      }
                    >
                      {question}
                    </li>

                  )
                )}

              </ul>

            </div>

          )}

        </div>

      </div>

    </div>
  );

}
