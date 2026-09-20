import {
  AnalyticalCapability,
  BusinessConcept,
  CapabilityDetectionResult,
} from "@/types/dataset";


const CONFIDENCE_THRESHOLD = 0.65;

const ENTITY_CONCEPTS = new Set([
  "Customer",
  "Product",
  "Employee",
  "Supplier",
  "Transaction/Order",
]);


type EvaluationResult = {
  supported: boolean;
  confidence: number;
  matchedColumns: BusinessConcept[];
  explanation: string;
};


class SemanticInventory {
  concepts: BusinessConcept[];

  constructor(concepts: BusinessConcept[]) {
    this.concepts = concepts.filter(
      concept =>
        concept.confidence >=
          CONFIDENCE_THRESHOLD &&
        concept.concept !== "Unknown"
    );
  }

  byConcept(concept: string): BusinessConcept[] {
    return this.concepts.filter(
      item => item.concept === concept
    );
  }

  byRole(role: string): BusinessConcept[] {
    return this.concepts.filter(
      item => item.role === role
    );
  }

  hasConcept(
    concept: string
  ): [boolean, number, BusinessConcept[]] {
    const matches = this.byConcept(concept);

    if (!matches.length) {
      return [false, 0, []];
    }

    const confidence = Math.min(
      ...matches.map(
        match => match.confidence
      )
    );

    return [true, confidence, matches];
  }

  hasRole(
    role: string
  ): [boolean, number, BusinessConcept[]] {
    const matches = this.byRole(role);

    if (!matches.length) {
      return [false, 0, []];
    }

    const confidence = Math.min(
      ...matches.map(
        match => match.confidence
      )
    );

    return [true, confidence, matches];
  }

  entityConcepts(): BusinessConcept[] {
    return this.concepts.filter(
      item =>
        ENTITY_CONCEPTS.has(item.concept)
    );
  }

  distinctEntityConceptNames(): Set<string> {
    return new Set(
      this.entityConcepts().map(
        item => item.concept
      )
    );
  }
}


function formatColumns(
  matches: BusinessConcept[]
): string {
  return matches
    .map(
      match =>
        `'${match.sourceColumn}' (${match.concept})`
    )
    .join(", ");
}


function combineConfidence(
  ...values: number[]
): number {
  const positive = values.filter(
    value => value > 0
  );

  if (!positive.length) {
    return 0;
  }

  return (
    Math.round(
      Math.min(...positive) * 100
    ) / 100
  );
}


function evaluateTimeSeries(
  inventory: SemanticInventory
): EvaluationResult {
  const [
    hasDate,
    dateConfidence,
    dateMatches,
  ] = inventory.hasRole("date");

  const [
    hasMeasure,
    measureConfidence,
    measureMatches,
  ] = inventory.hasRole("measure");

  const matched = [
    ...dateMatches,
    ...measureMatches,
  ];

  if (hasDate && hasMeasure) {
    return {
      supported: true,
      confidence: combineConfidence(
        dateConfidence,
        measureConfidence
      ),
      matchedColumns: matched,
      explanation:
        `Supported because the dataset includes ` +
        `a date column (${formatColumns(dateMatches)}) ` +
        `and a numeric measure (${formatColumns(measureMatches)}), ` +
        `enabling analysis over time.`,
    };
  }

  const missing: string[] = [];

  if (!hasDate) {
    missing.push("a date or time column");
  }

  if (!hasMeasure) {
    missing.push(
      "a numeric measure such as revenue or quantity"
    );
  }

  return {
    supported: false,
    confidence: 0,
    matchedColumns: matched,
    explanation:
      `Requires ${missing.join(" and ")}.` +
      (matched.length
        ? ` Found ${formatColumns(matched)}.`
        : ""),
  };
}


function evaluateTrendAnalysis(
  inventory: SemanticInventory
): EvaluationResult {
  const result = evaluateTimeSeries(inventory);

  if (result.supported) {
    const detail = result.explanation.slice(
      result.explanation.indexOf("the dataset")
    );

    result.explanation =
      `Supported because trend analysis needs a time ` +
      `dimension and a measure; ${detail}`;
  } else {
    result.explanation =
      `Trend analysis requires a date column and a ` +
      `numeric measure to compare values across periods.` +
      (result.matchedColumns.length
        ? ` Found ${formatColumns(result.matchedColumns)}.`
        : "");
  }

  return result;
}


function evaluateCategoryComparison(
  inventory: SemanticInventory
): EvaluationResult {
  const [
    hasCategory,
    categoryConfidence,
    categoryMatches,
  ] = inventory.hasRole("category");

  const [
    hasMeasure,
    measureConfidence,
    measureMatches,
  ] = inventory.hasRole("measure");

  const matched = [
    ...categoryMatches,
    ...measureMatches,
  ];

  if (hasCategory && hasMeasure) {
    return {
      supported: true,
      confidence: combineConfidence(
        categoryConfidence,
        measureConfidence
      ),
      matchedColumns: matched,
      explanation:
        `Supported because the dataset includes ` +
        `a categorical dimension (${formatColumns(categoryMatches)}) ` +
        `and a measure (${formatColumns(measureMatches)}) ` +
        `for comparing groups.`,
    };
  }

  const missing: string[] = [];

  if (!hasCategory) {
    missing.push(
      "a categorical column such as department, segment, or type"
    );
  }

  if (!hasMeasure) {
    missing.push("a numeric measure");
  }

  return {
    supported: false,
    confidence: 0,
    matchedColumns: matched,
    explanation:
      `Requires ${missing.join(" and ")}.` +
      (matched.length
        ? ` Found ${formatColumns(matched)}.`
        : ""),
  };
}


function evaluateSegmentation(
  inventory: SemanticInventory
): EvaluationResult {
  const [
    hasEntity,
    entityConfidence,
    entityMatches,
  ] = inventory.hasRole("entity");

  const [
    hasCategory,
    categoryConfidence,
    categoryMatches,
  ] = inventory.hasRole("category");

  const [
    hasMeasure,
    measureConfidence,
    measureMatches,
  ] = inventory.hasRole("measure");

  const hasSegmentDimension =
    hasCategory || hasMeasure;

  const matched = [
    ...entityMatches,
    ...categoryMatches,
    ...measureMatches,
  ];

  if (hasEntity && hasSegmentDimension) {
    const dimensionMatches = hasCategory
      ? categoryMatches
      : measureMatches;

    const dimensionLabel = hasCategory
      ? "category"
      : "measure";

    return {
      supported: true,
      confidence: combineConfidence(
        entityConfidence,
        hasCategory
          ? categoryConfidence
          : measureConfidence
      ),
      matchedColumns: matched,
      explanation:
        `Supported because the dataset includes ` +
        `an entity (${formatColumns(entityMatches)}) ` +
        `and a ${dimensionLabel} (${formatColumns(dimensionMatches)}) ` +
        `for grouping or segmenting records.`,
    };
  }

  return {
    supported: false,
    confidence: 0,
    matchedColumns: matched,
    explanation:
      `Segmentation requires an entity column and either ` +
      `a category or measure to define segments.` +
      (matched.length
        ? ` Found ${formatColumns(matched)}.`
        : ""),
  };
}


function evaluateConceptAnalysis(
  inventory: SemanticInventory,
  concept: string,
  label: string
): EvaluationResult {
  const [
    found,
    confidence,
    matches,
  ] = inventory.hasConcept(concept);

  if (found) {
    return {
      supported: true,
      confidence,
      matchedColumns: matches,
      explanation:
        `Supported because ${formatColumns(matches)} ` +
        `identifies ${concept.toLowerCase()} data suitable ` +
        `for ${label}.`,
    };
  }

  return {
    supported: false,
    confidence: 0,
    matchedColumns: [],
    explanation:
      `${label[0].toUpperCase()}${label.slice(1)} requires a column that ` +
      `represents ${concept.toLowerCase()} information, ` +
      `which was not identified in this dataset.`,
  };
}


function evaluateGeographicAnalysis(
  inventory: SemanticInventory
): EvaluationResult {
  const [
    foundConcept,
    conceptConfidence,
    conceptMatches,
  ] = inventory.hasConcept("Geography");

  const [
    foundRole,
    roleConfidence,
    roleMatches,
  ] = inventory.hasRole("geography");

  const matches =
    conceptMatches.length
      ? conceptMatches
      : roleMatches;

  if (foundConcept || foundRole) {
    return {
      supported: true,
      confidence: combineConfidence(
        conceptConfidence,
        roleConfidence
      ),
      matchedColumns: matches,
      explanation:
        `Supported because the dataset includes ` +
        `geographic columns (${formatColumns(matches)}).`,
    };
  }

  return {
    supported: false,
    confidence: 0,
    matchedColumns: [],
    explanation:
      `Geographic analysis requires location columns ` +
      `such as region, country, city, or territory.`,
  };
}


function evaluateAggregation(
  inventory: SemanticInventory
): EvaluationResult {
  const [
    found,
    confidence,
    matches,
  ] = inventory.hasRole("measure");

  if (found) {
    return {
      supported: true,
      confidence,
      matchedColumns: matches,
      explanation:
        `Supported because the dataset includes ` +
        `numeric measures (${formatColumns(matches)}) ` +
        `that can be summed, averaged, or counted.`,
    };
  }

  return {
    supported: false,
    confidence: 0,
    matchedColumns: [],
    explanation:
      `Aggregation requires at least one numeric measure ` +
      `column such as revenue, amount, or quantity.`,
  };
}


function evaluateDistributionOutlierAnalysis(
  inventory: SemanticInventory
): EvaluationResult {
  const result = evaluateAggregation(inventory);

  if (result.supported) {
    result.explanation =
      `Supported because distribution and outlier analysis ` +
      `needs numeric measures; found ` +
      `${formatColumns(result.matchedColumns)}.`;
  } else {
    result.explanation =
      `Distribution and outlier analysis requires numeric ` +
      `measure columns to analyze spread and extremes.`;
  }

  return result;
}


function evaluateStatusAnalysis(
  inventory: SemanticInventory
): EvaluationResult {
  const [
    foundConcept,
    conceptConfidence,
    conceptMatches,
  ] = inventory.hasConcept("Status");

  const [
    foundRole,
    roleConfidence,
    roleMatches,
  ] = inventory.hasRole("status");

  const matches =
    conceptMatches.length
      ? conceptMatches
      : roleMatches;

  if (foundConcept || foundRole) {
    return {
      supported: true,
      confidence: combineConfidence(
        conceptConfidence,
        roleConfidence
      ),
      matchedColumns: matches,
      explanation:
        `Supported because the dataset includes ` +
        `status columns (${formatColumns(matches)}) ` +
        `for pipeline or lifecycle analysis.`,
    };
  }

  return {
    supported: false,
    confidence: 0,
    matchedColumns: [],
    explanation:
      `Status analysis requires columns representing ` +
      `state, stage, or condition.`,
  };
}


function evaluateRelationshipAnalysis(
  inventory: SemanticInventory
): EvaluationResult {
  const entityNames =
    inventory.distinctEntityConceptNames();

  const entityMatches =
    inventory.entityConcepts();

  const [
    hasMeasure,
    measureConfidence,
    measureMatches,
  ] = inventory.hasRole("measure");

  const hasMultipleEntities =
    entityNames.size >= 2;

  const hasEntityWithDimension =
    entityNames.size >= 1 &&
    (inventory.byRole("category").length > 0 ||
      inventory.byRole("date").length > 0 ||
      inventory.byRole("geography").length > 0 ||
      hasMeasure);

  const matched = [
    ...entityMatches,
    ...measureMatches,
  ];

  if (hasMultipleEntities) {
    return {
      supported: true,
      confidence: Math.min(
        ...entityMatches.map(
          match => match.confidence
        )
      ),
      matchedColumns: entityMatches,
      explanation:
        `Supported because the dataset links multiple ` +
        `entity types (${formatColumns(entityMatches)}), ` +
        `enabling relationship analysis.`,
    };
  }

  if (hasEntityWithDimension) {
    const dimensionMatches = [
      ...inventory.byRole("category"),
      ...inventory.byRole("date"),
      ...inventory.byRole("geography"),
      ...measureMatches,
    ];

    return {
      supported: true,
      confidence: combineConfidence(
        Math.min(
          ...entityMatches.map(
            match => match.confidence
          )
        ),
        measureConfidence
      ),
      matchedColumns: [
        ...entityMatches,
        ...dimensionMatches,
      ],
      explanation:
        `Supported because the dataset combines ` +
        `entities (${formatColumns(entityMatches)}) ` +
        `with additional dimensions for ` +
        `cross-dimensional analysis.`,
    };
  }

  return {
    supported: false,
    confidence: 0,
    matchedColumns: matched,
    explanation:
      `Relationship analysis requires multiple related ` +
      `entities or an entity paired with a category, ` +
      `date, geography, or measure.` +
      (matched.length
        ? ` Found ${formatColumns(matched)}.`
        : ""),
  };
}


type CapabilityDefinition = {
  capability: string;
  label: string;
  requiredConcepts: string[];
  evaluate: (
    inventory: SemanticInventory
  ) => EvaluationResult;
};


const CAPABILITY_DEFINITIONS: CapabilityDefinition[] = [
  {
    capability: "time_series_analysis",
    label: "Time-series analysis",
    requiredConcepts: ["Date", "Revenue"],
    evaluate: evaluateTimeSeries,
  },
  {
    capability: "trend_analysis",
    label: "Trend analysis",
    requiredConcepts: ["Date", "Revenue"],
    evaluate: evaluateTrendAnalysis,
  },
  {
    capability: "category_comparison",
    label: "Category comparison",
    requiredConcepts: ["Category", "Revenue"],
    evaluate: evaluateCategoryComparison,
  },
  {
    capability: "segmentation",
    label: "Segmentation",
    requiredConcepts: ["Customer", "Category"],
    evaluate: evaluateSegmentation,
  },
  {
    capability: "customer_analysis",
    label: "Customer analysis",
    requiredConcepts: ["Customer"],
    evaluate: inventory =>
      evaluateConceptAnalysis(
        inventory,
        "Customer",
        "customer analysis"
      ),
  },
  {
    capability: "product_analysis",
    label: "Product analysis",
    requiredConcepts: ["Product"],
    evaluate: inventory =>
      evaluateConceptAnalysis(
        inventory,
        "Product",
        "product analysis"
      ),
  },
  {
    capability: "geographic_analysis",
    label: "Geographic analysis",
    requiredConcepts: ["Geography"],
    evaluate: evaluateGeographicAnalysis,
  },
  {
    capability: "transaction_analysis",
    label: "Transaction analysis",
    requiredConcepts: ["Transaction/Order"],
    evaluate: inventory =>
      evaluateConceptAnalysis(
        inventory,
        "Transaction/Order",
        "transaction analysis"
      ),
  },
  {
    capability: "aggregation",
    label: "Aggregation",
    requiredConcepts: ["Revenue"],
    evaluate: evaluateAggregation,
  },
  {
    capability: "distribution_outlier_analysis",
    label: "Distribution/outlier analysis",
    requiredConcepts: ["Revenue"],
    evaluate: evaluateDistributionOutlierAnalysis,
  },
  {
    capability: "status_analysis",
    label: "Status analysis",
    requiredConcepts: ["Status"],
    evaluate: evaluateStatusAnalysis,
  },
  {
    capability: "relationship_analysis",
    label: "Relationship analysis",
    requiredConcepts: ["Customer", "Product"],
    evaluate: evaluateRelationshipAnalysis,
  },
];


export function detectAnalyticalCapabilities(
  concepts: BusinessConcept[]
): CapabilityDetectionResult {
  const inventory = new SemanticInventory(
    concepts
  );

  let supportedCount = 0;

  const capabilities: AnalyticalCapability[] =
    CAPABILITY_DEFINITIONS.map(
      definition => {
        const result =
          definition.evaluate(inventory);

        if (result.supported) {
          supportedCount += 1;
        }

        return {
          capability:
            definition.capability,
          label: definition.label,
          supported: result.supported,
          confidence: result.confidence,
          required_concepts:
            definition.requiredConcepts,
          explanation: result.explanation,
          matched_columns:
            result.matchedColumns.map(
              match =>
                match.sourceColumn
            ),
        };
      }
    );

  return {
    capabilities,
    supported_count: supportedCount,
    total_count: capabilities.length,
  };
}
