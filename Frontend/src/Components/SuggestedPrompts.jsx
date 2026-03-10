import React from "react";
import { useTranslation } from "react-i18next";

const DEFAULT_PROMPTS = [
  "What stocks are trending today?",
  "Is NVDA still a good investment?",
  "What sectors have strong momentum?",
];

export default function SuggestedPrompts({ onPick = () => {}, prompts = DEFAULT_PROMPTS, dark = false, title = "Quick prompts" }) {
  const { t } = useTranslation();
  return (
    <div className="mb-3">
      <p className={`mb-2 text-[11px] uppercase tracking-wide font-semibold ${dark ? "text-slate-400" : "text-slate-500"}`}>{title}</p>
      <div className="flex flex-wrap gap-2">
      {prompts.map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onPick(p)}
          className={`${dark ? "bg-slate-800/80 text-slate-200 border-slate-700 hover:bg-slate-700/90" : "bg-slate-100 text-slate-700 border-slate-200 hover:bg-white"} px-3 py-1.5 rounded-full text-xs font-semibold border transition-all hover:-translate-y-0.5 hover:shadow-sm`}
        >
          {t(p) || p}
        </button>
      ))}
      </div>
    </div>
  );
}
