import React from "react";
import { useTranslation } from "react-i18next";
import { getLocalizedAssetTypeDescription, inferAssetMeta } from "../utils/assetMeta";

const SIGNAL_STYLE = {
  "Strong Buy": "bg-emerald-100 text-emerald-700",
  Buy: "bg-lime-100 text-lime-700",
  Hold: "bg-amber-100 text-amber-700",
  Sell: "bg-rose-100 text-rose-700",
};

export default function AISignals({ signals = [], dark = false }) {
  const { t, i18n } = useTranslation();
  const confidenceLabel = (value) => {
    if (!value) return t("confidenceLow");
    const normalized = String(value).toLowerCase();
    if (normalized === "high") return t("confidenceHigh");
    if (normalized === "medium") return t("confidenceMedium");
    return t("confidenceLow");
  };

  if (!signals.length) {
    return <div className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-500"} rounded-2xl border p-6 shadow-md`}>{t("noAiInsights")}</div>;
  }

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold mb-4`}>{t("aiMarketSignals")}</h3>
      <div className="space-y-3">
        {signals.map((s, idx) => {
          const assetMeta = inferAssetMeta({ symbol: s.symbol });
          const hasAiConfidence = s.aiConfidence != null;
          const hasLiveSignal = typeof s.signal === "string" && s.signal.trim().length > 0;
          const signalBadgeClass = hasLiveSignal
            ? SIGNAL_STYLE[s.signal] || "bg-slate-100 text-slate-700"
            : dark
              ? "border border-amber-400/30 bg-amber-500/10 text-amber-200"
              : "border border-amber-200 bg-amber-50 text-amber-700";
          const signalLabel = hasLiveSignal ? s.signal : t("limitedSignalFallback");

          return (
            <div key={`${s.symbol}-${idx}`} className={`${dark ? "bg-slate-900" : "bg-slate-50"} rounded-xl p-4 flex items-center justify-between gap-3 transition-all hover:-translate-y-[2px]`}>
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-bold text-[#2563EB]">{s.symbol}</p>
                  {assetMeta.isEtf ? (
                    <span
                      title={getLocalizedAssetTypeDescription(assetMeta.assetType, i18n.language) || undefined}
                      className={`${dark ? "bg-slate-800 text-sky-200 border-sky-400/30" : assetMeta.badgeClass} inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-wide cursor-help`}
                    >
                      {assetMeta.badgeLabel || "ETF"}
                    </span>
                  ) : null}
                </div>
                <div className="mt-1 space-y-0.5">
                  {hasAiConfidence ? (
                    <p className="text-sm text-slate-500">
                      {t("aiConfidence")}: {s.aiConfidence}%
                    </p>
                  ) : null}
                  <p className="text-sm text-slate-500">
                    {t("dataConfidence")}: {confidenceLabel(s.dataConfidence)}
                  </p>
                </div>
              </div>
              <span className={`px-2.5 py-1 rounded-full text-xs ${hasLiveSignal ? "font-bold" : "font-semibold"} ${signalBadgeClass}`}>
                {signalLabel}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
