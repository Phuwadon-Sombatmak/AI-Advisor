import React from "react";
import { useTranslation } from "react-i18next";

export default function SectorInsights({ sectors = [], rotation = [], dark = false }) {
  const { t } = useTranslation();

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md space-y-4`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold`}>{t("sectorInsights")}</h3>

      <div className="space-y-3">
        {sectors.map((s, idx) => (
          <div key={`${s.name}-${idx}`}>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="text-slate-600 font-medium">{s.name}</span>
              <span className="font-bold text-slate-700">{s.momentum}%</span>
            </div>
            <div className="h-2 rounded-full bg-slate-200 overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${s.momentum}%`, background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }} />
            </div>
          </div>
        ))}
      </div>

      <div className="pt-2 border-t border-slate-200">
        <p className="font-bold text-slate-800 mb-2">{t("sectorRotation")}</p>
        <p className="text-sm text-slate-500 mb-2">{t("capitalRotatingInto")}</p>
        <div className="flex flex-wrap gap-2">
          {rotation.map((r) => (
            <span key={r} className="px-2.5 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-700">{r}</span>
          ))}
        </div>
      </div>
    </section>
  );
}
