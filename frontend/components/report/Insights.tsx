import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
  } from "@/components/ui/card";
  
  import { Insight } from "@/types/report";
  
  interface Props {
    insights: Insight[];
  }
  
  function severityColor(severity: string) {
    switch (severity) {
      case "high":
        return "bg-red-100 text-red-800 border-red-200";
      case "medium":
        return "bg-yellow-100 text-yellow-800 border-yellow-200";
      default:
        return "bg-green-100 text-green-800 border-green-200";
    }
  }
  
  function severityIcon(severity: string) {
    switch (severity) {
      case "high":
        return "🔴";
      case "medium":
        return "🟡";
      default:
        return "🟢";
    }
  }
  
  export default function Insights({ insights }: Props) {
    if (!insights.length) {
      return null;
    }
  
    return (
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Key Insights</CardTitle>
        </CardHeader>
  
        <CardContent className="space-y-4">
          {insights.map((insight, index) => (
            <div
              key={index}
              className={`rounded-lg border p-4 ${severityColor(
                insight.severity
              )}`}
            >
              <div className="flex items-center gap-2">
                <span>{severityIcon(insight.severity)}</span>
  
                <h3 className="font-semibold">
                  {insight.title}
                </h3>
              </div>
  
              <p className="mt-2 text-sm">
                {insight.description}
              </p>
  
              <div className="mt-3 flex items-center justify-between text-xs opacity-80">
                <span>{insight.category}</span>
                <span className="uppercase">
                  {insight.severity}
                </span>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }