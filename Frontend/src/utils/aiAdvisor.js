export function mapConfidenceToBadge(confidence = 0) {
  const score = Number(confidence || 0);
  if (score >= 80) {
    return { label: "High confidence", tone: "bg-emerald-100 text-emerald-700 border-emerald-200" };
  }
  if (score >= 60) {
    return { label: "Medium confidence", tone: "bg-amber-100 text-amber-700 border-amber-200" };
  }
  return { label: "Low confidence", tone: "bg-rose-100 text-rose-700 border-rose-200" };
}

export function buildMarketSummary(summary = {}) {
  if (!summary || typeof summary !== "object") return "";
  const regime = summary.market_regime || summary.market_sentiment || "N/A";
  const confidence = summary.regime_confidence || "N/A";
  const score = summary.fear_greed_score ?? "-";
  const sector = summary.trending_sector || "N/A";
  const risk = summary.risk_outlook || "N/A";
  return `Regime ${regime} (${confidence}) • CNN ${score} • Sector ${sector} • Risk ${risk}`;
}

export function getFollowupPrompts(intent = "unclear_query", schema = {}, fallback = [], chatState = {}) {
  if (Array.isArray(fallback) && fallback.length) return fallback.slice(0, 4);
  const symbol = schema?.stock_overview?.ticker || schema?.ticker || "";
  const sector =
    schema?.sector_stock_picker?.sector ||
    schema?.sector_analysis?.sector ||
    schema?.sector_overview?.sector ||
    schema?.sector ||
    "";
  const comparisonPair = Array.isArray(chatState?.last_symbols) ? chatState.last_symbols.filter(Boolean).slice(0, 2) : [];
  const pairLabel = comparisonPair.length >= 2 ? `${comparisonPair[0]} vs ${comparisonPair[1]}` : "";
  if (intent === "stock_comparison") {
    return [
      pairLabel ? `Show valuation and risk difference for ${pairLabel}` : "Show valuation and risk difference",
      pairLabel ? `Which is better for short-term momentum: ${pairLabel}?` : "Which is better for short-term momentum?",
      pairLabel ? `What are the main downside risks for ${pairLabel}?` : "What are the main downside risks?",
    ];
  }
  if (intent === "single_stock_analysis" && symbol) {
    return [
      `Compare ${symbol} vs AMD`,
      `What are the downside risks for ${symbol}?`,
      `What should I watch next for ${symbol}?`,
    ];
  }
  if (intent === "sector_stock_picker") {
    return [
      `Compare top names in ${sector || "this sector"}`,
      `Show lower-risk stocks in ${sector || "this sector"}`,
      `Which ${sector || "sector"} names have bullish sentiment?`,
    ];
  }
  if (intent === "sector_explanation" || intent === "sector_analysis") {
    return [
      `Show top momentum stocks in ${sector || "this sector"}`,
      `What risks could weaken ${sector || "this sector"}?`,
      `Compare ${sector || "this sector"} vs Technology`,
    ];
  }
  if (intent === "market_overview") {
    return [
      "Which sectors are leading now?",
      "What are the biggest market risks now?",
      "Show top momentum stocks in the strongest sector",
    ];
  }
  if (intent === "trending_stock_discovery") {
    const names = Array.isArray(schema?.trending_stocks) ? schema.trending_stocks : [];
    const first = names[0]?.symbol || "";
    const second = names[1]?.symbol || "";
    return [
      first && second ? `Compare ${first} vs ${second}` : "Compare the top trending names",
      first ? `What are the downside risks for ${first}?` : "What are the downside risks for the top trending stock?",
      "Which sectors have the strongest momentum now?",
    ];
  }
  if (intent === "risk_explanation") {
    return [
      "What is the main market risk right now?",
      "Which sectors look most defensive now?",
      "Show stocks with lower downside risk",
    ];
  }
  if (intent === "portfolio_advice") {
    return [
      "Where is my concentration risk highest?",
      "How can I diversify this portfolio?",
      "Which holdings look weakest right now?",
    ];
  }
  if (pairLabel) {
    return [
      `Compare ${pairLabel}`,
      `What are the downside risks for ${pairLabel}?`,
      `Which is the stronger setup right now: ${pairLabel}?`,
    ];
  }
  return [
    "What stocks are trending today?",
    "Summarize today’s market sentiment",
    "Show bullish large-cap ideas",
  ];
}

export function formatAssistantResponse(raw = {}) {
  const confidenceSplit =
    raw.confidence_split ||
    raw.answer_schema?.confidence_split ||
    ((raw.data_confidence || raw.reasoning_confidence || raw.answer_schema?.data_confidence || raw.answer_schema?.reasoning_confidence)
      ? {
          data_confidence: raw.data_confidence || raw.answer_schema?.data_confidence || null,
          reasoning_confidence: raw.reasoning_confidence || raw.answer_schema?.reasoning_confidence || null,
        }
      : null);
  return {
    intent: raw.intent || "unclear_query",
    intentCategory: raw.intent_category || "",
    analysisType: raw.analysis_type || "",
    analysisEngine: raw.analysis_engine || "",
    text: raw.answer || "I could not generate a reliable answer right now.",
    confidence: Number(raw.confidence || raw.answer_schema?.confidence || 0),
    sources: Array.isArray(raw.sources) ? raw.sources : [],
    charts: raw.charts || null,
    warning: raw.warning || "",
    dataValidation: raw.data_validation || raw.answer_schema?.data_coverage || null,
    summary: raw.summary || null,
    schema: raw.answer_schema || null,
    followups: Array.isArray(raw.followups) ? raw.followups : [],
    status: raw.status || null,
    confidenceSplit,
  };
}
