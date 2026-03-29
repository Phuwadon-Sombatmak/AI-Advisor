import React from "react";
import { useTranslation } from "react-i18next";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { formatCurrencyUSD } from "../utils/formatters";

const STOCK_COLOR_PALETTE = [
  "#2563EB",
  "#16A34A",
  "#F59E0B",
  "#DC2626",
  "#7C3AED",
  "#0891B2",
  "#EA580C",
  "#0F766E",
  "#DB2777",
  "#475569",
];

function getStockColor(symbol = "", index = 0) {
  const token = String(symbol || "").trim().toUpperCase();
  if (!token) return STOCK_COLOR_PALETTE[index % STOCK_COLOR_PALETTE.length];
  const hash = [...token].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return STOCK_COLOR_PALETTE[hash % STOCK_COLOR_PALETTE.length];
}

function getAllocationStatus(item, largestPct) {
  const pct = Number(item?.allocationPct || 0);
  if (pct >= Math.max(25, largestPct * 0.7)) return "overweight";
  if (pct <= 5) return "underweight";
  return "normal";
}

function getExposureRiskLevel(value) {
  const pct = Number(value || 0);
  if (pct >= 45) return "high";
  if (pct >= 25) return "medium";
  return "low";
}

function renderCenterText({ viewBox, totalPortfolioValue, largestHoldingPct, language, dark, t }) {
  const { cx, cy } = viewBox || {};
  if (!Number.isFinite(cx) || !Number.isFinite(cy)) return null;

  return (
    <g>
      <text
        x={cx}
        y={cy - 18}
        textAnchor="middle"
        className={`fill-current ${dark ? "text-slate-400" : "text-slate-500"}`}
        style={{ fontSize: "12px", fontWeight: 600 }}
      >
        {t("totalValue")}
      </text>
      <text
        x={cx}
        y={cy + 2}
        textAnchor="middle"
        className={`fill-current ${dark ? "text-slate-100" : "text-slate-900"}`}
        style={{ fontSize: "16px", fontWeight: 700 }}
      >
        {formatCurrencyUSD(totalPortfolioValue, language)}
      </text>
      <text
        x={cx}
        y={cy + 22}
        textAnchor="middle"
        className={`fill-current ${dark ? "text-slate-400" : "text-slate-500"}`}
        style={{ fontSize: "11px", fontWeight: 600 }}
      >
        {t("largestHoldingPctLabel", { percentage: largestHoldingPct.toFixed(1) })}
      </text>
    </g>
  );
}

export default function AllocationChart({ allocation = [], sectorExposure = [], dark = false, language = "en" }) {
  const { t } = useTranslation();

  const sortedAllocation = [...allocation].sort((a, b) => Number(b.marketValue || 0) - Number(a.marketValue || 0));
  const totalPortfolioValue = sortedAllocation.reduce((sum, item) => sum + Number(item.marketValue || 0), 0);
  const largestHolding = sortedAllocation[0] || null;
  const largestHoldingPct = Number(largestHolding?.allocationPct || 0);

  const topFive = sortedAllocation.slice(0, 5);
  const others = sortedAllocation.slice(5);
  const othersValue = others.reduce((sum, item) => sum + Number(item.marketValue || 0), 0);
  const othersPct = others.reduce((sum, item) => sum + Number(item.allocationPct || 0), 0);

  const pieData = othersValue > 0
    ? [...topFive, { name: t("others"), symbol: "Others", sector: "Other", value: othersValue, marketValue: othersValue, allocationPct: othersPct }]
    : topFive;

  const topSector = [...sectorExposure].sort((a, b) => Number(b.value || 0) - Number(a.value || 0))[0] || null;
  const topSectorPct = Number(topSector?.value || 0);
  const concentrationBanner = topSector
    ? t("portfolioConcentrationBanner", { sector: topSector.name, percentage: topSectorPct.toFixed(0) })
    : t("portfolioAllocationBalanced");

  const sectorActionText = (item) => {
    const pct = Number(item?.value || 0);
    if (pct >= 45) return t("reduceExposure");
    if (pct <= 10) return t("buildExposure");
    return t("maintainExposure");
  };

  const sectorRiskLabel = (item) => {
    const level = getExposureRiskLevel(item?.value);
    if (level === "high") return t("riskHigh");
    if (level === "medium") return t("riskMedium");
    return t("riskLow");
  };

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md space-y-5`}>
      <div className="space-y-3">
        <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold`}>{t("portfolioAllocation")}</h3>
        <div className={`rounded-2xl border px-4 py-3 ${dark ? "bg-amber-500/10 border-amber-400/20 text-amber-100" : "bg-amber-50 border-amber-200 text-amber-900"}`}>
          <div className="text-sm font-semibold">{concentrationBanner}</div>
          {largestHolding ? (
            <div className={`mt-1 text-xs ${dark ? "text-amber-200/80" : "text-amber-800/80"}`}>
              {t("largestHoldingLabel", { ticker: largestHolding.symbol || largestHolding.name, percentage: largestHoldingPct.toFixed(1) })}
            </div>
          ) : null}
        </div>
      </div>

      <div className="h-64 min-w-0">
        <ResponsiveContainer width="100%" height={256} minWidth={0} minHeight={256}>
          <PieChart>
            <Pie
              data={pieData}
              cx="50%"
              cy="50%"
              innerRadius={58}
              outerRadius={92}
              dataKey="value"
              nameKey="name"
              stroke="none"
              label={({ name, payload }) => `${name} ${Number(payload?.allocationPct || 0).toFixed(1)}%`}
              labelLine={false}
            >
              {pieData.map((entry, index) => (
                <Cell key={`${entry.name}-${index}`} fill={getStockColor(entry.symbol || entry.name, index)} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value, _name, item) => [
                `${formatCurrencyUSD(value, language)} • ${Number(item?.payload?.allocationPct || 0).toFixed(2)}%`,
                item?.payload?.name || "",
              ]}
            />
            <Pie
              data={[{ value: 1 }]}
              dataKey="value"
              cx="50%"
              cy="50%"
              outerRadius={0}
              isAnimationActive={false}
              activeIndex={0}
              activeShape={(props) =>
                renderCenterText({
                  ...props,
                  totalPortfolioValue,
                  largestHoldingPct,
                  language,
                  dark,
                  t,
                })
              }
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 gap-2">
        {pieData.map((item, index) => {
          const status = getAllocationStatus(item, largestHoldingPct);
          const statusTone = status === "overweight"
            ? dark ? "text-rose-300 bg-rose-500/15 border-rose-500/30" : "text-rose-700 bg-rose-50 border-rose-200"
            : status === "underweight"
              ? dark ? "text-amber-300 bg-amber-500/15 border-amber-500/30" : "text-amber-700 bg-amber-50 border-amber-200"
              : dark ? "text-emerald-300 bg-emerald-500/15 border-emerald-500/30" : "text-emerald-700 bg-emerald-50 border-emerald-200";

          return (
            <div
              key={`${item.symbol}-${item.name}`}
              className={`flex items-center justify-between rounded-xl ${dark ? "bg-slate-900/60" : "bg-slate-50"} px-3 py-2 text-sm`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="h-3 w-3 rounded-full shrink-0" style={{ backgroundColor: getStockColor(item.symbol || item.name, index) }} />
                <div className="min-w-0">
                  <div className={`${dark ? "text-slate-200" : "text-slate-700"} font-medium truncate`}>
                    {item.symbol || item.name}
                  </div>
                  <div className="text-xs text-slate-500 truncate">{formatCurrencyUSD(item.marketValue || 0, language)}</div>
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className={`${dark ? "text-slate-100" : "text-slate-900"} font-semibold`}>
                  {Number(item.allocationPct || 0).toFixed(2)}%
                </div>
                <div className={`mt-1 inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusTone}`}>
                  {status === "overweight" ? t("overweight") : status === "underweight" ? t("underweight") : t("normal")}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="space-y-2">
        <h4 className={`${dark ? "text-slate-100" : "text-slate-900"} font-bold`}>{t("sectorExposure")}</h4>
        {sectorExposure.map((item, idx) => (
          <div key={`${item.name}-${idx}`}>
            <div className="flex items-center justify-between text-sm mb-1 gap-3">
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
            <div className="mt-1 flex items-center justify-between gap-3 text-xs">
              <span className="text-slate-500">{formatCurrencyUSD(item.marketValue || 0, language)}</span>
              <span className={`${item.isOverweight ? "text-rose-500" : "text-slate-500"} font-semibold`}>
                {sectorRiskLabel(item)} • {sectorActionText(item)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
