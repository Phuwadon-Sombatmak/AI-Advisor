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
  const sentiment = summary.market_sentiment || "Neutral";
  const score = summary.fear_greed_score ?? "-";
  const sector = summary.trending_sector || "Technology";
  const risk = summary.risk_outlook || "Medium";
  return `Market ${sentiment} (${score}) • Sector ${sector} • Risk ${risk}`;
}

export function getFollowupPrompts(intent = "unclear_query", schema = {}, fallback = []) {
  if (Array.isArray(fallback) && fallback.length) return fallback.slice(0, 4);
  const symbol = schema?.ticker || "";
  const sector = schema?.sector_stock_picker?.sector || schema?.sector || "";
  if (intent === "stock_comparison") {
    return [
      "Show valuation and risk difference",
      "Which is better for short-term momentum?",
      "What are the downside risks?",
    ];
  }
  if (intent === "single_stock_analysis" && symbol) {
    return [
      `Compare ${symbol} vs AMD`,
      `What are the downside risks for ${symbol}?`,
      `Show related ideas to ${symbol}`,
    ];
  }
  if (intent === "sector_stock_picker") {
    return [
      `Compare top names in ${sector || "this sector"}`,
      `Show lower-risk stocks in ${sector || "this sector"}`,
      `Which ${sector || "sector"} names have bullish sentiment?`,
    ];
  }
  if (intent === "sector_explanation") {
    return [
      `Show top momentum stocks in ${sector || "this sector"}`,
      `What risks could weaken ${sector || "this sector"}?`,
      `Is ${sector || "this sector"} still attractive overall?`,
    ];
  }
  if (intent === "market_overview" || intent === "risk_explanation") {
    return [
      "What sectors have strong momentum?",
      "What are the biggest market risks now?",
      "Show bullish large-cap ideas",
    ];
  }
  if (intent === "portfolio_advice") {
    return [
      "How can I reduce portfolio concentration risk?",
      "Suggest defensive allocations",
      "Which holdings are weakest by momentum?",
    ];
  }
  return [
    "What stocks are trending today?",
    "Summarize today’s market sentiment",
    "Show bullish large-cap ideas",
  ];
}

export function formatAssistantResponse(raw = {}) {
  return {
    intent: raw.intent || "unclear_query",
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
  };
}
