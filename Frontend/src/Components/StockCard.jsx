import React from "react";
import { useTranslation } from "react-i18next";
import { formatCurrencyUSD } from "../utils/formatters";
import { inferAssetMeta } from "../utils/assetMeta";

function MiniSparkline({ points = [], up = true }) {
  if (!points.length) return null;
  const width = 120;
  const height = 36;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const path = points
    .map((p, i) => {
      const x = (i / (points.length - 1 || 1)) * width;
      const y = height - ((p - min) / range) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-10">
      <path d={path} fill="none" stroke={up ? "#22C55E" : "#EF4444"} strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

export default function StockCard({ symbol, price, change, points, dark, actionSlot = null }) {
  const { i18n } = useTranslation();
  const up = change >= 0;
  const assetMeta = inferAssetMeta({ symbol });
  return (
    <div
      className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-100" : "bg-white border-slate-200 text-slate-900"} rounded-2xl border p-4 transition-all hover:-translate-y-1`}
      style={{ boxShadow: "0 10px 25px rgba(0,0,0,0.08)" }}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <p className="text-sm font-bold truncate">{symbol}</p>
              {assetMeta.isEtf ? (
                <span
                  title={assetMeta.assetTypeDescription || undefined}
                  className={`${dark ? "bg-slate-800 text-sky-200 border-sky-400/30" : assetMeta.badgeClass} inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-wide cursor-help`}
                >
                  {assetMeta.badgeLabel || "ETF"}
                </span>
              ) : null}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <p className={`text-xs font-bold whitespace-nowrap ${up ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
                {up ? "+" : ""}
                {change.toFixed(2)}%
              </p>
              {actionSlot}
            </div>
          </div>
          <p className="text-lg font-bold mt-2">{formatCurrencyUSD(price, i18n.language)}</p>
        </div>
      </div>
      <MiniSparkline points={points} up={up} />
    </div>
  );
}
