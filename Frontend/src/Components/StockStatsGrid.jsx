import React from "react";
import { Info } from "lucide-react";

function formatNumber(value, language = "en", digits = 2) {
  if (value === null || value === undefined || value === "") return "N/A";
  const num = Number(value);
  if (!Number.isFinite(num)) return "N/A";
  return num.toLocaleString(language?.startsWith("th") ? "th-TH" : "en-US", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatInt(value, language = "en") {
  if (value === null || value === undefined || value === "") return "N/A";
  const num = Number(value);
  if (!Number.isFinite(num)) return "N/A";
  return num.toLocaleString(language?.startsWith("th") ? "th-TH" : "en-US");
}

function formatCurrency(value, language = "en") {
  if (value === null || value === undefined || value === "") return "N/A";
  const num = Number(value);
  if (!Number.isFinite(num)) return "N/A";
  return new Intl.NumberFormat(language?.startsWith("th") ? "th-TH" : "en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
}

function formatCompactCurrency(value, language = "en") {
  if (value === null || value === undefined || value === "") return "N/A";
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) return "N/A";
  const abs = Math.abs(num);
  const locale = language?.startsWith("th") ? "th-TH" : "en-US";
  if (abs >= 1_000_000_000_000) return `${formatNumber(num / 1_000_000_000_000, locale, 2)}T`;
  if (abs >= 1_000_000_000) return `${formatNumber(num / 1_000_000_000, locale, 2)}B`;
  if (abs >= 1_000_000) return `${formatNumber(num / 1_000_000, locale, 2)}M`;
  return formatInt(num, locale);
}

function formatPercent(value, language = "en") {
  if (value === null || value === undefined || value === "") return "N/A";
  const num = Number(value);
  if (!Number.isFinite(num)) return "N/A";
  return `${formatNumber(num, language, 2)}%`;
}

function formatDate(value) {
  if (!value) return "N/A";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function StockStatsGrid({ details = null, loading = false, language = "en", dark = false }) {
  if (loading) {
    return (
      <div className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-100"} p-6 rounded-3xl border shadow-sm`}>
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className={`h-6 w-56 rounded-md animate-pulse ${dark ? "bg-slate-800" : "bg-slate-200"}`} />
          <div className={`h-5 w-36 rounded-full animate-pulse ${dark ? "bg-slate-800" : "bg-slate-200"}`} />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {Array.from({ length: 12 }).map((_, idx) => (
            <div
              key={`stock-stat-skeleton-${idx}`}
              className={`${dark ? "bg-slate-900/60 border-slate-700" : "bg-slate-50 border-slate-200"} rounded-2xl border px-4 py-3`}
            >
              <div className={`h-3 w-28 rounded animate-pulse ${dark ? "bg-slate-700" : "bg-slate-200"}`} />
              <div className={`mt-3 ml-auto h-5 w-24 rounded animate-pulse ${dark ? "bg-slate-700" : "bg-slate-200"}`} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!details) {
    return (
      <div className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-100"} p-6 rounded-3xl border shadow-sm`}>
        <p className={`text-sm ${dark ? "text-slate-300" : "text-slate-500"}`}>Financial statistics unavailable right now.</p>
      </div>
    );
  }

  const updatedAtLabel = details.updatedAt
    ? new Date(details.updatedAt).toLocaleString(language?.startsWith("th") ? "th-TH" : "en-US")
    : null;

  const stats = [
    { label: "PREVIOUS CLOSE", value: formatCurrency(details.previousClose, language), tip: "Previous trading session close price." },
    {
      label: "DAY'S RANGE",
      value: details.dayLow && details.dayHigh
        ? `${formatCurrency(details.dayLow, language)} - ${formatCurrency(details.dayHigh, language)}`
        : "N/A",
      tip: "Today's low and high trading range.",
    },
    {
      label: "52 WEEK RANGE",
      value: details.week52Low && details.week52High
        ? `${formatCurrency(details.week52Low, language)} - ${formatCurrency(details.week52High, language)}`
        : "N/A",
      tip: "Lowest and highest price in the last 52 weeks.",
    },
    { label: "VOLUME", value: formatInt(details.volume, language), tip: "Total shares traded today." },
    { label: "AVG VOLUME", value: formatInt(details.avgVolume, language), tip: "Average daily volume over recent months." },
    { label: "MARKET CAP", value: formatCompactCurrency(details.marketCap ?? details.marketCapRaw, language), tip: "Total company market value." },
    { label: "PE RATIO (TTM)", value: formatNumber(details.peRatio, language, 2), tip: "Price-to-Earnings ratio using trailing 12 months earnings." },
    { label: "EPS (TTM)", value: formatNumber(details.eps, language, 2), tip: "Earnings per share over trailing 12 months." },
    { label: "EARNINGS DATE", value: formatDate(details.earningsDate), tip: "Next reported earnings date." },
    { label: "DIVIDEND YIELD", value: formatPercent(details.dividendYield, language), tip: "Annual dividend yield percentage." },
    { label: "REVENUE (TTM)", value: formatCompactCurrency(details.revenueTTM, language), tip: "Total revenue over trailing 12 months." },
    { label: "FREE CASH FLOW", value: formatCompactCurrency(details.freeCashFlow, language), tip: "Cash generated after capital expenditures." },
    { label: "GROSS MARGIN", value: formatPercent(details.grossMargin, language), tip: "Gross profit as a percentage of revenue." },
  ];

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-100"} p-6 rounded-3xl border shadow-sm`}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className={`text-lg font-bold ${dark ? "text-slate-100" : "text-slate-800"}`}>Financial Statistics</h3>
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold ${dark ? "bg-emerald-900/30 text-emerald-300 border border-emerald-800/40" : "bg-emerald-50 text-emerald-700 border border-emerald-200"}`}>
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Live Data
          </span>
          <span className={`text-xs font-semibold ${dark ? "text-slate-400" : "text-slate-500"}`}>
            {updatedAtLabel ? `Updated ${updatedAtLabel}` : "Real-time market fundamentals"}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        {stats.map((item) => (
          <div
            key={item.label}
            className={`${dark ? "bg-slate-900/60 border-slate-700 hover:bg-slate-900/80" : "bg-slate-50 border-slate-200 hover:bg-white"} rounded-2xl border px-4 py-3 transition-all duration-200`}
          >
            <p className={`text-xs font-medium ${dark ? "text-slate-400" : "text-slate-500"} inline-flex items-center gap-1`}>
              {item.label}
              {item.tip ? <Info size={12} className="opacity-70" title={item.tip} /> : null}
            </p>
            <p className={`mt-1 text-right text-base font-bold ${dark ? "text-slate-100" : "text-slate-800"}`}>{item.value || "N/A"}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
