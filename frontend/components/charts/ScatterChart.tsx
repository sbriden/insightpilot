import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
} from "recharts";

type Props = {
    data: any[];
    visualization: any;
};

export default function BarChartView({
    data,
    visualization,
}: Props) {

    return (

        <div className="mt-6">

            <h4 className="font-semibold mb-3">

                {visualization.title}

            </h4>

            <ResponsiveContainer
                width="100%"
                height={350}
            >

                <ScatterChart>

                    <CartesianGrid/>

                    <XAxis
                        dataKey={visualization.x}
                    />

                    <YAxis
                        dataKey={visualization.y}
                    />

                    <Tooltip/>

                    <Scatter data={data}/>

                </ScatterChart>

            </ResponsiveContainer>

        </div>

    );
}