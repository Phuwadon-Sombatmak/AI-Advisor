import React from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import { formatCurrencyUSD } from "../utils/formatters";

export default function ReturnIndicator({
  symbol,
  currentPrice = 0,
  changeAbs = 0,
  dailyChangePct = 0,
  returnPct = 0,
  previousClose = null,
  dayRangeLow = null,
  dayRangeHigh = null,
  range52wLow = null,
  range52wHigh = null,
  volume = 0,
  rangeLabel = "1Y",
  language = "en",
  dark = false,
}) {
  const upToday = Number(dailyChangePct) >= 0;
  const upRange = Number(returnPct) >= 0;
  const rangeReturnLabel = `${rangeLabel} Return`;
  const fmtNum = (value, digits = 2) => Number(value || 0).toLocaleString(language?.startsWith("th") ? "th-TH" : "en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });

  return (
    <div className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-100"} p-8 rounded-3xl shadow-sm border space-y-5`}>
      <div className="flex justify-between items-center">
        <div>
        <h1 className={`${dark ? "text-slate-100" : "text-slate-800"} text-4xl font-black tracking-tight`}>{symbol}</h1>
        <p className="text-slate-500 font-medium mt-1">Latest market price</p>
        </div>

        <div className="text-right">
        <p className={`${dark ? "text-slate-100" : "text-slate-800"} text-5xl font-mono font-black`}>{formatCurrencyUSD(currentPrice, language)}</p>
          <p className={`${upToday ? "text-[#22C55E]" : "text-[#EF4444]"} font-bold flex items-center justify-end gap-1 mt-2 text-lg`}>
          {upToday ? <TrendingUp size={22} /> : <TrendingDown size={22} />}
            {upToday ? "+" : ""}{fmtNum(changeAbs)} ({upToday ? "+" : ""}{fmtNum(dailyChangePct)}%)
          </p>
          <div className="mt-2 flex items-center justify-end gap-2">
            <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${upRange ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>
              {rangeReturnLabel} {upRange ? "+" : ""}{fmtNum(returnPct)}%
            </span>
          </div>
        </div>
      </div>

    </div>
  );
}
