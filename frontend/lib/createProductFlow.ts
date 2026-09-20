export const CREATE_FLOW_STEPS = [
  {
    id: "upload",
    label: "Data source",
  },
  {
    id: "dataset-type",
    label: "Dataset type",
  },
  {
    id: "mapping",
    label: "Map fields",
  },
  {
    id: "products",
    label: "Products",
  },
  {
    id: "results",
    label: "Results",
  },
] as const;


export type CreateFlowStepId =
  typeof CREATE_FLOW_STEPS[number]["id"];


export function getCreateFlowSteps(options?: {
  skipMapping?: boolean;
}): Array<{
  id: CreateFlowStepId;
  label: string;
}> {

  if (options?.skipMapping) {
    return CREATE_FLOW_STEPS.filter(
      step => step.id !== "mapping"
    ).map(step => ({ ...step }));
  }

  return CREATE_FLOW_STEPS.map(
    step => ({ ...step })
  );

}


export function getCreateFlowStepIndex(
  stepId: CreateFlowStepId,
  steps: Array<{ id: string }> = [...CREATE_FLOW_STEPS]
): number {

  return steps.findIndex(
    step => step.id === stepId
  );

}
