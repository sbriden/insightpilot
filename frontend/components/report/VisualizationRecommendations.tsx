import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { VisualizationRecommendation } from "@/types/report";


interface Props {
  visualizations: VisualizationRecommendation[];
}


export default function VisualizationRecommendations({
  visualizations,
}: Props) {

  if (!visualizations?.length) {
    return null;
  }


  return (
    <Card className="mt-6">

      <CardHeader>
        <CardTitle>
          Recommended Visualizations
        </CardTitle>
      </CardHeader>


      <CardContent>

        <div className="grid gap-4">

          {visualizations.map((viz) => (

            <div
              key={viz.id}
              className="rounded border p-4"
            >

              <h3 className="font-semibold">
                {viz.title}
              </h3>


              <p className="mt-2 text-sm text-muted-foreground">
                {viz.reason}
              </p>


              <div className="mt-3 text-sm">

                <p>
                  Chart:
                  <span className="ml-2 font-medium">
                    {viz.chart}
                  </span>
                </p>


                <p>
                  X:
                  <span className="ml-2 font-medium">
                    {viz.x}
                  </span>
                </p>


                {viz.y && (
                  <p>
                    Y:
                    <span className="ml-2 font-medium">
                      {viz.y}
                    </span>
                  </p>
                )}

              </div>

            </div>

          ))}

        </div>

      </CardContent>

    </Card>
  );
}