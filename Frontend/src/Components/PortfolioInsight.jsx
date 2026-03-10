import React from "react";
import { useTranslation } from "react-i18next";

export default function PortfolioInsight({ insight, dark = false }) {
  const { t } = useTranslation();
  const riskTone =
    insight.riskLevel === "High"
      ? "bg-rose-100 text-rose-700"
      : insight.riskLevel === "Medium"
        ? "bg-amber-100 text-amber-700"
        : "bg-emerald-100 text-emerald-700";

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md space-y-4`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold`}>{t("aiPortfolioInsight")}</h3>
      <p className="text-slate-600 text-sm leading-relaxed">{insight.summary}</p>

      <div className="rounded-xl border border-slate-200 p-4">
        <div className="flex items-center justify-between mb-2">
          <p className="font-semibold text-slate-700">{t("portfolioRisk")}</p>
          <span className={`px-2 py-1 rounded-full text-xs font-bold ${riskTone}`}>{insight.riskLevel}</span>
        </div>
        <div className="h-2 rounded-full bg-slate-200 overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${insight.riskScore}%`, background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }} />
        </div>
      </div>

      <div className="rounded-xl bg-slate-50 p-4">
        <p className="font-bold text-slate-800 mb-2">{t("aiRebalanceSuggestion")}</p>
        <ul className="space-y-1 text-sm text-slate-600">
          {insight.rebalanceSuggestions.map((s) => (
            <li key={s}>• {s}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
