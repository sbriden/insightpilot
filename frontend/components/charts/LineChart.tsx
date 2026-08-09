"use client";

import {
    ResponsiveContainer,
    CartesianGrid,
    XAxis,
    YAxis,
    Tooltip,
    Line,
    LineChart as RechartsLineChart,
} from "recharts";

interface LineChartProps {
    data: any[];
    x: string;
    y: string;
}

export default function LineChartView({
    data,
    x,
    y,
}: LineChartProps) {

    return (
        <ResponsiveContainer
            width="100%"
            height={300}
        >
            <RechartsLineChart data={data}>

                <CartesianGrid
                    strokeDasharray="3 3"
                />

                <XAxis
                    dataKey={x}
                />

                <YAxis />

                <Tooltip />

                <Line
                    type="monotone"
                    dataKey={y}
                    dot={false}
                />

            </RechartsLineChart>
        </ResponsiveContainer>
    );
}