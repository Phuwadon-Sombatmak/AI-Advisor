import React from "react";
import { useTranslation } from "react-i18next";

const SIGNAL_STYLE = {
  "Strong Buy": "bg-emerald-100 text-emerald-700",
  Buy: "bg-lime-100 text-lime-700",
  Hold: "bg-amber-100 text-amber-700",
  Sell: "bg-rose-100 text-rose-700",
};

export default function AISignals({ signals = [], dark = false }) {
  const { t } = useTranslation();

  if (!signals.length) {
    return <div className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-500"} rounded-2xl border p-6 shadow-md`}>{t("noAiInsights")}</div>;
  }

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold mb-4`}>{t("aiMarketSignals")}</h3>
      <div className="space-y-3">
        {signals.map((s, idx) => (
          <div key={`${s.symbol}-${idx}`} className={`${dark ? "bg-slate-900" : "bg-slate-50"} rounded-xl p-4 flex items-center justify-between gap-3 transition-all hover:-translate-y-[2px]`}>
            <div>
              <p className="font-bold text-[#2563EB]">{s.symbol}</p>
              <p className="text-sm text-slate-500">
                {t("confidence")}: {s.confidence == null ? t("dataUnavailable") : `${s.confidence}%`}
              </p>
            </div>
            <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${SIGNAL_STYLE[s.signal] || "bg-slate-100 text-slate-700"}`}>
              {s.signal || t("dataUnavailable")}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
