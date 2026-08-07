import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DatasetProfile } from "@/types/report";

interface Props {
  profile: DatasetProfile;
}

export default function ExecutiveSummary({ profile }: Props) {
  const { rows, columns, data_quality_score } = profile.summary;

  const numeric = profile.columns.numeric.length;
  const categorical = profile.columns.categorical.length;

  return (
    <Card className="mt-6">
      <CardHeader>
        <CardTitle>Dataset Overview</CardTitle>
      </CardHeader>

      <CardContent className="space-y-3">
        <p>
          Your dataset contains{" "}
          <strong>{rows.toLocaleString()}</strong> records across{" "}
          <strong>{columns}</strong> columns.
        </p>

        <p>
          Overall data quality is{" "}
          <strong>{data_quality_score}%</strong>.
        </p>

        <p>
          The dataset includes{" "}
          <strong>{numeric}</strong> numeric measures and{" "}
          <strong>{categorical}</strong> categorical dimensions.
        </p>
      </CardContent>
    </Card>
  );
}