import React from "react";
import { BarChart3, TrendingDown, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import StarButton from "./StarButton";
import { formatCurrencyUSD } from "../utils/formatters";
import { inferAssetMeta } from "../utils/assetMeta";

function MiniSparkline({ points = [], gain = true }) {
  const width = 110;
  const height = 34;
  if (!points.length) {
    return (
      <div className="h-9 w-28 rounded-md bg-slate-100 text-slate-400 text-xs flex items-center justify-center">
        No data
      </div>
    );
  }

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
    <svg viewBox={`0 0 ${width} ${height}`} className="h-9 w-28">
      <path d={path} fill="none" stroke={gain ? "#22C55E" : "#EF4444"} strokeWidth="2.3" strokeLinecap="round" />
    </svg>
  );
}

const sentimentStyle = {
  Bullish: "bg-emerald-100 text-emerald-700",
  Neutral: "bg-slate-100 text-slate-600",
  Bearish: "bg-rose-100 text-rose-700",
};

export default function WatchlistRow({ item, dark, onRemove, onOpen }) {
  const { t, i18n } = useTranslation();
  const isGain = Number(item.change) >= 0;
  const hasAiScore = Number.isFinite(Number(item.aiScore));
  const sentimentKey = String(item.sentiment || "").toLowerCase();
  const assetMeta = inferAssetMeta({
    symbol: item.symbol,
    name: item.company,
    industry: item.sector,
  });
  const companyLabel = assetMeta.isEtf ? assetMeta.displayName : item.company;

  return (
    <tr className={`${dark ? "hover:bg-slate-800/40" : "hover:bg-blue-50/40"} transition-all duration-200 hover:-translate-y-[1px]`}>
      <td className="px-4 py-4">
        <div className="flex items-center gap-2">
          <StarButton active onToggle={() => onRemove(item.symbol)} size="sm" title={`${t("remove")} ${item.symbol}`} />
          <button onClick={() => onOpen(item.symbol)} className="font-bold text-[#2563EB] hover:underline">
            {item.symbol}
          </button>
          {assetMeta.isEtf ? (
            <span
              title={assetMeta.assetTypeDescription || undefined}
              className={`${dark ? "bg-slate-800 text-sky-200 border-sky-400/30" : assetMeta.badgeClass} inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[10px] font-black uppercase tracking-wide cursor-help`}
            >
              {assetMeta.shortBadgeLabel || "ETF"}
            </span>
          ) : null}
        </div>
      </td>
      <td className="px-4 py-4 font-medium">
        <div className="min-w-0">
          <div className="truncate">{companyLabel}</div>
          {assetMeta.isEtf ? (
            <div className="mt-1 text-xs font-semibold text-slate-500">{assetMeta.assetType}</div>
          ) : null}
        </div>
      </td>
      <td className="px-4 py-4 font-semibold">{formatCurrencyUSD(item.price || 0, i18n.language)}</td>
      <td className={`px-4 py-4 font-semibold ${isGain ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
        <span className="inline-flex items-center gap-1">
          {isGain ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
          {isGain ? "+" : ""}
          {Number(item.change || 0).toFixed(2)}%
        </span>
      </td>
      <td className="px-4 py-4">{Number(item.volume || 0).toLocaleString(i18n.language.startsWith("th") ? "th-TH" : "en-US")}</td>
      <td className="px-4 py-4">
        {hasAiScore ? (
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 text-sm font-semibold">
            <BarChart3 size={14} />
            {Math.round(Number(item.aiScore))}
          </div>
        ) : (
          <span className="text-sm text-slate-400">{t("dataUnavailable")}</span>
        )}
      </td>
      <td className="px-4 py-4">
        {item.sentiment ? (
          <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${sentimentStyle[item.sentiment] || sentimentStyle.Neutral}`}>
            {t(sentimentKey)}
          </span>
        ) : (
          <span className="text-sm text-slate-400">{t("dataUnavailable")}</span>
        )}
      </td>
      <td className="px-4 py-4">
        <MiniSparkline points={item.points || []} gain={isGain} />
      </td>
    </tr>
  );
}
