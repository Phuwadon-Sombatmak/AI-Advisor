import React from "react";
import { useTranslation } from "react-i18next";

export default function AIInsightPanel({ message, dark }) {
  const { t } = useTranslation();
  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-6 shadow-md`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold mb-2`}>{t("aiMarketInsight")}</h3>
      <p className="text-slate-600 font-normal leading-relaxed">{message}</p>
    </section>
  );
}
