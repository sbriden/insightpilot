import ChartRenderer from "./charts/ChartRenderer";

export interface AnalysisDashboard {
  id: string;
  title: string;
  summary: string;
  metrics: MetricCard[];
  visualizations: Visualization[];
  insights: Insight[];
  actions: string[];
  datasets: Record<string, unknown>;
}

type Props = {
  dashboard: AnalysisDashboard;
};
  
  export default function AnalysisDashboard({
    dashboard,
  }: Props) {

    console.log("Dashboard object:", dashboard);
    
    return (
  
      <div className="rounded-xl border bg-white p-6 shadow-sm">
  
        <h2 className="text-xl font-bold">
          {dashboard.title}
        </h2>
  
        <p className="mt-2 text-gray-600">
          {dashboard.summary}
        </p>

        <div className="mt-6 grid grid-cols-2 md:grid-cols-5 gap-4">

            {(dashboard.metrics ?? []).map((metric: any) => (

              <div
                key={metric.id}
                className="rounded-lg border p-4"
              >

                <div className="text-sm text-gray-500">
                  {metric.title}
                </div>

                <div className="mt-1 text-2xl font-semibold">
                  {metric.value}
                </div>

                {metric.subtitle && (

                  <div className="text-xs text-gray-400">

                    {metric.subtitle}

                  </div>

                )}

              </div>

            ))}

          </div>

          <div className="mt-8">

                <h3 className="font-semibold">

                    Insights

                </h3>

                <ul className="mt-3 space-y-2">

                    {(dashboard.insights ?? []).map((insight: any) => (

                    <li key={insight.message}>

                        • {insight.message}

                    </li>

                    ))}

                </ul>

            </div>

            <div className="mt-8">

                <h3 className="font-semibold">

                    Recommended Actions

                </h3>

                <ul className="mt-3 space-y-2">

                    {(dashboard.actions ?? []).map((action: string) => (

                    <li key={action}>

                        ✓ {action}

                    </li>

                    ))}

                </ul>

            </div>

            <div className="space-y-8 mt-8">

                {(dashboard.visualizations ?? []).map((viz: any) => (

                    <ChartRenderer
                        key={viz.id}
                        visualization={viz}
                        datasets={dashboard.datasets}
                    />

                ))}

            </div>
                
      </div>
  
    );
  }