import React from "react";
import { useTranslation } from "react-i18next";
import RiskCard from "./RiskCard";

export default function RiskSelector({ options, selected, onSelect, dark }) {
  const { t } = useTranslation();
  return (
    <section className="space-y-4">
      <div>
        <h2 className={`${dark ? "text-slate-100" : "text-slate-900"} text-2xl font-bold`}>{t("riskProfileSelector")}</h2>
        <p className="text-slate-500">{t("riskProfileSelectorSubtitle")}</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {options.map((option) => (
          <RiskCard
            key={option.level}
            option={option}
            active={selected === option.level}
            onSelect={onSelect}
            dark={dark}
          />
        ))}
      </div>
    </section>
  );
}
