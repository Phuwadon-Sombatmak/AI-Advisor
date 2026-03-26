import React from "react";
import { useTranslation } from "react-i18next";
import { inferAssetMeta } from "../utils/assetMeta";

function Sparkline({ points = [], up = true }) {
  if (!points.length) return null;
  const width = 120;
  const height = 36;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const d = points
    .map((p, i) => {
      const x = (i / Math.max(1, points.length - 1)) * width;
      const y = height - ((p - min) / range) * height;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-10">
      <path d={d} fill="none" stroke={up ? "#22C55E" : "#EF4444"} strokeWidth="2.5" strokeLinecap="round" />
    </svg>
  );
}

export default function TrendingStocks({ stocks = [], dark = false }) {
  const { t } = useTranslation();

  if (!stocks.length) {
    return <div className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-500"} rounded-2xl border p-6 shadow-md`}>{t("noAiInsights")}</div>;
  }

  return (
    <section className="space-y-3">
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold`}>{t("trendingStocks")}</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {stocks.map((s, idx) => (
          <div key={`${s.symbol}-${idx}`} className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-4 shadow-md transition-all hover:-translate-y-[2px] hover:shadow-lg`}>
            {(() => {
              const assetMeta = inferAssetMeta({ symbol: s.symbol });
              return (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <p className="font-bold text-[#2563EB] text-lg">{s.symbol}</p>
                {assetMeta.isEtf ? (
                  <span
                    title={assetMeta.assetTypeDescription || undefined}
                    className={`${dark ? "bg-slate-800 text-sky-200 border-sky-400/30" : assetMeta.badgeClass} inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-wide cursor-help`}
                  >
                    {assetMeta.badgeLabel || "ETF"}
                  </span>
                ) : null}
              </div>
              <span className="text-xs rounded-full px-2 py-1 bg-cyan-100 text-cyan-700 font-bold">
                {s.aiScore == null ? t("dataUnavailable") : `AI ${s.aiScore}`}
              </span>
            </div>
              );
            })()}
            <p className="mt-2 text-sm text-slate-500">{t("momentum")}: {s.momentum || t("dataUnavailable")}</p>
            <p className="text-sm text-slate-500">{t("sentiment")}: {s.sentiment || t("dataUnavailable")}</p>
            <div className="mt-3"><Sparkline points={s.points} up={s.sentiment !== "Bearish"} /></div>
          </div>
        ))}
      </div>
    </section>
  );
}
