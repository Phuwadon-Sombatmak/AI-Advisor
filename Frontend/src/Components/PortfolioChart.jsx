import React from "react";
import { useTranslation } from "react-i18next";
import { CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, AreaChart, Area, Line, Legend } from "recharts";

const RANGES = ["1M", "3M", "6M", "1Y"];

function CustomTooltip({ active, payload, label, dark, t }) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload || {};
  const portfolioReturn = Number(point?.portfolioReturnPct || 0);
  const spyReturn = Number(point?.spyReturnPct || 0);
  const difference = Number(point?.outperformancePct || 0);

  return (
    <div className={`rounded-xl border px-3 py-2 shadow-lg text-xs ${dark ? "bg-slate-900 border-slate-700 text-slate-100" : "bg-white border-slate-200 text-slate-800"}`}>
      <div className="mb-2 font-semibold">{label}</div>
      <div className="space-y-1">
        <div className="flex items-center justify-between gap-4">
          <span>{t("portfolioReturn")}</span>
          <span className="font-semibold">{portfolioReturn >= 0 ? "+" : ""}{portfolioReturn.toFixed(2)}%</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span>SPY {t("returnLabel")}</span>
          <span className="font-semibold">{spyReturn >= 0 ? "+" : ""}{spyReturn.toFixed(2)}%</span>
        </div>
        <div className="flex items-center justify-between gap-4">
          <span>{t("differenceLabel")}</span>
          <span className={`font-semibold ${difference >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
            {difference >= 0 ? "+" : ""}{difference.toFixed(2)}%
          </span>
        </div>
      </div>
    </div>
  );
}

export default function PortfolioChart({ data = [], range = "1M", onRangeChange = () => {}, dark = false }) {
  const { t } = useTranslation();

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md`}>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold`}>{t("portfolioPerformance")}</h3>
        <div className="flex items-center gap-2">
          {RANGES.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => onRangeChange(r)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                range === r ? "text-white" : dark ? "bg-slate-800 text-slate-300" : "bg-slate-100 text-slate-700"
              }`}
              style={range === r ? { background: "linear-gradient(135deg,#2563EB,#1E3A8A)" } : undefined}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="h-72 min-w-0">
        <ResponsiveContainer width="100%" height={288} minWidth={0} minHeight={288}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="portfolioGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2563EB" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#2563EB" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={dark ? "#1e293b" : "#e2e8f0"} />
            <XAxis dataKey="label" stroke={dark ? "#94a3b8" : "#64748b"} tickLine={false} axisLine={false} />
            <YAxis
              stroke={dark ? "#94a3b8" : "#64748b"}
              tickLine={false}
              axisLine={false}
              width={64}
              domain={["dataMin - 2", "dataMax + 2"]}
              tickFormatter={(value) => `${Number(value || 0).toFixed(0)}`}
            />
            <Tooltip
              content={<CustomTooltip dark={dark} t={t} />}
            />
            <Legend
              formatter={(value) =>
                value === "portfolioIndex"
                  ? `${t("portfolioReturn")} (100)`
                  : value === "spyIndex"
                    ? `${t("benchmark")}: SPY`
                    : value
              }
            />
            <Area type="monotone" dataKey="portfolioIndex" stroke="#2563EB" fill="url(#portfolioGradient)" strokeWidth={3} />
            {data.some((row) => row?.spyIndex !== undefined) ? (
              <Line type="monotone" dataKey="spyIndex" stroke="#F59E0B" strokeWidth={2} dot={false} />
            ) : null}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
