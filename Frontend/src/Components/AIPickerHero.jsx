import React from "react";
import { useTranslation } from "react-i18next";

export default function AIPickerHero({ onGenerate, loading = false }) {
  const { t } = useTranslation();
  return (
    <section className="rounded-3xl p-6 md:p-8 shadow-lg text-white" style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}>
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl md:text-4xl font-bold">{t("aiStockPicker")}</h1>
          <p className="text-blue-100 mt-2 font-normal">{t("aiPickerSubtitle")}</p>
        </div>
        <button
          onClick={onGenerate}
          className="px-5 py-3 rounded-xl font-semibold bg-white text-[#1E3A8A] transition-all hover:scale-[1.03] hover:brightness-110 disabled:opacity-60"
          disabled={loading}
        >
          {loading ? t("generating") : t("generatePicks")}
        </button>
      </div>
    </section>
  );
}
