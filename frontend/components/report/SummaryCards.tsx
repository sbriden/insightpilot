import { Card, CardContent } from "@/components/ui/card";
import { DatasetSummary } from "@/types/report";

interface SummaryCardsProps {
  summary: DatasetSummary;
}

export default function SummaryCards({
  summary,
}: SummaryCardsProps) {
  const cards = [
    {
      label: "Rows",
      value: summary.rows.toLocaleString(),
    },
    {
      label: "Columns",
      value: summary.columns,
    },
    {
      label: "Data Quality",
      value: `${summary.data_quality_score}%`,
    },
  ];

  return (
    <div className="mt-8 grid gap-4 md:grid-cols-3">
      {cards.map((card) => (
        <Card key={card.label}>
          <CardContent className="p-6">
            <p className="text-sm text-muted-foreground">
              {card.label}
            </p>

            <p className="mt-2 text-3xl font-bold">
              {card.value}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}