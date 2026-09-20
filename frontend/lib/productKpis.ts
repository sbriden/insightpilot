import {
  DataProductMetric,
} from "@/types/report";


const KPI_PRIORITY_PATTERNS: Array<{
  pattern: RegExp;
  weight: number;
}> = [
  {
    pattern: /total revenue|^revenue$/i,
    weight: 100,
  },
  {
    pattern: /profit|margin|ebitda/i,
    weight: 95,
  },
  {
    pattern: /growth|trend|change/i,
    weight: 90,
  },
  {
    pattern: /concentration|top 10|top customer|share/i,
    weight: 88,
  },
  {
    pattern: /^customers$|customer count/i,
    weight: 85,
  },
  {
    pattern: /average revenue|avg revenue|revenue per/i,
    weight: 80,
  },
  {
    pattern: /opportunity|potential|upside/i,
    weight: 75,
  },
  {
    pattern: /orders|transactions|units/i,
    weight: 70,
  },
  {
    pattern: /products per|cross-sell|attach/i,
    weight: 68,
  },
];


function normalizeMetricName(
  name: string
): string {

  return name
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");

}


export function formatMetricValue(
  value: unknown
): string {

  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  return String(value);

}


function scoreMetric(
  metric: DataProductMetric,
  index: number
): number {

  const name =
    metric.name ?? "";

  let score = 0;

  for (const {
    pattern,
    weight,
  } of KPI_PRIORITY_PATTERNS) {

    if (pattern.test(name)) {
      score = Math.max(
        score,
        weight
      );
    }

  }

  score += Math.max(
    0,
    24 - index
  );

  return score;

}


export function selectHeadlineKpis(
  metrics: DataProductMetric[] = [],
  limit = 6
): DataProductMetric[] {

  if (metrics.length === 0) {
    return [];
  }

  const ranked = metrics
    .map(
      (metric, index) => ({
        metric,
        score: scoreMetric(
          metric,
          index
        ),
        index,
      })
    )
    .sort(
      (left, right) => {

        if (
          right.score !== left.score
        ) {
          return (
            right.score - left.score
          );
        }

        return (
          left.index - right.index
        );

      }
    );

  const selected: DataProductMetric[] =
    [];

  const seen =
    new Set<string>();

  for (const {
    metric,
  } of ranked) {

    const key =
      normalizeMetricName(
        metric.name ?? metric.id
      );

    if (
      seen.has(key)
    ) {
      continue;
    }

    seen.add(key);
    selected.push(metric);

    if (
      selected.length >= limit
    ) {
      break;
    }

  }

  return selected;

}


export function getRemainingKpis(
  metrics: DataProductMetric[] = [],
  headline: DataProductMetric[] = []
): DataProductMetric[] {

  const headlineIds =
    new Set(
      headline.map(
        metric => metric.id
      )
    );

  return metrics.filter(
    metric =>
      !headlineIds.has(metric.id)
  );

}
