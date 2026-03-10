const SENTIMENT_CONFIG = {
  all: {
    key: "all",
    emoji: "✨",
    labelKey: "all",
    badgeLight: "bg-blue-50 text-blue-700 border-blue-200",
    badgeDark: "bg-blue-500/15 text-blue-200 border-blue-400/30",
    scoreLight: "text-blue-600",
    scoreDark: "text-blue-300",
    activeLight: "text-white bg-gradient-to-r from-[#2563EB] to-[#1E3A8A] border-transparent shadow-[0_6px_16px_rgba(37,99,235,0.28)]",
    activeDark: "text-white bg-gradient-to-r from-[#2563EB] to-[#1E3A8A] border-transparent shadow-[0_6px_16px_rgba(37,99,235,0.35)]",
  },
  bullish: {
    key: "bullish",
    emoji: "🐂",
    labelKey: "bullish",
    badgeLight: "bg-emerald-50 text-emerald-700 border-emerald-200",
    badgeDark: "bg-emerald-500/15 text-emerald-200 border-emerald-400/30",
    scoreLight: "text-emerald-600",
    scoreDark: "text-emerald-300",
    activeLight: "text-emerald-900 bg-emerald-200 border-emerald-300 shadow-[0_6px_16px_rgba(16,185,129,0.22)]",
    activeDark: "text-emerald-100 bg-emerald-500/30 border-emerald-400/45 shadow-[0_6px_16px_rgba(16,185,129,0.2)]",
  },
  neutral: {
    key: "neutral",
    emoji: "⚖️",
    labelKey: "neutral",
    badgeLight: "bg-slate-100 text-slate-700 border-slate-200",
    badgeDark: "bg-slate-500/20 text-slate-200 border-slate-400/35",
    scoreLight: "text-slate-500",
    scoreDark: "text-slate-300",
    activeLight: "text-slate-800 bg-slate-200 border-slate-300 shadow-[0_6px_16px_rgba(100,116,139,0.2)]",
    activeDark: "text-slate-100 bg-slate-500/30 border-slate-400/45 shadow-[0_6px_16px_rgba(100,116,139,0.25)]",
  },
  bearish: {
    key: "bearish",
    emoji: "🐻",
    labelKey: "bearish",
    badgeLight: "bg-rose-50 text-rose-700 border-rose-200",
    badgeDark: "bg-rose-500/15 text-rose-200 border-rose-400/30",
    scoreLight: "text-rose-600",
    scoreDark: "text-rose-300",
    activeLight: "text-rose-900 bg-rose-200 border-rose-300 shadow-[0_6px_16px_rgba(244,63,94,0.2)]",
    activeDark: "text-rose-100 bg-rose-500/30 border-rose-400/45 shadow-[0_6px_16px_rgba(244,63,94,0.22)]",
  },
};

const DEFAULT_INACTIVE_LIGHT = "bg-white text-slate-600 border-slate-200 hover:bg-slate-50";
const DEFAULT_INACTIVE_DARK = "bg-slate-900/60 text-slate-300 border-slate-700 hover:bg-slate-800/80";

export function normalizeSentimentKey(value) {
  const key = String(value || "").toLowerCase();
  if (key.includes("bull")) return "bullish";
  if (key.includes("bear")) return "bearish";
  if (key.includes("neutral")) return "neutral";
  if (key === "all") return "all";
  return "neutral";
}

export function getSentimentConfig(sentiment) {
  const key = normalizeSentimentKey(sentiment);
  return SENTIMENT_CONFIG[key] || SENTIMENT_CONFIG.neutral;
}

export function getSentimentFilterButtonClasses({ sentiment, active = false, dark = false }) {
  const cfg = getSentimentConfig(sentiment);
  const base =
    "inline-flex items-center gap-2 px-4 py-2 rounded-full border text-sm font-semibold transition-all duration-200 hover:-translate-y-0.5";
  if (active) {
    return `${base} ${dark ? cfg.activeDark : cfg.activeLight}`;
  }
  return `${base} ${dark ? DEFAULT_INACTIVE_DARK : DEFAULT_INACTIVE_LIGHT} hover:shadow-sm`;
}

export function getSentimentBadgeClasses({ sentiment, dark = false }) {
  const cfg = getSentimentConfig(sentiment);
  return `inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-semibold ${dark ? cfg.badgeDark : cfg.badgeLight}`;
}

export function getSentimentScoreClasses({ sentiment, score = 0, dark = false }) {
  const key = sentiment ? normalizeSentimentKey(sentiment) : (Number(score) > 0.2 ? "bullish" : Number(score) < -0.2 ? "bearish" : "neutral");
  const cfg = getSentimentConfig(key);
  return `text-sm font-semibold ${dark ? cfg.scoreDark : cfg.scoreLight}`;
}
