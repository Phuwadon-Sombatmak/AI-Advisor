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
import ReturnIndicator from "./Components/ReturnIndicator";
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

const FASTAPI_BASE = (import.meta.env.VITE_FASTAPI_URL || "/api-fastapi").replace(/\/$/, "");
const FALLBACK_NEWS = [
  {
    title: "ตลาดหุ้นสหรัฐแกว่งตัวจากแรงซื้อหุ้นเทคโนโลยีขนาดใหญ่",
    provider: "Market Watch",
    image: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=400&h=300&fit=crop",
    link: "https://finance.yahoo.com/",
  },
  {
    title: "นักลงทุนจับตาทิศทางดอกเบี้ยและผลประกอบการรายไตรมาส",
    provider: "Financial Times",
    image: "https://images.unsplash.com/photo-1642790551116-18e150f248e5?w=400&h=300&fit=crop",
    link: "https://www.ft.com/markets",
  },
  {
    title: "AI และเซมิคอนดักเตอร์ยังเป็นธีมหลักของตลาดปีนี้",
    provider: "Bloomberg",
    image: "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=400&h=300&fit=crop",
    link: "https://www.bloomberg.com/markets",
  },
];

const STOCK_MINI_DATA = [
  { symbol: "NVDA", price: 177.82, change: 2.31, points: [34, 36, 35, 38, 40, 39, 43] },
  { symbol: "MSFT", price: 428.15, change: 1.12, points: [28, 29, 31, 30, 33, 34, 35] },
  { symbol: "AAPL", price: 199.21, change: -0.64, points: [42, 41, 39, 40, 38, 37, 36] },
  { symbol: "TSLA", price: 219.75, change: 3.94, points: [21, 24, 23, 27, 29, 31, 33] },
];
const WATCHLIST_STORAGE_KEY = "ai-invest-watchlist-v1";
const NEWS_BOOKMARK_STORAGE_KEY = "ai-invest-news-bookmarks-v1";
const WATCHLIST_META = {
  NVDA: { company: "NVIDIA Corporation", sector: "Semiconductors", aiScore: 92, sentiment: "Bullish" },
  MSFT: { company: "Microsoft Corporation", sector: "Software", aiScore: 89, sentiment: "Bullish" },
  AAPL: { company: "Apple Inc.", sector: "Consumer Tech", aiScore: 84, sentiment: "Neutral" },
  TSLA: { company: "Tesla, Inc.", sector: "EV & Mobility", aiScore: 78, sentiment: "Bearish" },
  AMZN: { company: "Amazon.com, Inc.", sector: "E-Commerce", aiScore: 86, sentiment: "Bullish" },
  AMD: { company: "Advanced Micro Devices", sector: "Semiconductors", aiScore: 83, sentiment: "Bullish" },
  META: { company: "Meta Platforms, Inc.", sector: "Internet", aiScore: 81, sentiment: "Neutral" },
  GOOGL: { company: "Alphabet Inc.", sector: "Internet", aiScore: 82, sentiment: "Bullish" },
};

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

async function fetchJsonWithRetry(paths, retries = 2, timeoutMs = 8000, init = undefined) {
  let lastError = null;
  for (let i = 0; i < retries; i += 1) {
    for (const path of paths) {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);
        const res = await fetch(path, { ...(init || {}), signal: controller.signal });
        clearTimeout(timer);
        if (!res.ok) {
          lastError = new Error(`HTTP ${res.status}`);
          continue;
        }
        return await res.json();
      } catch (e) {
        lastError = e;
      }
    }
    await sleep(500 * (i + 1));
  }
  throw lastError || new Error("fetch failed");
}

function getWatchMeta(symbol) {
  const key = String(symbol || "").toUpperCase();
  const base = WATCHLIST_META[key] || {};
  return {
    symbol: key,
    company: base.company || `${key} Inc.`,
    sector: base.sector || "General",
    aiScore: base.aiScore || 75,
    sentiment: base.sentiment || "Neutral",
  };
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
  const [dailyNews, setDailyNews] = useState([]);
  const [summaryOpen, setSummaryOpen] = useState(false);

  const stocksList = [
    { name: "NVIDIA Corporation", symbol: "NVDA" },
    { name: "Microsoft Corporation", symbol: "MSFT" },
    { name: "Apple Inc.", symbol: "AAPL" },
    { name: "Tesla, Inc.", symbol: "TSLA" },
    { name: "Amazon.com, Inc.", symbol: "AMZN" },
  ];

  useEffect(() => {
    const fetchNews = async () => {
      setNewsLoading(true);
      try {
        const data = await fetchJsonWithRetry(
          [
            apiUrl("/news?symbols=NVDA,MSFT,AAPL&days_back=7"),
            "http://localhost:8000/news?symbols=NVDA,MSFT,AAPL&days_back=7",
          ],
          5
        );
        const merged = (Array.isArray(data) ? data : [])
          .flatMap((item) => item.news || [])
          .slice(0, 6);
        setDailyNews(merged.length > 0 ? merged : FALLBACK_NEWS);
      } catch {
        setDailyNews(FALLBACK_NEWS);
      } finally {
        setNewsLoading(false);
      }
    };

    fetchNews();
  }, []);

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
        suggestions={stocksList.map((s) => s.symbol)}
        onPick={(symbol) => {
          onRecordSearch(symbol);
          navigate(`/stock/${symbol}`);
        }}
      />

      <MarketSentiment dark={theme === "dark"} />

      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {STOCK_MINI_DATA.map((s) => {
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
        })}
      </section>

      <AIInsightCard symbol="NVDA" action="Buy" confidence={78} risk="Medium" dark={theme === "dark"} />

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
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {dailyNews.map((news, i) => <NewsCard key={i} news={news} dark={theme === "dark"} />)}
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
          sentiment: 50,
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
      setNewsItems([]);
      setNewsLoading(false);
      try {
        const rawSymbol = String(symbol || "").trim().toUpperCase();
        const safeSymbol = /^[A-Z0-9.-]{1,12}$/.test(rawSymbol) ? rawSymbol : "NVDA";
        const [stockJson, quoteJson] = await Promise.all([
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

        const first = Number(history[0]?.close || 0);
        const quoteLatest = Number(quoteJson?.latest_price || quoteJson?.price || 0);
        const historyLatest = Number(history[history.length - 1]?.close || 0);
        const latest = quoteLatest > 0 ? quoteLatest : historyLatest;
        const previousClose = Number(quoteJson?.previous_close || 0);
        const baseline = previousClose > 0 ? previousClose : first;
        const dailyChangePct = baseline ? ((latest - baseline) / baseline) * 100 : 0;
        const returnPct = range === "1d"
          ? dailyChangePct
          : (first ? ((latest - first) / first) * 100 : 0);

        // Keep chart endpoint consistent with displayed latest quote to avoid visible mismatch/jitter.
        if (quoteLatest > 0 && history.length) {
          const lastIdx = history.length - 1;
          history[lastIdx] = { ...history[lastIdx], close: quoteLatest };
        }

        if (!alive) return;
        setStockData({
          symbol: safeSymbol,
          latest_price: latest,
          daily_change_pct: dailyChangePct,
          return_pct: returnPct,
          history,
        });

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
          <ReturnIndicator
            symbol={stockData.symbol}
            currentPrice={stockData.latest_price}
            dailyChangePct={stockData.daily_change_pct}
            returnPct={stockData.return_pct}
            language={i18n.language}
            dark={theme === "dark"}
          />
        </div>
      </div>

      <div className={`${theme === "dark" ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-100"} p-6 rounded-3xl border shadow-sm space-y-4`}>
        <TimeRangeSelector range={range} onChange={setRange} dark={theme === "dark"} />
        <StockChart data={chartSeries} returnPct={stockData.return_pct} dark={theme === "dark"} />
      </div>

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

const AI_PICKER_UNIVERSE = [
  { ticker: "NVDA", company: "NVIDIA Corporation", risk: "MEDIUM", strategy: "AI Trend", sentiment: "Bullish", momentum: "Strong", aiScore: 92, confidence: 88 },
  { ticker: "MSFT", company: "Microsoft Corporation", risk: "LOW", strategy: "Growth", sentiment: "Bullish", momentum: "Strong", aiScore: 89, confidence: 86 },
  { ticker: "AAPL", company: "Apple Inc.", risk: "LOW", strategy: "Value", sentiment: "Neutral", momentum: "Moderate", aiScore: 80, confidence: 78 },
  { ticker: "TSLA", company: "Tesla Inc.", risk: "HIGH", strategy: "Momentum", sentiment: "Bearish", momentum: "Strong", aiScore: 75, confidence: 71 },
  { ticker: "AMZN", company: "Amazon.com Inc.", risk: "MEDIUM", strategy: "Growth", sentiment: "Bullish", momentum: "Strong", aiScore: 87, confidence: 84 },
  { ticker: "AMD", company: "Advanced Micro Devices", risk: "HIGH", strategy: "AI Trend", sentiment: "Bullish", momentum: "Strong", aiScore: 85, confidence: 80 },
  { ticker: "META", company: "Meta Platforms", risk: "MEDIUM", strategy: "Momentum", sentiment: "Neutral", momentum: "Strong", aiScore: 83, confidence: 79 },
  { ticker: "GOOGL", company: "Alphabet Inc.", risk: "LOW", strategy: "Value", sentiment: "Bullish", momentum: "Moderate", aiScore: 82, confidence: 81 },
  { ticker: "PLTR", company: "Palantir Technologies", risk: "HIGH", strategy: "AI Trend", sentiment: "Bullish", momentum: "Strong", aiScore: 88, confidence: 85 },
];

const AIPickerPage = () => {
  const { t } = useTranslation();
  const { theme } = useContext(ThemeContext);
  const dark = theme === "dark";
  const [risk, setRisk] = useState("MEDIUM");
  const [strategy, setStrategy] = useState("AI Trend");
  const [sentiment, setSentiment] = useState("Bullish");
  const [loading, setLoading] = useState(false);
  const [seed, setSeed] = useState(0);

  const picks = useMemo(() => {
    const byFilter = AI_PICKER_UNIVERSE.filter(
      (s) => s.risk === risk && s.strategy === strategy && s.sentiment === sentiment
    );
    const fallback = AI_PICKER_UNIVERSE.filter((s) => s.risk === risk);
    const selected = byFilter.length > 0 ? byFilter : fallback;
    return [...selected].sort((a, b) => b.aiScore - a.aiScore).slice(0, 9);
  }, [risk, strategy, sentiment, seed]);

  const topPicks = useMemo(() => [...picks].sort((a, b) => b.aiScore - a.aiScore).slice(0, 3), [picks]);

  const insight = useMemo(() => {
    const sectorBias = strategy === "AI Trend" ? "AI infrastructure and semiconductor names" : `${strategy.toLowerCase()} opportunities`;
    return `AI detected ${sentiment.toLowerCase()} sentiment with ${risk.toLowerCase()} risk preference. Current picks emphasize ${sectorBias} with improving momentum signals and relative strength versus market baseline.`;
  }, [risk, strategy, sentiment]);

  const onGenerate = async () => {
    setLoading(true);
    await sleep(450);
    setSeed((x) => x + 1);
    setLoading(false);
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
          const meta = getWatchMeta(safeSymbol);
          try {
            const stockJson = await fetchJsonWithRetry(
              [
                apiUrl(`/stock/${safeSymbol}?range=1m`),
                `http://localhost:8000/stock/${safeSymbol}?range=1m`,
              ],
              4
            );
            const history = stockJson.history || [];
            const latest = Number(history[history.length - 1]?.close || stockJson.price || 0);
            const prev = Number(history[history.length - 2]?.close || latest || 0);
            const change = prev ? ((latest - prev) / prev) * 100 : 0;
            const points = history.slice(-7).map((h) => Number(h.close || 0)).filter((x) => Number.isFinite(x) && x > 0);
            const volume = Number(history[history.length - 1]?.volume || stockJson.volume || 0);

            return {
              ...meta,
              price: latest,
              change,
              volume,
              points: points.length ? points : [10, 12, 11, 13, 14, 15, 16],
              sentiment: sentimentFromChange(change),
            };
          } catch {
            const fallback = STOCK_MINI_DATA.find((x) => x.symbol === safeSymbol);
            return {
              ...meta,
              price: Number(fallback?.price || 0),
              change: Number(fallback?.change || 0),
              volume: 0,
              points: fallback?.points || [10, 11, 10, 12, 13, 12, 14],
            };
          }
        })
      );

      if (!alive) return;
      setRows(nextRows.sort((a, b) => b.aiScore - a.aiScore));
      setLoading(false);
    };

    run();
    return () => {
      alive = false;
    };
  }, [watchlist]);

  const groupedBySector = useMemo(() => {
    const groups = rows.reduce((acc, item) => {
      if (!acc[item.sector]) acc[item.sector] = [];
      acc[item.sector].push(item);
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

const AIInsightsPage = () => {
  const { t } = useTranslation();
  const { theme } = useContext(ThemeContext);
  const dark = theme === "dark";

  const overview = {
    sentiment: "Greed",
    sector: "Semiconductors",
    topPick: "NVDA",
    riskLevel: "Medium",
  };

  const signals = [
    { symbol: "NVDA", signal: "Strong Buy", confidence: 86 },
    { symbol: "AMD", signal: "Buy", confidence: 78 },
    { symbol: "TSM", signal: "Hold", confidence: 65 },
    { symbol: "INTC", signal: "Sell", confidence: 58 },
  ];

  const trending = [
    { symbol: "NVDA", momentum: "Strong", sentiment: "Bullish", aiScore: 92, points: [22, 24, 25, 27, 29, 31, 34] },
    { symbol: "TSM", momentum: "Rising", sentiment: "Neutral", aiScore: 84, points: [20, 21, 21.5, 22, 23, 23.5, 24] },
    { symbol: "AVGO", momentum: "Strong", sentiment: "Bullish", aiScore: 88, points: [18, 19, 20, 21, 22, 23, 24] },
    { symbol: "MSFT", momentum: "Rising", sentiment: "Bullish", aiScore: 87, points: [25, 25.5, 26, 26.7, 27.1, 27.8, 28.4] },
  ];

  const sectors = [
    { name: "Technology", momentum: 78 },
    { name: "Semiconductors", momentum: 85 },
    { name: "Energy", momentum: 46 },
    { name: "Finance", momentum: 52 },
  ];

  const summary =
    "AI analysis shows strong momentum in semiconductor stocks driven by rising demand for AI infrastructure. Risk remains moderate while sector leadership continues to rotate toward compute and data-center suppliers.";

  return (
    <div className="space-y-6">
      <div>
        <h1 className={`${dark ? "text-slate-100" : "text-slate-900"} text-3xl font-bold`}>{t("aiInsightsHub")}</h1>
        <p className="text-slate-500">{t("aiInsightsSubtitle")}</p>
      </div>

      <AIOverviewCards overview={overview} dark={dark} />

      <div className="grid grid-cols-1 xl:grid-cols-[2fr,1fr] gap-5 items-start">
        <div className="space-y-5">
          <AISignals signals={signals} dark={dark} />
          <TrendingStocks stocks={trending} dark={dark} />
        </div>

        <div className="space-y-5 xl:sticky xl:top-20">
          <SectorInsights
            sectors={sectors}
            rotation={["Semiconductors", "AI Infrastructure"]}
            dark={dark}
          />
          <AIMarketSummary
            summary={summary}
            radar={["NVDA", "TSM", "AVGO"]}
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
            <Route path="/search" element={<SearchPage watchlist={watchlist} onToggleWatchlist={toggleWatchSymbol} recentSearches={recentSearches} onRecordSearch={recordRecentSearch} />} />
            <Route path="/stock/:symbol" element={<Stockdetail watchlist={watchlist} onToggleWatchlist={toggleWatchSymbol} />} />
            <Route path="/watchlist" element={<WatchlistPage watchlist={watchlist} onToggleWatchlist={toggleWatchSymbol} onAddWatchSymbol={addWatchSymbol} bookmarkedNews={bookmarkedNews} />} />
            <Route path="/risk" element={<RiskPage />} />
            <Route path="/ai-picker" element={<AIPickerPage />} />
            <Route path="/ai-insights" element={<AIInsightsPage />} />
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
            sentiment: 50,
          }}
          dark={theme === "dark"}
        />
      </ThemeContext.Provider>
    </AuthProvider>
  );
}
