import React, { useState, useEffect, useContext, useMemo, useCallback } from "react";
import { Routes, Route, Navigate, Outlet, useNavigate, useParams, useLocation } from "react-router-dom";
import { ArrowLeft, Loader2, ShieldAlert, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import { AuthProvider, AuthContext } from "./Components/AuthContext";
import Sidebar from "./Components/Sidebar";
import Topbar from "./Components/Topbar";
import HeroSearch from "./Components/HeroSearch";
import StockCard from "./Components/StockCard";
import StockChart from "./Components/StockChart";
import StockCompanyHeader from "./Components/StockCompanyHeader";
import StockStatsGrid from "./Components/StockStatsGrid";
import TimeRangeSelector from "./Components/TimeRangeSelector";
import NewsCard from "./Components/NewsCard";
import AIInsightCard from "./Components/AIInsightCard";
import NewsSentimentFilter from "./Components/NewsSentimentFilter";
import RiskSelector from "./Components/RiskSelector";
import RiskExplanation from "./Components/RiskExplanation";
import RiskStockCard from "./Components/RiskStockCard";
import AIPickerHero from "./Components/AIPickerHero";
import AIPickerFilters from "./Components/AIPickerFilters";
import StockPickCard from "./Components/StockPickCard";
import AIInsightPanel from "./Components/AIInsightPanel";
import MarketSentiment from "./Components/MarketSentiment";
import NewsHeader from "./Components/NewsHeader";
import NewsFilters from "./Components/NewsFilters";
import NewsFeed from "./Components/NewsFeed";
import NewsSentimentSummary from "./Components/NewsSentimentSummary";
import StarButton from "./Components/StarButton";
import WatchlistTable from "./Components/WatchlistTable";
import WatchlistInsight from "./Components/WatchlistInsight";
import PortfolioSummary from "./Components/PortfolioSummary";
import PortfolioChart from "./Components/PortfolioChart";
import PortfolioTable from "./Components/PortfolioTable";
import AllocationChart from "./Components/AllocationChart";
import PortfolioInsight from "./Components/PortfolioInsight";
import PortfolioPositionModal from "./Components/PortfolioPositionModal";
import AIOverviewCards from "./Components/AIOverviewCards";
import AISignals from "./Components/AISignals";
import TrendingStocks from "./Components/TrendingStocks";
import SectorInsights from "./Components/SectorInsights";
import AIMarketSummary from "./Components/AIMarketSummary";
import AISummaryPanel from "./Components/AISummaryPanel";
import AIAdvisorWidget from "./Components/AIAdvisorWidget";
import AIInvestmentAnalysis from "./Components/AIInvestmentAnalysis";
import { formatCurrencyUSD, formatDateTimeByLang } from "./utils/formatters";
const ThemeContext = React.createContext({ theme: "light", toggleTheme: () => {} });

const RAW_FASTAPI_BASE = (import.meta.env.VITE_FASTAPI_URL || "/api-fastapi").replace(/\/$/, "");
const FASTAPI_BASE = (() => {
  if (typeof window === "undefined") return RAW_FASTAPI_BASE;
  try {
    if (/^https?:\/\//i.test(RAW_FASTAPI_BASE)) {
      const u = new URL(RAW_FASTAPI_BASE);
      // Force same-origin path usage to avoid CORS/access-control issues when app is served on another origin/port.
      return (u.pathname || "/api-fastapi").replace(/\/$/, "") || "/api-fastapi";
    }
  } catch {
    // keep raw fallback
  }
  return RAW_FASTAPI_BASE;
})();
const WATCHLIST_STORAGE_KEY = "ai-invest-watchlist-v1";
const NEWS_BOOKMARK_STORAGE_KEY = "ai-invest-news-bookmarks-v1";
const AI_INSIGHTS_CACHE_TTL_MS = 120000;
const aiInsightsViewCache = new Map();

const BRAND_LOGO = "/Ail.svg?v=20260308";

const TEXT = {
  th: {
    lang: "EN",
    navSearch: "ค้นหาหุ้น",
    navRisk: "ประเมินความเสี่ยง",
    sideHome: "หน้าหลัก",
    sideSearchNews: "ค้นหาหุ้น & ข่าว",
    sideRisk: "ประเมินความเสี่ยง",
    welcomeInvestor: "ยินดีต้อนรับนักลงทุน",
    popularStocks: "หุ้นยอดนิยม:",
    summaryAi: "สรุปภาพรวมด้วย AI",
    logout: "ออกจากระบบ",
    welcome: "ยินดีต้อนรับสู่ StockAI",
    loginSub: "เข้าสู่ระบบเพื่อดูข้อมูลหุ้นและคำแนะนำจาก AI",
    email: "อีเมล",
    password: "รหัสผ่าน",
    login: "เข้าสู่ระบบ",
    loggingIn: "กำลังเข้าสู่ระบบ...",
    register: "สมัครสมาชิก",
    guest: "เข้าใช้งานแบบ Guest",
    registerTitle: "สมัครสมาชิก",
    registerSub: "สร้างบัญชีเพื่อใช้งานระบบแนะนำการลงทุน",
    dob: "วันเกิด",
    confirmPassword: "ยืนยันรหัสผ่าน",
    registering: "กำลังสมัคร...",
    backToLogin: "กลับไปหน้าเข้าสู่ระบบ",
    requireVerify: "ลงทะเบียนสำเร็จ กรุณาตรวจสอบอีเมลและยืนยันก่อนเข้าสู่ระบบ",
    invalidEmail: "รูปแบบอีเมลไม่ถูกต้อง",
    invalidDob: "ผู้ใช้งานต้องมีอายุอย่างน้อย 18 ปีขึ้นไป",
    passwordShort: "รหัสผ่านต้องมีอย่างน้อย 8 ตัวอักษร",
    passwordMismatch: "รหัสผ่านและยืนยันรหัสผ่านไม่ตรงกัน",
    requiredField: "กรุณากรอกข้อมูลให้ครบถ้วน",
    verifyTitle: "ยืนยันอีเมล",
    verifying: "กำลังยืนยันอีเมล...",
    verifyOk: "ยืนยันอีเมลสำเร็จ สามารถเข้าสู่ระบบได้แล้ว",
    verifyFail: "ลิงก์ยืนยันไม่ถูกต้องหรือหมดอายุ",
    goLogin: "ไปหน้าเข้าสู่ระบบ",
    searchHero: "ค้นหาหุ้นที่คุณสนใจ",
    searchPlaceholder: "พิมพ์ชื่อหุ้น เช่น NVDA, AAPL...",
    latestNews: "ข่าวสารตลาดล่าสุด",
    loadingNews: "กำลังโหลดข่าว...",
    backSearch: "กลับไปหน้าค้นหา",
    marketPrice: "ราคาล่าสุดอิงจากตลาด",
    analyzing: "กำลังวิเคราะห์ข้อมูล",
    loadingReco: "กำลังโหลดคำแนะนำ...",
    noRiskData: "ไม่พบข้อมูลในระดับนี้",
    riskTitle: "โปรไฟล์ความเสี่ยงการลงทุน",
    riskSub: "เลือกความเสี่ยงเพื่อดูหุ้นที่เหมาะสมจากโมเดล",
    connectError: "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้",
    loginFailed: "ล็อกอินไม่สำเร็จ",
    registerFailed: "สมัครสมาชิกไม่สำเร็จ",
  },
  en: {
    lang: "TH",
    navSearch: "Search",
    navRisk: "Risk",
    sideHome: "Home",
    sideSearchNews: "Search & News",
    sideRisk: "Risk Profile",
    welcomeInvestor: "Welcome, Investor",
    popularStocks: "Popular:",
    summaryAi: "AI Summary",
    logout: "Logout",
    welcome: "Welcome to StockAI",
    loginSub: "Sign in to view stocks and AI recommendations",
    email: "Email",
    password: "Password",
    login: "Sign in",
    loggingIn: "Signing in...",
    register: "Create account",
    guest: "Continue as Guest",
    registerTitle: "Create Account",
    registerSub: "Create an account to use the investment recommendation system",
    dob: "Date of birth",
    confirmPassword: "Confirm password",
    registering: "Creating account...",
    backToLogin: "Back to login",
    requireVerify: "Registration complete. Please verify your email before login.",
    invalidEmail: "Invalid email format",
    invalidDob: "You must be at least 18 years old to register",
    passwordShort: "Password must be at least 8 characters",
    passwordMismatch: "Password and confirmation do not match",
    requiredField: "Please fill in all required fields",
    verifyTitle: "Email Verification",
    verifying: "Verifying your email...",
    verifyOk: "Email verified successfully. You can now sign in.",
    verifyFail: "Invalid or expired verification link",
    goLogin: "Go to login",
    searchHero: "Search your stock",
    searchPlaceholder: "Type symbol, e.g. NVDA, AAPL...",
    latestNews: "Latest Market News",
    loadingNews: "Loading news...",
    backSearch: "Back to search",
    marketPrice: "Latest market price",
    analyzing: "Analyzing",
    loadingReco: "Loading recommendations...",
    noRiskData: "No data for this level",
    riskTitle: "Investment Risk Profile",
    riskSub: "Select your risk level to view model recommendations",
    connectError: "Unable to connect to server",
    loginFailed: "Login failed",
    registerFailed: "Registration failed",
  },
};

const apiUrl = (path) => {
  if (path.startsWith("http")) return path;
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${FASTAPI_BASE}${normalized}`;
};

const localFastapiUrl = (path) => {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (typeof window === "undefined") return `http://localhost:8000${normalized}`;
  const host = window.location.hostname || "localhost";
  return `http://${host}:8000${normalized}`;
};

const getMaxDobFor18 = () => {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 18);
  return d.toISOString().slice(0, 10);
};

const isAtLeast18 = (dob) => {
  if (!dob) return false;
  const birth = new Date(dob);
  if (Number.isNaN(birth.getTime())) return false;
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const m = now.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < birth.getDate())) age -= 1;
  return age >= 18;
};

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function fetchJsonWithRetry(paths, retries = 2, timeoutMs = 20000, init = undefined) {
  let lastError = null;
  const isLocalHost = (host) => host === "localhost" || host === "127.0.0.1";
  const usablePaths = (paths || []).filter((p) => {
    const path = String(p || "");
    if (!path) return false;
    if (typeof window === "undefined") return true;
    if (!/^https?:\/\//i.test(path)) return true;
    try {
      const u = new URL(path);
      // Skip cross-origin URLs in browser to prevent access-control failures.
      if (u.origin === window.location.origin) return true;
      // Allow local dev fallback across localhost ports (e.g. :80 -> :8000)
      if (isLocalHost(u.hostname) && isLocalHost(window.location.hostname)) return true;
      return false;
    } catch {
      return false;
    }
  });

  if (!usablePaths.length) {
    throw new Error("No same-origin API path available");
  }

  for (let i = 0; i < retries; i += 1) {
    for (const path of usablePaths) {
      let timer = null;
      try {
        const controller = new AbortController();
        timer = setTimeout(() => controller.abort(), timeoutMs);
        const res = await fetch(path, { ...(init || {}), signal: controller.signal });
        if (!res.ok) {
          lastError = new Error(`HTTP ${res.status}`);
          continue;
        }
        return await res.json();
      } catch (e) {
        if (e?.name === "AbortError") {
          lastError = new Error(`Request timeout after ${timeoutMs}ms: ${path}`);
        } else {
          lastError = e;
        }
      } finally {
        if (timer) clearTimeout(timer);
      }
    }
    await sleep(500 * (i + 1));
  }
  throw lastError || new Error("fetch failed");
}

function sentimentFromChange(change) {
  if (change > 0.2) return "Bullish";
  if (change < -0.2) return "Bearish";
  return "Neutral";
}

const NEWS_TOPIC_SYMBOLS = {
  all: ["NVDA", "MSFT", "AAPL", "AMZN", "TSLA", "META"],
  technology: ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
  ai: ["NVDA", "MSFT", "PLTR", "AMD", "GOOGL"],
  semiconductors: ["NVDA", "AMD", "AVGO", "INTC", "TSM"],
  macro: ["SPY", "QQQ", "DIA", "TLT", "GLD"],
  crypto: ["COIN", "MSTR", "RIOT", "MARA", "BTCUSD"],
};

function sentimentLabelFromScore(score) {
  if (score > 0.2) return "Bullish";
  if (score < -0.2) return "Bearish";
  return "Neutral";
}

function impactFromScore(score) {
  const v = Math.abs(Number(score || 0));
  if (v > 0.6) return "High";
  if (v > 0.3) return "Medium";
  return "Low";
}

function inferSectorTag(item) {
  const raw = `${item.title || ""} ${item.provider || ""}`.toLowerCase();
  if (/(nvidia|amd|intel|broadcom|semiconductor|chip)/.test(raw)) return "Semiconductors";
  if (/(ai|artificial intelligence|openai|model|inference|gpu)/.test(raw)) return "AI";
  if (/(bitcoin|crypto|ethereum|coinbase|mara|riot)/.test(raw)) return "Crypto";
  if (/(fed|inflation|rates|treasury|jobs|macro|cpi|gdp)/.test(raw)) return "Macro";
  if (/(apple|microsoft|google|amazon|meta|technology|tech)/.test(raw)) return "Technology";
  return "Technology";
}

function normalizeSymbolList(values = []) {
  const out = [];
  const seen = new Set();
  for (const value of values) {
    const symbol = String(value || "").trim().toUpperCase();
    if (!/^[A-Z0-9.-]{1,12}$/.test(symbol)) continue;
    if (seen.has(symbol)) continue;
    seen.add(symbol);
    out.push(symbol);
  }
  return out;
}

function dedupeNewsItems(items = []) {
  const seen = new Set();
  const out = [];
  for (const item of items) {
    const key = String(item?.link || item?.title || "").trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

const PrivateLayout = () => {
  const { user, logout } = useContext(AuthContext);
  const { t, i18n } = useTranslation();
  const { theme, toggleTheme } = useContext(ThemeContext);
  const navigate = useNavigate();
  const location = useLocation();
  const isThai = String(i18n.resolvedLanguage || i18n.language || "en").startsWith("th");
  const languageLabel = isThai ? "EN" : "TH";
  const toggleLanguage = () => i18n.changeLanguage(isThai ? "en" : "th");

  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className={`${theme === "dark" ? "bg-[#020617] text-slate-100" : "bg-[#F8FAFC] text-slate-900"} min-h-screen font-sans md:flex`}>
      <Sidebar pathname={location.pathname} onNavigate={navigate} onLogout={logout} logoutLabel={t("logout")} />

      <main className="flex-1">
        <Topbar
          theme={theme}
          toggleTheme={toggleTheme}
          languageLabel={languageLabel}
          toggleLanguage={toggleLanguage}
          title={t("welcomeInvestor")}
        />
        <div className="p-4 md:p-8">
          <div className="max-w-[1280px] mx-auto">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
};
const LoginPage = () => {
  const { loginAsGuest, loginWithToken } = useContext(AuthContext);
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const isThai = String(i18n.resolvedLanguage || i18n.language || "en").startsWith("th");
  const languageLabel = isThai ? "EN" : "TH";
  const toggleLanguage = () => i18n.changeLanguage(isThai ? "en" : "th");

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!email || !password) return;

    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || t("loginFailed"));
        return;
      }
      loginWithToken(data.token, data.username);
      navigate("/search", { replace: true });
    } catch {
      setError(t("connectError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="bg-white p-10 rounded-[2rem] shadow-xl max-w-md w-full text-center border border-slate-100">
        <div className="flex items-center justify-center gap-[10px] mb-6">
          <img src={BRAND_LOGO} className="h-9 w-auto" alt="AI Invest Logo" />
          <span className="text-[18px] font-semibold text-[#1E3A8A]">AI Invest</span>
        </div>
        <button
          type="button"
          onClick={toggleLanguage}
          className="mb-4 text-xs font-black px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200"
        >
          {languageLabel}
        </button>
        <h1 className="text-3xl font-black text-slate-800 mb-2 tracking-tight">{t("welcome")}</h1>
        <p className="text-slate-500 font-medium mb-8">{t("loginSub")}</p>

        <form className="space-y-3" onSubmit={handleLogin}>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("email")}
            className="w-full rounded-xl border border-slate-200 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t("password")}
            className="w-full rounded-xl border border-slate-200 px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
          {error ? <p className="text-sm text-rose-600 font-medium text-left">{error}</p> : null}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-bold py-3 rounded-xl transition-colors"
          >
            {loading ? t("loggingIn") : t("login")}
          </button>
        </form>

        <button
          type="button"
          onClick={() => navigate("/register")}
          className="w-full mt-3 bg-white hover:bg-slate-50 text-indigo-600 border border-indigo-200 font-bold py-3 rounded-xl transition-colors"
        >
          {t("register")}
        </button>

        <button
          onClick={() => {
            loginAsGuest();
            navigate("/search");
          }}
          className="w-full mt-3 bg-slate-900 hover:bg-black text-white font-black py-3 rounded-xl transition-all shadow-lg hover:shadow-xl"
        >
          {t("guest")}
        </button>
      </div>
    </div>
  );
};

const RegisterPage = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [dob, setDob] = useState("1995-01-01");
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const isThai = String(i18n.resolvedLanguage || i18n.language || "en").startsWith("th");
  const languageLabel = isThai ? "EN" : "TH";
  const toggleLanguage = () => i18n.changeLanguage(isThai ? "en" : "th");

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    const nextErrors = {};

    if (!email.trim() || !password || !confirmPassword || !dob) {
      setError(t("requiredField"));
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      nextErrors.email = t("invalidEmail");
    }
    if (!isAtLeast18(dob)) {
      nextErrors.dob = t("invalidDob");
    }
    if ((password || "").length < 8) {
      nextErrors.password = t("passwordShort");
    }
    if (password !== confirmPassword) {
      nextErrors.confirmPassword = t("passwordMismatch");
    }
    setFieldErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setLoading(true);
    try {
      const res = await fetch("/api/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          dob,
          recaptcha: "dev-bypass",
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || t("registerFailed"));
        return;
      }
      setSuccess(t("requireVerify"));
    } catch {
      setError(t("connectError"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="bg-white p-10 rounded-[2rem] shadow-xl max-w-md w-full border border-slate-100">
        <div className="flex items-center justify-center gap-[10px] mb-4">
          <img src={BRAND_LOGO} className="h-9 w-auto" alt="AI Invest Logo" />
          <span className="text-[18px] font-semibold text-[#1E3A8A]">AI Invest</span>
        </div>
        <button
          type="button"
          onClick={toggleLanguage}
          className="mb-4 text-xs font-black px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200"
        >
          {languageLabel}
        </button>
        <h1 className="text-2xl font-black text-slate-800 mb-2">{t("registerTitle")}</h1>
        <p className="text-slate-500 mb-6">{t("registerSub")}</p>
        <form className="space-y-3" onSubmit={onSubmit}>
          <input
            type="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setFieldErrors((prev) => ({ ...prev, email: "" }));
            }}
            placeholder={t("email")}
            className={`w-full rounded-xl border px-4 py-3 ${fieldErrors.email ? "border-rose-500 text-rose-700" : "border-slate-200"}`}
          />
          {fieldErrors.email ? <p className="text-sm text-rose-600">{fieldErrors.email}</p> : null}
          <input
            type="date"
            value={dob}
            max={getMaxDobFor18()}
            onChange={(e) => {
              setDob(e.target.value);
              setFieldErrors((prev) => ({ ...prev, dob: "" }));
            }}
            className={`w-full rounded-xl border px-4 py-3 ${fieldErrors.dob ? "border-rose-500 text-rose-700" : "border-slate-200"}`}
          />
          {fieldErrors.dob ? <p className="text-sm text-rose-600">{fieldErrors.dob}</p> : null}
          <input
            type="password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setFieldErrors((prev) => ({ ...prev, password: "" }));
            }}
            placeholder={t("password")}
            className={`w-full rounded-xl border px-4 py-3 ${fieldErrors.password ? "border-rose-500 text-rose-700" : "border-slate-200"}`}
          />
          {fieldErrors.password ? <p className="text-sm text-rose-600">{fieldErrors.password}</p> : null}
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => {
              setConfirmPassword(e.target.value);
              setFieldErrors((prev) => ({ ...prev, confirmPassword: "" }));
            }}
            placeholder={t("confirmPassword")}
            className={`w-full rounded-xl border px-4 py-3 ${fieldErrors.confirmPassword ? "border-rose-500 text-rose-700" : "border-slate-200"}`}
          />
          {fieldErrors.confirmPassword ? <p className="text-sm text-rose-600">{fieldErrors.confirmPassword}</p> : null}
          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          {success ? <p className="text-sm text-emerald-600">{success}</p> : null}
          <button type="submit" disabled={loading} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 rounded-xl disabled:bg-indigo-400">
            {loading ? t("registering") : t("register")}
          </button>
        </form>
        <button onClick={() => navigate("/login")} className="w-full mt-3 border border-slate-200 text-slate-700 font-bold py-3 rounded-xl">
          {t("backToLogin")}
        </button>
      </div>
    </div>
  );
};

const VerifyEmailPage = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [ok, setOk] = useState(false);
  const [message, setMessage] = useState(t("verifying"));
  const isThai = String(i18n.resolvedLanguage || i18n.language || "en").startsWith("th");
  const languageLabel = isThai ? "EN" : "TH";
  const toggleLanguage = () => i18n.changeLanguage(isThai ? "en" : "th");

  useEffect(() => {
    const run = async () => {
      const params = new URLSearchParams(location.search);
      const token = params.get("token");
      if (!token) {
        setOk(false);
        setMessage(t("verifyFail"));
        setLoading(false);
        return;
      }

      try {
        const res = await fetch(`/api/verify-email?token=${encodeURIComponent(token)}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || t("verifyFail"));
        setOk(true);
        setMessage(data.message || t("verifyOk"));
      } catch (e) {
        setOk(false);
        setMessage(e.message || t("verifyFail"));
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [location.search, t]);

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="bg-white p-10 rounded-[2rem] shadow-xl max-w-md w-full border border-slate-100 text-center">
        <div className="flex items-center justify-center gap-[10px] mb-4">
          <img src={BRAND_LOGO} className="h-9 w-auto" alt="AI Invest Logo" />
          <span className="text-[18px] font-semibold text-[#1E3A8A]">AI Invest</span>
        </div>
        <button
          type="button"
          onClick={toggleLanguage}
          className="mb-4 text-xs font-black px-3 py-1.5 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200"
        >
          {languageLabel}
        </button>
        <h1 className="text-2xl font-black text-slate-800 mb-2">{t("verifyTitle")}</h1>
        <p className={`mb-6 ${loading ? "text-slate-500" : ok ? "text-emerald-600" : "text-rose-600"}`}>{message}</p>
        <button onClick={() => navigate("/login")} className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 rounded-xl">
          {t("goLogin")}
        </button>
      </div>
    </div>
  );
};

const SearchPage = ({ watchlist = [], onToggleWatchlist = () => {}, recentSearches = [], onRecordSearch = () => {} }) => {
  const { t, i18n } = useTranslation();
  const { theme } = useContext(ThemeContext);
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [newsLoading, setNewsLoading] = useState(true);
  const [miniLoading, setMiniLoading] = useState(true);
  const [dailyNews, setDailyNews] = useState([]);
  const [miniCards, setMiniCards] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [highlight, setHighlight] = useState(null);
  const [marketSentimentScore, setMarketSentimentScore] = useState(null);
  const [summaryOpen, setSummaryOpen] = useState(false);

  const seedSymbols = useMemo(
    () => normalizeSymbolList([...(recentSearches || []), ...(watchlist || [])]),
    [recentSearches, watchlist]
  );

  useEffect(() => {
    let alive = true;
    const run = async () => {
      setNewsLoading(true);
      setMiniLoading(true);
      setHighlight(null);

      let symbols = [...seedSymbols];
      if (!symbols.length) {
        try {
          const picker = await fetchJsonWithRetry(
            [
              apiUrl("/ai-picker?strategy=BALANCED&limit=8"),
              "http://localhost:8000/ai-picker?strategy=BALANCED&limit=8",
            ],
            2,
            8000
          );
          symbols = normalizeSymbolList((picker?.items || []).map((item) => item?.ticker));
        } catch {
          symbols = [];
        }
      }

      if (!symbols.length) {
        try {
          const summary = await fetchJsonWithRetry(
            [
              apiUrl("/api/ai-summary"),
              "http://localhost:8000/api/ai-summary",
            ],
            1,
            8000,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ context: { watchlist, recent_searches: recentSearches } }),
            }
          );
          symbols = normalizeSymbolList([summary?.summary?.top_ai_pick]);
        } catch {
          symbols = [];
        }
      }

      const primarySymbols = symbols.slice(0, 8);
      if (alive) setSuggestions(primarySymbols.slice(0, 5));

      try {
        if (!primarySymbols.length) {
          if (alive) setDailyNews([]);
        } else {
          const newsData = await fetchJsonWithRetry(
            [
              apiUrl(`/news?symbols=${encodeURIComponent(primarySymbols.slice(0, 4).join(","))}&days_back=7`),
              `http://localhost:8000/news?symbols=${encodeURIComponent(primarySymbols.slice(0, 4).join(","))}&days_back=7`,
            ],
            3,
            8000
          );
          const merged = dedupeNewsItems(
            (Array.isArray(newsData) ? newsData : []).flatMap((item) => item.news || [])
          ).slice(0, 6);
          if (alive) setDailyNews(merged);
        }
      } catch {
        if (alive) setDailyNews([]);
      }

      try {
        const sentimentPayload = await fetchJsonWithRetry(
          [
            apiUrl("/api/market-sentiment"),
            "http://localhost:8000/api/market-sentiment",
          ],
          2,
          8000
        );
        if (alive) setMarketSentimentScore(Number(sentimentPayload?.score ?? sentimentPayload?.market_score ?? 50));
      } catch {
        if (alive) setMarketSentimentScore(null);
      }

      try {
        const cardSymbols = primarySymbols.slice(0, 4);
        const cards = await Promise.all(
          cardSymbols.map(async (symbol) => {
            const payload = await fetchJsonWithRetry(
              [
                apiUrl(`/stock/${symbol}?range=1m`),
                `http://localhost:8000/stock/${symbol}?range=1m`,
              ],
              2,
              8000
            );
            const history = Array.isArray(payload?.history) ? payload.history : [];
            const points = history
              .slice(-8)
              .map((row) => Number(row?.close ?? row?.price ?? 0))
              .filter((value) => Number.isFinite(value) && value > 0);
            return {
              symbol,
              price: Number(payload?.latest_price ?? payload?.price ?? 0),
              change: Number(payload?.change_pct ?? payload?.daily_change_pct ?? 0),
              points,
            };
          })
        );
        if (alive) setMiniCards(cards.filter((item) => Number.isFinite(item.price) && item.price > 0));
      } catch {
        if (alive) setMiniCards([]);
      }

      try {
        const topSymbol = primarySymbols[0];
        if (!topSymbol) {
          if (alive) setHighlight(null);
        } else {
          const reco = await fetchJsonWithRetry(
            [
              apiUrl(`/recommend?symbol=${topSymbol}&window_days=14`),
              `http://localhost:8000/recommend?symbol=${topSymbol}&window_days=14`,
            ],
            1,
            8000
          );
          if (alive) {
            setHighlight({
              symbol: topSymbol,
              action: reco?.recommendation || "Hold",
              confidence: Math.round((Number(reco?.confidence || 0.65) || 0.65) * 100),
              risk: reco?.risk_level || "Medium",
            });
          }
        }
      } catch {
        if (alive) setHighlight(null);
      }

      if (alive) {
        setMiniLoading(false);
        setNewsLoading(false);
      }
    };
    run();
    return () => {
      alive = false;
    };
  }, [seedSymbols, watchlist, recentSearches]);

  const handleSearch = () => {
    if (query.trim()) {
      const symbol = query.toUpperCase();
      onRecordSearch(symbol);
      navigate(`/stock/${symbol}`);
    }
  };

  return (
    <div className="space-y-8">
      <HeroSearch
        query={query}
        setQuery={setQuery}
        onSearch={handleSearch}
        suggestions={suggestions}
        onPick={(symbol) => {
          onRecordSearch(symbol);
          navigate(`/stock/${symbol}`);
        }}
      />

      <MarketSentiment dark={theme === "dark"} />

      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {miniLoading ? (
          <div className={`${theme === "dark" ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-500"} col-span-full rounded-2xl border p-6 shadow-sm`}>
            {t("analyzing")}...
          </div>
        ) : miniCards.length === 0 ? (
          <div className={`${theme === "dark" ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-500"} col-span-full rounded-2xl border p-6 shadow-sm`}>
            {t("noData") === "noData" ? "No market data available right now." : t("noData")}
          </div>
        ) : (
          miniCards.map((s) => {
            const saved = watchlist.includes(s.symbol);
            return (
              <div key={s.symbol} className="relative">
                <StarButton
                  active={saved}
                  onToggle={() => onToggleWatchlist(s.symbol)}
                  className="absolute top-3 right-3 z-10"
                  title={saved ? `${t("removeFromWatchlist")} ${s.symbol}` : `${t("addToWatchlist")} ${s.symbol}`}
                />
                <StockCard symbol={s.symbol} price={s.price} change={s.change} points={s.points} dark={theme === "dark"} />
              </div>
            );
          })
        )}
      </section>

      {highlight ? (
        <AIInsightCard
          symbol={highlight.symbol}
          action={highlight.action}
          confidence={highlight.confidence}
          risk={highlight.risk}
          dark={theme === "dark"}
        />
      ) : null}

      <div className="space-y-4">
        <div className="flex items-center justify-between mb-6">
          <h2 className={`${theme === "dark" ? "text-slate-100" : "text-slate-900"} text-3xl md:text-4xl font-bold`}>{t("latestNews")}</h2>
          <button
            onClick={() => setSummaryOpen(true)}
            className="hidden md:flex items-center gap-2 text-white px-5 py-2.5 rounded-2xl font-bold shadow-md whitespace-nowrap transition-all hover:-translate-y-1 hover:brightness-110 hover:scale-[1.01]"
            style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
          >
            {t("summaryAi")}
          </button>
        </div>
        {newsLoading ? (
          <div className="text-slate-500 font-medium">{t("loadingNews")}</div>
        ) : dailyNews.length === 0 ? (
          <div className="text-slate-500 font-medium">{t("newsNoData")}</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {dailyNews.map((news, i) => <NewsCard key={`${news.link || news.title || "news"}-${i}`} news={news} dark={theme === "dark"} />)}
          </div>
        )}
      </div>

      <AISummaryPanel
        open={summaryOpen}
        onClose={() => setSummaryOpen(false)}
        dark={theme === "dark"}
        context={{
          watchlist,
          recent_searches: recentSearches,
          sentiment: marketSentimentScore,
          portfolio: watchlist.map((s) => ({ symbol: s })),
        }}
      />
    </div>
  );
};

const NewsPage = ({ bookmarkedNews = [], onToggleNewsBookmark = () => {} }) => {
  const { t, i18n } = useTranslation();
  const { theme } = useContext(ThemeContext);
  const dark = theme === "dark";
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [refreshToken, setRefreshToken] = useState(0);
  const [sentimentFilter, setSentimentFilter] = useState("all");
  const [topicFilter, setTopicFilter] = useState("all");
  const [sortBy, setSortBy] = useState("sortNewest");

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      try {
        const symbols = NEWS_TOPIC_SYMBOLS[topicFilter] || NEWS_TOPIC_SYMBOLS.all;
        const query = symbols.join(",");
        const data = await fetchJsonWithRetry(
          [
            apiUrl(`/news?symbols=${encodeURIComponent(query)}&days_back=7`),
            `http://localhost:8000/news?symbols=${encodeURIComponent(query)}&days_back=7`,
          ],
          4
        );

        const merged = (Array.isArray(data) ? data : []).flatMap((row) => row.news || []);
        setItems(merged);
      } catch {
        setItems([]);
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [topicFilter, refreshToken]);

  const normalized = useMemo(() => {
    const mapped = items.map((item, idx) => {
      let score = Number(item.sentiment_score ?? item.sentimentScore);
      if (!Number.isFinite(score)) {
        const sentimentText = String(item.sentiment || "").toLowerCase();
        if (sentimentText.includes("positive") || sentimentText.includes("bull")) score = 0.55;
        else if (sentimentText.includes("negative") || sentimentText.includes("bear")) score = -0.55;
        else score = 0;
      }
      const dateRaw = item.date || item.published_at || item.published || item.pubDate;
      const primaryDate = dateRaw ? new Date(dateRaw) : null;
      const fallbackDate =
        dateRaw && typeof dateRaw === "string" && dateRaw.includes(" ")
          ? new Date(dateRaw.replace(" ", "T"))
          : null;
      const timestamp =
        primaryDate && !Number.isNaN(primaryDate.getTime())
          ? primaryDate.getTime()
          : fallbackDate && !Number.isNaN(fallbackDate.getTime())
            ? fallbackDate.getTime()
            : 0;
      const displayDate = timestamp ? formatDateTimeByLang(new Date(timestamp), i18n.language) : "-";
      const sectorTag = inferSectorTag(item);
      const safeLink = String(item.link || "");
      const safeTitle = String(item.title || "news");
      const provider = item.provider || item.source || "Market Feed";
      const dedupeKey = `${safeLink}|${safeTitle}|${provider}|${timestamp}`;
      return {
        id: item.id || `${dedupeKey}|${idx}`,
        dedupeKey,
        title: safeTitle || "Untitled market news",
        link: safeLink || "#",
        provider,
        image: item.image || "",
        timestamp,
        displayDate,
        sentimentScore: score,
        sentiment: sentimentLabelFromScore(score),
        impact: impactFromScore(score),
        sectorTag,
      };
    });
    const seen = new Set();
    return mapped.filter((row) => {
      if (seen.has(row.dedupeKey)) return false;
      seen.add(row.dedupeKey);
      return true;
    });
  }, [items, i18n.language]);

  const topicFiltered = useMemo(() => {
    if (topicFilter === "all") return normalized;
    return normalized.filter((item) => String(item.sectorTag || "").toLowerCase() === topicFilter);
  }, [normalized, topicFilter]);

  const filteredItems = useMemo(() => {
    if (sentimentFilter === "all") return topicFiltered;
    return topicFiltered.filter((item) => String(item.sentiment || "").toLowerCase() === sentimentFilter);
  }, [topicFiltered, sentimentFilter]);

  const sortedItems = useMemo(() => {
    const impactRank = { High: 3, Medium: 2, Low: 1 };
    const arr = [...filteredItems];
    if (sortBy === "sortHighestImpact") {
      arr.sort((a, b) => {
        const d = (impactRank[b.impact] || 0) - (impactRank[a.impact] || 0);
        if (d !== 0) return d;
        return (b.timestamp || 0) - (a.timestamp || 0);
      });
      return arr;
    }
    if (sortBy === "sortMostBullish") {
      arr.sort((a, b) => Number(b.sentimentScore || 0) - Number(a.sentimentScore || 0));
      return arr;
    }
    arr.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    return arr;
  }, [filteredItems, sortBy]);

  const sentimentDistribution = useMemo(() => {
    const source = topicFiltered;
    const total = source.length || 1;
    const bullish = source.filter((x) => x.sentiment === "Bullish").length;
    const neutral = source.filter((x) => x.sentiment === "Neutral").length;
    const bearish = source.filter((x) => x.sentiment === "Bearish").length;
    return {
      bullish: Math.round((bullish / total) * 100),
      neutral: Math.round((neutral / total) * 100),
      bearish: Math.round((bearish / total) * 100),
    };
  }, [topicFiltered]);

  const aiSummary = useMemo(() => {
    if (!topicFiltered.length) return "No clear news signal yet. Expand sectors or refresh for latest market intelligence.";
    const avg = topicFiltered.reduce((acc, item) => acc + Number(item.sentimentScore || 0), 0) / topicFiltered.length;
    const sentimentLabel = sentimentLabelFromScore(avg);
    const highImpactCount = topicFiltered.filter((x) => x.impact === "High").length;
    const topSector = topicFiltered.reduce((acc, item) => {
      acc[item.sectorTag] = (acc[item.sectorTag] || 0) + 1;
      return acc;
    }, {});
    const topSectorName = Object.entries(topSector).sort((a, b) => b[1] - a[1])[0]?.[0] || "Technology";
    return `${t("aiMarketInsight")}: ${t("sentiment")} ${t(sentimentLabel.toLowerCase())}, ${topSectorName} • ${t("impactHigh")} ${highImpactCount}`;
  }, [topicFiltered, t]);

  const impactDistribution = useMemo(() => {
    const src = topicFiltered;
    return {
      high: src.filter((x) => x.impact === "High").length,
      medium: src.filter((x) => x.impact === "Medium").length,
      low: src.filter((x) => x.impact === "Low").length,
    };
  }, [topicFiltered]);

  return (
    <div className="space-y-5">
      <NewsHeader loading={loading} onRefresh={() => setRefreshToken((x) => x + 1)} dark={dark} />
      <NewsFilters
        sentimentFilter={sentimentFilter}
        topicFilter={topicFilter}
        sortBy={sortBy}
        setSentimentFilter={setSentimentFilter}
        setTopicFilter={setTopicFilter}
        setSortBy={setSortBy}
        dark={dark}
      />

      <div className="grid grid-cols-1 xl:grid-cols-[2fr,1fr] gap-5 items-start">
        <NewsFeed
          items={sortedItems}
          loading={loading}
          dark={dark}
          bookmarkedNews={bookmarkedNews}
          onToggleBookmark={onToggleNewsBookmark}
        />

        <div className="space-y-4 xl:sticky xl:top-20">
          <NewsSentimentSummary distribution={sentimentDistribution} dark={dark} />
          <section className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-200" : "bg-white border-slate-200 text-slate-800"} rounded-2xl border p-5 shadow-md`}>
            <h3 className="text-lg font-bold mb-3">{t("impactLevel")}</h3>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl bg-rose-50 text-rose-700 p-2">
                <p className="text-xs font-semibold">{t("impactHigh")}</p>
                <p className="text-xl font-bold">{impactDistribution.high}</p>
              </div>
              <div className="rounded-xl bg-amber-50 text-amber-700 p-2">
                <p className="text-xs font-semibold">{t("impactMedium")}</p>
                <p className="text-xl font-bold">{impactDistribution.medium}</p>
              </div>
              <div className="rounded-xl bg-emerald-50 text-emerald-700 p-2">
                <p className="text-xs font-semibold">{t("impactLow")}</p>
                <p className="text-xl font-bold">{impactDistribution.low}</p>
              </div>
            </div>
          </section>
          <AIInsightPanel message={aiSummary} dark={dark} />
        </div>
      </div>
    </div>
  );
};

const Stockdetail = ({ watchlist = [], onToggleWatchlist = () => {} }) => {
  const { t, i18n } = useTranslation();
  const { theme } = useContext(ThemeContext);
  const { symbol } = useParams();
  const navigate = useNavigate();
  const [stockData, setStockData] = useState(null);
  const [reco, setReco] = useState(null);
  const [stockDetails, setStockDetails] = useState(null);
  const [stockDetailsLoading, setStockDetailsLoading] = useState(true);
  const [stockProfile, setStockProfile] = useState(null);
  const [newsItems, setNewsItems] = useState([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [range, setRange] = useState("1m");

  useEffect(() => {
    let alive = true;
    const run = async () => {
      setLoading(true);
      setError("");
      setReco(null);
      setStockDetails(null);
      setStockDetailsLoading(true);
      setStockProfile(null);
      setNewsItems([]);
      setNewsLoading(false);
      try {
        const rawSymbol = String(symbol || "").trim().toUpperCase();
        if (!/^[A-Z0-9.-]{1,12}$/.test(rawSymbol)) {
          throw new Error("invalid_symbol");
        }
        const safeSymbol = rawSymbol;
        const [stockJson, quoteJson, detailsJson, profileJson] = await Promise.all([
          fetchJsonWithRetry(
            [
              apiUrl(`/api/stock-history?ticker=${safeSymbol}&period=${range}`),
              apiUrl(`/stock/${safeSymbol}?range=${range}`),
              `http://localhost:8000/api/stock-history?ticker=${safeSymbol}&period=${range}`,
              `http://localhost:8000/stock/${safeSymbol}?range=${range}`,
            ],
            2,
            5000
          ),
          fetchJsonWithRetry(
            [
              apiUrl(`/stock/${safeSymbol}?range=${range}`),
              `http://localhost:8000/stock/${safeSymbol}?range=${range}`,
            ],
            2,
            5000
          ).catch(() => null),
          fetchJsonWithRetry(
            [
              apiUrl(`/api/stock/financials/${safeSymbol}`),
              apiUrl(`/stock/financials/${safeSymbol}`),
              apiUrl(`/api/stock/details/${safeSymbol}`),
              apiUrl(`/stock/details/${safeSymbol}`),
              `http://localhost:8000/api/stock/financials/${safeSymbol}`,
              `http://localhost:8000/stock/financials/${safeSymbol}`,
              `http://localhost:8000/api/stock/details/${safeSymbol}`,
              `http://localhost:8000/stock/details/${safeSymbol}`,
            ],
            1,
            6000
          ).catch(() => null),
          fetchJsonWithRetry(
            [
              apiUrl(`/api/stock/profile/${safeSymbol}`),
              apiUrl(`/stock/profile/${safeSymbol}`),
              `http://localhost:8000/api/stock/profile/${safeSymbol}`,
              `http://localhost:8000/stock/profile/${safeSymbol}`,
            ],
            1,
            6000
          ).catch(() => null),
        ]);

        const rawHistory = Array.isArray(stockJson)
          ? stockJson
          : Array.isArray(stockJson?.history)
            ? stockJson.history
            : [];

        const history = rawHistory
          .map((row) => ({
            date: String(row?.date || ""),
            close: Number(row?.price ?? row?.close ?? 0),
            volume: Number(row?.volume ?? 0),
          }))
          .filter((row) => row.date && Number.isFinite(row.close) && row.close > 0)
          .sort((a, b) => String(a.date).localeCompare(String(b.date)));

        if (!history.length) {
          throw new Error("no_history");
        }

        const firstClose = Number(quoteJson?.first_close || history[0]?.close || 0);
        const lastClose = Number(quoteJson?.last_close || history[history.length - 1]?.close || 0);
        const previousClose = Number(quoteJson?.previous_close || 0);
        const latest = lastClose > 0 ? lastClose : Number(history[history.length - 1]?.close || 0);

        // Strict close-only range return to match finance platforms.
        const rangeReturnFromClose = firstClose > 0 ? ((latest - firstClose) / firstClose) * 100 : 0;
        const dailyChangePct = Number.isFinite(Number(quoteJson?.change_pct))
          ? Number(quoteJson?.change_pct)
          : (previousClose > 0 ? ((latest - previousClose) / previousClose) * 100 : 0);
        const changeAbs = Number.isFinite(Number(quoteJson?.change))
          ? Number(quoteJson?.change)
          : (previousClose > 0 ? (latest - previousClose) : 0);
        const returnPct = Number.isFinite(Number(quoteJson?.range_return_pct))
          ? Number(quoteJson?.range_return_pct)
          : (range === "1d" ? dailyChangePct : rangeReturnFromClose);

        if (!alive) return;
        setStockData({
          symbol: safeSymbol,
          latest_price: latest,
          change_abs: changeAbs,
          daily_change_pct: dailyChangePct,
          return_pct: returnPct,
          previous_close: previousClose > 0 ? previousClose : null,
          first_close: firstClose > 0 ? firstClose : null,
          last_close: latest > 0 ? latest : null,
          volume: Number(quoteJson?.volume || history[history.length - 1]?.volume || 0),
          day_range_low: Number(quoteJson?.day_range_low || 0) || null,
          day_range_high: Number(quoteJson?.day_range_high || 0) || null,
          range_52w_low: Number(quoteJson?.range_52w_low || 0) || null,
          range_52w_high: Number(quoteJson?.range_52w_high || 0) || null,
          history,
        });
        setStockDetails(detailsJson && typeof detailsJson === "object" ? detailsJson : null);
        setStockDetailsLoading(false);
        setStockProfile(profileJson && typeof profileJson === "object" ? profileJson : { name: safeSymbol, ticker: safeSymbol });

        setLoading(false);
        setNewsLoading(true);

        const [recoJson, newsJson] = await Promise.all([
          fetchJsonWithRetry(
            [
              apiUrl(`/recommend?symbol=${safeSymbol}&window_days=30`),
              `http://localhost:8000/recommend?symbol=${safeSymbol}&window_days=30`,
            ],
            1,
            4000
          ).catch(() => null),
          fetchJsonWithRetry(
            [
              apiUrl(`/news?symbols=${safeSymbol}&days_back=14`),
              `http://localhost:8000/news?symbols=${safeSymbol}&days_back=14`,
            ],
            1,
            4000
          ).catch(() => []),
        ]);

        if (!alive) return;
        if (recoJson) {
          setReco({
            recommendation: recoJson.recommendation || "HOLD",
            target_price: recoJson.target_price || recoJson.target_price_mean || latest,
            target_price_mean: recoJson.target_price || recoJson.target_price_mean || latest,
            target_price_high: recoJson.target_price_high || 0,
            target_price_low: recoJson.target_price_low || 0,
            current_price: recoJson.current_price || latest,
            upside_pct: Number(recoJson.upside_pct || 0),
            confidence: typeof recoJson.confidence === "number" ? recoJson.confidence : 0.7,
            simple_action: recoJson.simple_action || "",
            risk_level: recoJson.risk_level || "Medium",
            ai_score: Number(recoJson.ai_score || 50),
            sentiment_avg: Number(recoJson.sentiment_avg || 0),
            signals: recoJson.signals || {},
            weights: recoJson.weights || {},
            technical_indicators: recoJson.technical_indicators || {},
            news_sentiment_distribution: recoJson.news_sentiment_distribution || {},
            forecast: recoJson.forecast || {},
            sources: Array.isArray(recoJson.sources) ? recoJson.sources : [],
          });
        }
        const mergedNews = (Array.isArray(newsJson) ? newsJson : [newsJson]).flatMap((item) => item?.news || []);
        setNewsItems(mergedNews.slice(0, 12));
        setNewsLoading(false);
      } catch {
        if (!alive) return;
        setError(t("stockLoadError") === "stockLoadError" ? "ไม่สามารถโหลดข้อมูลหุ้นได้ในขณะนี้" : t("stockLoadError"));
        setStockData(null);
        setStockDetails(null);
        setStockDetailsLoading(false);
        setStockProfile(null);
        setReco(null);
        setNewsItems([]);
      } finally {
        if (alive) {
          setNewsLoading(false);
          setLoading(false);
        }
      }
    };

    run();
    return () => {
      alive = false;
    };
  }, [symbol, range, t]);

  const chartSeries = useMemo(() => {
    const history = stockData?.history || [];
    if (!history.length) return [];

    const prices = history.map((point) => Number(point.close || 0));
    const movingAvg = (index, window) => {
      if (index + 1 < window) return null;
      const slice = prices.slice(index - window + 1, index + 1).filter((value) => Number.isFinite(value) && value > 0);
      if (!slice.length) return null;
      return Number((slice.reduce((sum, value) => sum + value, 0) / slice.length).toFixed(2));
    };

    return history.map((point, index) => {
      const current = Number(point.close || 0);
      const previous = Number(index > 0 ? history[index - 1]?.close : current);
      const dailyChangePct = previous ? ((current - previous) / previous) * 100 : 0;
      return {
        date: point.date,
        price: Number(current.toFixed(2)),
        volume: Number(point.volume || 0),
        dailyChangePct: Number(dailyChangePct.toFixed(2)),
        ma50: movingAvg(index, 50),
        ma200: movingAvg(index, 200),
      };
    });
  }, [stockData]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-slate-400">
        <Loader2 className="animate-spin mb-4" size={40} />
        <p className="font-medium text-lg">{t("analyzing")} {symbol}...</p>
      </div>
    );
  }

  if (error || !stockData) {
    return (
      <div className={`${theme === "dark" ? "bg-[#0F172A] border-rose-900/40" : "bg-white border-rose-100"} rounded-2xl border p-8 text-rose-600 font-medium`}>
        {error || t("connectError")}
      </div>
    );
  }

  const isSaved = watchlist.includes(stockData.symbol);

  return (
    <div className="space-y-6">
      <button onClick={() => navigate(-1)} className="flex items-center text-slate-500 hover:text-[#2563EB] font-bold transition-colors">
        <ArrowLeft className="mr-2" size={20} /> {t("backSearch")}
      </button>

      <div className="flex items-start gap-3">
        <StarButton
          active={isSaved}
          onToggle={() => onToggleWatchlist(stockData.symbol)}
          size="lg"
          title={isSaved ? `${t("removeFromWatchlist")} ${stockData.symbol}` : `${t("addToWatchlist")} ${stockData.symbol}`}
          className={theme === "dark" ? "bg-slate-900 border-slate-700 text-slate-300" : ""}
        />
        <div className="flex-1">
          <StockCompanyHeader
            profile={stockProfile}
            symbol={stockData.symbol}
            currentPrice={stockData.latest_price}
            changeAbs={stockData.change_abs}
            dailyChangePct={stockData.daily_change_pct}
            returnPct={stockData.return_pct}
            rangeLabel={String(range || "1y").toUpperCase()}
            language={i18n.language}
            dark={theme === "dark"}
          />
        </div>
      </div>

      <div className={`${theme === "dark" ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-100"} p-6 rounded-3xl border shadow-sm space-y-4`}>
        <TimeRangeSelector range={range} onChange={setRange} dark={theme === "dark"} />
        <StockChart data={chartSeries} returnPct={stockData.return_pct} dark={theme === "dark"} />
      </div>

      <StockStatsGrid details={stockDetails} loading={stockDetailsLoading} language={i18n.language} dark={theme === "dark"} />

      {reco ? <AIInvestmentAnalysis reco={reco} language={i18n.language} dark={theme === "dark"} /> : null}

      <NewsSentimentFilter items={newsItems} loading={newsLoading} dark={theme === "dark"} />
    </div>
  );
};

const RISK_PROFILE_OPTIONS = [
  {
    level: "LOW",
    titleKey: "riskLowTitle",
    title: "Stable long-term growth",
    descriptionKey: "riskLowDesc",
    description: "Lower volatility with resilient large-cap and defensive assets.",
    expectedReturnKey: "riskLowReturn",
    expectedReturn: "4% - 8% / year",
    volatilityKey: "riskVolLow",
    volatility: "Low",
    suitableForKey: "riskLowSuitable",
    suitableFor: "Recommended for conservative investors",
    strategyKeys: ["riskLowStrategy1", "riskLowStrategy2", "riskLowStrategy3"],
    strategy: ["Prioritize stable cashflow businesses", "Allocate toward dividend and broad-market ETF", "Rebalance quarterly for risk control"],
    allocation: [
      { labelKey: "allocationStocks", label: "Stocks", value: "40%" },
      { labelKey: "allocationEtf", label: "ETF", value: "40%" },
      { labelKey: "allocationCash", label: "Cash", value: "20%" },
    ],
  },
  {
    level: "MEDIUM",
    titleKey: "riskMediumTitle",
    title: "Balanced growth",
    descriptionKey: "riskMediumDesc",
    description: "Balanced mix between growth and stability for long-term performance.",
    expectedReturnKey: "riskMediumReturn",
    expectedReturn: "8% - 14% / year",
    volatilityKey: "riskVolModerate",
    volatility: "Moderate",
    suitableForKey: "riskMediumSuitable",
    suitableFor: "Suitable for long-term investors",
    strategyKeys: ["riskMediumStrategy1", "riskMediumStrategy2", "riskMediumStrategy3"],
    strategy: ["Mix growth leaders and high-quality value names", "Use ETF for diversification buffer", "Keep tactical cash for opportunities"],
    allocation: [
      { labelKey: "allocationStocks", label: "Stocks", value: "60%" },
      { labelKey: "allocationEtf", label: "ETF", value: "30%" },
      { labelKey: "allocationCash", label: "Cash", value: "10%" },
    ],
  },
  {
    level: "HIGH",
    titleKey: "riskHighTitle",
    title: "Aggressive growth",
    descriptionKey: "riskHighDesc",
    description: "Higher upside potential from momentum and thematic growth stocks.",
    expectedReturnKey: "riskHighReturn",
    expectedReturn: "14%+ / year",
    volatilityKey: "riskVolHigh",
    volatility: "High",
    suitableForKey: "riskHighSuitable",
    suitableFor: "Suitable for risk-tolerant investors",
    strategyKeys: ["riskHighStrategy1", "riskHighStrategy2", "riskHighStrategy3"],
    strategy: ["Focus on high growth sectors and innovation themes", "Use strict stop-loss and position sizing", "Review portfolio weekly for fast changes"],
    allocation: [
      { labelKey: "allocationStocks", label: "Stocks", value: "80%" },
      { labelKey: "allocationEtf", label: "ETF", value: "15%" },
      { labelKey: "allocationCash", label: "Cash", value: "5%" },
    ],
  },
];

const strategyToApi = (strategy) => {
  if (strategy === "Momentum" || strategy === "AI Trend") return "AGGRESSIVE";
  if (strategy === "Value") return "DEFENSIVE";
  return "BALANCED";
};

const sentimentFromValue = (raw) => {
  const score = Number(raw);
  if (Number.isFinite(score)) {
    if (score > 0.2) return "Bullish";
    if (score < -0.2) return "Bearish";
    return "Neutral";
  }
  const text = String(raw || "").toLowerCase();
  if (text.includes("bull")) return "Bullish";
  if (text.includes("bear")) return "Bearish";
  return "Neutral";
};

const riskFromVolatility = (volatility) => {
  const vol = Number(volatility);
  if (!Number.isFinite(vol)) return "MEDIUM";
  if (vol >= 0.4) return "HIGH";
  if (vol >= 0.22) return "MEDIUM";
  return "LOW";
};

const momentumFromReturn = (ret30) => {
  const value = Number(ret30);
  if (!Number.isFinite(value)) return "Moderate";
  if (value >= 8) return "Strong";
  if (value <= -3) return "Weak";
  return "Moderate";
};

const AIPickerPage = () => {
  const { t } = useTranslation();
  const { theme } = useContext(ThemeContext);
  const dark = theme === "dark";
  const [risk, setRisk] = useState("MEDIUM");
  const [strategy, setStrategy] = useState("AI Trend");
  const [sentiment, setSentiment] = useState("Bullish");
  const [allPicks, setAllPicks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadPicks = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetchJsonWithRetry(
        [
          apiUrl(`/ai-picker?strategy=${strategyToApi(strategy)}&limit=30`),
          `http://localhost:8000/ai-picker?strategy=${strategyToApi(strategy)}&limit=30`,
        ],
        2,
        12000
      );
      const mapped = (response?.items || []).map((row) => {
        const aiScore = Number(row?.ai_score ?? row?.score ?? 0);
        const confidenceRaw = Number(row?.confidence);
        return {
          ticker: String(row?.ticker || "").toUpperCase(),
          company: row?.company || row?.name || String(row?.ticker || "").toUpperCase(),
          risk: riskFromVolatility(row?.volatility),
          strategy,
          sentiment: sentimentFromValue(row?.sentiment),
          momentum: momentumFromReturn(row?.ret30),
          aiScore: Math.max(0, Math.min(100, Number.isFinite(aiScore) ? aiScore : 0)),
          confidence: Number.isFinite(confidenceRaw) ? Math.max(0, Math.min(100, confidenceRaw)) : null,
          reason: row?.reason || "",
        };
      });
      setAllPicks(mapped);
    } catch (e) {
      setAllPicks([]);
      setError(e?.message || "Unable to load AI picks");
    } finally {
      setLoading(false);
    }
  }, [strategy]);

  useEffect(() => {
    loadPicks();
  }, [loadPicks]);

  const picks = useMemo(() => {
    const byRisk = allPicks.filter((item) => item.risk === risk);
    const bySentiment = byRisk.filter((item) => item.sentiment === sentiment);
    const selected = bySentiment.length ? bySentiment : byRisk;
    return selected.sort((a, b) => b.aiScore - a.aiScore).slice(0, 9);
  }, [allPicks, risk, sentiment]);

  const topPicks = useMemo(() => [...picks].sort((a, b) => b.aiScore - a.aiScore).slice(0, 3), [picks]);

  const insight = useMemo(() => {
    if (!picks.length) return t("noPicks");
    const averageScore = (picks.reduce((sum, item) => sum + Number(item.aiScore || 0), 0) / picks.length).toFixed(1);
    return `Top picks reflect ${sentiment.toLowerCase()} sentiment with ${risk.toLowerCase()} risk profile. Strategy focus: ${strategy}. Average AI score: ${averageScore}.`;
  }, [picks, risk, strategy, sentiment, t]);

  const onGenerate = async () => {
    await loadPicks();
  };

  return (
    <div className="space-y-6">
      <AIPickerHero onGenerate={onGenerate} loading={loading} />

      <AIPickerFilters
        risk={risk}
        setRisk={setRisk}
        strategy={strategy}
        setStrategy={setStrategy}
        sentiment={sentiment}
        setSentiment={setSentiment}
        dark={dark}
      />

      <section className="space-y-3">
        <h2 className={`${dark ? "text-slate-100" : "text-slate-900"} text-2xl font-bold`}>{t("topAiPicksToday")}</h2>
        {error ? (
          <div className={`${dark ? "bg-rose-950/30 border-rose-900/50 text-rose-300" : "bg-rose-50 border-rose-200 text-rose-700"} rounded-2xl border p-4 text-sm font-medium`}>
            {error}
          </div>
        ) : null}
        {topPicks.length === 0 ? (
          <div className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-500"} rounded-2xl border p-8 shadow-md`}>
            {t("noPicks")}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {topPicks.map((stock) => (
              <StockPickCard key={`top-${stock.ticker}`} stock={stock} dark={dark} />
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className={`${dark ? "text-slate-100" : "text-slate-900"} text-2xl font-bold`}>{t("aiStockPicks")}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {picks.map((stock) => (
            <StockPickCard key={stock.ticker} stock={stock} dark={dark} />
          ))}
        </div>
      </section>

      <AIInsightPanel message={insight} dark={dark} />
    </div>
  );
};

const RiskPage = () => {
  const { t } = useTranslation();
  const { theme } = useContext(ThemeContext);
  const [level, setLevel] = useState("LOW");
  const [refreshToken, setRefreshToken] = useState(0);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState("");

  useEffect(() => {
    const run = async () => {
      setLoading(true);
      try {
        const res = await fetch(apiUrl(`/risk/recommend?level=${level}&limit=10`));
        if (!res.ok) throw new Error("risk api failed");
        const data = await res.json();
        const primary = data.items || [];

        if (primary.length > 0) {
          setItems(primary);
          setNote("");
          return;
        }

        const fallbackLevels = ["LOW", "MEDIUM", "HIGH"].filter((x) => x !== level);
        for (const lv of fallbackLevels) {
          const fRes = await fetch(apiUrl(`/risk/recommend?level=${lv}&limit=10`));
          if (!fRes.ok) continue;
          const fData = await fRes.json();
          const fItems = fData.items || [];
          if (fItems.length > 0) {
            setItems(fItems);
            setNote(t("riskFallbackLevel", { level, fallback: lv }));
            return;
          }
        }

        setItems([]);
        setNote(t("riskNoDataRetry"));
      } catch {
        setItems([]);
        setNote(t("riskLoadFail"));
      } finally {
        setLoading(false);
      }
    };

    run();
  }, [level, refreshToken, t]);

  const selectedProfile = RISK_PROFILE_OPTIONS.find((p) => p.level === level) || RISK_PROFILE_OPTIONS[0];
  const dark = theme === "dark";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className={`${dark ? "text-slate-100" : "text-slate-900"} text-3xl font-bold`}>{t("aiRiskAnalysis")}</h1>
          <p className="text-slate-500">{t("riskSub")}</p>
        </div>
        <button
          onClick={() => setRefreshToken((x) => x + 1)}
          className="px-4 py-2 rounded-xl text-white font-semibold transition-all hover:brightness-110 hover:scale-[1.01]"
          style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
        >
          {t("refreshRecommendations")}
        </button>
      </div>

      <RiskSelector options={RISK_PROFILE_OPTIONS} selected={level} onSelect={setLevel} dark={dark} />
      <RiskExplanation profile={selectedProfile} dark={dark} />

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className={`${dark ? "text-slate-100" : "text-slate-900"} text-2xl font-bold`}>{t("aiRecommendedStocks")}</h2>
          <span className="text-sm text-slate-500">{t("profile")}: {level}</span>
        </div>

        {note ? <div className="px-4 py-3 text-sm text-amber-700 bg-amber-50 border border-amber-100 rounded-xl">{note}</div> : null}

        {loading ? (
          <div className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-10 text-center text-slate-500 shadow-md`}>
            {t("loadingReco")}
          </div>
        ) : items.length === 0 ? (
          <div className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-500"} rounded-2xl border p-10 shadow-md text-center`}>
            <ShieldAlert className="mx-auto mb-3 text-slate-400" size={34} />
            <p className="font-semibold">{t("noRecommendedStocks")}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {items.map((item, idx) => (
              <RiskStockCard key={`${item.Symbol || item.symbol}-${idx}`} item={item} level={level} dark={dark} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

const WatchlistPage = ({ watchlist = [], onToggleWatchlist = () => {}, onAddWatchSymbol = () => {}, bookmarkedNews = [] }) => {
  const { t } = useTranslation();
  const { theme } = useContext(ThemeContext);
  const dark = theme === "dark";
  const navigate = useNavigate();
  const [inputSymbol, setInputSymbol] = useState("");
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState([]);

  useEffect(() => {
    let alive = true;

    const run = async () => {
      if (!watchlist.length) {
        setRows([]);
        return;
      }
      setLoading(true);
      const nextRows = await Promise.all(
        watchlist.map(async (symbol) => {
          const safeSymbol = String(symbol || "").toUpperCase();
          try {
            const [stockJson, recoJson] = await Promise.all([
              fetchJsonWithRetry(
                [
                  apiUrl(`/stock/${safeSymbol}?range=1m`),
                  `http://localhost:8000/stock/${safeSymbol}?range=1m`,
                ],
                4
              ),
              fetchJsonWithRetry(
                [
                  apiUrl(`/recommend?symbol=${safeSymbol}&window_days=14`),
                  `http://localhost:8000/recommend?symbol=${safeSymbol}&window_days=14`,
                ],
                1,
                7000
              ).catch(() => null),
            ]);
            const history = stockJson.history || [];
            const company = String(stockJson.name || safeSymbol);
            const latest = Number(stockJson.latest_price || stockJson.price || history[history.length - 1]?.close || 0);
            const previousClose = Number(stockJson.previous_close || history[history.length - 2]?.close || latest || 0);
            const change = previousClose ? ((latest - previousClose) / previousClose) * 100 : 0;
            const points = history
              .slice(-7)
              .map((h) => Number(h.close || h.price || 0))
              .filter((x) => Number.isFinite(x) && x > 0);
            const volume = Number(history[history.length - 1]?.volume || stockJson.volume || 0);
            const aiScore = Number(recoJson?.ai_score || 0);

            return {
              symbol: safeSymbol,
              company,
              sector: String(recoJson?.risk_level || "Unclassified"),
              price: latest,
              change,
              volume,
              aiScore: Number.isFinite(aiScore) ? Math.round(aiScore) : 0,
              points,
              sentiment: sentimentFromChange(change),
            };
          } catch {
            return null;
          }
        })
      );

      if (!alive) return;
      const cleanRows = nextRows.filter((item) => item && Number.isFinite(item.price) && item.price > 0);
      setRows(cleanRows.sort((a, b) => b.aiScore - a.aiScore));
      setLoading(false);
    };

    run();
    return () => {
      alive = false;
    };
  }, [watchlist]);

  const groupedBySector = useMemo(() => {
    const groups = rows.reduce((acc, item) => {
      const sectorName = String(item?.sector || "Unclassified");
      if (!acc[sectorName]) acc[sectorName] = [];
      acc[sectorName].push(item);
      return acc;
    }, {});
    return Object.keys(groups).map((sector) => ({ sector, items: groups[sector] }));
  }, [rows]);

  const onAdd = () => {
    const next = inputSymbol.trim().toUpperCase();
    if (!/^[A-Z0-9.-]{1,12}$/.test(next)) return;
    onAddWatchSymbol(next);
    setInputSymbol("");
  };

  return (
    <div className="space-y-6">
      <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-6 shadow-md`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className={`${dark ? "text-slate-100" : "text-slate-900"} text-3xl font-bold`}>{t("myWatchlist")}</h1>
            <p className="text-slate-500">{t("watchlistSubtitle")}</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              value={inputSymbol}
              onChange={(e) => setInputSymbol(e.target.value)}
              placeholder="e.g. NVDA"
              className={`${dark ? "bg-slate-900 border-slate-700 text-slate-100" : "bg-slate-50 border-slate-200 text-slate-800"} rounded-xl border px-3 py-2 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-[#2563EB]`}
            />
            <button
              type="button"
              onClick={onAdd}
              className="inline-flex items-center gap-2 text-white font-semibold px-4 py-2 rounded-xl shadow-md transition-all hover:scale-[1.02] hover:brightness-110"
              style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
            >
              <Plus size={16} />
              {t("addStock")}
            </button>
          </div>
        </div>
      </section>

      {loading ? (
        <div className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-500"} rounded-2xl border p-10 text-center shadow-md`}>
          {t("loadingWatchlist")}
        </div>
      ) : rows.length === 0 ? (
        <section className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-600"} rounded-2xl border p-10 text-center shadow-md`}>
          <p className="text-lg font-semibold mb-3">{t("emptyWatchlist")}</p>
          <button
            type="button"
            onClick={() => navigate("/search")}
            className="text-white font-semibold px-5 py-2 rounded-xl shadow-md transition-all hover:brightness-110"
            style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
          >
            {t("browseStocks")}
          </button>
        </section>
      ) : (
        <>
          <WatchlistTable
            groups={groupedBySector}
            dark={dark}
            onRemove={onToggleWatchlist}
            onOpen={(symbol) => navigate(`/stock/${symbol}`)}
          />
          <WatchlistInsight items={rows} dark={dark} bookmarkedNews={bookmarkedNews} />
        </>
      )}
    </div>
  );
};

const PortfolioPage = ({ watchlist = [] }) => {
  const { t, i18n } = useTranslation();
  const { theme } = useContext(ThemeContext);
  const { token } = useContext(AuthContext);
  const navigate = useNavigate();
  const dark = theme === "dark";
  const [range, setRange] = useState("1M");
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState([]);
  const [summary, setSummary] = useState({
    totalValue: 0,
    dailyChangePct: 0,
    totalGainPct: 0,
    holdingsCount: 0,
    diversificationScore: 0,
  });
  const [allocation, setAllocation] = useState([]);
  const [sectorExposure, setSectorExposure] = useState([]);
  const [performanceData, setPerformanceData] = useState([]);
  const [insight, setInsight] = useState({
    riskScore: 0,
    riskLevel: "Low",
    summary: t("portfolioDiversificationHint"),
    rebalanceSuggestions: [t("rebalanceIncreaseEtf")],
  });
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRow, setEditingRow] = useState(null);
  const hasToken = Boolean(token);

  const authHeaders = useMemo(
    () => ({
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }),
    [token]
  );

  const mapRangeForApi = (uiRange) => {
    const key = String(uiRange || "1M").toUpperCase();
    if (key === "1M") return "1m";
    if (key === "3M") return "3m";
    if (key === "6M") return "6m";
    return "1y";
  };

  const loadPortfolio = useCallback(
    async (selectedRange = range) => {
      if (!hasToken) return;
      setLoading(true);
      try {
        const overview = await fetchJsonWithRetry(
          [
            apiUrl(`/api/portfolio/overview?range=${mapRangeForApi(selectedRange)}`),
            `http://localhost:8000/api/portfolio/overview?range=${mapRangeForApi(selectedRange)}`,
          ],
          2,
          10000,
          { method: "GET", headers: authHeaders }
        );

        const tableRows = Array.isArray(overview?.rows)
          ? overview.rows.map((row) => ({
              ...row,
              avgPrice: Number(row.avgPrice || row.average_buy_price || 0),
            }))
          : [];
        setRows(tableRows);
        setSummary(overview?.summary || {});
        setAllocation(Array.isArray(overview?.allocation) ? overview.allocation : []);
        setSectorExposure(Array.isArray(overview?.sectorExposure) ? overview.sectorExposure : []);
        setPerformanceData(Array.isArray(overview?.performance) ? overview.performance : []);
        setInsight({
          riskScore: Number(overview?.risk?.score || 0),
          riskLevel: overview?.risk?.level || "Low",
          summary: overview?.insight?.summary || t("portfolioDiversificationHint"),
          rebalanceSuggestions:
            Array.isArray(overview?.insight?.suggestions) && overview.insight.suggestions.length
              ? overview.insight.suggestions
              : [t("rebalanceIncreaseEtf")],
        });
      } catch (error) {
        console.error("load portfolio failed", error);
        setRows([]);
        setSummary({
          totalValue: 0,
          dailyChangePct: 0,
          totalGainPct: 0,
          holdingsCount: 0,
          diversificationScore: 0,
        });
      } finally {
        setLoading(false);
      }
    },
    [authHeaders, hasToken, range, t]
  );

  useEffect(() => {
    loadPortfolio(range);
  }, [loadPortfolio, range]);

  useEffect(() => {
    if (!hasToken) return undefined;
    const timer = setInterval(() => {
      loadPortfolio(range);
    }, 45000);
    return () => clearInterval(timer);
  }, [hasToken, loadPortfolio, range]);

  const createPosition = async (payload) => {
    const res = await fetch(apiUrl("/api/portfolio/positions"), {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || "Unable to add position");
    await loadPortfolio(range);
  };

  const updatePosition = async (payload) => {
    if (!editingRow?.id) throw new Error("Missing position id");
    const res = await fetch(apiUrl(`/api/portfolio/positions/${editingRow.id}`), {
      method: "PUT",
      headers: authHeaders,
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || "Unable to update position");
    await loadPortfolio(range);
  };

  const deletePosition = async (row) => {
    const ok = window.confirm(`Delete ${row.symbol} position?`);
    if (!ok) return;
    const res = await fetch(apiUrl(`/api/portfolio/positions/${row.id}`), {
      method: "DELETE",
      headers: authHeaders,
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data?.detail || "Delete failed");
      return;
    }
    await loadPortfolio(range);
  };

  if (!hasToken) {
    return (
      <section className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-600"} rounded-2xl border p-10 text-center shadow-md`}>
        <p className="text-lg font-semibold mb-3">Please sign in to use portfolio tracking.</p>
        <button
          type="button"
          onClick={() => navigate("/login")}
          className="text-white font-semibold px-5 py-2 rounded-xl shadow-md transition-all hover:brightness-110"
          style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
        >
          Go to Login
        </button>
      </section>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
        <h1 className={`${dark ? "text-slate-100" : "text-slate-900"} text-3xl font-bold`}>{t("portfolioDashboard")}</h1>
        <p className="text-slate-500">{t("portfolioSubtitle")}</p>
        </div>
        <button
          type="button"
          onClick={() => {
            setEditingRow(null);
            setModalOpen(true);
          }}
          className="text-white font-semibold px-5 py-2 rounded-xl shadow-md transition-all hover:brightness-110"
          style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
        >
          + Add Position
        </button>
      </div>

      <PortfolioSummary summary={summary} dark={dark} language={i18n.language} />

      <div className="grid grid-cols-1 xl:grid-cols-[2fr,1fr] gap-5">
        <PortfolioChart data={performanceData} range={range} onRangeChange={setRange} dark={dark} />
        <AllocationChart allocation={allocation} sectorExposure={sectorExposure} dark={dark} />
      </div>

      {loading ? (
        <div className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-500"} rounded-2xl border p-10 text-center shadow-md`}>
          {t("loadingPortfolio")}
        </div>
      ) : !rows.length ? (
        <section className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-600"} rounded-2xl border p-10 text-center shadow-md`}>
          <p className="text-lg font-semibold mb-3">{t("emptyPortfolio")}</p>
          <button
            type="button"
            onClick={() => {
              setEditingRow(null);
              setModalOpen(true);
            }}
            className="text-white font-semibold px-5 py-2 rounded-xl shadow-md transition-all hover:brightness-110"
            style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
          >
            {t("addFirstStock")}
          </button>
        </section>
      ) : (
        <PortfolioTable
          rows={rows}
          dark={dark}
          language={i18n.language}
          onEdit={(row) => {
            setEditingRow(row);
            setModalOpen(true);
          }}
          onDelete={deletePosition}
        />
      )}

      <PortfolioInsight insight={insight} dark={dark} />

      <PortfolioPositionModal
        open={modalOpen}
        mode={editingRow ? "edit" : "create"}
        initialValue={editingRow}
        dark={dark}
        onClose={() => {
          setModalOpen(false);
          setEditingRow(null);
        }}
        onSubmit={editingRow ? updatePosition : createPosition}
      />
    </div>
  );
};

const AIInsightsPage = ({ watchlist = [], recentSearches = [] }) => {
  const { t } = useTranslation();
  const { theme } = useContext(ThemeContext);
  const dark = theme === "dark";
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [overview, setOverview] = useState({ sentiment: "-", sector: "-", topPick: "-", riskLevel: "-" });
  const [signals, setSignals] = useState([]);
  const [trending, setTrending] = useState([]);
  const [sectors, setSectors] = useState([]);
  const [rotation, setRotation] = useState([]);
  const [summary, setSummary] = useState("");
  const [radar, setRadar] = useState([]);

  useEffect(() => {
    let alive = true;
    const cacheKey = JSON.stringify({
      w: normalizeSymbolList(Array.isArray(watchlist) ? watchlist : []).slice(0, 8),
      r: normalizeSymbolList(Array.isArray(recentSearches) ? recentSearches : []).slice(0, 8),
    });

    const setFromSnapshot = (snapshot) => {
      setOverview(snapshot.overview || { sentiment: "-", sector: "-", topPick: "-", riskLevel: "-" });
      setSignals(snapshot.signals || []);
      setSectors(snapshot.sectors || []);
      setRotation(snapshot.rotation || []);
      setSummary(snapshot.summary || "");
      setRadar(snapshot.radar || []);
      setTrending(snapshot.trending || []);
    };

    const cached = aiInsightsViewCache.get(cacheKey);
    if (cached && (Date.now() - Number(cached.ts || 0)) < AI_INSIGHTS_CACHE_TTL_MS) {
      setFromSnapshot(cached.data || {});
      setLoading(false);
    }

    const run = async () => {
      if (!cached) setLoading(true);
      setError("");
      try {
        const [summaryResult, pickerResult] = await Promise.allSettled([
          fetchJsonWithRetry(
            [apiUrl("/api/ai-summary"), localFastapiUrl("/api/ai-summary")],
            1,
            9000,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ context: { watchlist, recent_searches: recentSearches } }),
            }
          ),
          fetchJsonWithRetry(
            [apiUrl("/ai-picker?strategy=BALANCED&limit=8"), localFastapiUrl("/ai-picker?strategy=BALANCED&limit=8")],
            1,
            7000
          ),
        ]);

        const summaryPayload = summaryResult.status === "fulfilled" ? summaryResult.value : null;
        const pickerPayload = pickerResult.status === "fulfilled" ? pickerResult.value : { items: [] };

        const summaryData = summaryPayload?.summary || {};
        const pickerItems = Array.isArray(pickerPayload?.items) ? pickerPayload.items : [];
        const topSymbols = normalizeSymbolList(pickerItems.map((item) => item?.ticker)).slice(0, 4);

        const rankedSectors = Object.entries(summaryData?.sector_performance || {})
          .map(([name, score]) => ({ name, momentum: Math.max(0, Math.min(100, Number(score) || 0)) }))
          .sort((a, b) => b.momentum - a.momentum)
          .slice(0, 6);

        const signalRows = pickerItems.slice(0, 5).map((item) => {
          const score = Number(item?.ai_score || 0);
          return {
            symbol: String(item?.ticker || "").toUpperCase(),
            confidence: Math.max(35, Math.min(97, Math.round(55 + score * 0.4))),
            signal: score >= 80 ? "Strong Buy" : score >= 60 ? "Buy" : score >= 40 ? "Hold" : "Sell",
          };
        });

        if (!alive) return;
        const snapshot = {
          overview: {
            sentiment: String(summaryData?.market_sentiment || "-"),
            sector: String(summaryData?.trending_sector || "-"),
            topPick: String(summaryData?.top_ai_pick || "-"),
            riskLevel: String(summaryData?.risk_outlook || "-"),
          },
          signals: signalRows,
          sectors: rankedSectors,
          rotation: rankedSectors.slice(0, 2).map((item) => item.name),
          summary: String(summaryData?.explanation || ""),
          radar: topSymbols.slice(0, 3),
          trending: [],
        };

        setFromSnapshot(snapshot);
        aiInsightsViewCache.set(cacheKey, { ts: Date.now(), data: snapshot });

        // Fetch trending mini charts in background so overview can render immediately.
        Promise.allSettled(
          topSymbols.map(async (symbol) => {
            const history = await fetchJsonWithRetry(
              [apiUrl(`/api/stock-history?ticker=${symbol}&period=1m`), localFastapiUrl(`/api/stock-history?ticker=${symbol}&period=1m`)],
              1,
              4500
            );
            const points = (Array.isArray(history) ? history : [])
              .slice(-7)
              .map((row) => Number(row?.price ?? row?.close ?? 0))
              .filter((value) => Number.isFinite(value) && value > 0);
            const picker = pickerItems.find((row) => String(row?.ticker || "").toUpperCase() === symbol);
            return {
              symbol,
              momentum: momentumFromReturn(picker?.ret30),
              sentiment: sentimentFromValue(picker?.sentiment),
              aiScore: Math.round(Number(picker?.ai_score || 0)),
              points,
            };
          })
        ).then((rows) => {
          if (!alive) return;
          const trendRows = rows
            .filter((row) => row.status === "fulfilled")
            .map((row) => row.value)
            .filter((row) => row && row.points?.length);
          setTrending(trendRows);
          aiInsightsViewCache.set(cacheKey, {
            ts: Date.now(),
            data: {
              ...snapshot,
              trending: trendRows,
            },
          });
        });
      } catch (e) {
        if (!alive) return;
        setError(e?.message || "Unable to load AI insights");
        setOverview({ sentiment: "-", sector: "-", topPick: "-", riskLevel: "-" });
        setSignals([]);
        setTrending([]);
        setSectors([]);
        setRotation([]);
        setSummary("");
        setRadar([]);
      } finally {
        if (alive) setLoading(false);
      }
    };
    run();
    return () => {
      alive = false;
    };
  }, [watchlist, recentSearches]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className={`${dark ? "text-slate-100" : "text-slate-900"} text-3xl font-bold`}>{t("aiInsightsHub")}</h1>
        <p className="text-slate-500">{t("aiInsightsSubtitle")}</p>
      </div>

      {error ? (
        <div className={`${dark ? "bg-rose-950/30 border-rose-900/50 text-rose-300" : "bg-rose-50 border-rose-200 text-rose-700"} rounded-2xl border p-4 text-sm font-medium`}>
          {error}
        </div>
      ) : null}

      <AIOverviewCards overview={overview} dark={dark} />

      <div className="grid grid-cols-1 xl:grid-cols-[2fr,1fr] gap-5 items-start">
        <div className="space-y-5">
          <AISignals signals={loading ? [] : signals} dark={dark} />
          <TrendingStocks stocks={loading ? [] : trending} dark={dark} />
        </div>

        <div className="space-y-5 xl:sticky xl:top-20">
          <SectorInsights
            sectors={sectors}
            rotation={rotation}
            dark={dark}
          />
          <AIMarketSummary
            summary={summary}
            radar={radar}
            riskAlert={t("marketVolatilityIncreasing")}
            dark={dark}
          />
        </div>
      </div>
    </div>
  );
};

export default function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "light");
  const [watchlist, setWatchlist] = useState(() => {
    try {
      const raw = localStorage.getItem(WATCHLIST_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });
  const [bookmarkedNews, setBookmarkedNews] = useState(() => {
    try {
      const raw = localStorage.getItem(NEWS_BOOKMARK_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });
  const [recentSearches, setRecentSearches] = useState(() => {
    try {
      const raw = localStorage.getItem("ai-invest-recent-searches-v1");
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(watchlist));
  }, [watchlist]);
  useEffect(() => {
    localStorage.setItem(NEWS_BOOKMARK_STORAGE_KEY, JSON.stringify(bookmarkedNews));
  }, [bookmarkedNews]);
  useEffect(() => {
    localStorage.setItem("ai-invest-recent-searches-v1", JSON.stringify(recentSearches));
  }, [recentSearches]);

  const toggleTheme = () => {
    setTheme((prev) => {
      const next = prev === "light" ? "dark" : "light";
      localStorage.setItem("theme", next);
      return next;
    });
  };

  const addWatchSymbol = (symbol) => {
    const safeSymbol = String(symbol || "").trim().toUpperCase();
    if (!/^[A-Z0-9.-]{1,12}$/.test(safeSymbol)) return;
    setWatchlist((prev) => (prev.includes(safeSymbol) ? prev : [...prev, safeSymbol]));
  };

  const toggleWatchSymbol = (symbol) => {
    const safeSymbol = String(symbol || "").trim().toUpperCase();
    if (!safeSymbol) return;
    setWatchlist((prev) => (prev.includes(safeSymbol) ? prev.filter((s) => s !== safeSymbol) : [...prev, safeSymbol]));
  };
  const toggleNewsBookmark = (item) => {
    const id = item.id || item.link || item.title;
    if (!id) return;
    setBookmarkedNews((prev) => {
      const exists = prev.some((x) => x.id === id);
      if (exists) return prev.filter((x) => x.id !== id);
      return [{ ...item, id }, ...prev].slice(0, 100);
    });
  };
  const recordRecentSearch = (symbol) => {
    const s = String(symbol || "").toUpperCase().trim();
    if (!s) return;
    setRecentSearches((prev) => [s, ...prev.filter((x) => x !== s)].slice(0, 10));
  };

  return (
    <AuthProvider>
      <ThemeContext.Provider value={{ theme, toggleTheme }}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/verify" element={<VerifyEmailPage />} />
          <Route element={<PrivateLayout />}>
            <Route path="/dashboard" element={<SearchPage watchlist={watchlist} onToggleWatchlist={toggleWatchSymbol} recentSearches={recentSearches} onRecordSearch={recordRecentSearch} />} />
            <Route path="/search" element={<SearchPage watchlist={watchlist} onToggleWatchlist={toggleWatchSymbol} recentSearches={recentSearches} onRecordSearch={recordRecentSearch} />} />
            <Route path="/stock/:symbol" element={<Stockdetail watchlist={watchlist} onToggleWatchlist={toggleWatchSymbol} />} />
            <Route path="/watchlist" element={<WatchlistPage watchlist={watchlist} onToggleWatchlist={toggleWatchSymbol} onAddWatchSymbol={addWatchSymbol} bookmarkedNews={bookmarkedNews} />} />
            <Route path="/risk" element={<RiskPage />} />
            <Route path="/ai-picker" element={<AIPickerPage />} />
            <Route path="/ai-insights" element={<AIInsightsPage watchlist={watchlist} recentSearches={recentSearches} />} />
            <Route path="/portfolio" element={<PortfolioPage watchlist={watchlist} onAddWatchSymbol={addWatchSymbol} />} />
            <Route path="/news" element={<NewsPage bookmarkedNews={bookmarkedNews} onToggleNewsBookmark={toggleNewsBookmark} />} />
          </Route>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
        <AIAdvisorWidget
          context={{
            watchlist,
            recent_searches: recentSearches,
            portfolio: watchlist.map((s) => ({ symbol: s })),
            sentiment: null,
          }}
          dark={theme === "dark"}
        />
      </ThemeContext.Provider>
    </AuthProvider>
  );
}
