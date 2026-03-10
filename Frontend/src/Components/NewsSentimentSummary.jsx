import React from "react";
import { useTranslation } from "react-i18next";

function Bar({ label, value, color }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="font-semibold text-slate-600">{label}</span>
        <span className="font-bold text-slate-700">{value}%</span>
      </div>
      <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-300" style={{ width: `${value}%`, background: color }} />
      </div>
    </div>
  );
}

export default function NewsSentimentSummary({ distribution, dark }) {
  const { t } = useTranslation();
  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-lg font-bold mb-4`}>{t("aiSentimentSummary")}</h3>
      <div className="space-y-3">
        <Bar label={t("bullish")} value={distribution.bullish} color="#22C55E" />
        <Bar label={t("neutral")} value={distribution.neutral} color="#64748B" />
        <Bar label={t("bearish")} value={distribution.bearish} color="#EF4444" />
      </div>
    </section>
  );
}
