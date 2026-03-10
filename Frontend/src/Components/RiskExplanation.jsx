import React from "react";
import { useTranslation } from "react-i18next";

export default function RiskExplanation({ profile, dark }) {
  const { t } = useTranslation();
  const strategy = (profile.strategy || []).map((line, idx) => {
    if (line && typeof line === "object" && line.key) return t(line.key);
    if (typeof line === "string" && profile.strategyKeys?.[idx]) return t(profile.strategyKeys[idx]);
    return line;
  });
  const allocation = (profile.allocation || []).map((a) => ({
    ...a,
    label: a.labelKey ? t(a.labelKey) : a.label,
  }));

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-6 shadow-md`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold`}>{t("riskProfile")}: {profile.level}</h3>
      <p className="mt-2 text-slate-500">{t("recommendedStrategy")}:</p>
      <ul className="mt-2 space-y-1 text-sm text-slate-600">
        {strategy.map((line) => (
          <li key={line}>• {line}</li>
        ))}
      </ul>

      <div className="mt-5">
        <p className="text-slate-500 mb-3">{t("exampleAllocation")}:</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {allocation.map((a) => (
            <div key={a.label} className="rounded-xl bg-slate-50 px-4 py-3">
              <p className="text-sm text-slate-500">{a.label}</p>
              <p className="text-lg font-bold text-slate-800">{a.value}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
