import React from "react";
import { useTranslation } from "react-i18next";

function Card({ title, value, dark }) {
  return (
    <div className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md transition-all hover:shadow-lg`}>
      <p className="text-sm text-slate-500 font-medium">{title}</p>
      <p className={`${dark ? "text-slate-100" : "text-slate-900"} mt-2 text-2xl font-bold`}>
        {value === null || value === undefined || value === "" || value === "-" ? "Data unavailable" : value}
      </p>
    </div>
  );
}

export default function AIOverviewCards({ overview, dark = false }) {
  const { t } = useTranslation();
  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      <Card title={t("marketSentiment")} value={overview.sentiment} dark={dark} />
      <Card title={t("trendingSector")} value={overview.sector} dark={dark} />
      <Card title={t("topAiPick")} value={overview.topPick} dark={dark} />
      <Card title={t("marketRiskLevel")} value={overview.riskLevel} dark={dark} />
    </section>
  );
}
