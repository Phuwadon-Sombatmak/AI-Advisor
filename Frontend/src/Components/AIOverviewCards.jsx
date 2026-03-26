import React from "react";
import { useTranslation } from "react-i18next";
import { inferAssetMeta } from "../utils/assetMeta";

function Card({ title, value, dark, assetMeta = null }) {
  return (
    <div className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md transition-all hover:shadow-lg`}>
      <p className="text-sm text-slate-500 font-medium">{title}</p>
      <div className={`${dark ? "text-slate-100" : "text-slate-900"} mt-2 text-2xl font-bold flex items-center gap-2 flex-wrap`}>
        <span>{value === null || value === undefined || value === "" || value === "-" ? "Data unavailable" : value}</span>
        {assetMeta?.isEtf ? (
          <span
            title={assetMeta.assetTypeDescription || undefined}
            className={`${dark ? "bg-slate-800 text-sky-200 border-sky-400/30" : assetMeta.badgeClass} inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-wide cursor-help`}
          >
            {assetMeta.badgeLabel || "ETF"}
          </span>
        ) : null}
      </div>
    </div>
  );
}

export default function AIOverviewCards({ overview, dark = false }) {
  const { t } = useTranslation();
  const topPickMeta = inferAssetMeta({ symbol: overview?.topPick });
  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      <Card title={t("marketSentiment")} value={overview.sentiment} dark={dark} />
      <Card title={t("trendingSector")} value={overview.sector} dark={dark} />
      <Card title={t("topAiPick")} value={overview.topPick} dark={dark} assetMeta={topPickMeta} />
      <Card title={t("marketRiskLevel")} value={overview.riskLevel} dark={dark} />
    </section>
  );
}
