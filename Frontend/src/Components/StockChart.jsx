import React, { useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Area,
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function tooltipDate(v) {
  if (!v) return "-";
  return String(v);
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  const pricePoint = payload.find((p) => p.dataKey === "price");
  const volumePoint = payload.find((p) => p.dataKey === "volume");
  const dailyChange = pricePoint?.payload?.dailyChangePct ?? 0;
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-lg text-xs">
      <p className="font-semibold text-slate-700 mb-1">{tooltipDate(label)}</p>
      <p className="text-slate-600">Price: ${Number(pricePoint?.value || 0).toFixed(2)}</p>
      <p className={`${dailyChange >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"} font-semibold`}>
        Daily: {dailyChange >= 0 ? "+" : ""}{Number(dailyChange).toFixed(2)}%
      </p>
      {volumePoint ? <p className="text-slate-500">Volume: {Number(volumePoint.value || 0).toLocaleString()}</p> : null}
    </div>
  );
}

export default function StockChart({ data = [], returnPct = 0, dark = false }) {
  const { t } = useTranslation();
  const positive = Number(returnPct) >= 0;
  const lineColor = positive ? "#22C55E" : "#EF4444";
  const fillId = positive ? "priceFillPos" : "priceFillNeg";

  const prepared = useMemo(() => data.map((d) => ({ ...d })), [data]);

  if (!prepared.length) {
    const noChartLabel = t("noChartData");
    return (
      <div className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-100 text-slate-500"} p-6 rounded-3xl border shadow-sm`}>
        {noChartLabel === "noChartData" ? "No chart data" : noChartLabel}
      </div>
    );
  }

  return (
    <div className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-100"} p-6 rounded-3xl border shadow-sm`}>
      <div className="h-[420px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={prepared} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
            <defs>
              <linearGradient id="priceFillPos" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22C55E" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#22C55E" stopOpacity={0.02} />
              </linearGradient>
              <linearGradient id="priceFillNeg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#EF4444" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#EF4444" stopOpacity={0.02} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" stroke={dark ? "#1e293b" : "#e2e8f0"} />
            <XAxis dataKey="date" tick={{ fill: dark ? "#94a3b8" : "#64748b", fontSize: 11 }} minTickGap={24} />
            <YAxis yAxisId="price" orientation="right" tick={{ fill: dark ? "#94a3b8" : "#64748b", fontSize: 11 }} width={70} domain={["auto", "auto"]} />
            <YAxis yAxisId="volume" orientation="left" tick={false} axisLine={false} width={8} domain={[0, "dataMax"]} />
            <Tooltip content={<CustomTooltip />} />
            <Legend />

            <Bar yAxisId="volume" dataKey="volume" name={t("volume")} fill="#94A3B8" opacity={0.35} barSize={6} />

            <Area
              yAxisId="price"
              type="monotone"
              dataKey="price"
              stroke={lineColor}
              fill={`url(#${fillId})`}
              strokeWidth={2.5}
              dot={false}
              isAnimationActive
              animationDuration={450}
              name={t("price")}
            />

            <Line yAxisId="price" type="monotone" dataKey="ma50" name="MA50" stroke="#2563EB" strokeWidth={1.8} dot={false} isAnimationActive animationDuration={450} />
            <Line yAxisId="price" type="monotone" dataKey="ma200" name="MA200" stroke="#F59E0B" strokeWidth={1.8} dot={false} isAnimationActive animationDuration={450} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
