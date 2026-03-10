import React from "react";
import { useTranslation } from "react-i18next";
import { formatCurrencyUSD } from "../utils/formatters";

function SummaryCard({ label, value, tone = "neutral", dark = false }) {
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
      <p className="text-sm text-slate-500 font-medium">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${toneClass}`}>{value}</p>
    </div>
  );
}

export default function PortfolioSummary({ summary, dark = false, language = "en" }) {
  const { t } = useTranslation();
  return (
    <section className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
      <SummaryCard
        label={t("portfolioValue")}
        value={formatCurrencyUSD(summary.totalValue || 0, language)}
        dark={dark}
      />
      <SummaryCard
        label={t("dailyChange")}
        value={`${Number(summary.dailyChangePct || 0) >= 0 ? "+" : ""}${Number(summary.dailyChangePct || 0).toFixed(2)}%`}
        tone={Number(summary.dailyChangePct || 0) >= 0 ? "gain" : "loss"}
        dark={dark}
      />
      <SummaryCard
        label={t("totalGainLoss")}
        value={`${Number(summary.totalGainPct || 0) >= 0 ? "+" : ""}${Number(summary.totalGainPct || 0).toFixed(2)}%`}
        tone={Number(summary.totalGainPct || 0) >= 0 ? "gain" : "loss"}
        dark={dark}
      />
      <SummaryCard
        label={t("numberHoldings")}
        value={`${summary.holdingsCount || 0} ${t("stocks")}`}
        dark={dark}
      />
      <SummaryCard
        label={t("diversificationScore")}
        value={`${Math.round(Number(summary.diversificationScore || 0))}/100`}
        tone={Number(summary.diversificationScore || 0) >= 70 ? "gain" : Number(summary.diversificationScore || 0) < 40 ? "loss" : "neutral"}
        dark={dark}
      />
    </section>
  );
}
