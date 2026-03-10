import React from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import { useTranslation } from "react-i18next";
import { formatCurrencyUSD } from "../utils/formatters";

export default function ReturnIndicator({
  symbol,
  currentPrice = 0,
  dailyChangePct = 0,
  returnPct = 0,
  language = "en",
  dark = false,
}) {
  const { t } = useTranslation();
  const upToday = Number(dailyChangePct) >= 0;
  const upRange = Number(returnPct) >= 0;

  return (
    <div className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-100"} flex justify-between items-center p-8 rounded-3xl shadow-sm border`}>
      <div>
        <h1 className={`${dark ? "text-slate-100" : "text-slate-800"} text-4xl font-black tracking-tight`}>{symbol}</h1>
        <p className="text-slate-500 font-medium mt-1">{t("marketPrice")}</p>
      </div>

      <div className="text-right">
        <p className={`${dark ? "text-slate-100" : "text-slate-800"} text-5xl font-mono font-black`}>{formatCurrencyUSD(currentPrice, language)}</p>
        <p className={`${upToday ? "text-[#22C55E]" : "text-[#EF4444]"} font-bold flex items-center justify-end gap-1 mt-2 text-lg`}>
          {upToday ? <TrendingUp size={22} /> : <TrendingDown size={22} />}
          {upToday ? "+" : ""}{Number(dailyChangePct || 0).toFixed(2)}%
        </p>
        <div className="mt-2 flex items-center justify-end gap-2">
          <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${upToday ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>
            {upToday ? "+" : ""}{Number(dailyChangePct || 0).toFixed(2)}% {t("today") === "today" ? "Today" : t("today")}
          </span>
          <span className={`text-sm font-bold ${upRange ? "text-[#22C55E]" : "text-[#EF4444]"}`}>
            {(t("returnRange") === "returnRange" ? "Range Return" : t("returnRange"))}: {upRange ? "+" : ""}{Number(returnPct || 0).toFixed(2)}%
          </span>
        </div>
      </div>
    </div>
  );
}
