import React from "react";
import { useTranslation } from "react-i18next";
import WatchlistRow from "./WatchlistRow";

export default function WatchlistTable({ groups, dark, onRemove, onOpen }) {
  const { t } = useTranslation();
  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <section
          key={group.sector}
          className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-4 shadow-md`}
        >
          <div className="flex items-center justify-between mb-3">
            <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-lg font-bold`}>{group.sector}</h3>
            <span className="text-xs font-semibold text-slate-500">{group.items.length} {t("stocks")}</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] text-sm">
              <thead>
                <tr className={`${dark ? "text-slate-400 border-slate-700" : "text-slate-500 border-slate-200"} border-b`}>
                  <th className="px-4 py-3 text-left font-semibold">{t("ticker")}</th>
                  <th className="px-4 py-3 text-left font-semibold">{t("company")}</th>
                  <th className="px-4 py-3 text-left font-semibold">{t("price")}</th>
                  <th className="px-4 py-3 text-left font-semibold">{t("dailyChange")}</th>
                  <th className="px-4 py-3 text-left font-semibold">{t("volume")}</th>
                  <th className="px-4 py-3 text-left font-semibold">AI Score</th>
                  <th className="px-4 py-3 text-left font-semibold">{t("sentiment")}</th>
                  <th className="px-4 py-3 text-left font-semibold">{t("miniChart")}</th>
                </tr>
              </thead>
              <tbody className={`${dark ? "text-slate-200" : "text-slate-700"}`}>
                {group.items.map((item) => (
                  <WatchlistRow key={item.symbol} item={item} dark={dark} onRemove={onRemove} onOpen={onOpen} />
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}
