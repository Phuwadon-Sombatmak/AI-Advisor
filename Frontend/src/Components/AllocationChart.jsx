import React from "react";
import { useTranslation } from "react-i18next";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { formatCurrencyUSD } from "../utils/formatters";

const SECTOR_COLORS = {
  Technology: "#2563EB",
  "Information Technology": "#2563EB",
  Energy: "#16A34A",
  Healthcare: "#DC2626",
  Financial: "#F59E0B",
  Industrials: "#7C3AED",
  "Consumer Defensive": "#0F766E",
  "Consumer Cyclical": "#EA580C",
  Utilities: "#475569",
  Communication: "#0891B2",
  Other: "#64748B",
};

function getSectorColor(sector) {
  return SECTOR_COLORS[sector] || SECTOR_COLORS.Other;
}

export default function AllocationChart({ allocation = [], sectorExposure = [], dark = false, language = "en" }) {
  const { t } = useTranslation();
  const sortedAllocation = [...allocation].sort((a, b) => Number(b.marketValue || 0) - Number(a.marketValue || 0));
  const topFive = sortedAllocation.slice(0, 5);
  const others = sortedAllocation.slice(5);
  const othersValue = others.reduce((sum, item) => sum + Number(item.marketValue || 0), 0);
  const othersPct = others.reduce((sum, item) => sum + Number(item.allocationPct || 0), 0);
  const pieData = othersValue > 0
    ? [...topFive, { name: t("others"), symbol: "Others", sector: "Other", value: othersValue, marketValue: othersValue, allocationPct: othersPct }]
    : topFive;

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md space-y-5`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold`}>{t("portfolioAllocation")}</h3>
      <div className="h-64 min-w-0">
        <ResponsiveContainer width="100%" height={256} minWidth={0} minHeight={256}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              innerRadius={52}
              outerRadius={92}
              dataKey="value"
              nameKey="name"
              stroke="none"
              label={({ name, payload }) => `${name} ${Number(payload?.allocationPct || 0).toFixed(1)}%`}
            >
              {pieData.map((entry, index) => (
                <Cell key={`${entry.name}-${index}`} fill={getSectorColor(entry.sector)} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value, _name, item) => [
                `${formatCurrencyUSD(value, language)} • ${Number(item?.payload?.allocationPct || 0).toFixed(2)}%`,
                item?.payload?.name || "",
              ]}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 gap-2">
        {pieData.map((item) => (
          <div
            key={`${item.symbol}-${item.name}`}
            className={`flex items-center justify-between rounded-xl ${dark ? "bg-slate-900/60" : "bg-slate-50"} px-3 py-2 text-sm`}
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: getSectorColor(item.sector) }} />
              <span className={`${dark ? "text-slate-200" : "text-slate-700"} font-medium truncate`}>
                {item.symbol || item.name}
              </span>
            </div>
            <div className="text-right">
              <div className={`${dark ? "text-slate-100" : "text-slate-900"} font-semibold`}>
                {Number(item.allocationPct || 0).toFixed(2)}%
              </div>
              <div className="text-xs text-slate-500">{formatCurrencyUSD(item.marketValue || 0, language)}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-2">
        <h4 className={`${dark ? "text-slate-100" : "text-slate-900"} font-bold`}>{t("sectorExposure")}</h4>
        {sectorExposure.map((item, idx) => (
          <div key={`${item.name}-${idx}`}>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className={`font-medium ${item.isOverweight ? "text-rose-500" : "text-slate-500"}`}>{item.name}</span>
              <span className={`font-bold ${item.isOverweight ? "text-rose-500" : dark ? "text-slate-200" : "text-slate-700"}`}>
                {item.value}%{item.isOverweight ? ` • ${t("overweight")}` : ""}
              </span>
            </div>
            <div className={`h-2 rounded-full ${dark ? "bg-slate-800" : "bg-slate-200"} overflow-hidden`}>
              <div
                className="h-full rounded-full"
                style={{
                  width: `${item.value}%`,
                  background: item.isOverweight ? "linear-gradient(135deg,#ef4444,#b91c1c)" : "linear-gradient(135deg,#2563EB,#1E3A8A)",
                }}
              />
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {formatCurrencyUSD(item.marketValue || 0, language)}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
