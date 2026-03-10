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
  return (
    <div className={`mt-2 rounded-xl border px-3 py-2 ${
      dark ? "bg-slate-900/80 border-slate-700 text-slate-300" : "bg-slate-50 border-slate-200 text-slate-600"
    }`}>
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className={`px-2 py-0.5 rounded-full border font-semibold ${badge.tone}`}>{badge.label}</span>
        <span className="font-semibold">AI Confidence: {Math.round(Number(confidence || 0))}%</span>
        {updatedAt ? <span>Last updated: {updatedAt}</span> : null}
      </div>
      {Array.isArray(sources) && sources.length ? (
        <p className="mt-1 text-[11px]">Sources: {sources.join(" · ")}</p>
      ) : null}
      {dataCoverage ? (
        <p className="mt-1 text-[11px]">
          Coverage: price {dataCoverage.price_data ? "available" : "missing"} · news {dataCoverage.news_data ?? dataCoverage.news_sentiment ? "available" : "partial"} · technical {dataCoverage.technical_data ?? dataCoverage.technical_signals ? "available" : "missing"}
        </p>
      ) : null}
    </div>
  );
}
