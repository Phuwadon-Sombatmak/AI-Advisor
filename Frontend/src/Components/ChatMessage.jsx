import React from "react";
import { AlertTriangle, BarChart3, Building2, LineChart as LineChartIcon, ShieldAlert, Target } from "lucide-react";
import { Bar, BarChart, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ConfidenceFooter from "./ConfidenceFooter";
import { buildMarketSummary } from "../utils/aiAdvisor";

function formatForecastValue(value) {
  if (value == null || value === "" || Number.isNaN(Number(value))) {
    return "N/A";
  }

  const numeric = Number(value);
  return `${numeric >= 0 ? "+" : ""}${numeric.toFixed(2)}%`;
}

function SourceTags({ tags = [], dark }) {
  if (!Array.isArray(tags) || tags.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {tags.map((tag) => (
        <span
          key={tag}
          className={`px-2 py-0.5 rounded-full border text-[10px] font-semibold ${
            dark
              ? "bg-slate-900/80 border-slate-600 text-cyan-200"
              : "bg-slate-50 border-slate-200 text-slate-600"
          }`}
        >
          {tag}
        </span>
      ))}
    </div>
  );
}

function ChartBlock({ charts, dark }) {
  if (!charts) return null;
  const price = charts?.price?.points || [];
  const sentiment = charts?.sentiment?.points || [];

  return (
    <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
      {price.length > 0 ? (
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2`}>
          <p className="text-[11px] font-semibold text-slate-500 mb-1">{charts?.price?.title || "Price chart"}</p>
          <div className="h-24 min-w-0">
            <ResponsiveContainer width="100%" height={96} minWidth={0} minHeight={96}>
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
          <div className="h-24 min-w-0">
            <ResponsiveContainer width="100%" height={96} minWidth={0} minHeight={96}>
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

function getStructuredLead(schema, intent) {
  if (!schema || typeof schema !== "object") return null;
  const hasStructuredStock =
    schema?.stock_overview && schema?.market_context && schema?.technical_signals_section && schema?.investment_interpretation;
  const hasStructuredSector =
    schema?.market_context && schema?.sector_analysis && schema?.investment_interpretation;
  const hasTrending = intent === "trending_stock_discovery" && Array.isArray(schema?.trending_stocks);

  if (hasStructuredStock || hasStructuredSector || hasTrending) {
    return typeof schema.direct_answer === "string" && schema.direct_answer.trim()
      ? schema.direct_answer.trim()
      : null;
  }

  return null;
}

function StructuredAnswer({ schema, summary, intent, dark }) {
  if (!schema || typeof schema !== "object") return null;
  if (intent === "trending_stock_discovery" && Array.isArray(schema?.trending_stocks)) {
    const marketContext = schema?.market_context || {};
    return (
      <div className="mt-2 space-y-2 text-[13px]">
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold inline-flex items-center gap-1.5">
            <BarChart3 size={12} className="text-blue-500" /> Market Context
          </p>
          <ul className="mt-1 space-y-1">
            <li>• Market sentiment: {marketContext.market_sentiment || "Relevant data is not available."}</li>
            <li>• Fear &amp; Greed: {marketContext.fear_greed_index ?? "Relevant data is not available."}</li>
            <li>• Leading sector: {marketContext.top_sector || "Relevant data is not available."}</li>
          </ul>
        </div>
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold inline-flex items-center gap-1.5">
            <LineChartIcon size={12} className="text-cyan-500" /> Trending Stocks
          </p>
          <div className="mt-2 space-y-2">
            {schema.trending_stocks.slice(0, 5).map((item) => (
              <div key={item.symbol} className={`${dark ? "bg-slate-950/70" : "bg-slate-50"} rounded-lg px-3 py-2`}>
                <p className="font-semibold">{item.name} ({item.symbol})</p>
                <p className="text-[12px] text-slate-500">
                  Price: ${Number(item.price || 0).toFixed(2)}
                  {item.change_pct != null ? ` • Day change ${Number(item.change_pct) >= 0 ? "+" : ""}${Number(item.change_pct).toFixed(2)}%` : ""}
                  {item.month_return != null ? ` • 1M return ${Number(item.month_return) >= 0 ? "+" : ""}${Number(item.month_return).toFixed(2)}%` : ""}
                </p>
                <p className="text-[12px] mt-1">{item.reason || "Relevant data is not available."}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
  const stockOverview = schema?.stock_overview || null;
  const marketContext = schema?.market_context || null;
  const technicalSignalsSection = schema?.technical_signals_section || null;
  const fundamentalDrivers = schema?.fundamental_drivers || null;
  const riskFactors = schema?.risk_factors || null;
  const investmentInterpretation = schema?.investment_interpretation || null;
  if (stockOverview && marketContext && technicalSignalsSection && investmentInterpretation) {
    const risks = Array.isArray(riskFactors?.points)
      ? riskFactors.points.slice(0, 4)
      : Array.isArray(schema?.risks)
        ? schema.risks.slice(0, 4)
        : [];
    const marketContextPoints = Array.isArray(marketContext?.points) ? marketContext.points.slice(0, 3) : [];
    const technicalPoints = Array.isArray(technicalSignalsSection?.points) ? technicalSignalsSection.points.slice(0, 5) : [];
    const driverPoints = Array.isArray(fundamentalDrivers?.points) ? fundamentalDrivers.points.slice(0, 4) : [];
    return (
      <div className="mt-2 space-y-2 text-[13px]">
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold inline-flex items-center gap-1.5">
            <Building2 size={12} className="text-blue-500" /> Market Context
          </p>
          <ul className="mt-1 space-y-1">
            {marketContextPoints.map((line, idx) => (
              <li key={`${line}-${idx}`} className="leading-relaxed">• {line}</li>
            ))}
          </ul>
        </div>
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold inline-flex items-center gap-1.5">
            <Building2 size={12} className="text-blue-500" /> Stock Overview
          </p>
          <p className="mt-1 font-semibold">{stockOverview.company_name} ({stockOverview.ticker})</p>
          <p className="text-[12px] text-slate-500 mt-0.5">
            {stockOverview.sector} • {stockOverview.industry}
          </p>
          {stockOverview.price != null ? <p className="mt-1 font-medium">Price: ${Number(stockOverview.price).toFixed(2)}</p> : null}
          {stockOverview.price_change != null || stockOverview.price_change_pct != null ? (
            <p className="text-[12px] text-slate-500 mt-0.5">
              Change: {stockOverview.price_change != null ? `${Number(stockOverview.price_change) >= 0 ? "+" : ""}${Number(stockOverview.price_change).toFixed(2)}` : "N/A"}
              {stockOverview.price_change_pct != null ? ` (${Number(stockOverview.price_change_pct) >= 0 ? "+" : ""}${Number(stockOverview.price_change_pct).toFixed(2)}%)` : ""}
            </p>
          ) : null}
        </div>
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold inline-flex items-center gap-1.5">
            <LineChartIcon size={12} className="text-cyan-500" /> Technical Signals
          </p>
          <ul className="mt-1 space-y-1">
            {technicalPoints.map((line, idx) => (
              <li key={`${line}-${idx}`} className="leading-relaxed">• {line}</li>
            ))}
          </ul>
        </div>
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold inline-flex items-center gap-1.5">
            <BarChart3 size={12} className="text-emerald-500" /> Fundamental Drivers
          </p>
          <ul className="mt-1 space-y-1">
            {driverPoints.length ? driverPoints.map((line, idx) => (
              <li key={`${line}-${idx}`} className="leading-relaxed">• {line}</li>
            )) : <li className="leading-relaxed">• Relevant data is not available.</li>}
          </ul>
        </div>
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold inline-flex items-center gap-1.5">
            <ShieldAlert size={12} className="text-rose-500" /> Risk Factors
          </p>
          <ul className="mt-1 space-y-1">
            {risks.map((line, idx) => (
              <li key={`${line}-${idx}`} className="leading-relaxed">• {line}</li>
            ))}
          </ul>
        </div>
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold inline-flex items-center gap-1.5">
            <Target size={12} className="text-emerald-500" /> Investment Interpretation
          </p>
          <p className="mt-1 font-semibold">{investmentInterpretation.recommendation}</p>
          <p className="text-[12px] text-slate-500 mt-0.5">AI Confidence: {investmentInterpretation.confidence}%</p>
          <p className="text-[12px] mt-1 leading-relaxed">{investmentInterpretation.text || "Relevant data is not available."}</p>
          <p className="text-[12px] mt-1">
            Forecast: 7D {formatForecastValue(investmentInterpretation?.forecast_horizon?.["7d"])} • 30D {formatForecastValue(investmentInterpretation?.forecast_horizon?.["30d"])} • 90D {formatForecastValue(investmentInterpretation?.forecast_horizon?.["90d"])}
          </p>
        </div>
      </div>
    );
  }
  const rationale = Array.isArray(schema.rationale) ? schema.rationale : Array.isArray(schema.summary_points) ? schema.summary_points : [];
  const risks = Array.isArray(schema.risks) ? schema.risks : [];
  const outlook = schema.actionable_view || schema.stance || "-";
  return (
    <div className="mt-2 space-y-2 text-[13px]">
      {summary ? (
        <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">Overview</p>
          <p className="mt-1 font-medium">{buildMarketSummary(summary)}</p>
        </div>
      ) : null}

      <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} rounded-xl border p-2.5`}>
        <p className="text-[11px] uppercase tracking-wide text-slate-500 font-semibold">Key Drivers</p>
        <ul className="mt-1 space-y-1">
          {rationale.slice(0, 4).map((line, idx) => (
            <li key={`${line}-${idx}`} className="leading-relaxed">• {line}</li>
          ))}
        </ul>
      </div>

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
  const structuredLead = !isUser ? getStructuredLead(message.schema, message.intent) : null;
  const shouldHideFullParagraph = Boolean(structuredLead);
  const sourceTags = Array.isArray(message?.schema?.source_tags) ? message.schema.source_tags : [];
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
        {shouldHideFullParagraph ? (
          <p className="whitespace-pre-wrap leading-relaxed font-medium">{structuredLead}</p>
        ) : (
          <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>
        )}

        {!isUser && message.warning ? (
          <div className="mt-2 rounded-lg bg-amber-500/15 border border-amber-400/40 text-amber-200 text-[12px] px-2 py-1 inline-flex items-center gap-1.5">
            <AlertTriangle size={14} />
            {message.warning}
          </div>
        ) : null}

        {!isUser ? <StructuredAnswer schema={message.schema} summary={message.summary} intent={message.intent} dark={dark} /> : null}
        {!isUser ? <SourceTags tags={sourceTags} dark={dark} /> : null}
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
