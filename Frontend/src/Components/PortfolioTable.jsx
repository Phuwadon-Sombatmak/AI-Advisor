import React from "react";
import { useTranslation } from "react-i18next";
import { formatCurrencyUSD } from "../utils/formatters";
import { Pencil, Trash2 } from "lucide-react";

export default function PortfolioTable({
  rows = [],
  dark = false,
  language = "en",
  onEdit = () => {},
  onDelete = () => {},
}) {
  const { t } = useTranslation();

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-4 shadow-md`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold mb-4`}>{t("holdings")}</h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1120px] text-sm">
          <thead>
            <tr className={`${dark ? "text-slate-300 border-slate-700" : "text-slate-600 border-slate-200"} border-b`}>
              <th className="px-3 py-3 text-left font-semibold">{t("ticker")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("company")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("shares")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("avgPrice")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("currentPrice")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("marketValue")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("gainLoss")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("gainLoss")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("dailyChange")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("aiScore")}</th>
              <th className="px-3 py-3 text-left font-semibold">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const gainPct = Number(row.gainPct || 0);
              const gainClass = gainPct >= 0 ? "text-emerald-500" : "text-rose-500";
              const gainLoss = Number(row.gainLoss || 0);
              const dailyChange = Number(row.dailyChangePct || 0);
              return (
                <tr key={`${row.symbol}-${row.id || row.purchaseDate || ""}`} className={`${dark ? "border-slate-800 hover:bg-slate-900/50" : "border-slate-100 hover:bg-slate-50"} border-b transition-all`}>
                  <td className="px-3 py-3 font-bold text-[#2563EB]">{row.symbol}</td>
                  <td className="px-3 py-3 font-medium">{row.company}</td>
                  <td className="px-3 py-3">{row.shares}</td>
                  <td className="px-3 py-3">{formatCurrencyUSD(row.avgPrice, language)}</td>
                  <td className="px-3 py-3">{formatCurrencyUSD(row.currentPrice, language)}</td>
                  <td className="px-3 py-3 font-semibold">{formatCurrencyUSD(row.marketValue, language)}</td>
                  <td className={`px-3 py-3 font-bold ${gainLoss >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                    {gainLoss >= 0 ? "+" : ""}{formatCurrencyUSD(gainLoss, language)}
                  </td>
                  <td className={`px-3 py-3 font-bold ${gainClass}`}>{gainPct >= 0 ? "+" : ""}{gainPct.toFixed(2)}%</td>
                  <td className={`px-3 py-3 font-semibold ${dailyChange >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                    {dailyChange >= 0 ? "+" : ""}{dailyChange.toFixed(2)}%
                  </td>
                  <td className="px-3 py-3">
                    <span className="px-2 py-1 rounded-full bg-cyan-100 text-cyan-700 font-semibold">{Math.round(row.aiScore || 0)}</span>
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        className={`${dark ? "bg-slate-800 text-slate-200" : "bg-slate-100 text-slate-700"} p-2 rounded-lg hover:brightness-110`}
                        onClick={() => onEdit(row)}
                        title="Edit"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        type="button"
                        className="bg-rose-100 text-rose-700 p-2 rounded-lg hover:brightness-110"
                        onClick={() => onDelete(row)}
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
