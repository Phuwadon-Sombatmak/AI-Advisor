import React, { useMemo } from "react";
import { formatCurrencyUSD } from "../utils/formatters";

const REC_STYLE = {
  "Strong Buy": "text-emerald-400 bg-emerald-500/15 border-emerald-400/40",
  Buy: "text-lime-300 bg-lime-500/15 border-lime-300/30",
  Hold: "text-slate-300 bg-slate-500/15 border-slate-300/30",
  Sell: "text-rose-300 bg-rose-500/15 border-rose-300/30",
  "Strong Sell": "text-rose-200 bg-rose-700/30 border-rose-200/30",
};

function recommendationStyle(level) {
  if (typeof level !== "string") return REC_STYLE.Hold;
  if (level.startsWith("Hold")) return REC_STYLE.Hold;
  return REC_STYLE[level] || REC_STYLE.Hold;
}

function scoreColor(score = null) {
  if (score === null || score === undefined || Number.isNaN(Number(score))) return "text-slate-400";
  const numeric = Number(score);
  if (numeric >= 70) return "text-emerald-400";
  if (numeric >= 50) return "text-amber-300";
  return "text-rose-300";
}

function riskBadge(level = "Medium") {
  const key = String(level).toLowerCase();
  if (key === "low") return "bg-emerald-500/15 text-emerald-300 border-emerald-300/30";
  if (key === "high") return "bg-rose-500/15 text-rose-300 border-rose-300/30";
  return "bg-amber-500/15 text-amber-300 border-amber-300/30";
}

function sparklinePath(points = []) {
  if (!points.length) return "";
  const values = points.map((p) => Number(p.price || p.value || 0));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  return values
    .map((v, i) => {
      const x = (i / Math.max(values.length - 1, 1)) * 100;
      const y = 40 - ((v - min) / range) * 35;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function toNumberOrNull(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function deriveTargetBand({ currentPrice, targetAvg, targetLow, targetHigh, forecastPct, aiScore }) {
  const current = toNumberOrNull(currentPrice);
  const average = toNumberOrNull(targetAvg);
  const low = toNumberOrNull(targetLow);
  const high = toNumberOrNull(targetHigh);
  const forecast = toNumberOrNull(forecastPct);
  const score = toNumberOrNull(aiScore);

  const bandPct = score != null
    ? Math.max(6, Math.min(14, 12 - ((score - 50) * 0.08)))
    : 8;

  const derivedAverage = average != null
    ? average
    : current != null && forecast != null
      ? current * (1 + (forecast / 100))
      : null;

  const derivedLow = low != null
    ? low
    : derivedAverage != null
      ? derivedAverage * (1 - (bandPct / 100))
      : null;

  const derivedHigh = high != null
    ? high
    : derivedAverage != null
      ? derivedAverage * (1 + (bandPct / 100))
      : null;

  const upside = derivedAverage != null && current != null && current > 0
    ? ((derivedAverage - current) / current) * 100
    : null;

  return {
    targetAvg: derivedAverage,
    targetLow: derivedLow,
    targetHigh: derivedHigh,
    upsidePct: upside,
  };
}

function deriveNewsLabel(label, distribution) {
  if (label && label !== "N/A") return label;
  const bullish = toNumberOrNull(distribution?.bullish);
  const neutral = toNumberOrNull(distribution?.neutral);
  const bearish = toNumberOrNull(distribution?.bearish);
  const values = [
    ["Bullish", bullish],
    ["Neutral", neutral],
    ["Bearish", bearish],
  ].filter(([, value]) => value != null);
  if (!values.length) return "N/A";
  values.sort((a, b) => b[1] - a[1]);
  return values[0][0];
}

function SummaryCard({ title, children, dark = false }) {
  return (
    <div className={`${dark ? "bg-[#111d39] border-slate-700" : "bg-slate-50 border-slate-200"} rounded-2xl border p-4 shadow-md`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</p>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export default function AIInvestmentAnalysis({ reco, language = "en", dark = false }) {
  const recommendation = typeof reco?.recommendation === "string" && reco.recommendation.trim()
    ? reco.recommendation
    : "N/A";
  const confidencePct = typeof reco?.confidence === "number" ? Math.round(Number(reco.confidence) * 100) : null;
  const currentPrice = reco?.current_price ?? null;
  const aiScore = reco?.ai_score ?? null;
  const riskLevel = reco?.risk_level || "N/A";
  const signals = reco?.signals || {};
  const technical = reco?.technical_indicators || {};
  const newsDist = reco?.news_sentiment_distribution || {};
  const forecast = reco?.forecast || {};
  const weights = reco?.weights || {};
  const miniPath = useMemo(() => sparklinePath(forecast?.points || []), [forecast]);
  const sourceNotes = Array.isArray(reco?.sources) ? reco.sources : [];
  const hasAnalystTarget = sourceNotes.some((entry) => String(entry).toLowerCase().includes("analyst target"));
  const targetSourceLabel = hasAnalystTarget ? "Analyst Target" : "Model Target";
  const forecastSourceLabel = "Model Forecast";
  const derivedTargets = useMemo(
    () => deriveTargetBand({
      currentPrice,
      targetAvg: reco?.target_price ?? reco?.target_price_mean ?? null,
      targetLow: reco?.target_price_low ?? null,
      targetHigh: reco?.target_price_high ?? null,
      forecastPct: forecast?.predicted_return_pct ?? null,
      aiScore,
    }),
    [aiScore, currentPrice, forecast?.predicted_return_pct, reco?.target_price, reco?.target_price_high, reco?.target_price_low, reco?.target_price_mean]
  );
  const targetLow = derivedTargets.targetLow;
  const targetAvg = derivedTargets.targetAvg;
  const targetHigh = derivedTargets.targetHigh;
  const upsidePct = reco?.upside_pct ?? derivedTargets.upsidePct;
  const newsLabel = deriveNewsLabel(signals?.news_sentiment_label, newsDist);

  const hasTargetBand = Number(targetAvg) > 0 || Number(targetLow) > 0 || Number(targetHigh) > 0;
  const lowBound = Number(targetLow) > 0 ? Number(targetLow) : Math.min(Number(currentPrice || 0), Number(targetAvg || 0));
  const highBound = Number(targetHigh) > 0 ? Number(targetHigh) : Math.max(Number(currentPrice || 0), Number(targetAvg || 0), 1);
  const progress = hasTargetBand
    ? Math.max(0, Math.min(100, ((Number(currentPrice || 0) - lowBound) / Math.max(highBound - lowBound, 1e-9)) * 100))
    : 0;

  return (
    <section className="rounded-3xl border border-slate-700/70 bg-[#0F172A] p-6 shadow-xl text-slate-100">
      <div className="mb-5">
        <h3 className="text-2xl font-bold">AI Investment Analysis</h3>
        <p className="text-sm text-slate-400 mt-1">Multi-signal model from trend, technicals, sentiment, momentum, and AI forecast.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <SummaryCard title="Recommendation" dark>
          <div className={`inline-flex items-center rounded-xl border px-3 py-1.5 text-lg font-bold ${recommendationStyle(recommendation)}`}>
            {recommendation}
          </div>
          <p className="text-sm text-slate-300 mt-3">Confidence {confidencePct != null ? `${confidencePct}%` : "N/A"}</p>
        </SummaryCard>

        <SummaryCard title="Target Price" dark>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{targetSourceLabel}</p>
          <div className="space-y-1 text-sm">
            <p>Low: <span className="font-semibold">{targetLow != null ? formatCurrencyUSD(targetLow, language) : "N/A"}</span></p>
            <p>Average: <span className="font-semibold">{targetAvg != null ? formatCurrencyUSD(targetAvg, language) : "N/A"}</span></p>
            <p>High: <span className="font-semibold">{targetHigh != null ? formatCurrencyUSD(targetHigh, language) : "N/A"}</span></p>
            <p className="pt-1 text-slate-300">Current: {currentPrice != null ? formatCurrencyUSD(currentPrice, language) : "N/A"}</p>
            <p className={`font-semibold ${Number(upsidePct) >= 0 ? "text-emerald-400" : "text-rose-300"}`}>Upside: {upsidePct != null ? `${Number(upsidePct) >= 0 ? "+" : ""}${Number(upsidePct).toFixed(2)}%` : "N/A"}</p>
          </div>
          <div className="mt-3 h-2 w-full rounded-full bg-slate-700 overflow-hidden">
            <div className="h-full rounded-full bg-gradient-to-r from-[#2563EB] to-[#1E3A8A]" style={{ width: `${progress.toFixed(1)}%` }} />
          </div>
        </SummaryCard>

        <SummaryCard title="AI Confidence" dark>
          <p className={`text-3xl font-black ${scoreColor(aiScore)}`}>{confidencePct != null ? `${confidencePct}%` : "N/A"}</p>
          <p className="text-xs text-slate-400 mt-2">Model signals align across technical trend, sentiment, and momentum.</p>
        </SummaryCard>

        <SummaryCard title="Risk Level" dark>
          <span className={`inline-flex rounded-xl border px-3 py-1.5 text-sm font-bold ${riskBadge(riskLevel)}`}>{riskLevel}</span>
          <p className="text-sm text-slate-300 mt-3">AI Score: <span className={`font-bold ${scoreColor(aiScore)}`}>{aiScore != null ? `${Number(aiScore).toFixed(1)} / 100` : "N/A"}</span></p>
        </SummaryCard>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mt-5">
        <SummaryCard title="Technical Score" dark>
          <p className={`text-2xl font-black ${scoreColor(signals?.technical_score)}`}>{signals?.technical_score != null ? `${Number(signals.technical_score).toFixed(1)} / 100` : "N/A"}</p>
          <div className="mt-2 text-xs text-slate-300 space-y-1">
            <p>RSI: {technical?.rsi != null ? Number(technical.rsi).toFixed(1) : "N/A"}</p>
            <p>MACD: {technical?.macd != null && technical?.macd_signal != null ? `${Number(technical.macd).toFixed(3)} / ${Number(technical.macd_signal).toFixed(3)}` : "N/A"}</p>
            <p>
              MA50 vs MA200: {
                technical?.golden_cross != null
                  ? (technical.golden_cross ? "Golden Cross" : "Death Cross")
                  : (technical?.ma50 != null || technical?.ma200 != null)
                    ? `MA50 ${technical?.ma50 != null ? Number(technical.ma50).toFixed(2) : "N/A"} / MA200 ${technical?.ma200 != null ? Number(technical.ma200).toFixed(2) : "N/A"}`
                    : "Insufficient history"
              }
            </p>
          </div>
        </SummaryCard>

        <SummaryCard title="News Sentiment" dark>
          <p className="text-lg font-bold">{newsLabel} <span className="text-sm text-slate-400">{reco?.sentiment_avg != null ? Number(reco.sentiment_avg).toFixed(2) : "N/A"}</span></p>
          <div className="mt-3 space-y-2 text-xs">
            <p className="text-emerald-300">Bullish: {newsDist?.bullish != null ? `${Number(newsDist.bullish).toFixed(1)}%` : "N/A"}</p>
            <p className="text-slate-300">Neutral: {newsDist?.neutral != null ? `${Number(newsDist.neutral).toFixed(1)}%` : "N/A"}</p>
            <p className="text-rose-300">Bearish: {newsDist?.bearish != null ? `${Number(newsDist.bearish).toFixed(1)}%` : "N/A"}</p>
          </div>
        </SummaryCard>

        <SummaryCard title="Momentum" dark>
          <p className={`text-2xl font-black ${scoreColor(signals?.momentum_score)}`}>{signals?.momentum_score != null ? `${Number(signals.momentum_score).toFixed(1)} / 100` : "N/A"}</p>
          <p className="text-xs text-slate-300 mt-2">Trend: {technical?.trend_label || "N/A"}</p>
          <p className="text-xs text-slate-400 mt-1">
            Weight model: T{weights.technical ?? "N/A"}% / N{weights.news_sentiment ?? "N/A"}% / M{weights.momentum ?? "N/A"}% / V{weights.volatility_risk ?? "N/A"}%
          </p>
        </SummaryCard>

        <SummaryCard title="AI Forecast" dark>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">{forecastSourceLabel}</p>
          <p className={`text-2xl font-black ${forecast?.predicted_return_pct != null ? (Number(forecast.predicted_return_pct) >= 0 ? "text-emerald-400" : "text-rose-300") : "text-slate-400"}`}>
            {forecast?.predicted_return_pct != null ? `${Number(forecast.predicted_return_pct) >= 0 ? "+" : ""}${Number(forecast.predicted_return_pct).toFixed(2)}%` : "N/A"}
          </p>
          <p className="text-xs text-slate-400">Predicted 30-day return</p>
          {miniPath ? (
            <svg viewBox="0 0 100 42" className="w-full h-14 mt-2">
              <path d={miniPath} fill="none" stroke="url(#forecastGradient)" strokeWidth="2.5" strokeLinecap="round" />
              <defs>
                <linearGradient id="forecastGradient" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#38BDF8" />
                  <stop offset="100%" stopColor="#2563EB" />
                </linearGradient>
              </defs>
            </svg>
          ) : (
            <p className="mt-2 text-xs text-slate-500">Forecast data unavailable.</p>
          )}
        </SummaryCard>
      </div>
    </section>
  );
}
