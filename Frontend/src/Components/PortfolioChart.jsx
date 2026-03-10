import React from "react";
import { useTranslation } from "react-i18next";
import { AreaChart, Area, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const RANGES = ["1M", "3M", "6M", "1Y"];

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

      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="portfolioGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2563EB" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#2563EB" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke={dark ? "#1e293b" : "#e2e8f0"} />
            <XAxis dataKey="label" stroke={dark ? "#94a3b8" : "#64748b"} tickLine={false} axisLine={false} />
            <YAxis stroke={dark ? "#94a3b8" : "#64748b"} tickLine={false} axisLine={false} width={60} />
            <Tooltip />
            <Area type="monotone" dataKey="value" stroke="#2563EB" fill="url(#portfolioGradient)" strokeWidth={3} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
