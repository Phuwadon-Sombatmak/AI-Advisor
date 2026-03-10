import React from "react";
import { useTranslation } from "react-i18next";
import { getSentimentConfig, getSentimentFilterButtonClasses } from "../utils/sentimentUi";

const SENTIMENT_FILTERS = ["all", "bullish", "neutral", "bearish"];
const TOPIC_FILTERS = ["all", "technology", "ai", "semiconductors", "macro", "crypto"];

function Pill({ active, onClick, label, dark = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2 rounded-full text-sm font-semibold transition-all duration-200 ${
        active ? "bg-[#2563EB] text-white" : dark ? "bg-slate-900/60 text-slate-300 border border-slate-700 hover:bg-slate-800/80" : "bg-[#F1F5F9] text-[#334155] hover:brightness-95"
      } hover:scale-[1.02]`}
    >
      {label}
    </button>
  );
}

const SORT_OPTIONS = ["sortNewest", "sortHighestImpact", "sortMostBullish"];

export default function NewsFilters({
  sentimentFilter,
  topicFilter,
  sortBy,
  setSentimentFilter,
  setTopicFilter,
  setSortBy,
  dark = false,
}) {
  const { t } = useTranslation();
  return (
    <section className="space-y-3">
      <div className={`${dark ? "bg-slate-900/80 border-slate-700" : "bg-slate-50 border-slate-200"} inline-flex flex-wrap gap-2 rounded-full border p-1.5`}>
        {SENTIMENT_FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setSentimentFilter(f)}
            className={getSentimentFilterButtonClasses({ sentiment: f, active: sentimentFilter === f, dark })}
          >
            <span aria-hidden="true">{getSentimentConfig(f).emoji}</span>
            <span>{t(f)}</span>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-2 items-center justify-between">
        <div className="flex flex-wrap gap-2">
        {TOPIC_FILTERS.map((f) => (
          <Pill key={f} label={t(f)} active={topicFilter === f} onClick={() => setTopicFilter(f)} dark={dark} />
        ))}
        </div>
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className={`rounded-xl border px-3 py-2 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-[#2563EB] ${
            dark ? "border-slate-700 bg-slate-900 text-slate-200" : "border-slate-200 bg-white text-slate-700"
          }`}
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt} value={opt}>
              {t(opt)}
            </option>
          ))}
        </select>
      </div>
    </section>
  );
}
