import React from "react";
import { mapConfidenceToBadge } from "../utils/aiAdvisor";

export default function ConfidenceFooter({
  confidence = 0,
  sources = [],
  updatedAt = "",
  dataCoverage = null,
  dark = false,
}) {
  const badge = mapConfidenceToBadge(confidence);
  const limitedMode =
    Array.isArray(sources) && sources.includes("Cached Market Context") ||
    (dataCoverage && dataCoverage.price_data === false && dataCoverage.technical_data === false);
  const priceState = dataCoverage?.price_data ? "available" : "limited";
  const newsState =
    dataCoverage?.news_data === true || dataCoverage?.news_sentiment === true
      ? "available"
      : dataCoverage?.news_data === false || dataCoverage?.news_sentiment === false
        ? "limited"
        : "partial";
  const technicalState =
    dataCoverage?.technical_data === true || dataCoverage?.technical_signals === true
      ? "available"
      : dataCoverage?.technical_data === false || dataCoverage?.technical_signals === false
        ? "limited"
        : "partial";
  return (
    <div className={`mt-2 rounded-xl border px-3 py-2 ${
      dark ? "bg-slate-900/80 border-slate-700 text-slate-300" : "bg-slate-50 border-slate-200 text-slate-600"
    }`}>
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className={`px-2 py-0.5 rounded-full border font-semibold ${limitedMode ? "bg-amber-100 text-amber-700 border-amber-200" : badge.tone}`}>
          {limitedMode ? "Limited live validation" : badge.label}
        </span>
        <span className="font-semibold">{limitedMode ? "Confidence guide" : "AI Confidence"}: {Math.round(Number(confidence || 0))}%</span>
        {updatedAt ? <span>Last updated: {updatedAt}</span> : null}
      </div>
      {Array.isArray(sources) && sources.length ? (
        <p className="mt-1 text-[11px]">Sources: {sources.join(" · ")}</p>
      ) : null}
      {dataCoverage ? (
        <p className="mt-1 text-[11px]">
          Coverage: price {priceState} · news {newsState} · technical {technicalState}
        </p>
      ) : null}
    </div>
  );
}
