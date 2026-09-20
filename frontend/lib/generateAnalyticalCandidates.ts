import {
  AnalyticalCandidate,
  AnalyticalCandidateResult,
  AnalyticalCapability,
  DatasetArchetype,
  DatasetClassificationResult,
} from "@/types/dataset";

type ArchetypeInput =
  | DatasetClassificationResult
  | { primary?: string | null; primary_archetype?: string | null }
  | DatasetArchetype
  | string
  | null
  | undefined;

/**
 * Declarative analysis catalog mirrored from the backend.
 * Sales analyses are definitions — not assumed by the pipeline.
 */
type AnalysisDefinition = {
  id: string;
  title: string;
  description: string;
  requiredCapabilities: string[];
  archetypes: string[];
  domain: string;
  executable: boolean;
};

const ANALYSIS_DEFINITIONS: AnalysisDefinition[] = [
  {
    id: "revenue_trends",
    title: "Revenue Trends",
    description:
      "Analyze revenue performance and trends over time.",
    requiredCapabilities: [
      "trend_analysis",
      "aggregation",
    ],
    archetypes: ["sales_revenue", "finance"],
    domain: "sales",
    executable: true,
  },
  {
    id: "customer_concentration",
    title: "Customer Concentration",
    description:
      "Analyze revenue concentration across customers.",
    requiredCapabilities: [
      "customer_analysis",
      "aggregation",
    ],
    archetypes: ["sales_revenue", "customer"],
    domain: "sales",
    executable: true,
  },
  {
    id: "customer_growth",
    title: "Customer Growth",
    description:
      "Measure customer revenue growth across periods.",
    requiredCapabilities: [
      "customer_analysis",
      "trend_analysis",
    ],
    archetypes: ["sales_revenue", "customer"],
    domain: "sales",
    executable: true,
  },
  {
    id: "customer_performance",
    title: "Customer Performance",
    description:
      "Rank and compare customers by revenue contribution.",
    requiredCapabilities: [
      "customer_analysis",
      "aggregation",
    ],
    archetypes: ["sales_revenue", "customer"],
    domain: "sales",
    executable: true,
  },
  {
    id: "product_performance",
    title: "Product Performance",
    description:
      "Evaluate product revenue and contribution.",
    requiredCapabilities: [
      "product_analysis",
      "aggregation",
    ],
    archetypes: ["sales_revenue"],
    domain: "sales",
    executable: true,
  },
  {
    id: "customer_product",
    title: "Customer Product Affinity",
    description:
      "Analyze which products customers purchase together.",
    requiredCapabilities: [
      "customer_analysis",
      "product_analysis",
      "relationship_analysis",
    ],
    archetypes: ["sales_revenue"],
    domain: "sales",
    executable: true,
  },
  {
    id: "cross_sell",
    title: "Cross-Sell Opportunities",
    description:
      "Identify products customers are likely to purchase together.",
    requiredCapabilities: [
      "customer_analysis",
      "product_analysis",
      "relationship_analysis",
    ],
    archetypes: ["sales_revenue"],
    domain: "sales",
    executable: true,
  },
  {
    id: "profitability",
    title: "Profitability",
    description:
      "Analyze profit and margin across the business.",
    requiredCapabilities: ["aggregation"],
    archetypes: ["sales_revenue", "finance"],
    domain: "sales",
    executable: true,
  },
  {
    id: "profit_improvement",
    title: "Profit Improvement",
    description:
      "Surface products and segments with margin upside.",
    requiredCapabilities: [
      "product_analysis",
      "aggregation",
    ],
    archetypes: ["sales_revenue"],
    domain: "sales",
    executable: true,
  },
  {
    id: "opportunity_summary",
    title: "Opportunity Summary",
    description:
      "Prioritize the highest-value opportunities identified across analyses.",
    requiredCapabilities: [],
    archetypes: ["sales_revenue", "customer"],
    domain: "sales",
    executable: true,
  },
  {
    id: "workforce_composition",
    title: "Workforce Composition",
    description:
      "Summarize headcount mix across departments, roles, or other workforce categories.",
    requiredCapabilities: ["category_comparison"],
    archetypes: ["workforce"],
    domain: "workforce",
    executable: false,
  },
  {
    id: "compensation_analysis",
    title: "Compensation Analysis",
    description:
      "Analyze compensation distribution, levels, and outliers across the workforce.",
    requiredCapabilities: [
      "aggregation",
      "distribution_outlier_analysis",
    ],
    archetypes: ["workforce"],
    domain: "workforce",
    executable: false,
  },
  {
    id: "department_comparison",
    title: "Department Comparison",
    description:
      "Compare workforce measures such as compensation or headcount across departments.",
    requiredCapabilities: [
      "category_comparison",
      "aggregation",
    ],
    archetypes: ["workforce"],
    domain: "workforce",
    executable: false,
  },
  {
    id: "workforce_segmentation",
    title: "Workforce Segmentation",
    description:
      "Segment employees by category or measure to reveal workforce structure.",
    requiredCapabilities: ["segmentation"],
    archetypes: ["workforce"],
    domain: "workforce",
    executable: false,
  },
  {
    id: "headcount_trends",
    title: "Headcount Trends",
    description:
      "Track workforce size and related measures over time.",
    requiredCapabilities: ["trend_analysis"],
    archetypes: ["workforce"],
    domain: "workforce",
    executable: false,
  },
  {
    id: "player_overview",
    title: "Player Overview",
    description:
      "Analyze a player's performance, usage, trends and fantasy outlook.",
    requiredCapabilities: ["fantasy_signal_analysis"],
    archetypes: ["fantasy_sports"],
    domain: "fantasy",
    executable: true,
  },
  {
    id: "fantasy_signals",
    title: "Fantasy Signals",
    description:
      "Promote actionable fantasy football signals into structured insights.",
    requiredCapabilities: ["fantasy_signal_analysis"],
    archetypes: ["fantasy_sports"],
    domain: "fantasy",
    executable: true,
  },
];

function supportedCapabilityMap(
  capabilities: AnalyticalCapability[]
): Map<string, AnalyticalCapability> {
  const supported = new Map<
    string,
    AnalyticalCapability
  >();

  for (const item of capabilities) {
    if (!item.supported || !item.capability) {
      continue;
    }

    supported.set(item.capability, item);
  }

  return supported;
}

function primaryArchetype(
  datasetArchetype: ArchetypeInput
): string | null {
  if (datasetArchetype == null) {
    return null;
  }

  if (typeof datasetArchetype === "string") {
    const value = datasetArchetype.trim();
    return value || null;
  }

  const primary =
    ("primary_archetype" in datasetArchetype
      ? datasetArchetype.primary_archetype
      : null) ??
    ("primary" in datasetArchetype
      ? datasetArchetype.primary
      : null) ??
    null;

  if (primary == null) {
    return null;
  }

  const value = String(primary).trim();
  return value || null;
}

function candidateConfidence(
  definition: AnalysisDefinition,
  supported: Map<string, AnalyticalCapability>
): number {
  if (definition.requiredCapabilities.length === 0) {
    return 1;
  }

  const confidences = definition.requiredCapabilities
    .map(capability => supported.get(capability)?.confidence ?? 0)
    .filter(value => value > 0);

  if (confidences.length === 0) {
    return 0;
  }

  return Math.round(Math.min(...confidences) * 100) / 100;
}

function candidateExplanation(
  definition: AnalysisDefinition,
  supported: Map<string, AnalyticalCapability>,
  archetype: string | null
): string {
  const labels = definition.requiredCapabilities
    .map(capability => {
      const item = supported.get(capability);
      return item?.label || capability;
    })
    .filter(Boolean);

  const parts: string[] = [];

  if (labels.length > 0) {
    parts.push(`Supported by ${labels.join(", ")}`);
  } else if (definition.requiredCapabilities.length === 0) {
    parts.push(
      "Applicable as a summary over related analyses"
    );
  }

  if (archetype) {
    parts.push(
      `for the '${archetype}' dataset archetype`
    );
  }

  if (parts.length === 0) {
    return definition.description;
  }

  return `${parts.join(". ")}.`;
}

/**
 * Determine which analyses are applicable from semantic capabilities.
 */
export function generateAnalyticalCandidates(
  capabilities: AnalyticalCapability[],
  datasetArchetype?: ArchetypeInput
): AnalyticalCandidateResult {
  const supported = supportedCapabilityMap(capabilities);
  const archetype = primaryArchetype(datasetArchetype);
  const candidates: AnalyticalCandidate[] = [];

  for (const definition of ANALYSIS_DEFINITIONS) {
    const missing = definition.requiredCapabilities.filter(
      capability => !supported.has(capability)
    );

    if (missing.length > 0) {
      continue;
    }

    if (
      definition.archetypes.length > 0 &&
      (archetype == null ||
        !definition.archetypes.includes(archetype))
    ) {
      continue;
    }

    if (definition.id === "opportunity_summary") {
      const hasSibling = ANALYSIS_DEFINITIONS.some(
        item =>
          item.id !== "opportunity_summary" &&
          item.domain === definition.domain &&
          (item.archetypes.length === 0 ||
            (archetype != null &&
              item.archetypes.includes(archetype))) &&
          item.requiredCapabilities.every(capability =>
            supported.has(capability)
          )
      );

      if (!hasSibling) {
        continue;
      }
    }

    candidates.push({
      id: definition.id,
      title: definition.title,
      description: definition.description,
      domain: definition.domain,
      executable: definition.executable,
      required_capabilities: [
        ...definition.requiredCapabilities,
      ],
      matched_capabilities: [
        ...definition.requiredCapabilities,
      ],
      archetypes: [...definition.archetypes],
      confidence: candidateConfidence(
        definition,
        supported
      ),
      explanation: candidateExplanation(
        definition,
        supported,
        archetype
      ),
    });
  }

  return {
    candidates,
    candidate_count: candidates.length,
    archetype,
    supported_capabilities: [...supported.keys()].sort(),
  };
}
