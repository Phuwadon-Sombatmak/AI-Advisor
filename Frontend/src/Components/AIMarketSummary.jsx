import React from "react";
import { useTranslation } from "react-i18next";
import { inferAssetMeta } from "../utils/assetMeta";

export default function AIMarketSummary({ summary, radar = [], riskAlert, dark = false }) {
  const { t } = useTranslation();
  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md space-y-4`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold`}>{t("aiMarketSummary")}</h3>
      <p className="text-sm text-slate-600 leading-relaxed">{summary}</p>

      <div className="rounded-xl bg-slate-50 p-4">
        <p className="font-bold text-slate-800 mb-2">{t("aiOpportunityRadar")}</p>
        <div className="flex flex-wrap gap-2">
          {radar.map((r) => {
            const assetMeta = inferAssetMeta({ symbol: r });
            return (
              <div key={r} className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-700">{r}</span>
                {assetMeta.isEtf ? (
                  <span
                    title={assetMeta.assetTypeDescription || undefined}
                    className={`${dark ? "bg-slate-800 text-sky-200 border-sky-400/30" : assetMeta.badgeClass} inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-wide cursor-help`}
                  >
                    {assetMeta.shortBadgeLabel || "ETF"}
                  </span>
                ) : null}
              </div>
            );
          })}
        </div>
      </div>

      <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
        <p className="font-bold text-rose-700 mb-1">{t("aiRiskAlert")}</p>
        <p className="text-sm text-rose-700">{riskAlert || t("marketVolatilityIncreasing")}</p>
      </div>
    </section>
  );
}
