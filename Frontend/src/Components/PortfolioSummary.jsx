import React from "react";
import { useTranslation } from "react-i18next";
import { formatCurrencyUSD } from "../utils/formatters";
import { Info } from "lucide-react";

function SummaryCard({ label, value, hint = "", tone = "neutral", dark = false }) {
  const toneClass =
    tone === "gain"
      ? "text-emerald-500"
      : tone === "loss"
        ? "text-rose-500"
        : dark
          ? "text-slate-100"
          : "text-slate-900";

  return (
    <div
      className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md transition-all duration-200 hover:shadow-lg`}
    >
      <div className="flex items-center gap-2 text-sm text-slate-500 font-medium">
        <p>{label}</p>
        {hint ? <Info size={14} className="opacity-70" title={hint} /> : null}
      </div>
      <p className={`mt-2 text-2xl font-bold ${toneClass}`}>{value}</p>
      {hint ? <p className="mt-2 text-xs text-slate-500 leading-relaxed">{hint}</p> : null}
    </div>
  );
}

function formatPercentWithArrow(value) {
  const numeric = Number(value || 0);
  const arrow = numeric >= 0 ? "↑" : "↓";
  return `${arrow} ${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}%`;
}

export default function PortfolioSummary({ summary, dark = false, language = "en" }) {
  const { t } = useTranslation();
  const portfolioReturnPct = Number(summary.portfolioReturnPct || 0);
  const spyReturnPct = Number(summary.spyReturnPct || 0);
  const outperformancePct = Number(summary.outperformancePct || 0);

  return (
    <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-7 gap-4">
      <SummaryCard
        label={t("portfolioValue")}
        value={formatCurrencyUSD(summary.totalValue || 0, language)}
        hint={t("portfolioValueHint")}
        dark={dark}
      />
      <SummaryCard
        label={t("dailyChange")}
        value={`${Number(summary.dailyChange || 0) >= 0 ? "+" : ""}${formatCurrencyUSD(Math.abs(Number(summary.dailyChange || 0)), language)} (${Number(summary.dailyChangePct || 0) >= 0 ? "+" : ""}${Number(summary.dailyChangePct || 0).toFixed(2)}%)`}
        tone={Number(summary.dailyChange || 0) >= 0 ? "gain" : "loss"}
        hint={t("dailyChangeHint")}
        dark={dark}
      />
      <SummaryCard
        label={t("totalGainLoss")}
        value={`${Number(summary.totalGainLoss || 0) >= 0 ? "+" : ""}${formatCurrencyUSD(Math.abs(Number(summary.totalGainLoss || 0)), language)} (${Number(summary.totalGainPct || 0) >= 0 ? "+" : ""}${Number(summary.totalGainPct || 0).toFixed(2)}%)`}
        tone={Number(summary.totalGainPct || 0) >= 0 ? "gain" : "loss"}
        hint={t("totalGainLossHint")}
        dark={dark}
      />
      <SummaryCard
        label={t("numberHoldings")}
        value={`${summary.holdingsCount || 0} ${t("stocks")}`}
        hint={t("numberHoldingsHint")}
        dark={dark}
      />
      <SummaryCard
        label={t("portfolioScore")}
        value={`${Math.round(Number(summary.portfolioScore || 0))}/100`}
        tone={Number(summary.portfolioScore || 0) >= 70 ? "gain" : Number(summary.portfolioScore || 0) < 40 ? "loss" : "neutral"}
        hint={summary.scoreBreakdown?.explanation || t("portfolioScoreHint")}
        dark={dark}
      />
      <SummaryCard
        label={t("portfolioReturn")}
        value={formatPercentWithArrow(portfolioReturnPct)}
        tone={portfolioReturnPct >= 0 ? "gain" : "loss"}
        hint={t("portfolioReturnHint")}
        dark={dark}
      />
      <SummaryCard
        label={`${summary.benchmark || "SPY"} ${t("returnLabel")}`}
        value={formatPercentWithArrow(spyReturnPct)}
        tone={spyReturnPct >= 0 ? "gain" : "loss"}
        hint={t("spyReturnHint")}
        dark={dark}
      />
      <SummaryCard
        label={t("outperformanceVsSpy")}
        value={formatPercentWithArrow(outperformancePct)}
        tone={outperformancePct >= 0 ? "gain" : "loss"}
        hint={t("outperformanceVsSpyHint")}
        dark={dark}
      />
    </section>
  );
}
