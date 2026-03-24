import React from "react";
import { LayoutDashboard, Search, ShieldCheck, BriefcaseBusiness, Sparkles, Newspaper, LogOut, Star } from "lucide-react";
import { useTranslation } from "react-i18next";

const ITEMS = [
  { key: "dashboard", labelKey: "dashboard", icon: LayoutDashboard, path: "/dashboard" },
  { key: "stock", labelKey: "stockSearch", icon: Search, path: "/search" },
  { key: "watchlist", labelKey: "watchlist", icon: Star, path: "/watchlist" },
  { key: "risk", labelKey: "riskAnalysis", icon: ShieldCheck, path: "/risk" },
  { key: "picker", labelKey: "aiPicker", icon: Sparkles, path: "/ai-picker" },
  { key: "portfolio", labelKey: "portfolio", icon: BriefcaseBusiness, path: "/portfolio" },
  { key: "ai", labelKey: "aiInsights", icon: Sparkles, path: "/ai-insights" },
  { key: "news", labelKey: "news", icon: Newspaper, path: "/news" },
];

export default function Sidebar({ pathname, onNavigate, onLogout, logoutLabel = "Logout" }) {
  const { t } = useTranslation();

  const isActive = (key) => {
    if (key === "dashboard") return pathname.startsWith("/dashboard");
    if (key === "stock") return pathname.startsWith("/search") || pathname.startsWith("/stock");
    if (key === "watchlist") return pathname.startsWith("/watchlist");
    if (key === "risk") return pathname.startsWith("/risk");
    if (key === "picker") return pathname.startsWith("/ai-picker");
    if (key === "portfolio") return pathname.startsWith("/portfolio");
    if (key === "ai") return pathname.startsWith("/ai-insights");
    if (key === "news") return pathname.startsWith("/news");
    return false;
  };

  return (
    <aside className="w-full md:w-[280px] bg-[#0F172A] text-slate-200 border-r border-slate-800 flex md:flex-col md:h-screen md:sticky md:top-0">
      <div className="hidden md:flex items-center justify-between px-6 py-6 border-b border-slate-800">
        <button
          onClick={() => onNavigate("/dashboard")}
          className="flex items-center gap-[10px] rounded-xl px-2 py-2 transition-all duration-200 hover:bg-slate-800 hover:-translate-y-0.5"
        >
          <img src="/Ail.svg?v=20260308" className="h-9 w-auto" alt="AI Invest Logo" />
          <span className="text-[18px] font-semibold text-white">AI Invest</span>
        </button>
      </div>

      <nav className="flex-1 p-3 md:p-4 flex md:flex-col gap-2">
        {ITEMS.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.key);
          return (
            <button
              key={item.key}
              onClick={() => onNavigate(item.path)}
              className={`group w-full flex items-center justify-between px-4 py-3 rounded-[10px] font-medium transition-all duration-200 ${
                active ? "bg-[#1E3A8A] text-white" : "text-slate-300 hover:bg-slate-800 hover:text-white hover:translate-x-[2px]"
              }`}
            >
              <span className="flex items-center gap-3">
                <Icon size={18} />
                <span className="hidden md:inline">{t(item.labelKey)}</span>
              </span>
              {item.soon ? <span className="hidden md:inline text-[10px] rounded-md bg-slate-700 px-1.5 py-0.5">{t("soon")}</span> : null}
            </button>
          );
        })}
      </nav>

      <div className="hidden md:block p-4 border-t border-slate-800 mt-auto">
        <button
          onClick={onLogout}
          className="w-full flex items-center gap-2 px-4 py-3 rounded-xl bg-slate-800 text-rose-300 hover:bg-slate-700 hover:text-rose-200 font-semibold"
        >
          <LogOut size={18} />
          {logoutLabel || t("logout")}
        </button>
      </div>
    </aside>
  );
}
