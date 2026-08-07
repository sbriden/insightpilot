import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
  } from "@/components/ui/card";
  
  import { Recommendation } from "@/types/report";
  
  interface Props {
    recommendations: Recommendation[];
  }
  
  export default function Recommendations({
    recommendations,
  }: Props) {
    return (
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>
            Recommended Analysis
          </CardTitle>
        </CardHeader>
  
        <CardContent className="space-y-4">
          {recommendations.map((recommendation) => (
            <div
              key={recommendation.id}
              className="rounded-lg border p-4"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">
                  {recommendation.title}
                </h3>
  
                <span className="rounded bg-slate-100 px-2 py-1 text-xs">
                  {recommendation.priority}
                </span>
              </div>
  
              <p className="mt-2 text-sm text-muted-foreground">
                {recommendation.description}
              </p>
  
              <p className="mt-2 text-xs text-slate-500">
                {recommendation.category}
              </p>
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }