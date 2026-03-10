import React from "react";
import { useTranslation } from "react-i18next";

export default function RiskCard({ option, active, onSelect, dark }) {
  const { t } = useTranslation();
  const title = option.titleKey ? t(option.titleKey) : option.title;
  const description = option.descriptionKey ? t(option.descriptionKey) : option.description;
  const expectedReturn = option.expectedReturnKey ? t(option.expectedReturnKey) : option.expectedReturn;
  const volatility = option.volatilityKey ? t(option.volatilityKey) : option.volatility;
  const suitableFor = option.suitableForKey ? t(option.suitableForKey) : option.suitableFor;

  return (
    <button
      type="button"
      onClick={() => onSelect(option.level)}
      className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-100" : "bg-white border-slate-200 text-slate-900"} w-full text-left rounded-2xl border p-5 shadow-md transition-all duration-200 hover:-translate-y-[2px] hover:shadow-lg ${
        active ? "border-2 border-[#2563EB] bg-[#EFF6FF] text-slate-900" : ""
      }`}
    >
      <p className="text-xs font-bold uppercase tracking-wider text-[#2563EB]">{option.level}</p>
      <h4 className="mt-1 text-lg font-bold">{title}</h4>
      <p className="mt-2 text-sm text-slate-500 font-normal">{description}</p>
      <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <p className="text-slate-500">{t("expectedReturn")}</p>
          <p className="font-semibold text-slate-800">{expectedReturn}</p>
        </div>
        <div className="rounded-lg bg-slate-50 px-3 py-2">
          <p className="text-slate-500">{t("volatility")}</p>
          <p className="font-semibold text-slate-800">{volatility}</p>
        </div>
      </div>
      <p className="mt-3 text-xs text-slate-500">{suitableFor}</p>
    </button>
  );
}
