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

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className={`rounded-xl border ${dark ? "border-slate-700 bg-slate-900/60" : "border-slate-200 bg-slate-50"} p-4`}>
          <p className="text-sm text-slate-500">{t("marketRegime")}</p>
          <p className={`mt-2 text-xl font-bold ${dark ? "text-slate-100" : "text-slate-900"}`}>{insight.marketRegime || "Neutral"}</p>
        </div>
        <div className={`rounded-xl border ${dark ? "border-slate-700 bg-slate-900/60" : "border-slate-200 bg-slate-50"} p-4`}>
          <p className="text-sm text-slate-500">{t("marketSentiment")}</p>
          <p className={`mt-2 text-xl font-bold ${dark ? "text-slate-100" : "text-slate-900"}`}>{insight.marketSentiment || "Neutral"}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className={`rounded-xl border ${dark ? "border-slate-700 bg-slate-900/60" : "border-slate-200 bg-slate-50"} p-4`}>
          <p className="text-sm text-slate-500">{t("diversificationScore")}</p>
          <p className={`mt-2 text-2xl font-bold ${dark ? "text-slate-100" : "text-slate-900"}`}>
            {Math.round(Number(insight?.scoreBreakdown?.diversification || 0))}/100
          </p>
        </div>
        <div className={`rounded-xl border ${dark ? "border-slate-700 bg-slate-900/60" : "border-slate-200 bg-slate-50"} p-4`}>
          <p className="text-sm text-slate-500">{t("riskConcentration")}</p>
          <p className={`mt-2 text-2xl font-bold ${dark ? "text-slate-100" : "text-slate-900"}`}>
            {Math.round(Number(insight?.scoreBreakdown?.riskConcentration || 0))}/100
          </p>
        </div>
        <div className={`rounded-xl border ${dark ? "border-slate-700 bg-slate-900/60" : "border-slate-200 bg-slate-50"} p-4`}>
          <p className="text-sm text-slate-500">{t("sectorBalance")}</p>
          <p className={`mt-2 text-2xl font-bold ${dark ? "text-slate-100" : "text-slate-900"}`}>
            {Math.round(Number(insight?.scoreBreakdown?.sectorBalance || 0))}/100
          </p>
        </div>
      </div>

      <div className={`rounded-xl ${dark ? "bg-slate-900/60 border-slate-700" : "bg-slate-50 border-slate-200"} border p-4`}>
        <p className={`font-bold mb-2 ${dark ? "text-slate-100" : "text-slate-900"}`}>{t("portfolioScore")}</p>
        <p className="text-sm text-slate-600">
          {insight?.scoreBreakdown?.explanation || t("portfolioDiversificationHint")}
        </p>
      </div>

      <div className={`rounded-xl ${dark ? "bg-slate-900/60 border-slate-700" : "bg-white border-slate-200"} border p-4 space-y-4`}>
        <div>
          <p className={`font-bold mb-1 ${dark ? "text-slate-100" : "text-slate-900"}`}>{t("portfolioActionPlan")}</p>
          <p className="text-sm text-slate-600">{insight?.actionPlan?.rationale || t("portfolioDiversificationHint")}</p>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <div className={`rounded-xl ${dark ? "bg-rose-950/20 border-rose-900/40" : "bg-rose-50 border-rose-100"} border p-4`}>
            <p className="font-bold text-rose-700 mb-3">{t("reducePositions")}</p>
            <div className="space-y-3">
              {(insight?.actionPlan?.reduce || []).length ? (
                insight.actionPlan.reduce.map((item) => (
                  <div key={`reduce-${item.ticker}`} className="text-sm space-y-1">
                    <p className={`${dark ? "text-slate-100" : "text-slate-900"} font-semibold`}>
                      {item.ticker}: {item.fromPct}% → {item.toPct}%
                    </p>
                    <p className="text-slate-600">{item.reason}</p>
                    <p className="text-slate-500">{t("scalingStrategy")}: {item.scaling}</p>
                    <p className="text-slate-500">{t("invalidationCondition")}: {item.invalidation}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500">{t("noImmediateReduction")}</p>
              )}
            </div>
          </div>

          <div className={`rounded-xl ${dark ? "bg-emerald-950/20 border-emerald-900/40" : "bg-emerald-50 border-emerald-100"} border p-4`}>
            <p className="font-bold text-emerald-700 mb-3">{t("increasePositions")}</p>
            <div className="space-y-3">
              {(insight?.actionPlan?.increase || []).length ? (
                insight.actionPlan.increase.map((item) => (
                  <div key={`increase-${item.ticker}-${item.sector}`} className="text-sm space-y-1">
                    <p className={`${dark ? "text-slate-100" : "text-slate-900"} font-semibold`}>
                      {item.ticker}: {item.fromPct}% → {item.targetPct}%
                    </p>
                    <p className="text-slate-600">{item.reason}</p>
                    <p className="text-slate-500">{t("scalingStrategy")}: {item.scaling}</p>
                    <p className="text-slate-500">{t("stopLossSuggestion")}: {item.stopLoss}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500">{t("noImmediateIncrease")}</p>
              )}
            </div>
          </div>
        </div>

        <div>
          <p className={`font-bold mb-2 ${dark ? "text-slate-100" : "text-slate-900"}`}>{t("targetAllocationPlan")}</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {(insight?.actionPlan?.targetAllocation || []).map((item) => (
              <div key={`target-${item.sector}`} className={`rounded-lg ${dark ? "bg-slate-950/50" : "bg-slate-50"} px-3 py-2`}>
                <p className="text-xs text-slate-500">{item.sector}</p>
                <p className={`${dark ? "text-slate-100" : "text-slate-900"} font-semibold`}>{item.targetPct}%</p>
              </div>
            ))}
          </div>
        </div>
      </div>

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
