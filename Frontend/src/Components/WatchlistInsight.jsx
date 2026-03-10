import React from "react";
import { BellRing, Sparkles } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function WatchlistInsight({ items = [], dark, bookmarkedNews = [] }) {
  const { t } = useTranslation();
  const topMomentum = [...items].sort((a, b) => Number(b.change || 0) - Number(a.change || 0))[0];
  const hasBearish = items.some((x) => x.sentiment === "Bearish");

  const alertMessage = topMomentum
    ? `${topMomentum.symbol} momentum increasing with ${topMomentum.change > 0 ? "+" : ""}${Number(topMomentum.change).toFixed(2)}% today.`
    : "Add stocks to unlock AI watchlist alerts.";

  const insightMessage = items.length
    ? `AI พบสัญญาณเด่นในกลุ่ม ${topMomentum?.sector || "Growth"} และแนะนำติดตามความผันผวนระยะสั้นก่อนเพิ่มน้ำหนักลงทุน`
    : "ยังไม่มีข้อมูล watchlist สำหรับวิเคราะห์";

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-200" : "bg-white border-slate-200 text-slate-800"} rounded-2xl border p-5 shadow-md`}>
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={18} className="text-[#2563EB]" />
        <h3 className="text-lg font-bold">{t("aiWatchlistInsight")}</h3>
      </div>

      <p className="text-sm text-slate-500 mb-4">{insightMessage}</p>

      <div className={`rounded-xl p-3 border ${hasBearish ? "bg-rose-50 border-rose-100 text-rose-700" : "bg-emerald-50 border-emerald-100 text-emerald-700"}`}>
        <div className="flex items-center gap-2 font-semibold text-sm">
          <BellRing size={16} />
          {t("aiAlert")}
        </div>
        <p className="text-sm mt-1">{alertMessage}</p>
      </div>

      <div className="mt-4">
        <h4 className="text-sm font-bold mb-2">{t("bookmarkedNewsInsights")}</h4>
        {bookmarkedNews.length === 0 ? (
          <p className="text-sm text-slate-500">{t("noBookmarkedNews")}</p>
        ) : (
          <div className="space-y-2">
            {bookmarkedNews.slice(0, 5).map((item) => (
              <a
                key={item.id}
                href={item.link || "#"}
                target="_blank"
                rel="noreferrer"
                className={`${dark ? "bg-slate-900 border-slate-700 text-slate-200" : "bg-slate-50 border-slate-200 text-slate-700"} block rounded-xl border p-3 hover:border-[#2563EB]`}
              >
                <p className="text-sm font-semibold line-clamp-2">{item.title}</p>
                <p className="text-xs text-slate-500 mt-1">{item.provider} • {item.displayDate}</p>
              </a>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
