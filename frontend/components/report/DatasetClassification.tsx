import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DatasetClassification as DatasetClassificationType } from "@/types/report";

interface Props {
  classification: DatasetClassificationType;
}

export default function DatasetClassification({
  classification,
}: Props) {
  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>
          Dataset Classification
        </CardTitle>
      </CardHeader>

      <CardContent className="space-y-4">

        <div>
          <p className="text-sm text-muted-foreground">
            Dataset Type
          </p>

          <p className="text-2xl font-bold">
            {classification.type}
          </p>
        </div>


        <div>
          <p className="text-sm text-muted-foreground">
            Confidence
          </p>

          <p className="text-xl font-semibold">
            {classification.confidence}%
          </p>
        </div>


        {classification.matched_fields.length > 0 && (
          <div>
            <p className="mb-2 text-sm text-muted-foreground">
              Matched Fields
            </p>

            <ul className="list-disc space-y-1 pl-5">
              {classification.matched_fields.map((field) => (
                <li key={field}>
                  {field}
                </li>
              ))}
            </ul>
          </div>
        )}

      </CardContent>
    </Card>
  );
}