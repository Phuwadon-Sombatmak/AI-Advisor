import React, { useEffect, useMemo, useRef, useState } from "react";
import { Bot } from "lucide-react";
import { useTranslation } from "react-i18next";
import ChatHeader from "./ChatHeader";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import SuggestedPrompts from "./SuggestedPrompts";
import TypingIndicator from "./TypingIndicator";
import { formatAssistantResponse, getFollowupPrompts } from "../utils/aiAdvisor";

const AI_ADVISOR_CACHE_TTL_MS = 5 * 60 * 1000;
const advisorResponseCache = new Map();

const ENDPOINTS = [
  "/api-fastapi/api/ai-advisor",
  "/api-fastapi/ai-advisor",
];

const BASE_PROMPTS = [
  "What stocks are trending today?",
  "Is NVDA still a good investment?",
  "What sectors have strong momentum?",
  "Show bullish large-cap ideas",
  "What are the biggest market risks now?",
  "Summarize today’s market sentiment",
];

const LOADING_STAGES = [
  "Analyzing price action...",
  "Reviewing recent news sentiment...",
  "Building investment view...",
];

function buildGreetingMessage(greetingText) {
  return {
    role: "assistant",
    text: greetingText,
    time: now(),
    confidence: null,
    sources: [],
    followups: BASE_PROMPTS.slice(0, 3),
    intent: "unclear_query",
  };
}

async function askAI(payload) {
  const cacheKey = JSON.stringify(payload);
  const cached = advisorResponseCache.get(cacheKey);
  if (cached && Date.now() - Number(cached.ts || 0) < AI_ADVISOR_CACHE_TTL_MS) {
    return cached.data;
  }
  let lastErr;
  for (const endpoint of ENDPOINTS) {
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      advisorResponseCache.set(cacheKey, { ts: Date.now(), data });
      return data;
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error("ai advisor failed");
}

function now() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function extractSymbolFromText(text = "") {
  const stop = new Set([
    "IS", "ARE", "WAS", "WERE", "THE", "THIS", "THAT", "A", "AN", "AND", "OR", "VS",
    "SHOW", "TOP", "RISK", "NEWS", "MARKET", "SECTOR", "SECTORS", "STOCK", "STOCKS",
    "TODAY", "NOW", "BEST", "COMPARE", "WHICH", "WHY", "LEADING", "MOMENTUM", "WITH",
    "FOR", "ABOUT", "SUMMARIZE", "BULLISH", "BEARISH", "NEUTRAL", "HOW", "DO", "DOES",
    "TECHNOLOGY", "ENERGY", "FINANCIALS", "HEALTHCARE", "INDUSTRIALS", "STAPLES",
    "DISCRETIONARY", "XLK", "XLE", "XLF", "XLV", "XLI", "XLP", "XLY",
  ]);
  const matches = String(text || "").toUpperCase().match(/\b[A-Z]{2,5}(?:[.-][A-Z])?\b/g) || [];
  const found = matches.find((s) => !stop.has(s));
  return found || "";
}

export default function AIAdvisorWidget({ context, dark = false }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState(LOADING_STAGES[0]);
  const [status, setStatus] = useState({
    online: true,
    message: "Connected",
    live_data_ready: true,
    market_context_loaded: true,
  });
  const [sessionContext, setSessionContext] = useState({
    last_symbol: "",
    last_symbols: [],
    last_sector: "",
    last_intent: "unclear_query",
  });
  const [messages, setMessages] = useState([
    buildGreetingMessage(t("aiAdvisorGreeting")),
  ]);

  const scrollRef = useRef(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (!loading) return undefined;
    let idx = 0;
    const timer = setInterval(() => {
      idx = (idx + 1) % LOADING_STAGES.length;
      setLoadingStage(LOADING_STAGES[idx]);
    }, 1500);
    return () => clearInterval(timer);
  }, [loading]);

  const latestAssistant = useMemo(
    () => [...messages].reverse().find((m) => m.role === "assistant"),
    [messages],
  );
  const latestUser = useMemo(
    () => [...messages].reverse().find((m) => m.role === "user"),
    [messages],
  );

  const prompts = useMemo(() => {
    const dynamic = getFollowupPrompts(latestAssistant?.intent, latestAssistant?.schema, latestAssistant?.followups, sessionContext);
    const normalizedLatestUser = String(latestUser?.text || "").trim().toLowerCase();
    const deduped = (dynamic.length ? dynamic : BASE_PROMPTS).filter((prompt, index, arr) => {
      const normalizedPrompt = String(prompt || "").trim().toLowerCase();
      return normalizedPrompt && normalizedPrompt !== normalizedLatestUser && arr.findIndex((item) => String(item || "").trim().toLowerCase() === normalizedPrompt) === index;
    });
    return deduped.length ? deduped : BASE_PROMPTS.filter((prompt) => String(prompt).trim().toLowerCase() !== normalizedLatestUser);
  }, [latestAssistant, latestUser, sessionContext]);

  const sendQuestion = async (questionText) => {
    const q = String(questionText || input).trim();
    if (!q || loading) return;

    setMessages((prev) => [...prev, { role: "user", text: q, time: now() }]);
    setInput("");
    setLoading(true);
    setLoadingStage(LOADING_STAGES[0]);
      setStatus((prev) => ({ ...prev, message: "Analyzing market data...", degraded: false }));

    try {
      const parsedQuestionSymbol = extractSymbolFromText(q) || sessionContext.last_symbol || context?.selected_stock || "";
      const payload = {
        question: q,
        context: {
          ...(context || {}),
          chat_state: sessionContext,
          selected_stock: parsedQuestionSymbol,
        },
      };
      const raw = await askAI(payload);
      const formatted = formatAssistantResponse(raw);
      const symbols = [];
      const parsed = extractSymbolFromText(q);
      if (parsed) symbols.push(parsed);
      if (raw?.analysis?.left_symbol) symbols.push(String(raw.analysis.left_symbol).toUpperCase());
      if (raw?.analysis?.right_symbol) symbols.push(String(raw.analysis.right_symbol).toUpperCase());
      if (raw?.analysis?.ticker) symbols.push(String(raw.analysis.ticker).toUpperCase());
      if (formatted?.schema?.comparison?.left_symbol) symbols.push(String(formatted.schema.comparison.left_symbol).toUpperCase());
      if (formatted?.schema?.comparison?.right_symbol) symbols.push(String(formatted.schema.comparison.right_symbol).toUpperCase());
      if (formatted?.schema?.stock_overview?.ticker) symbols.push(String(formatted.schema.stock_overview.ticker).toUpperCase());
      const uniqueSymbols = [...new Set(symbols.filter(Boolean))];
      const symbol = uniqueSymbols[0] || sessionContext.last_symbol;
      const lastSector =
        formatted?.schema?.sector_stock_picker?.sector ||
        formatted?.schema?.sector_analysis?.sector ||
        raw?.analysis?.sector ||
        raw?.summary?.trending_sector ||
        sessionContext.last_sector ||
        "";

      const comparisonSymbols = formatted.intent === "stock_comparison"
        ? uniqueSymbols.slice(0, 3)
        : [];

      setSessionContext((prev) => ({
        last_symbol: symbol,
        last_symbols: comparisonSymbols.length ? comparisonSymbols : (formatted.intent === "stock_comparison" ? prev.last_symbols || [] : []),
        last_sector: lastSector,
        last_intent: formatted.intent || "unclear_query",
      }));
      setStatus({
        ...(raw?.status || {
          online: true,
          message: "Connected",
          live_data_ready: true,
          market_context_loaded: true,
        }),
      });

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          time: now(),
          ...formatted,
        },
      ]);
    } catch {
      const fallbackText = "Live data is temporarily unavailable. Unable to verify market data.";
      setStatus({
        online: true,
        message: "Live data unavailable",
        live_data_ready: false,
        market_context_loaded: false,
        degraded: true,
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: fallbackText,
          time: now(),
          confidence: null,
          sources: [],
          warning: "",
          dataValidation: { price_data: false, news_data: false, technical_data: false },
          followups: [
            "Try again in a moment",
            "Ask about a different stock",
            "Summarize today’s market sentiment",
          ],
          intent: "unclear_query",
        },
      ]);
    } finally {
      setLoading(false);
      setStatus((prev) => ({ ...prev, message: "Connected" }));
    }
  };

  const clearChat = () => {
    setSessionContext({
      last_symbol: "",
      last_symbols: [],
      last_sector: "",
      last_intent: "unclear_query",
    });
    setMessages([
      buildGreetingMessage(t("aiAdvisorGreeting")),
    ]);
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 text-white p-4 rounded-full shadow-2xl hover:scale-110 transition-transform z-50 flex items-center justify-center"
        style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
      >
        <Bot size={24} />
      </button>
    );
  }

  return (
    <div className={`fixed bottom-5 right-5 w-[460px] max-w-[95vw] h-[72vh] min-h-[520px] ${dark ? "bg-[#0B1220]/95 border-slate-700" : "bg-white/95 border-slate-200"} rounded-3xl shadow-2xl border overflow-hidden z-50 flex flex-col backdrop-blur-md animate-[fadeIn_.22s_ease-out]`}>
      <ChatHeader dark={dark} onClose={() => setOpen(false)} status={status} />

      <div ref={scrollRef} className={`${dark ? "bg-[#0B1220]" : "bg-slate-50"} px-3 pt-3 pb-2 flex-1 overflow-y-auto space-y-3`}>
        {messages.map((m, idx) => <ChatMessage key={`${m.time}-${idx}`} message={m} dark={dark} />)}
        {loading ? <TypingIndicator stage={loadingStage} dark={dark} /> : null}
      </div>

      <div className={`px-3 pt-2 ${dark ? "bg-[#0B1220]" : "bg-white"}`}>
        <SuggestedPrompts
          onPick={sendQuestion}
          prompts={prompts}
          dark={dark}
          title="Suggested questions"
        />
      </div>

      <ChatInput
        value={input}
        onChange={setInput}
        onSend={() => sendQuestion(input)}
        onClear={clearChat}
        loading={loading}
        dark={dark}
      />
    </div>
  );
}
