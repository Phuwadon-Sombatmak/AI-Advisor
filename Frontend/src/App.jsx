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
const ENABLE_DIRECT_BACKEND_FALLBACK = String(import.meta.env.VITE_ENABLE_DIRECT_BACKEND_FALLBACK || "").toLowerCase() === "true";
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
const GET_REQUEST_CACHE_TTL_MS = 60000;
const getRequestCache = new Map();
const inFlightGetRequests = new Map();
const SYMBOL_ALIASES = {
  MICROSOFT: "MSFT",
  MICROSOFTCORPORATION: "MSFT",
  MICRSOFT: "MSFT",
  MICORSOFT: "MSFT",
  APPLE: "AAPL",
  APPLEINC: "AAPL",
  APPL: "AAPL",
  AAPL: "AAPL",
  NVIDIA: "NVDA",
  NVDIA: "NVDA",
  NVIDIACORPORATION: "NVDA",
  NVDA: "NVDA",
  AMAZON: "AMZN",
  AMAZONCOM: "AMZN",
  AMAZONCOMINC: "AMZN",
  AMAZN: "AMZN",
  ALPHABET: "GOOGL",
  ALPHABETINC: "GOOGL",
  GOOGLE: "GOOGL",
  GOOGLEINC: "GOOGL",
  META: "META",
  METAPLATFORMS: "META",
  METAPLATFORMSINC: "META",
  TESLA: "TSLA",
  TESLAINC: "TSLA",
  TESAL: "TSLA",
  TSAL: "TSLA",
  BERKSHIREHATHAWAY: "BRK.A",
  BERKSHIREHATHAWAYINC: "BRK.A",
  UNITEDHEALTH: "UNH",
  UNITEDHEALTHGROUP: "UNH",
  UNITEDHEALTHGROUPINC: "UNH",
};

const COMMON_SYMBOLS = new Set([
  "AAPL", "AMD", "AMZN", "AVGO", "BRK.A", "BRK.B", "COIN", "DIA", "GLD",
  "GOOG", "GOOGL", "INTC", "IWM", "META", "MSFT", "MSTR", "MARA", "NFLX",
  "NVDA", "PLTR", "QQQ", "RIOT", "SPY", "TSLA", "TSM", "UNH", "XLB", "XLE",
  "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
]);

function boundedLevenshtein(a = "", b = "", maxDistance = 1) {
  if (a === b) return 0;
  if (Math.abs(a.length - b.length) > maxDistance) return maxDistance + 1;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i += 1) {
    const curr = [i];
    let rowMin = curr[0];
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost);
      rowMin = Math.min(rowMin, curr[j]);
    }
    if (rowMin > maxDistance) return maxDistance + 1;
    prev = curr;
  }
  return prev[b.length];
}

function isSingleTransposition(a = "", b = "") {
  if (a.length !== b.length) return false;
  const diffs = [];
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) diffs.push(i);
  }
  if (diffs.length !== 2) return false;
  const [i, j] = diffs;
  return j === i + 1 && a[i] === b[j] && a[j] === b[i];
}

function fuzzySymbolMatch(raw = "") {
  if (!raw || !/^[A-Z]{3,8}$/.test(raw)) return raw;
  if (COMMON_SYMBOLS.has(raw)) return raw;
  const candidates = [];
  for (const symbol of COMMON_SYMBOLS) {
    const token = symbol.replace(/[.-]/g, "");
    if (Math.abs(raw.length - token.length) > 1) continue;
    if (isSingleTransposition(raw, token) || boundedLevenshtein(raw, token, 1) <= 1) {
      candidates.push(symbol);
    }
  }
  return candidates.length === 1 ? candidates[0] : raw;
}

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
  if (!ENABLE_DIRECT_BACKEND_FALLBACK) return "";
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
  const method = String(init?.method || "GET").toUpperCase();
  const usablePaths = (paths || []).filter((p) => {
    const path = String(p || "");
    if (!path) return false;
    if (typeof window === "undefined") return true;
    if (!/^https?:\/\//i.test(path)) return true;
    try {
      const u = new URL(path);
      // Skip cross-origin URLs in browser to prevent access-control failures.
      if (u.origin === window.location.origin) return true;
      return false;
    } catch {
      return false;
    }
  });

  if (!usablePaths.length) {
    throw new Error("No same-origin API path available");
  }

  const isCacheableGet =
    method === "GET" &&
    (!init || Object.keys(init).every((key) => ["method", "headers"].includes(key))) &&
    usablePaths.length > 0;
  const cacheKey = isCacheableGet ? usablePaths[0] : null;
  if (cacheKey) {
    const cached = getRequestCache.get(cacheKey);
    if (cached && (Date.now() - cached.ts) < GET_REQUEST_CACHE_TTL_MS) {
      return cached.data;
    }
    const inFlight = inFlightGetRequests.get(cacheKey);
    if (inFlight) {
      return inFlight;
    }
  }

  const runner = (async () => {
    for (let i = 0; i < retries; i += 1) {
      for (const path of usablePaths) {
        let timer = null;
        try {
          const controller = new AbortController();
          timer = setTimeout(() => controller.abort(), timeoutMs);
          const res = await fetch(path, { ...(init || {}), method, signal: controller.signal });
          if (!res.ok) {
            lastError = new Error(`HTTP ${res.status}`);
            continue;
          }
          const data = await res.json();
          if (cacheKey) {
            getRequestCache.set(cacheKey, { ts: Date.now(), data });
          }
          return data;
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
  })();

  if (cacheKey) {
    inFlightGetRequests.set(cacheKey, runner);
  }
  try {
    return await runner;
  } finally {
    if (cacheKey) {
      inFlightGetRequests.delete(cacheKey);
    }
  }
}

const isFiniteNumber = (value) => {
  if (value === null || value === undefined) return false;
  if (typeof value === "string" && value.trim() === "") return false;
  return Number.isFinite(Number(value));
};

const clampValue = (value, min = 0, max = 100) => {
  if (!isFiniteNumber(value)) return null;
  return Math.max(min, Math.min(max, Number(value)));
};

const averageDefined = (values = []) => {
  const filtered = values.filter((value) => isFiniteNumber(value));
  if (!filtered.length) return null;
  return filtered.reduce((sum, value) => sum + Number(value), 0) / filtered.length;
};

const scoreLinear = (value, min, max) => {
  if (!isFiniteNumber(value) || max <= min) return null;
  const normalized = ((Number(value) - min) / (max - min)) * 100;
  return clampValue(normalized);
};

const computeEmaSeries = (values = [], period = 12) => {
  const prices = values.map((value) => Number(value)).filter((value) => Number.isFinite(value) && value > 0);
  if (!prices.length) return [];
  const multiplier = 2 / (period + 1);
  const ema = [prices[0]];
  for (let index = 1; index < prices.length; index += 1) {
    ema.push((prices[index] * multiplier) + (ema[index - 1] * (1 - multiplier)));
  }
  return ema;
};

const computeRsiValue = (values = [], period = 14) => {
  const prices = values.map((value) => Number(value)).filter((value) => Number.isFinite(value) && value > 0);
  if (prices.length <= period) return null;
  let gains = 0;
  let losses = 0;
  for (let index = 1; index <= period; index += 1) {
    const delta = prices[index] - prices[index - 1];
    if (delta >= 0) gains += delta;
    else losses += Math.abs(delta);
  }
  let avgGain = gains / period;
  let avgLoss = losses / period;
  for (let index = period + 1; index < prices.length; index += 1) {
    const delta = prices[index] - prices[index - 1];
    const gain = Math.max(delta, 0);
    const loss = Math.max(-delta, 0);
    avgGain = ((avgGain * (period - 1)) + gain) / period;
    avgLoss = ((avgLoss * (period - 1)) + loss) / period;
  }
  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return 100 - (100 / (1 + rs));
};

const sentimentFromArticle = (item) => {
  if (!item || typeof item !== "object") return null;
  const score = Number(item.sentiment_score ?? item.sentimentScore);
  if (Number.isFinite(score)) return score;
  const text = String(item.sentiment || "").toLowerCase();
  if (text.includes("bull") || text.includes("positive")) return 0.55;
  if (text.includes("bear") || text.includes("negative")) return -0.55;
  if (text.includes("neutral")) return 0;
  return null;
};

const sentimentLabelFromScore = (score) => {
  if (!isFiniteNumber(score)) return "N/A";
  if (Number(score) > 0.2) return "Bullish";
  if (Number(score) < -0.2) return "Bearish";
  return "Neutral";
};

const deriveDashboardHighlight = (card) => {
  if (!card || !isFiniteNumber(card.price) || Number(card.price) <= 0) return null;
  const points = Array.isArray(card.points) ? card.points.filter((value) => isFiniteNumber(value) && Number(value) > 0) : [];
  const first = points[0];
  const last = points[points.length - 1];
  const rangeReturn = isFiniteNumber(first) && isFiniteNumber(last) && Number(first) > 0 ? ((Number(last) - Number(first)) / Number(first)) * 100 : null;
  const changePct = isFiniteNumber(card.change) ? Number(card.change) : null;
  const signal = averageDefined([
    isFiniteNumber(changePct) ? 50 + changePct * 6 : null,
    isFiniteNumber(rangeReturn) ? 50 + rangeReturn * 4 : null,
  ]);
  const normalizedSignal = isFiniteNumber(signal) ? Math.max(0, Math.min(100, Number(signal))) : null;

  let action = null;
  if (isFiniteNumber(normalizedSignal)) {
    if (normalizedSignal >= 62) action = "Buy";
    else if (normalizedSignal >= 45) action = "Hold";
    else if (normalizedSignal >= 28) action = "Sell";
    else action = "Strong Sell";
  }

  let risk = null;
  if (points.length >= 3) {
    const moves = [];
    for (let index = 1; index < points.length; index += 1) {
      const prev = Number(points[index - 1]);
      const curr = Number(points[index]);
      if (prev > 0 && Number.isFinite(curr)) moves.push(Math.abs((curr - prev) / prev));
    }
    const avgMove = averageDefined(moves);
    if (isFiniteNumber(avgMove)) {
      if (avgMove >= 0.03) risk = "High";
      else if (avgMove <= 0.012) risk = "Low";
      else risk = "Medium";
    }
  }

  return {
    symbol: card.symbol,
    action,
    confidence: isFiniteNumber(normalizedSignal) ? Math.round(Number(normalizedSignal)) : null,
    risk,
    available: Boolean(action),
  };
};

const isUnavailableText = (value) => {
  if (typeof value !== "string") return false;
  const normalized = value.trim().toLowerCase();
  return normalized === "n/a" || normalized === "relevant data is not available.";
};

const hasUsableRecommendationData = (reco) => {
  if (!reco || typeof reco !== "object") return false;

  if (typeof reco.available === "boolean" && reco.available === false) {
    return false;
  }

  if (typeof reco.recommendation === "string" && reco.recommendation.trim() && !isUnavailableText(reco.recommendation)) {
    return true;
  }

  if ([reco.confidence, reco.ai_score, reco.sentiment_avg, reco.upside_pct].some((value) => isFiniteNumber(value))) {
    return true;
  }

  const signals = reco.signals || {};
  if (["technical_score", "news_sentiment_score", "momentum_score", "volatility_risk_score", "forecast_30d_pct"].some((key) => isFiniteNumber(signals[key]))) {
    return true;
  }

  const technical = reco.technical_indicators || {};
  if (["rsi", "macd", "macd_signal", "ma50", "ma200"].some((key) => isFiniteNumber(technical[key]))) {
    return true;
  }

  const newsDist = reco.news_sentiment_distribution || {};
  if (["bullish", "neutral", "bearish"].some((key) => isFiniteNumber(newsDist[key]))) {
    return true;
  }

  return false;
};

const mergeDefined = (base, override) => {
  if (Array.isArray(base) || Array.isArray(override)) {
    return Array.isArray(override) && override.length ? override : base;
  }
  if (base && typeof base === "object" && override && typeof override === "object") {
    const merged = { ...base };
    Object.entries(override).forEach(([key, value]) => {
      if (value === undefined || value === null) return;
      merged[key] = mergeDefined(base?.[key], value);
    });
    return merged;
  }
  return override !== undefined && override !== null ? override : base;
};

const buildDerivedRecommendation = ({ symbol, latestPrice, history = [], news = [], details = null }) => {
  const normalizedHistory = (Array.isArray(history) ? history : [])
    .map((row) => ({
      date: String(row?.date || ""),
      close: Number(row?.close ?? row?.price ?? 0),
      volume: Number(row?.volume ?? 0),
    }))
    .filter((row) => row.date && Number.isFinite(row.close) && row.close > 0)
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));

  const closes = normalizedHistory.map((row) => row.close);
  const currentPrice = Number(latestPrice || closes[closes.length - 1] || 0);
  if (!(currentPrice > 0)) return null;

  const averageWindow = (window) => {
    if (closes.length < window) return null;
    const slice = closes.slice(-window);
    return slice.reduce((sum, value) => sum + value, 0) / window;
  };

  const ma50 = averageWindow(50);
  const ma200 = averageWindow(200);
  const rsi = computeRsiValue(closes, 14);
  const ema12 = computeEmaSeries(closes, 12);
  const ema26 = computeEmaSeries(closes, 26);
  const macdSeries = closes.map((_, index) => {
    const fast = ema12[index];
    const slow = ema26[index];
    return Number.isFinite(fast) && Number.isFinite(slow) ? fast - slow : null;
  }).filter((value) => Number.isFinite(value));
  const macdSignalSeries = computeEmaSeries(macdSeries, 9);
  const macd = macdSeries.length ? macdSeries[macdSeries.length - 1] : null;
  const macdSignal = macdSignalSeries.length ? macdSignalSeries[macdSignalSeries.length - 1] : null;

  const priceVsMa50Score = ma50 ? (currentPrice > ma50 ? 72 : 34) : null;
  const maCrossScore = ma50 && ma200 ? (ma50 > ma200 ? 82 : 28) : null;
  const macdScore = isFiniteNumber(macd) && isFiniteNumber(macdSignal) ? (Number(macd) >= Number(macdSignal) ? 74 : 33) : null;
  const rsiScore = isFiniteNumber(rsi) ? clampValue(100 - Math.abs(Number(rsi) - 55) * 1.8) : null;
  const technicalScore = averageDefined([priceVsMa50Score, maCrossScore, macdScore, rsiScore]);

  const returnForWindow = (days) => {
    if (closes.length < 2) return null;
    const startIndex = Math.max(0, closes.length - Math.min(closes.length, days));
    const startPrice = closes[startIndex];
    if (!(startPrice > 0)) return null;
    return ((currentPrice - startPrice) / startPrice) * 100;
  };

  const momentum30 = returnForWindow(30);
  const momentum90 = returnForWindow(90);
  const momentumBlend = averageDefined([
    isFiniteNumber(momentum30) ? Number(momentum30) * 0.6 : null,
    isFiniteNumber(momentum90) ? Number(momentum90) * 0.4 : null,
  ]);
  const momentumScore = scoreLinear(momentumBlend, -20, 35);

  const dailyReturns = closes.slice(1).map((close, index) => {
    const previous = closes[index];
    if (!(previous > 0)) return null;
    return (close - previous) / previous;
  }).filter((value) => Number.isFinite(value));
  const volatility = dailyReturns.length
    ? Math.sqrt(dailyReturns.reduce((sum, value) => sum + (value ** 2), 0) / dailyReturns.length) * Math.sqrt(252)
    : null;

  const articleScores = (Array.isArray(news) ? news : [])
    .map((item) => sentimentFromArticle(item))
    .filter((value) => Number.isFinite(value));
  const sentimentAvg = averageDefined(articleScores);
  const newsSentimentScore = scoreLinear(sentimentAvg, -1, 1);
  const newsCount = articleScores.length;
  const bullishCount = articleScores.filter((value) => value > 0.2).length;
  const bearishCount = articleScores.filter((value) => value < -0.2).length;
  const neutralCount = Math.max(newsCount - bullishCount - bearishCount, 0);
  const distribution = newsCount
    ? {
        bullish: (bullishCount / newsCount) * 100,
        neutral: (neutralCount / newsCount) * 100,
        bearish: (bearishCount / newsCount) * 100,
      }
    : {};

  const weighted = [
    ["technical", technicalScore, 0.45],
    ["news_sentiment", newsSentimentScore, 0.25],
    ["momentum", momentumScore, 0.20],
    ["volatility_risk", isFiniteNumber(volatility) ? scoreLinear(0.55 - Number(volatility), -0.15, 0.45) : null, 0.10],
  ].filter(([, score]) => score !== null);

  const totalWeight = weighted.reduce((sum, [, , weight]) => sum + weight, 0);
  const aiScore = totalWeight
    ? weighted.reduce((sum, [, score, weight]) => sum + (Number(score) * weight), 0) / totalWeight
    : null;

  const normalizedForecastSignal = averageDefined([
    isFiniteNumber(momentum30) ? Number(momentum30) : null,
    isFiniteNumber(momentum90) ? Number(momentum90) * 0.7 : null,
    isFiniteNumber(technicalScore) ? ((Number(technicalScore) - 50) / 100) * 0.12 : null,
    isFiniteNumber(sentimentAvg) ? Number(sentimentAvg) * 0.08 : null,
    isFiniteNumber(volatility) ? -Math.min(Number(volatility), 0.12) * 0.35 : null,
  ]);
  const predictedReturnPct = isFiniteNumber(normalizedForecastSignal)
    ? Number(clampValue(Number(normalizedForecastSignal) * 100, -25, 25)?.toFixed(2))
    : null;

  const analystTarget = [
    details?.targetPrice,
    details?.target_price,
    details?.targetMeanPrice,
  ]
    .map((value) => Number(value))
    .find((value) => Number.isFinite(value) && value > 0) ?? null;

  const modelTargetMean = isFiniteNumber(predictedReturnPct)
    ? currentPrice * (1 + (Number(predictedReturnPct) / 100))
    : null;
  const targetMean = analystTarget ?? modelTargetMean;
  const bandPct = isFiniteNumber(volatility)
    ? Math.max(4, Math.min(18, Number(volatility) * Math.sqrt(30) * 100 * 1.35))
    : (isFiniteNumber(predictedReturnPct) ? 8 : null);
  const targetLow = targetMean && bandPct != null ? targetMean * (1 - (bandPct / 100)) : null;
  const targetHigh = targetMean && bandPct != null ? targetMean * (1 + (bandPct / 100)) : null;
  const upsidePct = targetMean && currentPrice > 0 ? ((targetMean - currentPrice) / currentPrice) * 100 : null;
  const forecastPoints = isFiniteNumber(predictedReturnPct)
    ? Array.from({ length: 6 }, (_, index) => {
        const step = (index + 1) / 6;
        const projectedPrice = currentPrice * (1 + ((Number(predictedReturnPct) / 100) * step));
        return {
          step: index + 1,
          price: Number(projectedPrice.toFixed(2)),
        };
      })
    : [];

  const baseAiScore = isFiniteNumber(aiScore) ? Number(aiScore) : null;
  const confidence = baseAiScore != null ? clampValue(baseAiScore / 100, 0, 0.95) : null;
  const riskLevel = !isFiniteNumber(volatility)
    ? "N/A"
    : Number(volatility) >= 0.42
      ? "High"
      : Number(volatility) >= 0.24
        ? "Medium"
        : "Low";

  const technicalBullish = isFiniteNumber(technicalScore)
    && Number(technicalScore) >= 60
    && isFiniteNumber(macd)
    && isFiniteNumber(macdSignal)
    && Number(macd) > Number(macdSignal)
    && isFiniteNumber(ma50)
    && isFiniteNumber(ma200)
    && Number(ma50) > Number(ma200);
  const technicalBearish = isFiniteNumber(technicalScore)
    && Number(technicalScore) <= 40
    && isFiniteNumber(macd)
    && isFiniteNumber(macdSignal)
    && Number(macd) < Number(macdSignal)
    && isFiniteNumber(ma50)
    && isFiniteNumber(ma200)
    && Number(ma50) < Number(ma200);

  const technicalStrong = isFiniteNumber(technicalScore) && Number(technicalScore) > 65;
  const technicalWeak = isFiniteNumber(technicalScore) && Number(technicalScore) < 40;
  const technicalVeryBearish = isFiniteNumber(technicalScore) && Number(technicalScore) < 30;
  const valuationPositive = isFiniteNumber(upsidePct) && Number(upsidePct) > 15;
  const momentumPositive = isFiniteNumber(momentumScore) && Number(momentumScore) > 60;
  const momentumVeryNegative = isFiniteNumber(momentumScore) && Number(momentumScore) < 30;
  const forecastPositive = isFiniteNumber(predictedReturnPct) && Number(predictedReturnPct) > 0;
  const forecastNegative = isFiniteNumber(predictedReturnPct) && Number(predictedReturnPct) < 0;
  const forecastVeryNegative = isFiniteNumber(predictedReturnPct) && Number(predictedReturnPct) < -20;
  const sentimentBearish = isFiniteNumber(newsSentimentScore) && Number(newsSentimentScore) <= 40;
  const bullishSignalCount = [
    isFiniteNumber(upsidePct) && Number(upsidePct) > 15,
    isFiniteNumber(technicalScore) && Number(technicalScore) >= 55,
    isFiniteNumber(momentumScore) && Number(momentumScore) >= 50,
    isFiniteNumber(predictedReturnPct) && Number(predictedReturnPct) > 0,
    isFiniteNumber(newsSentimentScore) && Number(newsSentimentScore) >= 55,
  ].filter(Boolean).length;
  const bearishSignalCount = [
    isFiniteNumber(upsidePct) && Number(upsidePct) < 15,
    isFiniteNumber(technicalScore) && Number(technicalScore) < 45,
    isFiniteNumber(momentumScore) && Number(momentumScore) < 45,
    isFiniteNumber(predictedReturnPct) && Number(predictedReturnPct) < 0,
    isFiniteNumber(newsSentimentScore) && Number(newsSentimentScore) <= 45,
  ].filter(Boolean).length;

  let recommendationDriver = baseAiScore;
  let recommendation = "N/A";
  if (recommendationDriver != null) {
    const holdLabel = bearishSignalCount > bullishSignalCount
      ? "Hold (Bearish Bias)"
      : bullishSignalCount > bearishSignalCount
        ? "Hold (Bullish Bias)"
        : "Hold";
    if (
      isFiniteNumber(upsidePct)
      && Number(upsidePct) > 30
      && technicalStrong
      && technicalBullish
      && isFiniteNumber(momentumScore)
      && Number(momentumScore) > 60
      && isFiniteNumber(predictedReturnPct)
      && Number(predictedReturnPct) > 0
    ) {
      recommendation = "Strong Buy";
    } else if (
      isFiniteNumber(upsidePct)
      && Number(upsidePct) >= 15
      && Number(upsidePct) <= 30
      && !technicalBearish
      && !forecastVeryNegative
    ) {
      recommendation = "Buy";
    } else if (
      isFiniteNumber(predictedReturnPct)
      && Number(predictedReturnPct) < -20
      && technicalVeryBearish
      && technicalBearish
      && momentumVeryNegative
      && sentimentBearish
      && !(isFiniteNumber(upsidePct) && Number(upsidePct) > 25)
    ) {
      recommendation = "Strong Sell";
    } else if (
      isFiniteNumber(upsidePct)
      && Number(upsidePct) > 25
      && technicalBearish
      && forecastNegative
    ) {
      recommendation = holdLabel;
    } else if (
      isFiniteNumber(upsidePct)
      && Number(upsidePct) < 15
      && technicalWeak
      && forecastNegative
      && !(isFiniteNumber(upsidePct) && Number(upsidePct) > 25)
    ) {
      recommendation = "Sell";
    } else if (
      technicalBearish
      && technicalVeryBearish
      && momentumVeryNegative
      && forecastNegative
    ) {
      recommendation = "Strong Sell";
    } else if (bullishSignalCount > 0 && bearishSignalCount > 0) {
      recommendation = holdLabel;
    } else if (technicalBearish && forecastNegative) {
      recommendation = "Sell";
    } else if (bullishSignalCount >= 4 && !forecastVeryNegative) {
      recommendation = "Buy";
    } else if (bearishSignalCount >= 4) {
      recommendation = "Strong Sell";
    } else {
      recommendation = holdLabel;
    }

    if (recommendation === "Strong Buy") recommendationDriver = Math.max(recommendationDriver, 82);
    else if (recommendation === "Buy") recommendationDriver = Math.max(Math.min(recommendationDriver, 79), 62);
    else if (recommendation.startsWith("Hold")) recommendationDriver = Math.min(Math.max(recommendationDriver, 40), 69);
    else if (recommendation === "Sell") recommendationDriver = Math.min(recommendationDriver, 39);
    else if (recommendation === "Strong Sell") recommendationDriver = Math.min(recommendationDriver, 19);
    recommendationDriver = Math.max(0, Math.min(100, recommendationDriver));
  }

  return {
    available: baseAiScore != null || isFiniteNumber(technicalScore) || isFiniteNumber(momentumScore),
    recommendation,
    target_price: isFiniteNumber(targetMean) ? Number(targetMean.toFixed(2)) : null,
    target_price_mean: isFiniteNumber(targetMean) ? Number(targetMean.toFixed(2)) : null,
    target_price_high: isFiniteNumber(targetHigh) ? Number(targetHigh.toFixed(2)) : null,
    target_price_low: isFiniteNumber(targetLow) ? Number(targetLow.toFixed(2)) : null,
    current_price: currentPrice,
    upside_pct: isFiniteNumber(upsidePct) ? Number(upsidePct.toFixed(2)) : null,
    confidence,
    simple_action: recommendation !== "N/A" ? recommendation.toUpperCase() : "",
    risk_level: riskLevel,
    ai_score: recommendationDriver != null ? Number(recommendationDriver.toFixed(2)) : null,
    base_ai_score: baseAiScore != null ? Number(baseAiScore.toFixed(2)) : null,
    sentiment_avg: isFiniteNumber(sentimentAvg) ? Number(sentimentAvg.toFixed(4)) : null,
    signals: {
      technical_score: isFiniteNumber(technicalScore) ? Number(technicalScore.toFixed(1)) : null,
      news_sentiment_score: isFiniteNumber(newsSentimentScore) ? Number(newsSentimentScore.toFixed(1)) : null,
      news_sentiment_label: sentimentLabelFromScore(sentimentAvg),
      momentum_score: isFiniteNumber(momentumScore) ? Number(momentumScore.toFixed(1)) : null,
      volatility_risk_score: isFiniteNumber(volatility) ? Number(scoreLinear(0.55 - Number(volatility), -0.15, 0.45).toFixed(1)) : null,
    },
    weights: {
      technical: weighted.some(([key]) => key === "technical") ? 45 : null,
      news_sentiment: weighted.some(([key]) => key === "news_sentiment") ? 25 : null,
      momentum: weighted.some(([key]) => key === "momentum") ? 20 : null,
      volatility_risk: weighted.some(([key]) => key === "volatility_risk") ? 10 : null,
    },
    technical_indicators: {
      rsi: isFiniteNumber(rsi) ? Number(rsi.toFixed(2)) : null,
      macd: isFiniteNumber(macd) ? Number(macd.toFixed(4)) : null,
      macd_signal: isFiniteNumber(macdSignal) ? Number(macdSignal.toFixed(4)) : null,
      ma50: isFiniteNumber(ma50) ? Number(ma50.toFixed(2)) : null,
      ma200: isFiniteNumber(ma200) ? Number(ma200.toFixed(2)) : null,
      golden_cross: ma50 !== null && ma200 !== null ? ma50 > ma200 : null,
      trend_label: isFiniteNumber(momentumBlend)
        ? Number(momentumBlend) >= 8
          ? "Strong"
          : Number(momentumBlend) >= 0
            ? "Moderate"
            : "Weak"
        : "N/A",
    },
    news_sentiment_distribution: {
      bullish: isFiniteNumber(distribution.bullish) ? Number(distribution.bullish.toFixed(1)) : null,
      neutral: isFiniteNumber(distribution.neutral) ? Number(distribution.neutral.toFixed(1)) : null,
      bearish: isFiniteNumber(distribution.bearish) ? Number(distribution.bearish.toFixed(1)) : null,
    },
    forecast: {
      predicted_return_pct: isFiniteNumber(predictedReturnPct) ? predictedReturnPct : null,
      points: forecastPoints,
      status: isFiniteNumber(predictedReturnPct) ? "Model-derived from real price history" : "Forecast unavailable",
    },
    sources: [
      symbol ? `Derived from live price history for ${symbol}` : "Derived from live price history",
      newsCount ? "Derived from recent real news sentiment" : "Relevant news sentiment data is not available.",
      analystTarget ? "Analyst target price from company financial data" : "Target band derived from 30-day trend and realized volatility",
    ],
  };
};

const extractNewsArticles = (payload) => {
  const queue = Array.isArray(payload) ? payload : [payload];
  return queue.flatMap((item) => {
    if (!item) return [];
    if (Array.isArray(item)) return item;
    if (Array.isArray(item?.news)) return item.news;
    if (Array.isArray(item?.items)) return extractNewsArticles(item.items);
    if (Array.isArray(item?.data)) return extractNewsArticles(item.data);
    if (typeof item === "object" && (item.title || item.headline)) return [item];
    return [];
  });
};

const dedupeNewsArticles = (items = []) => {
  const out = [];
  const seen = new Set();
  for (const item of Array.isArray(items) ? items : []) {
    const key = String(item?.link || item?.title || "").trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
};

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
    const symbol = normalizeSingleSymbol(value);
    if (!/^[A-Z0-9.-]{1,12}$/.test(symbol)) continue;
    if (seen.has(symbol)) continue;
    seen.add(symbol);
    out.push(symbol);
  }
  return out;
}

function normalizeSingleSymbol(value = "") {
  const raw = String(value || "").trim().toUpperCase().replace(/\s+/g, "");
  return fuzzySymbolMatch(SYMBOL_ALIASES[raw] || raw);
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
      const rawText = await res.text();
      let data = {};
      try {
        data = rawText ? JSON.parse(rawText) : {};
      } catch {
        data = {};
      }
      if (!res.ok) {
        setError(data.error || (res.status >= 500 ? t("connectError") : t("loginFailed")));
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

      let dashboardCards = [];

      try {
        const cardSymbols = primarySymbols.slice(0, 4);
        const [pricesPayload, historyPayloads] = await Promise.all([
          cardSymbols.length
            ? fetchJsonWithRetry(
                [
                  apiUrl(`/api/prices?symbols=${encodeURIComponent(cardSymbols.join(","))}`),
                  `http://localhost:8000/api/prices?symbols=${encodeURIComponent(cardSymbols.join(","))}`,
                ],
                2,
                5000
              ).catch(() => [])
            : Promise.resolve([]),
          Promise.all(
            cardSymbols.map((symbol) =>
              fetchJsonWithRetry(
                [
                  apiUrl(`/api/stock-history?ticker=${symbol}&period=1m`),
                  `http://localhost:8000/api/stock-history?ticker=${symbol}&period=1m`,
                ],
                2,
                5000
              ).catch(() => [])
            )
          ),
        ]);
        const priceRows = Array.isArray(pricesPayload)
          ? pricesPayload
          : Array.isArray(pricesPayload?.items)
            ? pricesPayload.items
            : [];
        const priceMap = new Map(
          priceRows
            .filter((item) => item?.ok !== false)
            .map((item) => [String(item?.symbol || "").toUpperCase(), item])
        );
        const cards = cardSymbols.map((symbol, index) => {
          const priceItem = priceMap.get(String(symbol).toUpperCase()) || {};
          const history = Array.isArray(historyPayloads[index]) ? historyPayloads[index] : [];
          const points = history
            .slice(-8)
            .map((row) => Number(row?.close ?? row?.price ?? 0))
            .filter((value) => Number.isFinite(value) && value > 0);
          return {
            symbol,
            price: Number(priceItem?.price ?? 0),
            change: Number(priceItem?.change_pct ?? 0),
            points,
          };
        });
        const validCards = cards.filter((item) => Number.isFinite(item.price) && item.price > 0);
        dashboardCards = validCards;
        if (alive) {
          setMiniCards(validCards);
          if (!highlight && validCards[0]) {
            setHighlight(deriveDashboardHighlight(validCards[0]));
          }
        }
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
              apiUrl(`/recommend?symbol=${topSymbol}&window_days=30`),
              `http://localhost:8000/recommend?symbol=${topSymbol}&window_days=30`,
            ],
            1,
            8000
          );
          if (alive) {
            const fallbackHighlight = deriveDashboardHighlight(dashboardCards.find((item) => item.symbol === topSymbol));
            const usableReco = hasUsableRecommendationData(reco);
            const rawConfidence = reco?.confidence;
            const confidencePct = rawConfidence === null || rawConfidence === undefined || rawConfidence === ""
              ? null
              : Number.isFinite(Number(rawConfidence))
                ? Math.round(Number(rawConfidence) * 100)
                : null;
            const action =
              typeof reco?.recommendation === "string" && reco.recommendation.trim() && reco.recommendation !== "N/A"
                ? reco.recommendation
                : null;
            const risk =
              typeof reco?.risk_level === "string" && reco.risk_level.trim() && reco.risk_level !== "N/A"
                ? reco.risk_level
                : null;

            const liveHighlight = {
              symbol: topSymbol,
              action,
              confidence: confidencePct,
              risk,
              available: reco?.available !== false && usableReco && Boolean(action || Number.isFinite(confidencePct) || risk),
            };
            setHighlight(
              liveHighlight.available
                ? liveHighlight
                : (fallbackHighlight || (topSymbol ? { symbol: topSymbol, action: null, confidence: null, risk: null, available: false } : null))
            );
          }
        }
      } catch {
        if (alive) {
          const topSymbol = primarySymbols[0];
          const fallbackHighlight = deriveDashboardHighlight(dashboardCards.find((item) => item.symbol === topSymbol));
          setHighlight(fallbackHighlight || (topSymbol ? { symbol: topSymbol, action: null, confidence: null, risk: null, available: false } : null));
        }
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
      const symbol = normalizeSingleSymbol(query);
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
              <StockCard
                key={s.symbol}
                symbol={s.symbol}
                price={s.price}
                change={s.change}
                points={s.points}
                dark={theme === "dark"}
                actionSlot={
                  <StarButton
                    active={saved}
                    onToggle={() => onToggleWatchlist(s.symbol)}
                    size="sm"
                    title={saved ? `${t("removeFromWatchlist")} ${s.symbol}` : `${t("addToWatchlist")} ${s.symbol}`}
                  />
                }
              />
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
  const [analysisHistory, setAnalysisHistory] = useState([]);

  useEffect(() => {
    let alive = true;
    const run = async () => {
      let primaryLoaded = false;
      let safeSymbol = "";
      let latest = 0;
      let history = [];
      let analysisHistoryRows = [];
      let latestDetails = null;
      let latestProfile = null;
      setLoading(true);
      setError("");
      setReco(null);
      setStockDetails(null);
      setStockDetailsLoading(true);
      setStockProfile(null);
      setAnalysisHistory([]);
      setNewsItems([]);
      setNewsLoading(false);
      try {
        const buildHistoryRows = (source) =>
          (Array.isArray(source) ? source : [])
            .map((row) => ({
              date: String(row?.date || ""),
              close: Number(row?.price ?? row?.close ?? 0),
              volume: Number(row?.volume ?? 0),
            }))
            .filter((row) => row.date && Number.isFinite(row.close) && row.close > 0)
            .sort((a, b) => String(a.date).localeCompare(String(b.date)));

        const loadSplitQuoteAndHistory = async (resolvedSymbol) => {
          const [pricesJson, historyJson] = await Promise.all([
            fetchJsonWithRetry(
              [
                apiUrl(`/api/prices?symbols=${resolvedSymbol}`),
                apiUrl(`/prices?symbols=${resolvedSymbol}`),
                localFastapiUrl(`/api/prices?symbols=${resolvedSymbol}`),
                localFastapiUrl(`/prices?symbols=${resolvedSymbol}`),
              ],
              1,
              5000
            ).catch(() => null),
            fetchJsonWithRetry(
              [
                apiUrl(`/api/stock-history?ticker=${resolvedSymbol}&period=${range}`),
                apiUrl(`/stock-history?ticker=${resolvedSymbol}&period=${range}`),
                localFastapiUrl(`/api/stock-history?ticker=${resolvedSymbol}&period=${range}`),
                localFastapiUrl(`/stock-history?ticker=${resolvedSymbol}&period=${range}`),
              ],
              1,
              5000
            ).catch(() => []),
          ]);

          const collectPriceRows = (payload) => {
            if (!payload) return [];
            if (Array.isArray(payload?.items)) return payload.items;
            if (Array.isArray(payload)) return payload;
            if (Array.isArray(payload?.data)) return payload.data;
            if (payload?.symbol || payload?.price || payload?.latest_price) return [payload];
            if (typeof payload === "object") {
              return Object.values(payload).filter(
                (value) => value && typeof value === "object" && !Array.isArray(value)
              );
            }
            return [];
          };

          const priceRows = collectPriceRows(pricesJson);
          const priceItem =
            priceRows.find((item) => String(item?.symbol || "").toUpperCase() === resolvedSymbol) ||
            priceRows.find((item) => {
              const candidate = normalizeSingleSymbol(item?.symbol || item?.ticker || item?.name || "");
              return candidate === resolvedSymbol;
            }) ||
            null;

          return {
            symbol: resolvedSymbol,
            latest_price: Number(
              priceItem?.price ??
              priceItem?.latest_price ??
              priceItem?.current_price ??
              priceItem?.c ??
              0
            ),
            previous_close: Number(
              priceItem?.previous_close ??
              priceItem?.pc ??
              0
            ),
            change_pct: Number(
              priceItem?.change_pct ??
              priceItem?.dp ??
              0
            ),
            change: Number(
              priceItem?.change ??
              priceItem?.d ??
              0
            ),
            history: Array.isArray(historyJson) ? historyJson : [],
            range,
            source_provider: priceItem?.provider || null,
            provider: priceItem?.provider || null,
          };
        };

        const hasUsablePrimaryQuote = (payload) => {
          const payloadHistory = buildHistoryRows(payload?.history);
          const payloadLatest = Number(
            payload?.latest_price ??
            payload?.price ??
            payload?.last_close ??
            payloadHistory[payloadHistory.length - 1]?.close ??
            0
          );
          return payloadLatest > 0 || payloadHistory.length > 0;
        };

        const rawSymbol = normalizeSingleSymbol(symbol);
        if (!/^[A-Z0-9.-]{1,12}$/.test(rawSymbol)) {
          throw new Error("invalid_symbol");
        }
        safeSymbol = rawSymbol;
        let quoteJson = null;
        try {
          quoteJson = await fetchJsonWithRetry(
            [
              apiUrl(`/stock/${safeSymbol}?range=${range}`),
              `http://localhost:8000/stock/${safeSymbol}?range=${range}`,
            ],
            2,
            6000
          );
          if (!hasUsablePrimaryQuote(quoteJson)) {
            quoteJson = await loadSplitQuoteAndHistory(safeSymbol);
          }
        } catch {
          quoteJson = await loadSplitQuoteAndHistory(safeSymbol);
        }

        const splitQuote = hasUsablePrimaryQuote(quoteJson)
          ? null
          : await loadSplitQuoteAndHistory(safeSymbol);

        history = buildHistoryRows(quoteJson?.history);
        if (!history.length && splitQuote?.history?.length) {
          history = buildHistoryRows(splitQuote.history);
        }

        const firstClose = Number(quoteJson?.first_close || splitQuote?.first_close || history[0]?.close || 0);
        const lastClose = Number(quoteJson?.last_close || splitQuote?.last_close || history[history.length - 1]?.close || 0);
        const previousClose = Number(quoteJson?.previous_close || splitQuote?.previous_close || 0);
        latest = lastClose > 0
          ? lastClose
          : Number(
            quoteJson?.latest_price ||
            quoteJson?.price ||
            splitQuote?.latest_price ||
            splitQuote?.price ||
            history[history.length - 1]?.close ||
            0
          );

        if (!(latest > 0) && !history.length) {
          throw new Error("no_quote_or_history");
        }

        // Strict close-only range return to match finance platforms.
        const rangeReturnFromClose = firstClose > 0 ? ((latest - firstClose) / firstClose) * 100 : 0;
        const dailyChangePct = Number.isFinite(Number(quoteJson?.change_pct))
          ? Number(quoteJson?.change_pct)
          : Number.isFinite(Number(splitQuote?.change_pct))
            ? Number(splitQuote?.change_pct)
          : (previousClose > 0 ? ((latest - previousClose) / previousClose) * 100 : 0);
        const changeAbs = Number.isFinite(Number(quoteJson?.change))
          ? Number(quoteJson?.change)
          : Number.isFinite(Number(splitQuote?.change))
            ? Number(splitQuote?.change)
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
          history,
        });
        analysisHistoryRows = history;
        const initialDerivedReco = buildDerivedRecommendation({
          symbol: safeSymbol,
          latestPrice: latest,
          history: analysisHistoryRows,
          news: [],
          details: null,
        });
        setReco(initialDerivedReco || null);
        primaryLoaded = true;
        setLoading(false);
      } catch {
        if (!alive) return;
        try {
          const [detailsJson, profileJson] = await Promise.all([
            fetchJsonWithRetry(
              [
                apiUrl(`/api/stock/financials/${safeSymbol}`),
                apiUrl(`/stock/financials/${safeSymbol}`),
                localFastapiUrl(`/api/stock/financials/${safeSymbol}`),
                localFastapiUrl(`/stock/financials/${safeSymbol}`),
              ],
              1,
              5000
            ).catch(() => null),
            fetchJsonWithRetry(
              [
                apiUrl(`/api/stock/profile/${safeSymbol}`),
                apiUrl(`/stock/profile/${safeSymbol}`),
                localFastapiUrl(`/api/stock/profile/${safeSymbol}`),
                localFastapiUrl(`/stock/profile/${safeSymbol}`),
              ],
              1,
              5000
            ).catch(() => null),
          ]);

          const fallbackPriceCandidates = [
            detailsJson?.currentPrice,
            detailsJson?.current_price,
            detailsJson?.latestPrice,
            detailsJson?.latest_price,
            detailsJson?.previousClose,
            detailsJson?.previous_close,
            detailsJson?.open,
          ]
            .map((value) => Number(value))
            .filter((value) => Number.isFinite(value) && value > 0);
          const fallbackPrice = fallbackPriceCandidates[0] || 0;

          if (detailsJson || profileJson) {
            latestDetails = detailsJson || null;
            latestProfile = profileJson || null;
            if (fallbackPrice > 0) {
              setStockData({
                symbol: safeSymbol,
                latest_price: fallbackPrice,
                change_abs: 0,
                daily_change_pct: 0,
                return_pct: 0,
                previous_close: fallbackPrice,
                first_close: fallbackPrice,
                last_close: fallbackPrice,
                volume: Number(detailsJson?.volume || 0),
                history: [],
              });
              setReco(
                buildDerivedRecommendation({
                  symbol: safeSymbol,
                  latestPrice: fallbackPrice,
                  history: analysisHistoryRows,
                  news: [],
                  details: detailsJson || null,
                }) || null
              );
            } else {
              setStockData(null);
              setReco(null);
            }
            setStockDetails(detailsJson || null);
            setStockDetailsLoading(false);
            setStockProfile(profileJson || null);
            setError(null);
            primaryLoaded = true;
          }
        } catch {
          // Fall through to hard error state when even secondary detail/profile fallback is unavailable.
        }

        if (!primaryLoaded) {
          setError(t("stockLoadError") === "stockLoadError" ? "ไม่สามารถโหลดข้อมูลหุ้นได้ในขณะนี้" : t("stockLoadError"));
          setStockData(null);
          setReco(null);
          setNewsItems([]);
        }
      } finally {
        if (alive) {
          setLoading(false);
        }
      }

      try {
        const [detailsJson, profileJson] = await Promise.all([
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
        if (!alive) return;
        latestDetails = detailsJson && typeof detailsJson === "object" ? detailsJson : null;
        latestProfile = profileJson && typeof profileJson === "object" ? profileJson : { name: safeSymbol, ticker: safeSymbol };
        setStockDetails(latestDetails);
        setStockProfile(latestProfile);
      } catch {
        if (!alive) return;
        latestDetails = null;
        latestProfile = { name: safeSymbol, ticker: safeSymbol };
        setStockDetails(latestDetails);
        setStockProfile(latestProfile);
      } finally {
        if (alive) {
          setStockDetailsLoading(false);
        }
      }

      try {
        const analysisJson = await fetchJsonWithRetry(
          [
            apiUrl(`/api/stock-history?ticker=${safeSymbol}&period=1y`),
            apiUrl(`/stock-history?ticker=${safeSymbol}&period=1y`),
            localFastapiUrl(`/api/stock-history?ticker=${safeSymbol}&period=1y`),
            localFastapiUrl(`/stock-history?ticker=${safeSymbol}&period=1y`),
          ],
          1,
          5000
        ).catch(() => []);
        const extendedHistory = buildHistoryRows(analysisJson);
        if (extendedHistory.length) {
          analysisHistoryRows = extendedHistory;
        }
        if (alive) {
          setAnalysisHistory(analysisHistoryRows);
          const refreshedReco = buildDerivedRecommendation({
            symbol: safeSymbol,
            latestPrice: latest,
            history: analysisHistoryRows,
            news: [],
            details: latestDetails || null,
          });
          if (refreshedReco) {
            setReco(refreshedReco);
          }
        }
      } catch {
        if (alive) {
          setAnalysisHistory(analysisHistoryRows);
        }
      }

      setNewsLoading(true);
      try {
        const [recoResult, newsResult, rssResult] = await Promise.allSettled([
          fetchJsonWithRetry(
            [
              apiUrl(`/recommend?symbol=${safeSymbol}&window_days=30`),
              `http://localhost:8000/recommend?symbol=${safeSymbol}&window_days=30`,
            ],
            1,
            4000
          ),
          fetchJsonWithRetry(
            [
              apiUrl(`/news?symbols=${safeSymbol}&days_back=14`),
              `http://localhost:8000/news?symbols=${safeSymbol}&days_back=14`,
            ],
            1,
            4000
          ),
          fetchJsonWithRetry(
            [
              apiUrl(`/rss/${safeSymbol}`),
              `http://localhost:8000/rss/${safeSymbol}`,
            ],
            1,
            3000
          ),
        ]);

        const recoJson = recoResult.status === "fulfilled" ? recoResult.value : null;
        const newsJson = newsResult.status === "fulfilled" ? newsResult.value : [];
        const rssJson = rssResult.status === "fulfilled" ? rssResult.value : [];
        let mergedNews = dedupeNewsArticles([
          ...extractNewsArticles(newsJson),
          ...extractNewsArticles(rssJson),
        ]);
        const backendReco = recoJson
          ? {
              recommendation: recoJson.recommendation || null,
              target_price: recoJson.target_price ?? recoJson.target_price_mean ?? null,
              target_price_mean: recoJson.target_price ?? recoJson.target_price_mean ?? null,
              target_price_high: recoJson.target_price_high ?? null,
              target_price_low: recoJson.target_price_low ?? null,
              current_price: recoJson.current_price ?? latest,
              upside_pct: recoJson.upside_pct ?? null,
              confidence: typeof recoJson.confidence === "number" ? recoJson.confidence : null,
              simple_action: recoJson.simple_action || "",
              risk_level: recoJson.risk_level || null,
              ai_score: recoJson.ai_score ?? null,
              sentiment_avg: recoJson.sentiment_avg ?? null,
              signals: recoJson.signals || {},
              weights: recoJson.weights || {},
              technical_indicators: recoJson.technical_indicators || {},
              news_sentiment_distribution: recoJson.news_sentiment_distribution || {},
              forecast: recoJson.forecast || {},
              sources: Array.isArray(recoJson.sources) ? recoJson.sources : [],
              available: recoJson.available !== false,
            }
          : null;
        const backendRecoUsable = hasUsableRecommendationData(backendReco);
        const derivedReco = buildDerivedRecommendation({
          symbol: safeSymbol,
          latestPrice: latest,
          history: analysisHistoryRows.length ? analysisHistoryRows : history,
          news: mergedNews,
          details: latestDetails || null,
        });

        if (!alive) return;
        if (backendReco || derivedReco || reco) {
          const backendRecoForMerge = backendRecoUsable
            ? backendReco
            : {
                current_price: backendReco?.current_price ?? latest,
                target_price: isFiniteNumber(backendReco?.target_price) ? backendReco.target_price : null,
                target_price_mean: isFiniteNumber(backendReco?.target_price_mean) ? backendReco.target_price_mean : null,
                target_price_high: isFiniteNumber(backendReco?.target_price_high) ? backendReco.target_price_high : null,
                target_price_low: isFiniteNumber(backendReco?.target_price_low) ? backendReco.target_price_low : null,
                upside_pct: isFiniteNumber(backendReco?.upside_pct) ? backendReco.upside_pct : null,
                forecast: backendReco?.forecast && !isUnavailableText(backendReco?.forecast?.status) ? backendReco.forecast : {},
                sources: Array.isArray(backendReco?.sources) ? backendReco.sources : [],
                available: false,
              };
          const mergedReco = mergeDefined(reco || {}, mergeDefined(derivedReco || {}, backendRecoForMerge || {}));
          if (!backendRecoUsable && derivedReco) {
            mergedReco.available = true;
            mergedReco.sources = [
              ...(Array.isArray(derivedReco.sources) ? derivedReco.sources : []),
              "Recommendation derived locally from real loaded market data",
            ];
          }
          setReco(mergedReco);
        }
        setNewsItems(mergedNews.slice(0, 12));
      } catch {
        if (!alive) return;
        setNewsItems([]);
      } finally {
        if (alive) {
          setNewsLoading(false);
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

  const effectiveStockData = useMemo(() => {
    if (stockData) return stockData;
    const fallbackPriceCandidates = [
      stockDetails?.currentPrice,
      stockDetails?.current_price,
      stockDetails?.latestPrice,
      stockDetails?.latest_price,
      stockDetails?.previousClose,
      stockDetails?.previous_close,
      stockDetails?.open,
    ]
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value) && value > 0);
    const fallbackPrice = fallbackPriceCandidates[0] || 0;
    if (!(fallbackPrice > 0) && !stockProfile && !stockDetails) return null;
    const fallbackSymbol = normalizeSingleSymbol(
      stockProfile?.ticker || stockProfile?.symbol || stockDetails?.symbol || symbol || ""
    );
    return {
      symbol: fallbackSymbol || normalizeSingleSymbol(symbol),
      latest_price: fallbackPrice > 0 ? fallbackPrice : null,
      change_abs: 0,
      daily_change_pct: 0,
      return_pct: 0,
      previous_close: fallbackPrice > 0 ? fallbackPrice : null,
      first_close: fallbackPrice > 0 ? fallbackPrice : null,
      last_close: fallbackPrice > 0 ? fallbackPrice : null,
      volume: Number(stockDetails?.volume || 0),
      history: [],
    };
  }, [stockData, stockDetails, stockProfile, symbol]);

  const effectiveReco = useMemo(() => {
    if (reco) return reco;
    const fallbackRecoPriceCandidates = [
      effectiveStockData?.latest_price,
      stockDetails?.currentPrice,
      stockDetails?.current_price,
      stockDetails?.latestPrice,
      stockDetails?.latest_price,
      stockDetails?.previousClose,
      stockDetails?.previous_close,
      stockDetails?.open,
    ]
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value) && value > 0);
    const fallbackRecoPrice = fallbackRecoPriceCandidates[0] || null;
    return buildDerivedRecommendation({
      symbol: effectiveStockData?.symbol || stockProfile?.ticker || stockDetails?.symbol || symbol,
      latestPrice: fallbackRecoPrice,
      history: analysisHistory.length ? analysisHistory : (effectiveStockData?.history || []),
      news: newsItems || [],
      details: stockDetails,
    });
  }, [reco, effectiveStockData, analysisHistory, newsItems, symbol, stockDetails, stockProfile]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] text-slate-400">
        <Loader2 className="animate-spin mb-4" size={40} />
        <p className="font-medium text-lg">{t("analyzing")} {symbol}...</p>
      </div>
    );
  }

  if (error && !effectiveStockData && !stockDetails && !stockProfile) {
    return (
      <div className={`${theme === "dark" ? "bg-[#0F172A] border-rose-900/40" : "bg-white border-rose-100"} rounded-2xl border p-8 text-rose-600 font-medium`}>
        {error || t("connectError")}
      </div>
    );
  }

  const displayStock = effectiveStockData || stockData;

  const isSaved = watchlist.includes(displayStock.symbol);

  return (
    <div className="space-y-6">
      <button onClick={() => navigate(-1)} className="flex items-center text-slate-500 hover:text-[#2563EB] font-bold transition-colors">
        <ArrowLeft className="mr-2" size={20} /> {t("backSearch")}
      </button>

      <div className="flex items-start gap-3">
        <StarButton
          active={isSaved}
          onToggle={() => onToggleWatchlist(displayStock.symbol)}
          size="lg"
          title={isSaved ? `${t("removeFromWatchlist")} ${displayStock.symbol}` : `${t("addToWatchlist")} ${displayStock.symbol}`}
          className={theme === "dark" ? "bg-slate-900 border-slate-700 text-slate-300" : ""}
        />
        <div className="flex-1">
          <StockCompanyHeader
            profile={stockProfile}
            symbol={displayStock.symbol}
            currentPrice={displayStock.latest_price}
            changeAbs={displayStock.change_abs}
            dailyChangePct={displayStock.daily_change_pct}
            returnPct={displayStock.return_pct}
            rangeLabel={String(range || "1y").toUpperCase()}
            adjustedReturn={String(range || "").toLowerCase() === "all"}
            language={i18n.language}
            dark={theme === "dark"}
          />
        </div>
      </div>

      <div className={`${theme === "dark" ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-100"} p-6 rounded-3xl border shadow-sm space-y-4`}>
        <TimeRangeSelector range={range} onChange={setRange} dark={theme === "dark"} />
        <StockChart data={chartSeries} returnPct={displayStock.return_pct} dark={theme === "dark"} />
      </div>

      <StockStatsGrid details={stockDetails} loading={stockDetailsLoading} language={i18n.language} dark={theme === "dark"} />

      {(effectiveReco || stockDetails || stockProfile) ? (
        <AIInvestmentAnalysis reco={effectiveReco} language={i18n.language} dark={theme === "dark"} />
      ) : null}

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
    volatilityKey: "riskVolLow",
    volatility: "Low",
    suitableForKey: "riskLowSuitable",
    suitableFor: "Recommended for conservative investors",
    strategyKeys: ["riskLowStrategy1", "riskLowStrategy2", "riskLowStrategy3"],
    strategy: ["Prioritize stable cashflow businesses", "Allocate toward dividend and broad-market ETF", "Rebalance quarterly for risk control"],
  },
  {
    level: "MEDIUM",
    titleKey: "riskMediumTitle",
    title: "Balanced growth",
    descriptionKey: "riskMediumDesc",
    description: "Balanced mix between growth and stability for long-term performance.",
    volatilityKey: "riskVolModerate",
    volatility: "Moderate",
    suitableForKey: "riskMediumSuitable",
    suitableFor: "Suitable for long-term investors",
    strategyKeys: ["riskMediumStrategy1", "riskMediumStrategy2", "riskMediumStrategy3"],
    strategy: ["Mix growth leaders and high-quality value names", "Use ETF for diversification buffer", "Keep tactical cash for opportunities"],
  },
  {
    level: "HIGH",
    titleKey: "riskHighTitle",
    title: "Aggressive growth",
    descriptionKey: "riskHighDesc",
    description: "Higher upside potential from momentum and thematic growth stocks.",
    volatilityKey: "riskVolHigh",
    volatility: "High",
    suitableForKey: "riskHighSuitable",
    suitableFor: "Suitable for risk-tolerant investors",
    strategyKeys: ["riskHighStrategy1", "riskHighStrategy2", "riskHighStrategy3"],
    strategy: ["Focus on high growth sectors and innovation themes", "Use strict stop-loss and position sizing", "Review portfolio weekly for fast changes"],
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
          recommendation: row?.recommendation || null,
          risk: row?.risk_level || null,
          strategy,
          sentiment: row?.sentiment_label || null,
          momentum: row?.momentum_label || null,
          aiScore: Math.max(0, Math.min(100, Number.isFinite(aiScore) ? aiScore : 0)),
          confidence: Number.isFinite(confidenceRaw) ? Math.max(0, Math.min(100, confidenceRaw)) : null,
          reason: row?.reason || "",
          latestPrice: Number.isFinite(Number(row?.latest_price)) ? Number(row.latest_price) : null,
          ret30: Number.isFinite(Number(row?.ret30)) ? Number(row.ret30) : null,
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
    const byRisk = allPicks.filter((item) => !item.risk || item.risk === risk);
    const bySentiment = byRisk.filter((item) => !item.sentiment || item.sentiment === sentiment);
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
          const safeSymbol = normalizeSingleSymbol(symbol);
          try {
            const [stockJson, recoJson, profileJson] = await Promise.all([
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
              fetchJsonWithRetry(
                [
                  apiUrl(`/api/stock/profile/${safeSymbol}`),
                  `http://localhost:8000/api/stock/profile/${safeSymbol}`,
                ],
                1,
                7000
              ).catch(() => null),
            ]);
            const history = stockJson.history || [];
            const company = String(profileJson?.name || stockJson.name || safeSymbol);
            const latest = Number(stockJson.latest_price || stockJson.price || history[history.length - 1]?.close || 0);
            const previousClose = Number(stockJson.previous_close || history[history.length - 2]?.close || latest || 0);
            const change = previousClose ? ((latest - previousClose) / previousClose) * 100 : 0;
            const points = history
              .slice(-7)
              .map((h) => Number(h.close || h.price || 0))
              .filter((x) => Number.isFinite(x) && x > 0);
            const volume = Number(history[history.length - 1]?.volume || stockJson.volume || 0);
            const aiScore = recoJson?.available && Number.isFinite(Number(recoJson?.ai_score)) ? Number(recoJson.ai_score) : null;
            const sentimentAvg = Number(recoJson?.sentiment_avg);
            const sentiment =
              Number.isFinite(sentimentAvg)
                ? sentimentFromValue(sentimentAvg)
                : null;
            const sector = String(profileJson?.industry || profileJson?.sector || "Unclassified");

            return {
              symbol: safeSymbol,
              company,
              sector,
              price: latest,
              change,
              volume,
              aiScore,
              points,
              sentiment,
            };
          } catch {
            return null;
          }
        })
      );

      if (!alive) return;
      const cleanRows = nextRows.filter((item) => item && Number.isFinite(item.price) && item.price > 0);
      setRows(cleanRows.sort((a, b) => (Number(b.aiScore ?? -1) - Number(a.aiScore ?? -1)) || (Number(b.change || 0) - Number(a.change || 0))));
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
    const next = normalizeSingleSymbol(inputSymbol);
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
  const [overview, setOverview] = useState({ sentiment: null, sector: null, topPick: null, riskLevel: null });
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
      setOverview(snapshot.overview || { sentiment: null, sector: null, topPick: null, riskLevel: null });
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

        const signalRows = pickerItems
          .map((item) => ({
            symbol: String(item?.ticker || "").toUpperCase(),
            confidence: Number.isFinite(Number(item?.confidence)) ? Math.round(Number(item.confidence)) : null,
            signal: item?.recommendation || null,
          }))
          .filter((item) => item.symbol && (item.signal || item.confidence != null))
          .slice(0, 5);

        if (!alive) return;
        const snapshot = {
          overview: {
            sentiment: summaryData?.market_sentiment || null,
            sector: summaryData?.trending_sector || null,
            topPick: summaryData?.top_ai_pick || null,
            riskLevel: summaryData?.risk_outlook || null,
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
              momentum: picker?.momentum_label || null,
              sentiment: picker?.sentiment_label || null,
              aiScore: Number.isFinite(Number(picker?.ai_score)) ? Math.round(Number(picker.ai_score)) : null,
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
        setOverview({ sentiment: null, sector: null, topPick: null, riskLevel: null });
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
      return Array.isArray(parsed) ? normalizeSymbolList(parsed) : [];
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
      return Array.isArray(parsed) ? normalizeSymbolList(parsed) : [];
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
    const safeSymbol = normalizeSingleSymbol(symbol);
    if (!/^[A-Z0-9.-]{1,12}$/.test(safeSymbol)) return;
    setWatchlist((prev) => (prev.includes(safeSymbol) ? prev : [...prev, safeSymbol]));
  };

  const toggleWatchSymbol = (symbol) => {
    const safeSymbol = normalizeSingleSymbol(symbol);
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
    const s = normalizeSingleSymbol(symbol);
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
