import React from "react";
import { Bookmark } from "lucide-react";
import { useTranslation } from "react-i18next";
import { getSentimentBadgeClasses, getSentimentConfig, getSentimentScoreClasses, normalizeSentimentKey } from "../utils/sentimentUi";

export default function NewsCard({ news, dark, variant = "grid", isBookmarked = false, onToggleBookmark = () => {} }) {
  const { t } = useTranslation();
  if (variant === "intel") {
    const hasImage = Boolean(news.image);
    const score = typeof news.sentimentScore === "number" ? news.sentimentScore : 0;
    const sentimentType = score > 0.2 ? "bullish" : score < -0.2 ? "bearish" : "neutral";
    const sentimentConfig = getSentimentConfig(sentimentType);
    const label = t(sentimentConfig.labelKey);
    const impact = news.impact || (Math.abs(score) > 0.6 ? "High" : Math.abs(score) > 0.3 ? "Medium" : "Low");
    const sectorMap = {
      Technology: t("technology"),
      AI: t("ai"),
      Semiconductors: t("semiconductors"),
      Macro: t("macro"),
      Crypto: t("crypto"),
    };
    const sector = sectorMap[news.sectorTag] || news.sectorTag || t("technology");
    const impactLabel = impact === "High" ? t("impactHigh") : impact === "Medium" ? t("impactMedium") : t("impactLow");
    const impactClass =
      impact === "High"
        ? "bg-rose-100 text-rose-700"
        : impact === "Medium"
          ? "bg-amber-100 text-amber-700"
          : "bg-emerald-100 text-emerald-700";

    return (
      <a
        href={news.link || "#"}
        target="_blank"
        rel="noreferrer"
        className={`${dark ? "bg-[#0F172A] border-slate-700 hover:border-slate-600" : "bg-white border-slate-200 hover:border-slate-300"} rounded-2xl border p-5 shadow-md transition-all hover:-translate-y-[2px] hover:shadow-lg block relative`}
      >
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onToggleBookmark(news);
          }}
          className={`absolute top-3 right-3 h-8 w-8 rounded-full border inline-flex items-center justify-center transition-all ${
            isBookmarked ? "bg-blue-100 border-blue-300 text-blue-700" : "bg-white border-slate-200 text-slate-400 hover:text-blue-700"
          }`}
          title={isBookmarked ? "Remove bookmark" : "Bookmark news"}
        >
          <Bookmark size={15} className={isBookmarked ? "fill-current" : ""} />
        </button>
        <div className="flex flex-col sm:flex-row gap-4">
          {hasImage ? (
            <img src={news.image} alt={news.title || "news"} className="w-full sm:w-40 h-24 rounded-xl object-cover bg-slate-200 shrink-0" />
          ) : (
            <div className="w-full sm:w-40 h-24 rounded-xl bg-slate-100 text-slate-500 text-sm font-semibold grid place-items-center shrink-0">
              {t("noImage")}
            </div>
          )}

          <div className="flex-1 min-w-0">
            <h4 className={`${dark ? "text-slate-100" : "text-slate-900"} text-base md:text-lg font-bold leading-snug line-clamp-2`}>
              {news.title}
            </h4>
            <p className={`mt-2 text-sm ${dark ? "text-slate-400" : "text-slate-500"}`}>
              {news.provider || "Yahoo Finance"} • {news.displayDate || "-"}
            </p>
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              <span className={getSentimentBadgeClasses({ sentiment: sentimentType, dark })}>
                <span aria-hidden="true">{sentimentConfig.emoji}</span>
                <span>{label}</span>
              </span>
              <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${impactClass}`}>{t("impact")} {impactLabel}</span>
              <span className={`${dark ? "bg-blue-500/15 text-blue-200 border-blue-400/30" : "bg-blue-50 text-blue-700 border-blue-200"} px-2.5 py-1 rounded-full text-xs font-bold border`}>{sector}</span>
              <span className={getSentimentScoreClasses({ sentiment: sentimentType, score, dark })}>
                {t("score")} {score >= 0 ? "+" : ""}
                {score.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      </a>
    );
  }

  if (variant === "sentiment") {
    const hasImage = Boolean(news.image);
    const score = typeof news.sentimentScore === "number" ? news.sentimentScore : 0;
    const sentimentType = normalizeSentimentKey(news.sentiment || (score > 0.2 ? "bullish" : score < -0.2 ? "bearish" : "neutral"));
    const sentimentConfig = getSentimentConfig(sentimentType);
    const label = t(sentimentConfig.labelKey);

    return (
      <a
        href={news.link || "#"}
        target="_blank"
        rel="noreferrer"
        className={`${dark ? "bg-[#0F172A] border-slate-700 hover:border-slate-600" : "bg-white border-slate-200 hover:border-slate-300"} rounded-2xl border p-5 shadow-md transition-all hover:-translate-y-[2px] hover:shadow-lg block`}
      >
        <div className="flex flex-col sm:flex-row gap-4">
          {hasImage ? (
            <img src={news.image} alt={news.title || "news"} className="w-full sm:w-40 h-24 rounded-xl object-cover bg-slate-200 shrink-0" />
          ) : (
            <div className="w-full sm:w-40 h-24 rounded-xl bg-slate-100 text-slate-500 text-sm font-semibold grid place-items-center shrink-0">
              {t("noImage")}
            </div>
          )}

          <div className="flex-1 min-w-0">
            <h4 className={`${dark ? "text-slate-100" : "text-slate-900"} text-base md:text-lg font-bold leading-snug line-clamp-2`}>
              {news.title}
            </h4>
            <p className={`mt-2 text-sm ${dark ? "text-slate-400" : "text-slate-500"}`}>
              {news.provider || "Yahoo Finance RSS"} • {news.displayDate || "-"}
            </p>
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              <span className={getSentimentBadgeClasses({ sentiment: sentimentType, dark })}>
                <span aria-hidden="true">{sentimentConfig.emoji}</span>
                <span>{label}</span>
              </span>
              <span className={getSentimentScoreClasses({ sentiment: sentimentType, score, dark })}>
                {t("score")} {score >= 0 ? "+" : ""}
                {score.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      </a>
    );
  }

  return (
    <a
      href={news.link || "#"}
      target="_blank"
      rel="noreferrer"
      className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border overflow-hidden group cursor-pointer flex flex-col transition-all hover:-translate-y-1`}
      style={{ boxShadow: "0 10px 25px rgba(0,0,0,0.08)" }}
    >
      <div className="h-44 bg-slate-200 overflow-hidden relative rounded-t-2xl">
        <img
          src={news.image || "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=400&h=300&fit=crop"}
          alt={news.title || "news"}
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
        />
      </div>
      <div className="p-4 flex-1">
        <span className="inline-block px-2 py-1 rounded-md text-[11px] font-bold text-cyan-700 bg-cyan-50 mb-2 uppercase tracking-wider">
          {news.provider || "Yahoo Finance"}
        </span>
        <h3 className={`${dark ? "text-slate-100" : "text-slate-800"} font-bold text-lg leading-tight group-hover:text-[#2563EB] transition-colors`}>
          {news.title}
        </h3>
      </div>
    </a>
  );
}
