import React from "react";
import { useTranslation } from "react-i18next";

function Sparkline({ points = [], up = true }) {
  if (!points.length) return null;
  const width = 110;
  const height = 34;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const path = points
    .map((p, i) => {
      const x = (i / (points.length - 1 || 1)) * width;
      const y = height - ((p - min) / range) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-9">
      <path d={path} fill="none" stroke={up ? "#22C55E" : "#EF4444"} strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

export default function RiskStockCard({ item, level, dark }) {
  const { t } = useTranslation();
  const symbol = item.Symbol || item.symbol || "-";
  const ret30 = Number(item.ret30 || 0);
  const riskScore = Number(item.risk_score || 0);
  const confidence = Math.max(55, Math.min(95, Math.round((1 - Math.min(riskScore, 1)) * 100)));
  const points = [
    ret30 * 10 - 0.8,
    ret30 * 10 - 0.3,
    ret30 * 10,
    ret30 * 10 + 0.2,
    ret30 * 10 + (ret30 >= 0 ? 0.8 : -0.8),
  ];

  return (
    <div className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-4 shadow-md transition-all hover:-translate-y-[2px] hover:shadow-lg`}>
      <p className="text-lg font-bold text-[#2563EB]">{symbol}</p>
      <p className="text-sm text-slate-500">{t("aiGrowthStock")}</p>
      <div className="mt-3 flex items-center gap-2 flex-wrap text-xs font-semibold">
        <span className="px-2 py-1 rounded-full bg-blue-100 text-blue-700">{t("riskLevel")}: {level}</span>
        <span className="px-2 py-1 rounded-full bg-cyan-100 text-cyan-700">{t("aiConfidence")}: {confidence}%</span>
      </div>
      <div className="mt-3">
        <Sparkline points={points} up={ret30 >= 0} />
      </div>
    </div>
  );
}
