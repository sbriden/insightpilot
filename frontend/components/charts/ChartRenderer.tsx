import BarChartView from "./BarChart";
import LineChartView from "./LineChart";
import ScatterChartView from "./ScatterChart";
import HistogramChartView from "./HistogramChart";

type Props = {
    visualization: any;
    datasets: Record<string, any[]>;
};

export default function ChartRenderer({
    visualization,
    datasets,
}: Props) {

    const data =
        datasets[
            visualization.dataset
        ] ?? [];

    switch (visualization.chart) {

        case "bar":
            return (
                <BarChartView
                    data={data}
                    visualization={visualization}
                />
            );

        case "line":
            return (
                <LineChartView
                    data={data}
                    visualization={visualization}
                />
            );

        case "scatter":
            return (
                <ScatterChartView
                    data={data}
                    visualization={visualization}
                />
            );

        case "histogram":
            return (
                <HistogramChartView
                    data={data}
                    visualization={visualization}
                />
            );

        default:
            return null;
    }
}