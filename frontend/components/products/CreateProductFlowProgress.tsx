"use client";

import {
  cn,
} from "@/lib/utils";


export interface CreateFlowStep {
  id: string;
  label: string;
}


interface Props {
  steps: CreateFlowStep[];
  currentStepId: string;
  maxReachableIndex: number;
  onStepClick: (
    stepId: string,
    index: number
  ) => void;
}


export default function CreateProductFlowProgress({
  steps,
  currentStepId,
  maxReachableIndex,
  onStepClick,
}: Props) {

  const currentIndex =
    steps.findIndex(
      step =>
        step.id === currentStepId
    );


  return (
    <nav
      aria-label="Create product progress"
      className="rounded-xl border bg-white px-4 py-5 sm:px-6"
    >

      <ol className="flex items-center gap-2 sm:gap-0">

        {steps.map(
          (step, index) => {

            const isCurrent =
              step.id ===
              currentStepId;

            const isComplete =
              index <
              currentIndex;

            const isReachable =
              index <=
              maxReachableIndex;

            const isClickable =
              isReachable &&
              index !== currentIndex;

            const stepNumber =
              index + 1;


            return (
              <li
                key={step.id}
                className="flex min-w-0 flex-1 items-center"
              >

                <button
                  type="button"
                  disabled={!isClickable}
                  onClick={() =>
                    isClickable &&
                    onStepClick(
                      step.id,
                      index
                    )
                  }
                  aria-current={
                    isCurrent
                      ? "step"
                      : undefined
                  }
                  className={cn(
                    "group flex min-w-0 flex-1 items-center gap-2 rounded-lg px-1 py-1 text-left transition-colors sm:px-2",
                    isClickable &&
                      "cursor-pointer hover:bg-gray-50",
                    !isReachable &&
                      "cursor-default opacity-50"
                  )}
                >

                  <span
                    className={cn(
                      "flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                      isCurrent &&
                        "bg-gray-900 text-white",
                      isComplete &&
                        !isCurrent &&
                        "bg-gray-200 text-gray-700 group-hover:bg-gray-300",
                      !isCurrent &&
                        !isComplete &&
                        isReachable &&
                        "border border-gray-300 text-gray-600",
                      !isReachable &&
                        "border border-gray-200 text-gray-400"
                    )}
                  >
                    {stepNumber}
                  </span>


                  <span className="hidden min-w-0 sm:block">

                    <span
                      className={cn(
                        "block truncate text-sm font-medium",
                        isCurrent
                          ? "text-gray-950"
                          : "text-gray-600"
                      )}
                    >
                      {step.label}
                    </span>

                  </span>

                </button>


                {index <
                  steps.length - 1 && (

                  <div
                    className={cn(
                      "mx-1 hidden h-px flex-1 sm:block",
                      index <
                        currentIndex
                        ? "bg-gray-400"
                        : "bg-gray-200"
                    )}
                    aria-hidden
                  />

                )}

              </li>
            );

          }
        )}

      </ol>


      {currentIndex >= 0 && (

        <p className="mt-3 text-sm text-gray-500 sm:hidden">
          Step {currentIndex + 1} of {steps.length}:{" "}
          <span className="font-medium text-gray-800">
            {steps[currentIndex]?.label}
          </span>
        </p>

      )}

    </nav>

  );

}
