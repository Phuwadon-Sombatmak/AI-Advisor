import React from "react";
import { useTranslation } from "react-i18next";
import { formatCurrencyUSD } from "../utils/formatters";

export default function RiskStockCard({ item, level, dark }) {
  const { t, i18n } = useTranslation();
  const symbol = item.Symbol || item.symbol || "-";
  const company = item.company || symbol;
  const ret30 = Number(item.ret30);
  const riskScore = Number(item.risk_score);
  const vol90 = Number(item.vol90);
  const mdd1y = Number(item.mdd1y);
  const lastClose = Number(item.last_close);
  const hasRet30 = Number.isFinite(ret30);
  const hasRiskScore = Number.isFinite(riskScore);
  const hasVol90 = Number.isFinite(vol90);
  const hasMdd = Number.isFinite(mdd1y);
  const hasPrice = Number.isFinite(lastClose);

  return (
    <div className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-4 shadow-md transition-all hover:-translate-y-[2px] hover:shadow-lg`}>
      <p className="text-lg font-bold text-[#2563EB]">{symbol}</p>
      <p className="text-sm text-slate-500">{company}</p>
      <div className="mt-3 flex items-center gap-2 flex-wrap text-xs font-semibold">
        <span className="px-2 py-1 rounded-full bg-blue-100 text-blue-700">{t("riskLevel")}: {level}</span>
        {hasRiskScore ? <span className="px-2 py-1 rounded-full bg-cyan-100 text-cyan-700">Risk score: {riskScore.toFixed(2)}</span> : null}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <p className="text-slate-500">{t("price")}</p>
          <p className="font-semibold text-slate-800">{hasPrice ? formatCurrencyUSD(lastClose, i18n.language) : t("dataUnavailable")}</p>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <p className="text-slate-500">30D Return</p>
          <p className="font-semibold text-slate-800">{hasRet30 ? `${ret30 >= 0 ? "+" : ""}${ret30.toFixed(2)}%` : t("dataUnavailable")}</p>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <p className="text-slate-500">90D Volatility</p>
          <p className="font-semibold text-slate-800">{hasVol90 ? `${vol90.toFixed(2)}%` : t("dataUnavailable")}</p>
        </div>
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <p className="text-slate-500">1Y Max Drawdown</p>
          <p className="font-semibold text-slate-800">{hasMdd ? `${mdd1y.toFixed(2)}%` : t("dataUnavailable")}</p>
        </div>
      </div>
    </div>
  );
}
