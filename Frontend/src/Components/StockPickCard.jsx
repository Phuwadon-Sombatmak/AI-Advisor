import React from "react";

function ScoreBar({ score }) {
  const pct = Math.max(0, Math.min(100, score));
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
        <span>AI Score</span>
        <span className="font-semibold text-slate-700">{pct}%</span>
      </div>
      <div className="h-2 rounded-full bg-slate-200 overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }} />
      </div>
    </div>
  );
}

const REC_STYLE = {
  "Strong Buy": "bg-emerald-100 text-emerald-700",
  Buy: "bg-lime-100 text-lime-700",
  Hold: "bg-amber-100 text-amber-700",
  Sell: "bg-rose-100 text-rose-700",
};

function ConfidenceGauge({ score }) {
  if (!Number.isFinite(score)) {
    return (
      <div className="w-16 h-16 rounded-full border border-slate-300 grid place-items-center text-[11px] font-semibold text-slate-500">
        N/A
      </div>
    );
  }
  const pct = Math.max(0, Math.min(100, score));
  const r = 24;
  const c = 2 * Math.PI * r;
  const d = c - (pct / 100) * c;
  return (
    <div className="relative w-16 h-16">
      <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
        <circle cx="32" cy="32" r={r} stroke="#E2E8F0" strokeWidth="6" fill="none" />
        <circle
          cx="32"
          cy="32"
          r={r}
          stroke="#2563EB"
          strokeWidth="6"
          fill="none"
          strokeDasharray={c}
          strokeDashoffset={d}
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-xs font-bold text-slate-700">{pct}%</div>
    </div>
  );
}

export default function StockPickCard({ stock, dark }) {
  const sentimentClass =
    stock.sentiment === "Bullish"
      ? "bg-[#DCFCE7] text-[#15803D]"
      : stock.sentiment === "Bearish"
        ? "bg-[#FEE2E2] text-[#B91C1C]"
        : "bg-[#E2E8F0] text-[#475569]";

  return (
    <article className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md transition-all hover:-translate-y-[3px] hover:shadow-lg`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold`}>{stock.ticker}</h4>
          <p className="text-sm text-slate-500">{stock.company}</p>
        </div>
        <ConfidenceGauge score={stock.confidence} />
      </div>

      <div className="mt-4 space-y-3 text-sm">
        <ScoreBar score={stock.aiScore} />
        <div className="flex items-center gap-2 flex-wrap">
          {stock.recommendation ? (
            <span className={`px-2 py-1 rounded-full text-xs font-semibold ${REC_STYLE[stock.recommendation] || "bg-slate-100 text-slate-700"}`}>
              {stock.recommendation}
            </span>
          ) : null}
          {stock.momentum ? <span className="px-2 py-1 rounded-full bg-blue-100 text-blue-700 text-xs font-semibold">Momentum: {stock.momentum}</span> : null}
          {stock.risk ? <span className="px-2 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-semibold">Risk: {stock.risk}</span> : null}
          {stock.sentiment ? <span className={`px-2 py-1 rounded-full text-xs font-semibold ${sentimentClass}`}>{stock.sentiment}</span> : null}
        </div>
      </div>
    </article>
  );
}
