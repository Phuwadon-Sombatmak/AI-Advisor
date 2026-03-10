import React, { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import FearGreedGauge from "./FearGreedGauge";
import SentimentIndicators from "./SentimentIndicators";

const sentimentLabel = (score) => {
  if (score <= 24) return "Extreme Fear";
  if (score <= 44) return "Fear";
  if (score <= 55) return "Neutral";
  if (score <= 74) return "Greed";
  return "Extreme Greed";
};

const sentimentDescription = (score) => {
  if (score < 25) return "sentDesc1";
  if (score < 50) return "sentDesc2";
  if (score < 65) return "sentDesc3";
  if (score < 80) return "sentDesc4";
  return "sentDesc5";
};

const ENDPOINTS = [
  "/api-fastapi/api/market-sentiment",
  "/api-fastapi/market-sentiment",
  "http://localhost:8000/api/market-sentiment",
  "http://localhost:8000/market-sentiment",
];

async function fetchSentiment() {
  let lastError = null;
  for (const endpoint of ENDPOINTS) {
    try {
      const res = await fetch(endpoint);
      if (!res.ok) {
        lastError = new Error(`HTTP ${res.status}`);
        continue;
      }
      return await res.json();
    } catch (e) {
      lastError = e;
    }
  }
  throw lastError || new Error("Failed to fetch market sentiment");
}

export default function MarketSentiment({ dark = false }) {
  const { t } = useTranslation();
  const [score, setScore] = useState(50);
  const [apiSentiment, setApiSentiment] = useState("Neutral");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rawIndicators, setRawIndicators] = useState({
    momentum: 50,
    strength: 50,
    volatility: 50,
    safeHaven: 50,
  });

  useEffect(() => {
    let mounted = true;
    const run = async () => {
      setLoading(true);
      setError("");
      try {
        const data = await fetchSentiment();
        if (!mounted) return;
        setScore(Math.max(0, Math.min(100, Number(data.score) || 50)));
        setApiSentiment(String(data.sentiment || "Neutral"));
        setRawIndicators({
          momentum: Number(data.indicators?.momentum ?? 50),
          strength: Number(data.indicators?.strength ?? 50),
          volatility: Number(data.indicators?.volatility ?? 50),
          safeHaven: Number(data.indicators?.safeHaven ?? 50),
        });
      } catch {
        if (!mounted) return;
        setError(t("sentimentFallback"));
      } finally {
        if (mounted) setLoading(false);
      }
    };
    run();
    const timer = setInterval(run, 10 * 60 * 1000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const label = sentimentLabel(score);
  const sentimentMap = {
    Fear: t("fearFear"),
    Greed: t("fearGreed"),
    Neutral: t("neutral"),
    "Extreme Fear": t("fearExtremeFear"),
    "Extreme Greed": t("fearExtremeGreed"),
  };
  const description = t(sentimentDescription(score));
  const indicators = useMemo(
    () => [
      { label: t("indicatorMomentum"), value: rawIndicators.momentum },
      { label: t("indicatorStrength"), value: rawIndicators.strength },
      { label: t("indicatorVolatility"), value: rawIndicators.volatility },
      { label: t("indicatorSafeHaven"), value: rawIndicators.safeHaven },
    ],
    [rawIndicators, t]
  );

  return (
    <section
      className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-[20px] border p-6 shadow-lg transition-all hover:shadow-xl`}
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-2xl font-bold`}>{t("marketSentiment")}</h3>
          <p className="text-slate-500 mt-1">{t("fearGreedIndex")}</p>
          <div className="mt-4">
            <FearGreedGauge value={score} dark={dark} />
          </div>
          <p className={`${dark ? "text-slate-200" : "text-slate-700"} mt-2 font-semibold`}>
            {t("sentiment")}: {loading ? t("loadingReco") : sentimentMap[apiSentiment] || sentimentMap[label] || apiSentiment}
          </p>
          <p className="text-slate-500 mt-1 text-sm">{description}</p>
          {error ? <p className="text-xs text-amber-600 mt-2">{error}</p> : null}
        </div>

        <div>
          <h4 className={`${dark ? "text-slate-100" : "text-slate-900"} text-lg font-bold mb-4`}>{t("indicators")}</h4>
          <SentimentIndicators indicators={indicators} dark={dark} />
        </div>
      </div>
    </section>
  );
}
