import React from "react";
import { useTranslation } from "react-i18next";

const DEFAULT_PROMPTS = [
  "What stocks are trending today?",
  "Is NVDA still a good investment?",
  "What sectors have strong momentum?",
];

export default function SuggestedPrompts({
  onPick = () => {},
  prompts = DEFAULT_PROMPTS,
  dark = false,
  title = "Quick prompts",
}) {
  const { t } = useTranslation();
  const items = Array.isArray(prompts) && prompts.length ? prompts : DEFAULT_PROMPTS;

  return (
    <div className="mb-3">
      <p className={`mb-2 text-[11px] uppercase tracking-[0.14em] font-semibold ${dark ? "text-slate-400" : "text-slate-500"}`}>
        {title}
      </p>
      <div className="flex flex-wrap gap-2">
        {items.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => onPick(p)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all hover:-translate-y-0.5 hover:shadow-sm ${
              dark
                ? "bg-slate-800/80 text-slate-200 border-slate-700 hover:bg-slate-700/90 hover:border-blue-500/40"
                : "bg-white text-slate-700 border-slate-200 hover:bg-blue-50 hover:border-blue-200"
            }`}
          >
            {t(p) || p}
          </button>
        ))}
      </div>
    </div>
  );
}
