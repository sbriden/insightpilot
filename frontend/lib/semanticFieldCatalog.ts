export interface SemanticFieldCatalogEntry {
  field: string;

  definition: string;

  keyRelationships: string;

  typicalBusinessQuestions: string[];
}


export const SEMANTIC_FIELD_CATALOG: SemanticFieldCatalogEntry[] = [
  {
    field: "customer_id",
    definition:
      "Unique identifier for a customer account. Represents the entity to which sales are attributed and should be used as the primary key for customer-level analysis.",
    keyRelationships:
      "Links to customer_name, customer_segment, region, and transactions. One customer can have many transactions.",
    typicalBusinessQuestions: [
      "Which customers generate the most revenue?",
      "Which customers are growing or declining?",
      "What is customer concentration?",
    ],
  },
  {
    field: "revenue",
    definition:
      "Monetary value generated from selling products to customers. Represents the top-line sales measure for a transaction.",
    keyRelationships:
      "Aggregates across customer, product, sales_rep, region, and transaction_date. Can be compared with cost to calculate gross profit and margin.",
    typicalBusinessQuestions: [
      "How much are we selling?",
      "Where is revenue growing?",
      "Which products, customers, reps, or regions drive revenue?",
    ],
  },
  {
    field: "product_id",
    definition:
      "Unique identifier for a product or SKU. Represents the specific product associated with a sales transaction.",
    keyRelationships:
      "Links to product_name and product_category. One product can appear in many transactions.",
    typicalBusinessQuestions: [
      "Which products sell the most?",
      "Which products generate the most revenue or profit?",
    ],
  },
  {
    field: "transaction_date",
    definition:
      "Date when the sales transaction occurred. Represents the time dimension for measuring sales activity and trends.",
    keyRelationships:
      "Provides the time axis for revenue, cost, and quantity. Supports daily, monthly, quarterly, and yearly aggregation.",
    typicalBusinessQuestions: [
      "Is revenue growing?",
      "Are there seasonal patterns?",
      "When did sales increase or decline?",
    ],
  },
  {
    field: "customer_name",
    definition:
      "Business or individual name associated with the customer account. Provides the human-readable representation of customer_id.",
    keyRelationships:
      "Many transactions can belong to one customer. Closely related to customer_segment and region.",
    typicalBusinessQuestions: [
      "Who are our largest customers?",
      "Which customers are buying specific products?",
    ],
  },
  {
    field: "customer_segment",
    definition:
      "Business classification that groups customers with similar characteristics, value, size, or purchasing behavior. Represents a customer-level segmentation dimension.",
    keyRelationships:
      "Groups customers and their transactions. Used to segment revenue, quantity, cost, and profitability.",
    typicalBusinessQuestions: [
      "Which segments are most valuable?",
      "Which segments are growing?",
      "Where should sales resources be focused?",
    ],
  },
  {
    field: "cost",
    definition:
      "Direct cost associated with the products sold in a transaction. Represents the cost basis used to evaluate the economic performance of a sale.",
    keyRelationships:
      "Directly relates to revenue. Combined with revenue to calculate gross profit and gross margin. Can be analyzed by customer, product, rep, region, and time.",
    typicalBusinessQuestions: [
      "Which products are most profitable?",
      "Where are margins under pressure?",
      "Which customers generate the most profit?",
    ],
  },
  {
    field: "sales_rep",
    definition:
      "Salesperson responsible for the customer relationship or transaction. Represents the sales ownership dimension.",
    keyRelationships:
      "Transactions can be attributed to a sales_rep, who may sell across multiple customers, products, segments, and regions.",
    typicalBusinessQuestions: [
      "Which reps generate the most revenue?",
      "Who has the strongest margins?",
      "Which reps have the best customer/product mix?",
    ],
  },
  {
    field: "product_name",
    definition:
      "Human-readable name of the product or SKU. Provides the business-facing representation of product_id.",
    keyRelationships:
      "Related to product_id and product_category. Products generate revenue, quantity, and cost through transactions.",
    typicalBusinessQuestions: [
      "Which products are top sellers?",
      "Which products are declining?",
      "What products drive revenue or margin?",
    ],
  },
  {
    field: "product_category",
    definition:
      "Business grouping of related products. Represents a higher-level product hierarchy used to analyze product portfolio performance.",
    keyRelationships:
      "Parent-level relationship to products. Can be used to aggregate revenue, quantity, cost, and profitability.",
    typicalBusinessQuestions: [
      "Which categories drive growth?",
      "Which categories have the strongest margins?",
      "What is our product mix?",
    ],
  },
  {
    field: "quantity",
    definition:
      "Number of product units sold in a transaction. Represents sales volume independent of the monetary value of the products.",
    keyRelationships:
      "Related to product, customer, sales_rep, region, and transaction_date. Can be combined with revenue to derive average selling price.",
    typicalBusinessQuestions: [
      "Are we selling more units?",
      "Which products have the highest volume?",
      "Is revenue growth driven by volume or price?",
    ],
  },
  {
    field: "region",
    definition:
      "Geographic sales territory associated with the customer or transaction. Represents the geographic dimension for evaluating market performance.",
    keyRelationships:
      "Groups customers and/or transactions geographically. Used to analyze revenue, quantity, cost, and profitability.",
    typicalBusinessQuestions: [
      "Which regions perform best?",
      "Where is growth occurring?",
      "Which regions have margin or sales-performance issues?",
    ],
  },
];


function normalizeFieldKey(
  value: string
): string {

  return String(value ?? "")
    .toLowerCase()
    .replace(
      /[^a-z0-9]/g,
      ""
    );

}


const CATALOG_BY_FIELD = new Map(
  SEMANTIC_FIELD_CATALOG.map(
    entry => [
      normalizeFieldKey(
        entry.field
      ),
      entry,
    ]
  )
);


export function getSemanticFieldCatalogEntry(
  field: string
): SemanticFieldCatalogEntry | undefined {

  return CATALOG_BY_FIELD.get(
    normalizeFieldKey(field)
  );

}


export function resolveSemanticFieldMetadata(
  field: string,
  fallbackDefinition?: string
): {
  definition: string;
  keyRelationships?: string;
  typicalBusinessQuestions?: string[];
} {

  const catalogEntry =
    getSemanticFieldCatalogEntry(
      field
    );


  if (catalogEntry) {
    return {
      definition:
        catalogEntry.definition,
      keyRelationships:
        catalogEntry.keyRelationships,
      typicalBusinessQuestions:
        catalogEntry.typicalBusinessQuestions,
    };
  }


  if (
    fallbackDefinition?.trim()
  ) {
    return {
      definition:
        fallbackDefinition.trim(),
    };
  }


  return {
    definition:
      `The ${field
        .replace(/_/g, " ")
        .replace(
          /\b\w/g,
          char =>
            char.toUpperCase()
        )} field used in data product analyses.`,
  };

}
