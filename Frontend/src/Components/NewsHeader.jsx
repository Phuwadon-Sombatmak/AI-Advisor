import React from "react";
import { RefreshCw } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function NewsHeader({ loading, onRefresh, dark }) {
  const { t } = useTranslation();
  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-6 shadow-md`}>
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className={`${dark ? "text-slate-100" : "text-slate-900"} text-3xl font-bold`}>{t("newsHeaderTitle")}</h1>
          <p className="text-slate-500 mt-1">{t("newsHeaderSubtitle")}</p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="inline-flex items-center gap-2 text-white px-4 py-2 rounded-xl font-semibold shadow-md transition-all hover:brightness-110 hover:scale-[1.02] disabled:opacity-70"
          style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
        >
          <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
          {loading ? t("refreshing") : t("refresh")}
        </button>
      </div>
    </section>
  );
}
