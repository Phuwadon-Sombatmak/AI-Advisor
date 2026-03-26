import React from "react";
import { inferAssetMeta } from "../utils/assetMeta";

export default function AIInsightCard({ symbol = "N/A", action = null, confidence = null, risk = null, dark }) {
  const assetMeta = inferAssetMeta({ symbol });
  const riskClass =
    risk === "High"
      ? "bg-rose-100 text-rose-700"
      : risk === "Low"
        ? "bg-emerald-100 text-emerald-700"
        : "bg-amber-100 text-amber-700";
  const hasAction = Boolean(action && action !== "Data unavailable");
  const confidenceText =
    confidence === null || confidence === undefined || confidence === ""
      ? null
      : Number.isFinite(Number(confidence))
        ? Number(confidence) > 0
          ? `${Number(confidence).toFixed(0)}%`
          : null
        : null;
  const hasSummary = Boolean(hasAction || confidenceText || risk);

  return (
    <div
      className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5`}
      style={{ boxShadow: "0 10px 25px rgba(0,0,0,0.08)" }}
    >
      <p className={`${dark ? "text-cyan-300" : "text-cyan-700"} text-xs font-semibold uppercase tracking-wider mb-2`}>AI Recommendation</p>
      <div className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold mb-4 flex items-center gap-2 flex-wrap`}>
        <span>{symbol}</span>
        {assetMeta.isEtf ? (
          <span
            title={assetMeta.assetTypeDescription || undefined}
            className={`${dark ? "bg-slate-800 text-sky-200 border-sky-400/30" : assetMeta.badgeClass} inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-wide cursor-help`}
          >
            {assetMeta.badgeLabel || "ETF"}
          </span>
        ) : null}
        <span className="text-[#2563EB]">→ {action || "Data unavailable"}</span>
      </div>
      {hasSummary ? (
        <div className="flex items-center gap-2 flex-wrap">
          {confidenceText ? <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-blue-100 text-blue-700">Confidence: {confidenceText}</span> : null}
          {risk ? <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${riskClass}`}>Risk: {risk}</span> : null}
        </div>
      ) : (
        <p className={`${dark ? "text-slate-400" : "text-slate-500"} text-sm`}>Relevant model output is not available yet.</p>
      )}
    </div>
  );
}
