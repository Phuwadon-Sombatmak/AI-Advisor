import React from "react";

export default function AIInsightCard({ symbol = "NVDA", action = "Buy", confidence = 78, risk = "Medium", dark }) {
  const riskClass = risk === "High" ? "bg-rose-100 text-rose-700" : risk === "Low" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700";

  return (
    <div
      className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5`}
      style={{ boxShadow: "0 10px 25px rgba(0,0,0,0.08)" }}
    >
      <p className={`${dark ? "text-cyan-300" : "text-cyan-700"} text-xs font-semibold uppercase tracking-wider mb-2`}>AI Recommendation</p>
      <p className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold mb-4`}>
        {symbol} <span className="text-[#2563EB]">→ {action}</span>
      </p>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-700">Confidence: {confidence}%</span>
        <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${riskClass}`}>Risk: {risk}</span>
      </div>
    </div>
  );
}
