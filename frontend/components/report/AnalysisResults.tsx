import { DatasetAnalysis } from "@/types/report";

import SummaryCards from "./SummaryCards";
import ExecutiveSummary from "./ExecutiveSummary";
import DatasetClassification from "./DatasetClassification";
import Recommendations from "./Recommendations";
import Insights from "./Insights";
import ColumnExplorer from "./ColumnExplorer";
import ExecutiveBrief from "./ExecutiveBrief";

import AnalysisDashboard from "@/components/AnalysisDashboard";

type Props = {
  result: DatasetAnalysis;
  executiveBrief: any;
  briefLoading: boolean;
};

export default function AnalysisResults({
  result,
}: Props) {
  return (
    <>
      <h2 className="text-2xl font-semibold">
        Data Profile
      </h2>

      <SummaryCards
        summary={result.profile.summary}
      />

      <ExecutiveBrief
            brief={
                result.executive_brief
            }
        
            loading={false}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">

        <ExecutiveSummary
          profile={result.profile}
        />

        <DatasetClassification
          classification={
            result.classification
          }
        />

        <Recommendations
          recommendations={
            result.recommendations
          }
        />

        <Insights
          insights={result.insights}
        />

      </div>

      <ColumnExplorer
        profile={result.profile}
      />

      {result.analysis_dashboards?.map(
        (dashboard: any) => (
          <AnalysisDashboard
            key={dashboard.id}
            dashboard={dashboard}
          />
        )
      )}
    </>
  );
}