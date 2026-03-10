import React, { useMemo } from "react";
import { formatCurrencyUSD } from "../utils/formatters";

const REC_STYLE = {
  "Strong Buy": "text-emerald-400 bg-emerald-500/15 border-emerald-400/40",
  Buy: "text-lime-300 bg-lime-500/15 border-lime-300/30",
  Hold: "text-slate-300 bg-slate-500/15 border-slate-300/30",
  Sell: "text-rose-300 bg-rose-500/15 border-rose-300/30",
  "Strong Sell": "text-rose-200 bg-rose-700/30 border-rose-200/30",
};

function scoreColor(score = 50) {
  if (score >= 70) return "text-emerald-400";
  if (score >= 50) return "text-amber-300";
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

function SummaryCard({ title, children, dark = false }) {
  return (
    <div className={`${dark ? "bg-[#111d39] border-slate-700" : "bg-slate-50 border-slate-200"} rounded-2xl border p-4 shadow-md`}>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</p>
      <div className="mt-2">{children}</div>
    </div>
  );
}

export default function AIInvestmentAnalysis({ reco, language = "en", dark = false }) {
  const recommendation = reco?.recommendation || "Hold";
  const confidencePct = Math.round(Number(reco?.confidence || 0) * 100);
  const currentPrice = Number(reco?.current_price || 0);
  const targetLow = Number(reco?.target_price_low || 0);
  const targetAvg = Number(reco?.target_price || reco?.target_price_mean || 0);
  const targetHigh = Number(reco?.target_price_high || 0);
  const upsidePct = Number(reco?.upside_pct || 0);
  const aiScore = Number(reco?.ai_score || 50);
  const riskLevel = reco?.risk_level || "Medium";
  const signals = reco?.signals || {};
  const technical = reco?.technical_indicators || {};
  const newsDist = reco?.news_sentiment_distribution || {};
  const forecast = reco?.forecast || {};
  const weights = reco?.weights || {};
  const miniPath = useMemo(() => sparklinePath(forecast?.points || []), [forecast]);

  const lowBound = targetLow > 0 ? targetLow : Math.min(currentPrice || 0, targetAvg || 0);
  const highBound = targetHigh > 0 ? targetHigh : Math.max(currentPrice || 0, targetAvg || 0, 1);
  const progress = Math.max(0, Math.min(100, ((currentPrice - lowBound) / Math.max(highBound - lowBound, 1e-9)) * 100));

  return (
    <section className="rounded-3xl border border-slate-700/70 bg-[#0F172A] p-6 shadow-xl text-slate-100">
      <div className="mb-5">
        <h3 className="text-2xl font-bold">AI Investment Analysis</h3>
        <p className="text-sm text-slate-400 mt-1">Multi-signal model from trend, technicals, sentiment, momentum, and AI forecast.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <SummaryCard title="Recommendation" dark>
          <div className={`inline-flex items-center rounded-xl border px-3 py-1.5 text-lg font-bold ${REC_STYLE[recommendation] || REC_STYLE.Hold}`}>
            {recommendation}
          </div>
          <p className="text-sm text-slate-300 mt-3">Confidence {confidencePct}%</p>
        </SummaryCard>

        <SummaryCard title="Target Price" dark>
          <div className="space-y-1 text-sm">
            <p>Low: <span className="font-semibold">{formatCurrencyUSD(targetLow, language)}</span></p>
            <p>Average: <span className="font-semibold">{formatCurrencyUSD(targetAvg, language)}</span></p>
            <p>High: <span className="font-semibold">{formatCurrencyUSD(targetHigh, language)}</span></p>
            <p className="pt-1 text-slate-300">Current: {formatCurrencyUSD(currentPrice, language)}</p>
            <p className={`font-semibold ${upsidePct >= 0 ? "text-emerald-400" : "text-rose-300"}`}>Upside: {upsidePct >= 0 ? "+" : ""}{upsidePct.toFixed(2)}%</p>
          </div>
          <div className="mt-3 h-2 w-full rounded-full bg-slate-700 overflow-hidden">
            <div className="h-full rounded-full bg-gradient-to-r from-[#2563EB] to-[#1E3A8A]" style={{ width: `${progress.toFixed(1)}%` }} />
          </div>
        </SummaryCard>

        <SummaryCard title="AI Confidence" dark>
          <p className={`text-3xl font-black ${scoreColor(aiScore)}`}>{confidencePct}%</p>
          <p className="text-xs text-slate-400 mt-2">Model signals align across technical trend, sentiment, and momentum.</p>
        </SummaryCard>

        <SummaryCard title="Risk Level" dark>
          <span className={`inline-flex rounded-xl border px-3 py-1.5 text-sm font-bold ${riskBadge(riskLevel)}`}>{riskLevel}</span>
          <p className="text-sm text-slate-300 mt-3">AI Score: <span className={`font-bold ${scoreColor(aiScore)}`}>{aiScore.toFixed(1)} / 100</span></p>
        </SummaryCard>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 mt-5">
        <SummaryCard title="Technical Score" dark>
          <p className={`text-2xl font-black ${scoreColor(signals?.technical_score)}`}>{Number(signals?.technical_score || 0).toFixed(1)} / 100</p>
          <div className="mt-2 text-xs text-slate-300 space-y-1">
            <p>RSI: {Number(technical?.rsi || 0).toFixed(1)}</p>
            <p>MACD: {Number(technical?.macd || 0).toFixed(3)} / {Number(technical?.macd_signal || 0).toFixed(3)}</p>
            <p>MA50 vs MA200: {technical?.golden_cross ? "Golden Cross" : "No Cross"}</p>
          </div>
        </SummaryCard>

        <SummaryCard title="News Sentiment" dark>
          <p className="text-lg font-bold">{signals?.news_sentiment_label || "Neutral"} <span className="text-sm text-slate-400">{Number(reco?.sentiment_avg || 0).toFixed(2)}</span></p>
          <div className="mt-3 space-y-2 text-xs">
            <p className="text-emerald-300">Bullish: {Number(newsDist?.bullish || 0).toFixed(1)}%</p>
            <p className="text-slate-300">Neutral: {Number(newsDist?.neutral || 0).toFixed(1)}%</p>
            <p className="text-rose-300">Bearish: {Number(newsDist?.bearish || 0).toFixed(1)}%</p>
          </div>
        </SummaryCard>

        <SummaryCard title="Momentum" dark>
          <p className={`text-2xl font-black ${scoreColor(signals?.momentum_score)}`}>{Number(signals?.momentum_score || 0).toFixed(1)} / 100</p>
          <p className="text-xs text-slate-300 mt-2">Trend: {technical?.trend_label || "Neutral"}</p>
          <p className="text-xs text-slate-400 mt-1">
            Weight model: T{weights.technical || 40}% / N{weights.news_sentiment || 30}% / M{weights.momentum || 20}% / V{weights.volatility_risk || 10}%
          </p>
        </SummaryCard>

        <SummaryCard title="AI Forecast" dark>
          <p className={`text-2xl font-black ${Number(forecast?.predicted_return_pct || 0) >= 0 ? "text-emerald-400" : "text-rose-300"}`}>
            {Number(forecast?.predicted_return_pct || 0) >= 0 ? "+" : ""}{Number(forecast?.predicted_return_pct || 0).toFixed(2)}%
          </p>
          <p className="text-xs text-slate-400">Predicted 30-day return</p>
          <svg viewBox="0 0 100 42" className="w-full h-14 mt-2">
            <path d={miniPath} fill="none" stroke="url(#forecastGradient)" strokeWidth="2.5" strokeLinecap="round" />
            <defs>
              <linearGradient id="forecastGradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor="#38BDF8" />
                <stop offset="100%" stopColor="#2563EB" />
              </linearGradient>
            </defs>
          </svg>
        </SummaryCard>
      </div>
    </section>
  );
}
