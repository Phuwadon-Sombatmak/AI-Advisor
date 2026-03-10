import React from "react";
import { Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function Topbar({ theme, toggleTheme, languageLabel, toggleLanguage, title }) {
  const { i18n } = useTranslation();
  const dark = theme === "dark";
  const isThai = String(i18n.resolvedLanguage || i18n.language || "en").startsWith("th");
  const switchLabel = languageLabel || (isThai ? "EN" : "TH");
  const onToggleLanguage = toggleLanguage || (() => i18n.changeLanguage(isThai ? "en" : "th"));

  return (
    <header className={`${dark ? "bg-[#020617] border-slate-800" : "bg-white border-slate-200"} h-14 border-b`}>
      <div className="h-full max-w-[1280px] mx-auto px-4 md:px-8 flex items-center justify-between">
        <h1 className={`${dark ? "text-slate-100" : "text-slate-800"} text-sm md:text-base font-bold`}>{title}</h1>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleTheme}
            className={`${dark ? "bg-slate-800 text-slate-100" : "bg-slate-100 text-slate-700"} p-2 rounded-lg transition-all hover:brightness-110`}
          >
            {dark ? <Sun size={14} /> : <Moon size={14} />}
          </button>
          <button
            onClick={onToggleLanguage}
            className={`${dark ? "bg-slate-800 text-slate-100" : "bg-slate-100 text-slate-700"} text-xs font-bold px-3 py-1.5 rounded-lg transition-all hover:brightness-110`}
          >
            {switchLabel}
          </button>
        </div>
      </div>
    </header>
  );
}
