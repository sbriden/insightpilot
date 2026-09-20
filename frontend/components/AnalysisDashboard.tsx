import ChartRenderer from "./charts/ChartRenderer";
import PromotedInsightsPanel from "@/components/products/PromotedInsightsPanel";

import {
  CandidateFinding,
  PromotedInsight,
} from "@/types/report";

type MetricCard = {
  id: string;
  title: string;
  value: string;
  subtitle?: string;
};

type Visualization = {
  id: string;
  [key: string]: unknown;
};

type Insight = {
  severity?: string;
  priority?: string;
  category?: string;
  message: string;
  title?: string;
  what_happened?: string;
  why_it_matters?: string;
  recommended_action?: string;
  id?: string;
  rule_id?: string;
};

export interface AnalysisDashboard {
  id: string;
  title: string;
  summary: string;
  metrics: MetricCard[];
  visualizations: Visualization[];
  insights: Insight[];
  candidate_findings?: CandidateFinding[];
  promoted_insights?: PromotedInsight[];
  actions: string[];
  datasets: Record<string, any[]>;
}

type Props = {
  dashboard: AnalysisDashboard;
  embedded?: boolean;
  hideHeader?: boolean;
};

export default function AnalysisDashboard({
  dashboard,
  embedded = false,
  hideHeader = false,
}: Props) {

  const promotedInsights =
    dashboard.promoted_insights ?? [];

  return (

    <div className={embedded ? "space-y-8" : "rounded-xl border bg-white p-6 shadow-sm"}>

      {!hideHeader && (

        <>

          <h2 className="text-xl font-bold">
            {dashboard.title}
          </h2>

          <p className="mt-2 text-gray-600">
            {dashboard.summary}
          </p>

        </>

      )}

      <div className={`${hideHeader ? "" : "mt-6 "}grid grid-cols-2 md:grid-cols-5 gap-4`}>

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

        <PromotedInsightsPanel
          insights={promotedInsights}
          analysisType={dashboard.id}
        />

      </div>

      <div className="mt-8 space-y-8">

        {(dashboard.visualizations ?? []).map(
          (viz: any) => (

            <ChartRenderer
              key={viz.id}
              visualization={viz}
              datasets={
                dashboard.datasets
              }
            />

          )
        )}

      </div>

    </div>

  );

}
