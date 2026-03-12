import React from "react";
import { AlertTriangle, BarChart3, Building2, LineChart as LineChartIcon, ShieldAlert, Target } from "lucide-react";
import { Bar, BarChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ConfidenceFooter from "./ConfidenceFooter";
import { buildMarketSummary } from "../utils/aiAdvisor";

function ChartBlock({ charts, dark }) {
  if (!charts) return null;
  const price = charts?.price?.points || [];
  const sentiment = charts?.sentiment?.points || [];

  return (
    <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
      {price.length > 0 ? (
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2`}>
          <p className="text-[11px] font-semibold text-slate-500 mb-1">{charts?.price?.title || "Price chart"}</p>
          <div className="h-24">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={price}>
                <XAxis dataKey="label" hide />
                <YAxis hide domain={["dataMin", "dataMax"]} />
                <Tooltip />
                <Line type="monotone" dataKey="value" stroke="#2563EB" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : null}
      {sentiment.length > 0 ? (
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2`}>
          <p className="text-[11px] font-semibold text-slate-500 mb-1">{charts?.sentiment?.title || "Sentiment chart"}</p>
          <div className="h-24">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sentiment}>
                <XAxis dataKey="label" hide />
                <YAxis hide domain={[-1, 1]} />
                <Tooltip />
                <Bar dataKey="value" fill="#38BDF8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ComparisonBlock({ schema, dark }) {
  const comp = schema?.comparison;
  const categories = Array.isArray(comp?.categories) ? comp.categories : [];
  if (!comp || categories.length === 0) return null;
  return (
    <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} mt-2 rounded-xl border p-2.5`}>
      <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">Side-by-Side</p>
      <div className="mt-1 overflow-x-auto">
        <table className="min-w-[320px] w-full text-[12px]">
          <thead>
            <tr className="text-slate-500">
              <th className="text-left py-1 pr-2">Metric</th>
              <th className="text-left py-1 pr-2">{comp.left_symbol}</th>
              <th className="text-left py-1 pr-2">{comp.right_symbol}</th>
              <th className="text-left py-1">Leader</th>
            </tr>
          </thead>
          <tbody>
            {categories.map((row, idx) => (
              <tr key={`${row.label}-${idx}`} className="border-t border-slate-200/30">
                <td className="py-1 pr-2">{row.label}</td>
                <td className="py-1 pr-2">{row.left_value}</td>
                <td className="py-1 pr-2">{row.right_value}</td>
                <td className="py-1 font-semibold">{row.winner}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StructuredAnswer({ schema, summary, intent, dark }) {
  if (!schema || typeof schema !== "object") return null;
  const stockOverview = schema?.stock_overview || null;
  const marketSignals = schema?.market_signals || null;
  const investmentView = schema?.investment_view || null;
  if (stockOverview && marketSignals && investmentView) {
    const risks = Array.isArray(schema?.risks) ? schema.risks.slice(0, 4) : [];
    return (
      <div className="mt-2 space-y-2 text-[13px]">
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold inline-flex items-center gap-1.5">
            <Building2 size={12} className="text-blue-500" /> Stock Overview
          </p>
          <p className="mt-1 font-semibold">{stockOverview.company_name} ({stockOverview.ticker})</p>
          <p className="text-[12px] text-slate-500 mt-0.5">
            {stockOverview.sector} • {stockOverview.industry}
          </p>
          {stockOverview.price ? <p className="mt-1 font-medium">Price: ${Number(stockOverview.price).toFixed(2)}</p> : null}
        </div>
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold inline-flex items-center gap-1.5">
            <LineChartIcon size={12} className="text-cyan-500" /> Market Signals
          </p>
          <ul className="mt-1 space-y-1">
            <li>• Technical trend: {marketSignals.technical_trend}</li>
            <li>• Momentum: {marketSignals.momentum}</li>
            <li>• News sentiment: {marketSignals.news_sentiment}</li>
            <li>• Fear & Greed: {marketSignals.fear_greed_index} ({marketSignals.market_regime})</li>
          </ul>
        </div>
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold inline-flex items-center gap-1.5">
            <ShieldAlert size={12} className="text-rose-500" /> Key Risks
          </p>
          <ul className="mt-1 space-y-1">
            {risks.map((line, idx) => (
              <li key={`${line}-${idx}`} className="leading-relaxed">• {line}</li>
            ))}
          </ul>
        </div>
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold inline-flex items-center gap-1.5">
            <Target size={12} className="text-emerald-500" /> Investment View
          </p>
          <p className="mt-1 font-semibold">{investmentView.recommendation}</p>
          <p className="text-[12px] text-slate-500 mt-0.5">AI Confidence: {investmentView.confidence}%</p>
          <p className="text-[12px] mt-1">
            Forecast: 7D {investmentView?.forecast_horizon?.["7d"] ?? 0}% • 30D {investmentView?.forecast_horizon?.["30d"] ?? 0}% • 90D {investmentView?.forecast_horizon?.["90d"] ?? 0}%
          </p>
        </div>
      </div>
    );
  }
  const isSectorStockPicker = intent === "sector_stock_picker" || schema.intent === "sector_stock_picker";
  if (isSectorStockPicker) {
    const picker = schema?.sector_stock_picker || {};
    const overview = schema?.sector_overview || {};
    const sector = picker?.sector || "Sector";
    const etf = picker?.etf || overview?.etf || "-";
    const stocks = Array.isArray(picker?.stocks) ? picker.stocks : [];
    const reasons = stocks.slice(0, 5);
    const riskText = (Array.isArray(schema?.risks) && schema.risks[0]) || "Sector stocks can remain volatile in weak market regimes.";
    const fg = overview?.fear_greed_index;
    const regime = overview?.market_regime || "-";
    return (
      <div className="mt-2 space-y-2 text-[13px]">
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">Sector Overview</p>
          <p className="mt-1 font-semibold">{sector} ({etf})</p>
          <p className="text-[12px] text-slate-500 mt-0.5">
            Top Stocks: {(overview?.top_stocks_inline || reasons.map((x) => x.symbol)).filter(Boolean).join(" • ") || "-"}
          </p>
          <p className="text-[12px] mt-1">
            Fear & Greed: {fg ?? "-"} ({regime})
          </p>
        </div>
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">Top Momentum Stocks</p>
          <ul className="mt-1 space-y-1">
            {reasons.map((x, idx) => (
              <li key={`${x.symbol || "S"}-${idx}`} className="leading-relaxed">
                • {x.name || x.symbol} ({x.symbol}) · {x.price != null ? `$${Number(x.price).toFixed(2)}` : "Price N/A"} · {x.return_3m_pct != null ? `3M ${Number(x.return_3m_pct) >= 0 ? "+" : ""}${Number(x.return_3m_pct).toFixed(2)}%` : "3M N/A"} · {x.momentum || "N/A"}
              </li>
            ))}
          </ul>
        </div>
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">Sector Risks</p>
          <p className="mt-1">{riskText}</p>
        </div>
      </div>
    );
  }
  const rationale = Array.isArray(schema.rationale) ? schema.rationale : Array.isArray(schema.summary_points) ? schema.summary_points : [];
  const risks = Array.isArray(schema.risks) ? schema.risks : [];
  const outlook = schema.actionable_view || schema.stance || "-";
  const isComparison = intent === "stock_comparison" || schema.intent === "stock_comparison";
  return (
    <div className="mt-2 space-y-2 text-[13px]">
      {summary ? (
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">Overview</p>
          <p className="mt-1 font-medium">{buildMarketSummary(summary)}</p>
        </div>
      ) : null}

      <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
        <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">{isComparison ? "Quick Verdict" : "Key Drivers"}</p>
        <ul className="mt-1 space-y-1">
          {rationale.slice(0, 4).map((line, idx) => (
            <li key={`${line}-${idx}`} className="leading-relaxed">• {line}</li>
          ))}
        </ul>
      </div>

      {isComparison ? <ComparisonBlock schema={schema} dark={dark} /> : null}

      <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
        <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">Risks</p>
        <ul className="mt-1 space-y-1">
          {risks.slice(0, 4).map((line, idx) => (
            <li key={`${line}-${idx}`} className="leading-relaxed">• {line}</li>
          ))}
        </ul>
      </div>

      <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
        <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">Actionable View</p>
        <p className="mt-1 font-semibold inline-flex items-center gap-1.5">
          <BarChart3 size={14} className="text-blue-500" />
          {outlook}
        </p>
      </div>
    </div>
  );
}

export default function ChatMessage({ message, dark = false }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[92%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
          isUser
            ? "bg-gradient-to-r from-[#2563EB] to-[#1E3A8A] text-white rounded-br-md"
            : dark
              ? "bg-slate-800 text-slate-100 rounded-bl-md border border-slate-700"
              : "bg-white text-slate-800 rounded-bl-md border border-slate-200"
        }`}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>

        {!isUser && message.warning ? (
          <div className="mt-2 rounded-lg bg-amber-500/15 border border-amber-400/40 text-amber-200 text-[12px] px-2 py-1 inline-flex items-center gap-1.5">
            <AlertTriangle size={14} />
            {message.warning}
          </div>
        ) : null}

        {!isUser ? <StructuredAnswer schema={message.schema} summary={message.summary} intent={message.intent} dark={dark} /> : null}
        {!isUser ? <ChartBlock charts={message.charts} dark={dark} /> : null}

        {!isUser ? (
          <ConfidenceFooter
            confidence={message.confidence}
            sources={message.sources}
            updatedAt={message.time}
            dataCoverage={message.dataValidation}
            dark={dark}
          />
        ) : null}

        <p className={`mt-2 text-[10px] ${isUser ? "text-blue-100" : dark ? "text-slate-400" : "text-slate-500"}`}>{message.time}</p>
      </div>
    </div>
  );
}
