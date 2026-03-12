import React, { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import NewsCard from "./NewsCard";
import { formatDateByLang } from "../utils/formatters";
import { getSentimentConfig, getSentimentFilterButtonClasses } from "../utils/sentimentUi";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "bullish", label: "Bullish" },
  { key: "neutral", label: "Neutral" },
  { key: "bearish", label: "Bearish" },
];

const toSentiment = (score) => {
  if (score > 0.2) return "bullish";
  if (score < -0.2) return "bearish";
  return "neutral";
};

export default function NewsSentimentFilter({ items = [], dark = false, loading = false }) {
  const { t, i18n } = useTranslation();
  const [filter, setFilter] = useState("all");

  const normalized = useMemo(() => {
    return items.map((item, idx) => {
      const scoreRaw = item.sentiment_score ?? item.score ?? item.sentimentScore ?? 0;
      const score = Number.isFinite(Number(scoreRaw)) ? Number(scoreRaw) : 0;
      const dateRaw = item.date || item.published_at || item.published || item.pubDate;
      const displayDate = dateRaw
        ? formatDateByLang(dateRaw, i18n.language)
        : "-";

      const baseId = item.id || item.link || `${item.title || "news"}-${idx}`;
      return {
        id: `${baseId}-${idx}`,
        title: item.title || "Untitled news",
        provider: item.provider || item.source || "Yahoo Finance RSS",
        link: item.link || "#",
        image: item.image || item.thumbnail || "",
        sentimentScore: score,
        sentiment: toSentiment(score),
        displayDate,
      };
    });
  }, [items, i18n.language]);

  const filtered = useMemo(() => {
    if (filter === "all") return normalized;
    return normalized.filter((item) => item.sentiment === filter);
  }, [normalized, filter]);

  return (
    <section
      className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-3xl border p-6 md:p-7 shadow-[0_10px_25px_rgba(0,0,0,0.08)] space-y-5`}
    >
      <div>
        <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-2xl font-bold`}>{t("newsSentimentTitle")}</h3>
        <p className="text-slate-500 mt-1">{t("newsSentimentSubtitle")}</p>
      </div>

      <div className={`${dark ? "bg-slate-900/80 border-slate-700" : "bg-slate-50 border-slate-200"} inline-flex flex-wrap gap-2 rounded-full border p-1.5`}>
        {FILTERS.map((f) => {
          const active = filter === f.key;
          const config = getSentimentConfig(f.key);
          return (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={getSentimentFilterButtonClasses({ sentiment: f.key, active, dark })}
            >
              <span aria-hidden="true">{config.emoji}</span>
              <span>{t(config.labelKey)}</span>
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="text-slate-500">{t("loadingSentimentNews")}</div>
      ) : filtered.length === 0 ? (
        <div className={`${dark ? "bg-slate-800 text-slate-300" : "bg-slate-50 text-slate-500"} rounded-xl p-4 text-sm`}>
          {t("noSentimentNews")}
        </div>
      ) : (
        <div className="space-y-4 transition-all duration-300">
          {filtered.map((item) => (
            <NewsCard key={item.id} news={item} dark={dark} variant="sentiment" />
          ))}
        </div>
      )}
    </section>
  );
}
