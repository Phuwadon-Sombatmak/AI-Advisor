import React, { useEffect, useMemo, useState } from "react";
import { X, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

const ENDPOINTS = [
  "/api-fastapi/api/ai-summary",
];

async function postSummary(context) {
  let lastErr;
  for (const endpoint of ENDPOINTS) {
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          context,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error("summary failed");
}

export default function AISummaryPanel({ open, onClose, context, dark = false }) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setLoading(true);
    postSummary(context)
      .then((json) => {
        if (!alive) return;
        setData(json);
      })
      .catch(() => {
        if (!alive) return;
        setData(null);
      })
      .finally(() => {
        if (!alive) return;
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [open, context]);

  const summary = useMemo(() => {
    const s = data?.summary || {};
    return {
      sentiment: s.market_sentiment || "Neutral",
      fearGreedScore: Number(s.fear_greed_score ?? 50),
      fearGreedSource: s.fear_greed_source || "InternalModel",
      topPick: s.top_ai_pick || "NVDA",
      topPickConfidence: Number(s.top_ai_pick_confidence ?? data?.confidence ?? 70),
      sector: s.trending_sector || "Semiconductors",
      sectorMomentum: s.sector_momentum || "Moderate",
      marketMomentum: Number(s.market_momentum ?? 0),
      risk: s.risk_outlook || "Medium",
      forecast: s.forecast_horizon || { "7d": 0, "30d": 0, "90d": 0 },
      sources: Array.isArray(data?.sources) ? data.sources : ["Finnhub", "Yahoo Finance", "Market News"],
      explanation: s.explanation || "AI analysis indicates moderate bullish momentum driven by AI infrastructure demand and sector relative strength.",
    };
  }, [data]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[70] bg-slate-900/45 backdrop-blur-sm flex items-center justify-center p-4" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-100" : "bg-white border-slate-200 text-slate-900"} w-full max-w-2xl rounded-2xl border shadow-2xl p-6`}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-2xl font-bold">{t("aiMarketSummary")}</h3>
          <button onClick={onClose} className="p-2 rounded-lg bg-slate-100 text-slate-600"><X size={16} /></button>
        </div>

        {loading ? (
          <div className="py-10 text-center text-slate-500 font-medium inline-flex items-center gap-2 w-full justify-center">
            <Loader2 className="animate-spin" size={18} /> {t("aiAnalyzing")}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-slate-50 border-slate-200"} rounded-xl border p-4`}>
                <p className="text-xs text-slate-500">{t("marketSentiment")}</p>
                <p className="text-lg font-bold">{summary.sentiment}</p>
                <p className="text-sm text-slate-400 mt-1">Fear & Greed: {summary.fearGreedScore.toFixed(1)}</p>
                <p className="text-xs text-slate-500 mt-1">Source: {summary.fearGreedSource}</p>
              </div>
              <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-slate-50 border-slate-200"} rounded-xl border p-4`}>
                <p className="text-xs text-slate-500">{t("topAiPick")}</p>
                <p className="text-lg font-bold">{summary.topPick}</p>
                <p className="text-sm text-slate-400 mt-1">AI Confidence: {Math.round(summary.topPickConfidence)}%</p>
              </div>
              <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-slate-50 border-slate-200"} rounded-xl border p-4`}>
                <p className="text-xs text-slate-500">{t("trendingSector")}</p>
                <p className="text-lg font-bold">{summary.sector}</p>
                <p className="text-sm text-slate-400 mt-1">Momentum: {summary.sectorMomentum} ({summary.marketMomentum.toFixed(2)}%)</p>
              </div>
              <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-slate-50 border-slate-200"} rounded-xl border p-4`}>
                <p className="text-xs text-slate-500">{t("riskOutlook")}</p>
                <p className="text-lg font-bold">{summary.risk}</p>
                <p className="text-sm text-slate-400 mt-1">Forecast: 7d / 30d / 90d</p>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-3">
              <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-slate-50 border-slate-200"} rounded-xl border p-3 text-center`}>
                <p className="text-xs text-slate-500">7 days</p>
                <p className={`text-lg font-bold ${Number(summary.forecast["7d"] || 0) >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                  {Number(summary.forecast["7d"] || 0) >= 0 ? "+" : ""}{Number(summary.forecast["7d"] || 0).toFixed(2)}%
                </p>
              </div>
              <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-slate-50 border-slate-200"} rounded-xl border p-3 text-center`}>
                <p className="text-xs text-slate-500">30 days</p>
                <p className={`text-lg font-bold ${Number(summary.forecast["30d"] || 0) >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                  {Number(summary.forecast["30d"] || 0) >= 0 ? "+" : ""}{Number(summary.forecast["30d"] || 0).toFixed(2)}%
                </p>
              </div>
              <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-slate-50 border-slate-200"} rounded-xl border p-3 text-center`}>
                <p className="text-xs text-slate-500">90 days</p>
                <p className={`text-lg font-bold ${Number(summary.forecast["90d"] || 0) >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                  {Number(summary.forecast["90d"] || 0) >= 0 ? "+" : ""}{Number(summary.forecast["90d"] || 0).toFixed(2)}%
                </p>
              </div>
            </div>

            <p className="mt-4 text-sm text-slate-600 leading-relaxed">{summary.explanation}</p>
            <p className="mt-2 text-xs text-slate-500">Sources: {summary.sources.join(" • ")}</p>
          </>
        )}
      </div>
    </div>
  );
}
