import {
  BusinessConcept,
  ConceptIdentificationResult,
  ConceptRole,
  DatasetField,
  FieldMapping,
} from "@/types/dataset";

import {
  inferColumnDataType,
} from "@/lib/inferColumnDataType";

import {
  normalizeFieldName,
} from "@/lib/fieldMapping";


type ConceptDefinition = {
  concept: string;
  defaultRole: ConceptRole;
  keywords: string[];
};


/*
 * Catalog of business concepts InsightPilot can recognize from column names.
 * This layer is schema-agnostic and does not depend on product definitions.
 */

const CONCEPT_DEFINITIONS: ConceptDefinition[] = [
  {
    concept: "Customer",
    defaultRole: "entity",
    keywords: [
      "customer",
      "client",
      "account",
      "buyer",
      "subscriber",
      "patron",
      "member",
      "consumer",
      "user",
    ],
  },
  {
    concept: "Transaction/Order",
    defaultRole: "entity",
    keywords: [
      "order",
      "transaction",
      "invoice",
      "purchase",
      "sale",
      "booking",
      "receipt",
      "payment",
    ],
  },
  {
    concept: "Product",
    defaultRole: "entity",
    keywords: [
      "product",
      "item",
      "sku",
      "merchandise",
      "service",
      "goods",
      "article",
    ],
  },
  {
    concept: "Revenue",
    defaultRole: "measure",
    keywords: [
      "revenue",
      "sales",
      "amount",
      "income",
      "total",
      "price",
      "cost",
      "profit",
      "margin",
      "value",
      "spend",
      "fee",
      "salary",
      "wage",
      "compensation",
      "pay",
    ],
  },
  {
    concept: "Quantity",
    defaultRole: "measure",
    keywords: [
      "quantity",
      "qty",
      "units",
      "count",
      "volume",
      "unitsold",
    ],
  },
  {
    concept: "Geography",
    defaultRole: "geography",
    keywords: [
      "region",
      "country",
      "state",
      "city",
      "territory",
      "location",
      "geo",
      "zip",
      "postal",
      "province",
      "market",
      "area",
    ],
  },
  {
    concept: "Date",
    defaultRole: "date",
    keywords: [
      "date",
      "time",
      "timestamp",
      "datetime",
      "month",
      "year",
      "week",
      "period",
      "day",
    ],
  },
  {
    concept: "Status",
    defaultRole: "status",
    keywords: [
      "status",
      "stage",
      "phase",
      "condition",
    ],
  },
  {
    concept: "Category",
    defaultRole: "category",
    keywords: [
      "category",
      "type",
      "class",
      "segment",
      "group",
      "department",
      "division",
      "channel",
      "brand",
    ],
  },
  {
    concept: "Employee",
    defaultRole: "entity",
    keywords: [
      "employee",
      "staff",
      "worker",
      "associate",
      "rep",
      "representative",
      "agent",
    ],
  },
  {
    concept: "Supplier",
    defaultRole: "entity",
    keywords: [
      "supplier",
      "vendor",
      "provider",
      "manufacturer",
    ],
  },
  {
    concept: "Player",
    defaultRole: "entity",
    keywords: [
      "player",
      "player_id",
      "gsis",
      "gsis_id",
      "athlete",
      "roster",
    ],
  },
  {
    concept: "Team",
    defaultRole: "entity",
    keywords: [
      "team",
      "team_id",
      "franchise",
      "club",
      "opponent",
    ],
  },
  {
    concept: "Game",
    defaultRole: "entity",
    keywords: [
      "game",
      "game_id",
      "matchup",
      "contest",
    ],
  },
  {
    concept: "Season",
    defaultRole: "category",
    keywords: [
      "season",
      "season_year",
      "nfl_season",
    ],
  },
  {
    concept: "Week",
    defaultRole: "category",
    keywords: [
      "week",
      "week_number",
      "nfl_week",
      "game_week",
    ],
  },
  {
    concept: "Position",
    defaultRole: "category",
    keywords: [
      "position",
      "pos",
      "roster_position",
    ],
  },
  {
    concept: "FantasyPoints",
    defaultRole: "measure",
    keywords: [
      "fantasy_points",
      "fantasy_point",
      "fpts",
      "ppr",
      "half_ppr",
      "fantasy_score",
    ],
  },
  {
    concept: "Targets",
    defaultRole: "measure",
    keywords: [
      "targets",
      "target",
      "target_share",
      "targetshare",
    ],
  },
  {
    concept: "Carries",
    defaultRole: "measure",
    keywords: [
      "carries",
      "carry",
      "rush_attempts",
      "rushing_attempts",
    ],
  },
  {
    concept: "Routes",
    defaultRole: "measure",
    keywords: [
      "routes",
      "route",
      "routes_run",
      "route_participation",
    ],
  },
  {
    concept: "SignalType",
    defaultRole: "category",
    keywords: [
      "signal_type",
      "signaltype",
      "fantasy_signal",
    ],
  },
  {
    concept: "SignalStrength",
    defaultRole: "measure",
    keywords: [
      "signal_strength",
      "signalstrength",
      "signal_score",
    ],
  },
];


const IDENTIFIER_TOKENS = [
  "id",
  "key",
  "code",
  "number",
  "num",
  "no",
  "uuid",
  "guid",
];

const DATE_TOKENS = [
  "date",
  "time",
  "timestamp",
  "datetime",
  "month",
  "year",
  "week",
  "period",
  "day",
];

const MEASURE_TOKENS = [
  "revenue",
  "amount",
  "price",
  "cost",
  "profit",
  "margin",
  "value",
  "sales",
  "income",
  "total",
  "quantity",
  "qty",
  "units",
  "count",
  "volume",
  "spend",
  "fee",
  "salary",
  "wage",
  "compensation",
  "pay",
  "fantasy_points",
  "fpts",
  "ppr",
  "targets",
  "target_share",
  "carries",
  "routes",
  "signal_strength",
];

const GEOGRAPHY_TOKENS = [
  "region",
  "country",
  "state",
  "city",
  "territory",
  "location",
  "geo",
  "zip",
  "postal",
  "province",
  "market",
  "area",
];

const STATUS_TOKENS = [
  "status",
  "stage",
  "phase",
  "condition",
];

const CATEGORY_TOKENS = [
  "category",
  "type",
  "class",
  "segment",
  "group",
  "department",
  "division",
  "channel",
  "brand",
];


function tokenizeColumnName(
  normalizedName: string
): string[] {

  return normalizedName
    .replace(
      /([a-z])([0-9])/g,
      "$1 $2"
    )
    .replace(
      /([0-9])([a-z])/g,
      "$1 $2"
    )
    .split(/[^a-z0-9]+/)
    .filter(Boolean);

}


function containsToken(
  tokens: string[],
  candidates: string[]
): boolean {

  return candidates.some(
    candidate =>
      tokens.includes(candidate) ||
      tokens.some(
        token =>
          token.endsWith(candidate) ||
          token.startsWith(candidate)
      )
  );

}


function scoreConceptMatch(
  normalizedName: string,
  tokens: string[],
  definition: ConceptDefinition
): number {

  let bestScore = 0;

  for (const keyword of definition.keywords) {

    const normalizedKeyword =
      normalizeFieldName(keyword);


    if (
      normalizedName === normalizedKeyword
    ) {
      bestScore = Math.max(
        bestScore,
        0.98
      );
      continue;
    }

    if (
      tokens.includes(
        normalizedKeyword
      )
    ) {
      bestScore = Math.max(
        bestScore,
        0.92
      );
      continue;
    }

    if (
      normalizedName.includes(
        normalizedKeyword
      )
    ) {
      bestScore = Math.max(
        bestScore,
        0.82
      );
    }

  }

  return bestScore;

}


function resolveRole(
  tokens: string[],
  concept: string,
  defaultRole: ConceptRole
): ConceptRole {

  const hasDateToken =
    containsToken(
      tokens,
      DATE_TOKENS
    );

  const hasIdentifierToken =
    containsToken(
      tokens,
      IDENTIFIER_TOKENS
    );

  const hasMeasureToken =
    containsToken(
      tokens,
      MEASURE_TOKENS
    );

  const hasGeographyToken =
    containsToken(
      tokens,
      GEOGRAPHY_TOKENS
    );

  const hasStatusToken =
    containsToken(
      tokens,
      STATUS_TOKENS
    );

  const hasCategoryToken =
    containsToken(
      tokens,
      CATEGORY_TOKENS
    );


  if (hasDateToken) {
    return "date";
  }

  if (hasGeographyToken) {
    return "geography";
  }

  if (hasStatusToken) {
    return "status";
  }

  if (
    hasIdentifierToken &&
    !hasMeasureToken
  ) {
    return "identifier";
  }

  if (hasMeasureToken) {
    return "measure";
  }

  if (hasCategoryToken) {
    return "category";
  }

  if (
    concept === "Date"
  ) {
    return "date";
  }

  if (
    concept === "Geography"
  ) {
    return "geography";
  }

  if (
    concept === "Status"
  ) {
    return "status";
  }

  if (
    concept === "Category"
  ) {
    return "category";
  }

  if (
    concept === "Revenue" ||
    concept === "Quantity" ||
    concept === "FantasyPoints" ||
    concept === "Targets" ||
    concept === "Carries" ||
    concept === "Routes" ||
    concept === "SignalStrength"
  ) {
    return "measure";
  }

  if (
    concept === "Player" ||
    concept === "Team" ||
    concept === "Game"
  ) {
    return "entity";
  }

  return defaultRole;

}


function pickBestConcept(
  normalizedName: string,
  tokens: string[]
): {
  concept: string;
  defaultRole: ConceptRole;
  confidence: number;
} {

  let bestMatch = {
    concept: "Unknown",
    defaultRole: "category" as ConceptRole,
    confidence: 0.35,
  };


  for (
    const definition
    of CONCEPT_DEFINITIONS
  ) {

    const score =
      scoreConceptMatch(
        normalizedName,
        tokens,
        definition
      );


    if (
      score > bestMatch.confidence
    ) {

      bestMatch = {
        concept:
          definition.concept,
        defaultRole:
          definition.defaultRole,
        confidence:
          score,
      };

    }

  }


  /*
   * When a column name contains both a transaction keyword and a date
   * keyword (e.g. "Order Date"), prefer the Date concept because the
   * column value represents a point in time.
   */

  const dateScore =
    scoreConceptMatch(
      normalizedName,
      tokens,
      CONCEPT_DEFINITIONS.find(
        definition =>
          definition.concept === "Date"
      )!
    );

  const transactionScore =
    scoreConceptMatch(
      normalizedName,
      tokens,
      CONCEPT_DEFINITIONS.find(
        definition =>
          definition.concept ===
          "Transaction/Order"
      )!
    );


  if (
    dateScore >= 0.82 &&
    transactionScore >= 0.82 &&
    containsToken(
      tokens,
      DATE_TOKENS
    )
  ) {

    bestMatch = {
      concept: "Date",
      defaultRole: "date",
      confidence:
        Math.max(
          dateScore,
          transactionScore
        ),
    };

  }


  /*
   * Identifier-style transaction columns (e.g. "Order ID") should map
   * to Transaction/Order rather than Date.
   */

  if (
    transactionScore >= 0.82 &&
    containsToken(
      tokens,
      IDENTIFIER_TOKENS
    ) &&
    !containsToken(
      tokens,
      DATE_TOKENS
    )
  ) {

    bestMatch = {
      concept:
        "Transaction/Order",
      defaultRole: "entity",
      confidence:
        transactionScore,
    };

  }


  return bestMatch;

}


export function identifyColumnConcept(
  columnName: string,
  sampleValue?: string,
  declaredDataType?: string
): BusinessConcept {

  const normalizedName =
    normalizeFieldName(
      columnName
    );

  const tokens =
    tokenizeColumnName(
      normalizedName
    );


  const match =
    pickBestConcept(
      normalizedName,
      tokens
    );


  const role =
    resolveRole(
      tokens,
      match.concept,
      match.defaultRole
    );


  const dataType =
    declaredDataType ??
    inferColumnDataType(
      columnName,
      sampleValue
    );


  return {
    concept:
      match.concept,
    sourceColumn:
      columnName,
    dataType,
    confidence:
      Math.round(
        match.confidence *
          100
      ) / 100,
    role,
  };

}


function buildUploadedToSemanticMap(
  fieldMappings: FieldMapping[]
): Map<string, string> {

  const map =
    new Map<string, string>();

  if (
    !Array.isArray(fieldMappings)
  ) {
    return map;
  }


  for (
    const mapping
    of fieldMappings
  ) {

    if (
      mapping.uploadedField
    ) {

      map.set(
        mapping.uploadedField,
        mapping.requiredField
      );

    }

  }


  return map;

}


export function identifyColumnConceptFromSemanticField(
  semanticFieldName: string,
  sourceColumn: string,
  sampleValue?: string,
  declaredDataType?: string
): BusinessConcept {

  const fromSemantic =
    identifyColumnConcept(
      semanticFieldName,
      sampleValue,
      declaredDataType
    );


  return {
    ...fromSemantic,
    sourceColumn,
    confidence: 1,
  };

}


export function identifyBusinessConcepts(
  fields: DatasetField[],
  sampleValues?: Record<string, string>,
  fieldMappings: FieldMapping[] = []
): ConceptIdentificationResult {

  if (
    !Array.isArray(fields)
  ) {

    return {
      concepts: [],
      columnCount: 0,
      identifiedCount: 0,
    };

  }


  const semanticByUploadedColumn =
    buildUploadedToSemanticMap(
      fieldMappings
    );


  const concepts =
    fields.map(
      field => {

        const semanticField =
          semanticByUploadedColumn.get(
            field.name
          );


        if (semanticField) {

          return identifyColumnConceptFromSemanticField(
            semanticField,
            field.name,
            sampleValues?.[
              field.name
            ],
            field.dataType
          );

        }


        return identifyColumnConcept(
          field.name,
          sampleValues?.[
            field.name
          ],
          field.dataType
        );

      }
    );


  const identifiedCount =
    concepts.filter(
      concept =>
        concept.concept !==
          "Unknown" &&
        concept.confidence >=
          0.65
    ).length;


  return {
    concepts,
    columnCount:
      fields.length,
    identifiedCount,
  };

}
