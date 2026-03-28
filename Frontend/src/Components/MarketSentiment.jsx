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
];

const hasNumber = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));

const buildIndicatorModel = (t, key, value) => {
  const v = hasNumber(value) ? Math.max(0, Math.min(100, Number(value))) : null;
  const positiveMetric = key === "momentum" || key === "strength";
  const isRiskMetric = !positiveMetric;

  if (v == null) {
    return {
      label: t(key === "momentum" ? "indicatorMomentum" : key === "strength" ? "indicatorStrength" : key === "volatility" ? "indicatorVolatility" : "indicatorSafeHaven"),
      value: null,
      direction: null,
      interpretation: t("dataUnavailable"),
      tooltip: t(`${key}Tooltip`),
      isRiskMetric,
    };
  }

  let direction = "down";
  let interpretation = "";

  if (key === "momentum") {
    direction = v >= 50 ? "up" : "down";
    interpretation = v >= 70 ? t("momentumStrong") : v >= 50 ? t("momentumImproving") : v >= 30 ? t("momentumWeak") : t("momentumBreakdown");
  } else if (key === "strength") {
    direction = v >= 50 ? "up" : "down";
    interpretation = v >= 70 ? t("strengthBroadParticipation") : v >= 50 ? t("strengthConstructive") : v >= 30 ? t("strengthNarrow") : t("strengthWeakBreadth");
  } else if (key === "volatility") {
    direction = v >= 50 ? "up" : "down";
    interpretation = v >= 70 ? t("volatilityRiskSpike") : v >= 50 ? t("volatilityElevated") : v >= 30 ? t("volatilityCooling") : t("volatilityCalm");
  } else if (key === "safeHaven") {
    direction = v >= 50 ? "up" : "down";
    interpretation = v >= 70 ? t("safeHavenDefensiveRush") : v >= 50 ? t("safeHavenDefensiveBid") : v >= 30 ? t("safeHavenEasing") : t("safeHavenRiskOn");
  }

  return {
    label: t(key === "momentum" ? "indicatorMomentum" : key === "strength" ? "indicatorStrength" : key === "volatility" ? "indicatorVolatility" : "indicatorSafeHaven"),
    value: v,
    direction,
    interpretation,
    tooltip: t(`${key}Tooltip`),
    isRiskMetric,
  };
};

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
  const [score, setScore] = useState(null);
  const [apiSentiment, setApiSentiment] = useState("");
  const [cnnReference, setCnnReference] = useState({
    score: null,
    divergence: null,
  });
  const [marketPositioning, setMarketPositioning] = useState({
    regime: null,
    confidence: null,
    positioning: {
      overweight: [],
      neutral: [],
      underweight: [],
    },
    suggestedEtfs: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rawIndicators, setRawIndicators] = useState({
    momentum: null,
    strength: null,
    volatility: null,
    safeHaven: null,
  });

  useEffect(() => {
    let mounted = true;
    const run = async () => {
      setLoading(true);
      setError("");
      try {
        const data = await fetchSentiment();
        if (!mounted) return;
        const nextScore = Number(data.sentiment_score ?? data.score);
        setScore(Number.isFinite(nextScore) ? Math.max(0, Math.min(100, nextScore)) : null);
        setApiSentiment(String(data.sentiment_label || data.sentiment || ""));
        setCnnReference({
          score: Number.isFinite(Number(data.cnn_reference?.score)) ? Number(data.cnn_reference.score) : null,
          divergence: Number.isFinite(Number(data.cnn_reference?.divergence)) ? Number(data.cnn_reference.divergence) : null,
        });
        setMarketPositioning({
          regime: String(data.regime || ""),
          confidence: String(data.confidence || ""),
          positioning: {
            overweight: Array.isArray(data.positioning?.overweight) ? data.positioning.overweight : [],
            neutral: Array.isArray(data.positioning?.neutral) ? data.positioning.neutral : [],
            underweight: Array.isArray(data.positioning?.underweight) ? data.positioning.underweight : [],
          },
          suggestedEtfs: Array.isArray(data.suggested_etfs) ? data.suggested_etfs : [],
        });
        setRawIndicators({
          momentum: Number.isFinite(Number(data.indicators?.momentum)) ? Number(data.indicators?.momentum) : null,
          strength: Number.isFinite(Number(data.indicators?.strength)) ? Number(data.indicators?.strength) : null,
          volatility: Number.isFinite(Number(data.indicators?.volatility)) ? Number(data.indicators?.volatility) : null,
          safeHaven: Number.isFinite(Number(data.indicators?.safeHaven)) ? Number(data.indicators?.safeHaven) : null,
        });
        setError(data.status === "degraded" ? (data.message || t("marketDataUnavailable")) : "");
      } catch {
        if (!mounted) return;
        setScore(null);
        setApiSentiment("");
        setCnnReference({ score: null, divergence: null });
        setMarketPositioning({
          regime: null,
          confidence: null,
          positioning: {
            overweight: [],
            neutral: [],
            underweight: [],
          },
          suggestedEtfs: [],
        });
        setRawIndicators({
          momentum: null,
          strength: null,
          volatility: null,
          safeHaven: null,
        });
        setError(t("marketDataUnavailable"));
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

  const label = score != null ? sentimentLabel(score) : null;
  const sentimentMap = {
    Fear: t("fearFear"),
    Greed: t("fearGreed"),
    Neutral: t("neutral"),
    "Extreme Fear": t("fearExtremeFear"),
    "Extreme Greed": t("fearExtremeGreed"),
  };
  const description = t(sentimentDescription(score));
  const divergenceWarning = Number.isFinite(Number(cnnReference.divergence)) && Math.abs(Number(cnnReference.divergence)) > 15;
  const indicators = useMemo(
    () => [
      buildIndicatorModel(t, "momentum", rawIndicators.momentum),
      buildIndicatorModel(t, "strength", rawIndicators.strength),
      buildIndicatorModel(t, "volatility", rawIndicators.volatility),
      buildIndicatorModel(t, "safeHaven", rawIndicators.safeHaven),
    ],
    [rawIndicators, t]
  );
  const divergenceText = useMemo(() => {
    const divergence = Number(cnnReference.divergence);
    if (!Number.isFinite(divergence)) return "";
    if (divergence > 10) return t("cnnDivergenceLessBearish");
    if (divergence < -10) return t("cnnDivergenceMoreBearish");
    return t("cnnDivergenceAligned");
  }, [cnnReference.divergence, t]);
  const keyDrivers = useMemo(() => {
    const bullets = [];
    const momentum = Number(rawIndicators.momentum);
    const strength = Number(rawIndicators.strength);
    const volatility = Number(rawIndicators.volatility);
    const safeHaven = Number(rawIndicators.safeHaven);

    if (Number.isFinite(momentum) && Number.isFinite(strength) && momentum < 40 && strength < 40) {
      bullets.push(t("driverWeakMomentumBreadth"));
    } else if (Number.isFinite(momentum) && momentum >= 60) {
      bullets.push(t("driverMomentumSupportive"));
    }

    if (Number.isFinite(volatility) && volatility >= 60) {
      bullets.push(t("driverVolatilityRiskOff"));
    } else if (Number.isFinite(volatility) && volatility <= 35) {
      bullets.push(t("driverVolatilityContained"));
    }

    if (Number.isFinite(safeHaven) && safeHaven >= 60) {
      bullets.push(t("driverSafeHavenDefensive"));
    } else if (Number.isFinite(safeHaven) && safeHaven <= 35) {
      bullets.push(t("driverSafeHavenRiskOn"));
    }

    if (!bullets.length && Number.isFinite(strength) && strength >= 55) {
      bullets.push(t("driverBreadthHolding"));
    }

    return bullets.slice(0, 4);
  }, [rawIndicators, t]);
  const positioningUi = useMemo(() => {
    const regime = String(marketPositioning.regime || "").toLowerCase();
    const label =
      regime === "risk-off"
        ? t("regimeRiskOff")
        : regime === "risk-on"
          ? t("regimeRiskOn")
          : regime === "neutral"
            ? t("regimeNeutral")
            : t("dataUnavailable");
    const badgeClass =
      regime === "risk-off"
        ? "bg-red-50 text-red-700 border-red-200"
        : regime === "risk-on"
          ? "bg-emerald-50 text-emerald-700 border-emerald-200"
          : "bg-slate-100 text-slate-700 border-slate-200";
    return {
      label,
      badgeClass,
      confidence: marketPositioning.confidence ? t(`confidence${String(marketPositioning.confidence).charAt(0).toUpperCase()}${String(marketPositioning.confidence).slice(1)}`) : t("dataUnavailable"),
      positioning: marketPositioning.positioning,
      etfs: marketPositioning.suggestedEtfs,
    };
  }, [marketPositioning, t]);

  return (
    <section
      className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-[20px] border p-6 shadow-lg transition-all hover:shadow-xl`}
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <div className="flex items-start justify-between gap-3">
            <div>
              <h3
                className={`${dark ? "text-slate-100" : "text-slate-900"} text-2xl font-bold`}
                title={t("marketSentimentTooltip")}
              >
                {t("marketSentimentModel")}
              </h3>
              <p className="text-slate-500 mt-1">{t("fearGreedIndex")}</p>
            </div>
            <div
              className={`${dark ? "bg-slate-800 text-slate-300 border-slate-700" : "bg-slate-50 text-slate-600 border-slate-200"} rounded-full border px-3 py-1 text-xs font-semibold whitespace-nowrap`}
              title={t("cnnReferenceTooltip")}
            >
              {t("cnnReferenceLabel")}: {loading ? "..." : (cnnReference.score ?? t("dataUnavailable"))}
            </div>
          </div>
          <div className="mt-4">
            {score != null ? (
              <FearGreedGauge value={score} dark={dark} />
            ) : (
              <div className={`${dark ? "bg-slate-900 text-slate-400 border-slate-700" : "bg-slate-50 text-slate-500 border-slate-200"} rounded-2xl border p-8 text-center text-sm font-medium`}>
                {loading ? t("loadingReco") : t("marketDataUnavailable")}
              </div>
            )}
          </div>
          <p className={`${dark ? "text-slate-200" : "text-slate-700"} mt-2 font-semibold`}>
            {t("sentiment")}: {loading ? t("loadingReco") : (sentimentMap[apiSentiment] || (label ? sentimentMap[label] : null) || t("dataUnavailable"))}
          </p>
          <p className="text-slate-500 mt-1 text-sm">{score != null ? description : t("marketDataUnavailable")}</p>
          {cnnReference.score != null ? (
            <p className={`${dark ? "text-slate-400" : "text-slate-500"} mt-2 text-xs`}>
              {t("cnnReferenceLabel")}: {cnnReference.score} {t("cnnReferenceSuffix")} {divergenceText}
            </p>
          ) : null}
          {divergenceWarning ? (
            <p className="text-xs text-amber-600 mt-2">{t("marketSentimentDivergenceWarning")}</p>
          ) : null}
          {error ? <p className="text-xs text-amber-600 mt-2">{error}</p> : null}
        </div>

        <div>
          <h4 className={`${dark ? "text-slate-100" : "text-slate-900"} text-lg font-bold mb-4`}>{t("indicators")}</h4>
          <SentimentIndicators indicators={indicators} dark={dark} />
        </div>
      </div>
      <div className="mt-6">
        <h4 className={`${dark ? "text-slate-100" : "text-slate-900"} text-lg font-bold mb-3`}>{t("keyDrivers")}</h4>
        {keyDrivers.length ? (
          <ul className={`space-y-2 text-sm ${dark ? "text-slate-300" : "text-slate-700"}`}>
            {keyDrivers.map((item) => (
              <li key={item} className="flex items-start gap-2">
                <span className="mt-1 text-sky-500">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className={`text-sm ${dark ? "text-slate-400" : "text-slate-500"}`}>{t("marketDataUnavailable")}</p>
        )}
      </div>
      <div className="mt-6">
        <div className="flex items-center justify-between gap-3 mb-3">
          <h4 className={`${dark ? "text-slate-100" : "text-slate-900"} text-lg font-bold`}>{t("marketPositioning")}</h4>
          <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${positioningUi.badgeClass}`}>
            {positioningUi.label}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-slate-50 border-slate-200"} rounded-2xl border p-4`}>
            <p className={`${dark ? "text-slate-400" : "text-slate-500"} text-xs font-semibold uppercase tracking-wide`}>{t("overweight")}</p>
            <ul className={`mt-2 space-y-2 text-sm ${dark ? "text-slate-200" : "text-slate-700"}`}>
              {positioningUi.positioning.overweight.map((item) => <li key={item}>• {item}</li>)}
            </ul>
          </div>
          <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-slate-50 border-slate-200"} rounded-2xl border p-4`}>
            <p className={`${dark ? "text-slate-400" : "text-slate-500"} text-xs font-semibold uppercase tracking-wide`}>{t("neutralAllocation")}</p>
            <ul className={`mt-2 space-y-2 text-sm ${dark ? "text-slate-200" : "text-slate-700"}`}>
              {positioningUi.positioning.neutral.map((item) => <li key={item}>• {item}</li>)}
            </ul>
          </div>
          <div className={`${dark ? "bg-slate-900 border-slate-700" : "bg-slate-50 border-slate-200"} rounded-2xl border p-4`}>
            <p className={`${dark ? "text-slate-400" : "text-slate-500"} text-xs font-semibold uppercase tracking-wide`}>{t("underweight")}</p>
            <ul className={`mt-2 space-y-2 text-sm ${dark ? "text-slate-200" : "text-slate-700"}`}>
              {positioningUi.positioning.underweight.map((item) => <li key={item}>• {item}</li>)}
            </ul>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <span className={`${dark ? "text-slate-300" : "text-slate-700"} text-sm font-semibold`}>
            {t("confidence")}: {positioningUi.confidence}
          </span>
          <span className={`${dark ? "text-slate-400" : "text-slate-500"} text-sm`}>
            {t("suggestedEtfs")}: {positioningUi.etfs.length ? positioningUi.etfs.join(", ") : t("dataUnavailable")}
          </span>
        </div>
      </div>
    </section>
  );
}
