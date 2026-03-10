import React from "react";
import { Search } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function HeroSearch({ query, setQuery, onSearch, suggestions, onPick }) {
  const { t } = useTranslation();
  return (
    <section
      className="rounded-3xl px-6 py-8 md:px-10 md:py-10 text-white shadow-[0_10px_25px_rgba(0,0,0,0.12)] transition-all duration-300"
      style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
    >
      <h1 className="text-3xl md:text-4xl font-bold mb-2 text-center">{t("searchHero")}</h1>
      <p className="text-center text-blue-100 font-normal mb-6">{t("searchSubtitle")}</p>

      <div className="max-w-3xl mx-auto relative">
        <input
          type="text"
          placeholder={t("searchPlaceholder")}
          className="w-full pl-6 pr-16 py-3 md:py-4 rounded-2xl bg-white/95 border border-white/40 text-slate-700 font-semibold text-lg md:text-xl placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#38BDF8]"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSearch()}
        />
        <button
          type="button"
          onClick={onSearch}
          className="absolute right-3 top-1/2 -translate-y-1/2 h-12 w-12 rounded-xl text-white flex items-center justify-center transition-all hover:scale-105 hover:brightness-110"
          style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
        >
          <Search size={24} />
        </button>
      </div>

      <div className="flex justify-center items-center gap-2 md:gap-3 mt-6 flex-wrap">
        <span className="text-blue-100 font-semibold">{t("popular")}</span>
        {suggestions.map((symbol) => (
          <button
            key={symbol}
            onClick={() => onPick(symbol)}
            className="px-5 py-2 bg-white/10 border border-white/30 hover:bg-white/20 rounded-2xl text-sm font-bold text-white transition-all hover:-translate-y-1"
          >
            {symbol}
          </button>
        ))}
      </div>
    </section>
  );
}
