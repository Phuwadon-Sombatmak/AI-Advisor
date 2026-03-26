import React from "react";
import { Building2, Info, Layers3, TrendingDown, TrendingUp } from "lucide-react";
import { formatCurrencyUSD } from "../utils/formatters";
import { inferAssetMeta } from "../utils/assetMeta";

function fmtNum(value, language = "en", digits = 2) {
  const n = Number(value || 0);
  return n.toLocaleString(language?.startsWith("th") ? "th-TH" : "en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export default function StockCompanyHeader({
  profile = null,
  symbol = "",
  currentPrice = 0,
  changeAbs = 0,
  dailyChangePct = 0,
  returnPct = 0,
  rangeLabel = "1Y",
  adjustedReturn = false,
  language = "en",
  dark = false,
}) {
  const upToday = Number(dailyChangePct) >= 0;
  const upRange = Number(returnPct) >= 0;
  const name = profile?.name || symbol;
  const ticker = profile?.ticker || symbol;
  const exchange = profile?.exchange || "-";
  const industry = profile?.industry || "-";
  const logo = profile?.logo || null;
  const assetMeta = inferAssetMeta({ symbol: ticker, name, industry, exchange });
  const assetType = assetMeta.assetType;
  const isEtf = assetMeta.isEtf;
  const displayName = assetMeta.displayName || name;
  const subtitle = isEtf
    ? `${assetType}${industry && industry !== "-" ? ` • ${industry}` : ""}`
    : industry;
  const normalizedRangeLabel = String(rangeLabel || "1Y").toUpperCase();
  const rangeBadgeLabel = adjustedReturn
    ? (language?.startsWith("th") ? "ผลตอบแทนสะสม (ปรับปรุงแล้ว)" : "Total Return (Adj.)")
    : `${normalizedRangeLabel} Return`;
  const adjustedTooltip = language?.startsWith("th")
    ? "รวมผลของการแตกพาร์และเงินปันผล"
    : "Includes stock splits and dividends";
  const timeframeNote = adjustedReturn
    ? (language?.startsWith("th") ? "ตั้งแต่เริ่มมีข้อมูล" : "Since inception")
    : null;

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-100"} p-8 rounded-3xl border shadow-sm`}>
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-5">
        <div className="flex items-center gap-4 min-w-0">
          <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-slate-50 border-slate-200"} h-10 w-10 rounded-xl border flex items-center justify-center overflow-hidden shrink-0`}>
            {logo ? (
              <img
                src={logo}
                alt={`${name} logo`}
                className="h-full w-full object-cover"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                  const fallback = e.currentTarget.parentElement?.querySelector("[data-fallback-logo]");
                  if (fallback) fallback.classList.remove("hidden");
                }}
              />
            ) : null}
            {isEtf ? (
              <Layers3 data-fallback-logo className={`${logo ? "hidden" : ""} ${dark ? "text-sky-300" : "text-sky-600"}`} size={18} />
            ) : (
              <Building2 data-fallback-logo className={`${logo ? "hidden" : ""} ${dark ? "text-slate-400" : "text-slate-500"}`} size={18} />
            )}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 min-w-0">
              <h1 className={`${dark ? "text-slate-100" : "text-slate-900"} text-3xl font-black truncate`}>{displayName}</h1>
              {isEtf ? (
                <span
                  title={assetMeta.assetTypeDescription || undefined}
                  className={`${dark ? "bg-slate-800 text-sky-200 border-sky-400/30" : assetMeta.badgeClass} inline-flex shrink-0 items-center rounded-full border px-2 py-0.5 text-[11px] font-black uppercase tracking-wide cursor-help`}
                >
                  ETF
                </span>
              ) : null}
            </div>
            <p className="text-sm text-slate-500 font-semibold mt-1">{ticker} • {exchange}</p>
            <p className="text-sm text-slate-500 mt-0.5 truncate">{subtitle}</p>
          </div>
        </div>

        <div className="text-right">
          <p className={`${dark ? "text-slate-100" : "text-slate-800"} text-5xl font-mono font-black`}>{formatCurrencyUSD(currentPrice, language)}</p>
          <p className={`${upToday ? "text-[#22C55E]" : "text-[#EF4444]"} font-bold flex items-center justify-end gap-1 mt-2 text-lg`}>
            {upToday ? <TrendingUp size={22} /> : <TrendingDown size={22} />}
            {upToday ? "+" : ""}{fmtNum(changeAbs, language)} ({upToday ? "+" : ""}{fmtNum(dailyChangePct, language)}%)
          </p>
          <div className="mt-2 flex items-center justify-end gap-2">
            <span
              title={adjustedReturn ? adjustedTooltip : undefined}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold ${upRange ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}
            >
              {rangeBadgeLabel} {upRange ? "+" : ""}{fmtNum(returnPct, language)}%
              {adjustedReturn ? <Info size={12} /> : null}
            </span>
          </div>
          {timeframeNote ? (
            <p className="mt-2 text-xs font-medium text-slate-500">{timeframeNote}</p>
          ) : null}
        </div>
      </div>
    </section>
  );
}
