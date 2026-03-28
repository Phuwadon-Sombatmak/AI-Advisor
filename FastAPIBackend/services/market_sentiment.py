from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
import json

import pandas as pd
import yfinance as yf
import requests
import os

CACHE_TTL = timedelta(minutes=10)
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY") or os.getenv("FINNHUB_TOKEN")
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

_cache_data: Dict[str, Any] = {"expires_at": datetime.min, "payload": None}

MARKET_BREADTH_UNIVERSE: List[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "XOM", "JNJ",
    "PG", "UNH", "V", "MA", "HD", "BAC", "AVGO", "LLY", "PFE", "KO",
    "PEP", "MRK", "CSCO", "WMT", "INTC", "CVX", "DIS", "ADBE", "CRM", "NFLX",
]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _regime_history_file() -> Path:
    return _project_root() / "qa" / "results" / "regime_history.jsonl"


def _append_regime_history(payload: Dict[str, Any]) -> None:
    try:
        indicators = payload.get("indicators") or {}
        row = {
            "timestamp": payload.get("updated_at") or (datetime.utcnow().isoformat() + "Z"),
            "regime": payload.get("regime"),
            "confidence": payload.get("confidence"),
            "sentiment_score": payload.get("sentiment_score"),
            "sentiment_label": payload.get("sentiment_label"),
            "cnn_reference_score": payload.get("cnn_reference_score"),
            "cnn_divergence": payload.get("cnn_divergence"),
            "momentum": indicators.get("momentum"),
            "strength": indicators.get("strength"),
            "volatility": indicators.get("volatility"),
            "safe_haven": indicators.get("safeHaven"),
        }
        path = _regime_history_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(v)))


def scale_linear(value: float, min_value: float, max_value: float) -> float:
    if max_value == min_value:
        return 50.0
    normalized = (value - min_value) / (max_value - min_value)
    return clamp(normalized * 100.0)


def compute_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)
    avg_gain = gains.rolling(period).mean()
    avg_loss = losses.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    last = rsi.dropna()
    if last.empty:
        return 50.0
    return float(last.iloc[-1])


def sentiment_label(score: float) -> str:
    if score <= 24:
        return "Extreme Fear"
    if score <= 44:
        return "Fear"
    if score <= 55:
        return "Neutral"
    if score <= 74:
        return "Greed"
    return "Extreme Greed"


def _invert_score(value: float) -> float:
    return clamp(100.0 - float(value))


def compute_market_regime(momentum: float, strength: float, volatility: float) -> str:
    momentum = float(momentum)
    strength = float(strength)
    volatility = float(volatility)
    if momentum < 30.0 and strength < 30.0:
        return "Risk-Off"
    if volatility <= 60.0 and momentum < 40.0 and strength < 45.0:
        return "Late Risk-Off"
    if volatility > 70.0 and momentum < 40.0:
        return "Risk-Off"
    if float(momentum) > 60.0 and float(strength) > 60.0:
        return "Risk-On"
    return "Neutral"


def _regime_confidence(regime: str, momentum: float, strength: float, volatility: float, safe_haven: float) -> str:
    aligned = 0
    if regime == "Risk-Off":
        aligned += 1 if float(momentum) < 30.0 else 0
        aligned += 1 if float(strength) < 30.0 else 0
        aligned += 1 if float(momentum) < 40.0 else 0
        aligned += 1 if float(safe_haven) > 60.0 else 0
    elif regime == "Late Risk-Off":
        aligned += 1 if float(volatility) <= 60.0 else 0
        aligned += 1 if float(momentum) < 40.0 else 0
        aligned += 1 if float(strength) < 45.0 else 0
        aligned += 1 if float(safe_haven) >= 50.0 else 0
    elif regime == "Risk-On":
        aligned += 1 if float(momentum) > 60.0 else 0
        aligned += 1 if float(strength) > 60.0 else 0
        aligned += 1 if float(volatility) < 45.0 else 0
        aligned += 1 if float(safe_haven) < 45.0 else 0
    else:
        aligned += 1 if 40.0 <= float(momentum) <= 60.0 else 0
        aligned += 1 if 40.0 <= float(strength) <= 60.0 else 0
        aligned += 1 if 35.0 <= float(volatility) <= 65.0 else 0
        aligned += 1 if 35.0 <= float(safe_haven) <= 65.0 else 0

    if aligned >= 3:
        return "high"
    if aligned >= 2:
        return "medium"
    return "low"


def _build_positioning(regime: str) -> Dict[str, Any]:
    if regime == "Risk-Off":
        return {
            "overweight": ["Energy", "Utilities", "Consumer Staples"],
            "neutral": ["Healthcare", "Financials"],
            "underweight": ["Technology", "Growth"],
            "suggested_etfs": ["XLP", "XLV", "XLE"],
        }
    if regime == "Late Risk-Off":
        return {
            "overweight": ["Utilities", "Consumer Staples", "Healthcare"],
            "neutral": ["Energy", "Financials"],
            "underweight": ["Technology"],
            "suggested_etfs": ["XLP", "XLV", "XLE"],
        }
    if regime == "Risk-On":
        return {
            "overweight": ["Technology", "Semiconductors"],
            "neutral": ["Financials", "Industrials"],
            "underweight": ["Defensive"],
            "suggested_etfs": ["QQQ", "XLK", "SOXX"],
        }
    return {
        "overweight": ["Balanced allocation"],
        "neutral": ["Technology", "Healthcare", "Industrials"],
        "underweight": ["High-beta Growth"],
        "suggested_etfs": ["SPY", "XLI"],
    }


def _regime_interpretation(regime: str) -> str:
    if regime == "Risk-Off":
        return "Momentum and breadth are both weak, so market conditions remain clearly defensive."
    if regime == "Late Risk-Off":
        return "Volatility calming does not imply bullish recovery when momentum and breadth remain weak."
    if regime == "Risk-On":
        return "Momentum and breadth are strong enough to support a pro-risk posture."
    return "Signals are mixed, so a balanced allocation remains the default posture."


def _extract_number(node: Any) -> float:
    if node is None:
        return -1.0
    if isinstance(node, (int, float)):
        return float(node)
    if isinstance(node, str):
        try:
            return float(node.strip())
        except Exception:
            return -1.0
    if isinstance(node, dict):
        preferred = [
            "score", "value", "now", "current", "currentScore", "fear_and_greed", "fearGreed",
            "fear_and_greed_index", "fearGreedIndex", "y", "ratingScore",
        ]
        for key in preferred:
            if key in node:
                v = _extract_number(node.get(key))
                if 0.0 <= v <= 100.0:
                    return v
        for v in node.values():
            out = _extract_number(v)
            if 0.0 <= out <= 100.0:
                return out
    if isinstance(node, list):
        for item in reversed(node):
            out = _extract_number(item)
            if 0.0 <= out <= 100.0:
                return out
    return -1.0


def _extract_label(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        s = node.strip().lower()
        if "extreme fear" in s:
            return "Extreme Fear"
        if "fear" in s and "extreme" not in s:
            return "Fear"
        if "extreme greed" in s:
            return "Extreme Greed"
        if "greed" in s and "extreme" not in s:
            return "Greed"
        if "neutral" in s:
            return "Neutral"
        return ""
    if isinstance(node, dict):
        for key in ["rating", "label", "status", "sentiment", "name"]:
            if key in node:
                out = _extract_label(node.get(key))
                if out:
                    return out
        for v in node.values():
            out = _extract_label(v)
            if out:
                return out
    if isinstance(node, list):
        for item in reversed(node):
            out = _extract_label(item)
            if out:
                return out
    return ""


def _fetch_cnn_fear_greed(timeout_sec: int = 8) -> Dict[str, Any]:
    # CNN endpoints can change; try multiple patterns and parse defensively.
    urls = [
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata/",
        "https://production.dataviz.cnn.io/index/fearandgreed/index",
        "https://edition.cnn.com/markets/fear-and-greed",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AIInvest/1.0; +https://localhost)",
        "Accept": "application/json,text/html,*/*",
    }

    last_error = None
    for url in urls:
        try:
            res = requests.get(url, timeout=timeout_sec, headers=headers)
            if res.status_code != 200:
                continue
            content_type = str(res.headers.get("content-type", "")).lower()
            payload = None
            if "application/json" in content_type:
                payload = res.json()
            else:
                # Some responses embed JSON in HTML; find first large JSON-looking block.
                text = res.text or ""
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    snippet = text[start:end + 1]
                    try:
                        payload = requests.models.complexjson.loads(snippet)
                    except Exception:
                        payload = None
            if payload is None:
                continue

            score = _extract_number(payload)
            if not (0.0 <= score <= 100.0):
                continue
            label = _extract_label(payload) or sentiment_label(score)
            return {
                "ok": True,
                "score": int(round(score)),
                "sentiment": label,
                "source": "CNN Fear & Greed Index",
                "raw": payload,
                "fetched_at": datetime.utcnow().isoformat() + "Z",
                "endpoint": url,
            }
        except Exception as e:
            last_error = str(e)
            continue
    return {"ok": False, "error": last_error or "cnn fetch failed"}


def _download_close(ticker: str, period: str = "1y", interval: str = "1d") -> pd.Series:
    df = yf.download(ticker, period=period, interval=interval, auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise ValueError(f"No data for {ticker}")

    close = None
    if isinstance(df.columns, pd.MultiIndex):
        if "Close" in df.columns.get_level_values(0):
            close = df["Close"]
    elif "Close" in df.columns:
        close = df["Close"]

    if close is None:
        raise ValueError(f"No close series for {ticker}")

    if isinstance(close, pd.DataFrame):
        if close.shape[1] == 0:
            raise ValueError(f"No close columns for {ticker}")
        close = close.iloc[:, 0]

    return close.dropna()


def _download_close_finnhub(symbol: str, days: int = 400, resolution: str = "D") -> pd.Series:
    if not FINNHUB_API_KEY:
        raise ValueError("missing finnhub key")
    now = datetime.utcnow()
    from_ts = int((now - timedelta(days=days)).timestamp())
    to_ts = int(now.timestamp())
    res = requests.get(
        f"{FINNHUB_BASE_URL}/stock/candle",
        params={
            "symbol": symbol,
            "resolution": resolution,
            "from": from_ts,
            "to": to_ts,
            "token": FINNHUB_API_KEY,
        },
        timeout=10,
    )
    if res.status_code != 200:
        raise ValueError(f"finnhub status {res.status_code}")
    data = res.json()
    if not isinstance(data, dict) or data.get("s") != "ok":
        raise ValueError(f"finnhub candle not ok for {symbol}")
    close = [float(x) for x in data.get("c", []) if x is not None]
    if len(close) < 2:
        raise ValueError(f"insufficient finnhub data for {symbol}")
    return pd.Series(close).dropna()


def _sp500_close_series() -> pd.Series:
    # Use Finnhub as primary (as requested), fallback to yfinance if symbol unsupported.
    for symbol in ["^GSPC", "SPY"]:
        try:
            return _download_close_finnhub(symbol, days=420, resolution="D")
        except Exception:
            continue
    return _download_close("^GSPC", period="1y")


def _vix_close_series() -> pd.Series:
    for symbol in ["^VIX", "VIX"]:
        try:
            return _download_close_finnhub(symbol, days=420, resolution="D")
        except Exception:
            continue
    return _download_close("^VIX", period="1y")


def _treasury_close_series() -> pd.Series:
    # TLT used as liquid treasury bond proxy.
    for symbol in ["TLT", "IEF"]:
        try:
            return _download_close_finnhub(symbol, days=420, resolution="D")
        except Exception:
            continue
    return _download_close("TLT", period="1y")


def _market_momentum(spx_close: pd.Series) -> float:
    current = float(spx_close.iloc[-1])
    ma_125 = float(spx_close.rolling(125).mean().dropna().iloc[-1])
    pct_diff = ((current - ma_125) / ma_125) * 100.0
    return scale_linear(pct_diff, -10.0, 10.0)


def _stock_price_strength() -> float:
    # Percent of stocks above their MA50 (market breadth strength)
    df = yf.download(MARKET_BREADTH_UNIVERSE, period="6mo", interval="1d", auto_adjust=False, progress=False)
    if df is None or df.empty:
        return 50.0

    close = df.get("Close")
    if close is None or close.empty:
        return 50.0

    if isinstance(close, pd.Series):
        ma50 = close.rolling(50).mean()
        if ma50.dropna().empty:
            return 50.0
        return 100.0 if float(close.iloc[-1]) > float(ma50.iloc[-1]) else 0.0

    if len(close) < 55:
        return 50.0

    ma50 = close.rolling(50).mean()
    latest_close = close.iloc[-1]
    latest_ma50 = ma50.iloc[-1]
    mask = latest_close.notna() & latest_ma50.notna()
    if int(mask.sum()) == 0:
        return 50.0

    above = int((latest_close[mask] > latest_ma50[mask]).sum())
    total = int(mask.sum())
    return clamp((above / max(total, 1)) * 100.0)


def _market_volatility(vix_close: pd.Series) -> float:
    current = float(vix_close.iloc[-1])
    ma_50 = float(vix_close.rolling(50).mean().dropna().iloc[-1])
    ratio = current / ma_50 if ma_50 else 1.0
    # Higher VIX relative to its average means more fear / volatility demand.
    return scale_linear(ratio, 0.7, 1.5)


def _safe_haven_demand(spx_close: pd.Series, tnx_close: pd.Series) -> float:
    spx_ret20 = float(spx_close.pct_change(20).dropna().iloc[-1]) * 100.0
    tnx_ret20 = float(tnx_close.pct_change(20).dropna().iloc[-1]) * 100.0
    spread = spx_ret20 - tnx_ret20
    # Higher safe-haven demand means Treasuries outperform equities.
    return scale_linear(-spread, -5.0, 5.0)


def _market_trend(spx_close: pd.Series) -> float:
    rsi = compute_rsi(spx_close, 14)
    return clamp(rsi)


def _compute_internal_indicators(now: datetime) -> Dict[str, Any]:
    spx = None
    vix = None
    tnx = None
    try:
        spx = _sp500_close_series()
    except Exception:
        spx = None
    try:
        vix = _vix_close_series()
    except Exception:
        vix = None
    try:
        tnx = _treasury_close_series()
    except Exception:
        tnx = None

    try:
        momentum = _market_momentum(spx) if spx is not None and len(spx) >= 130 else 50.0
    except Exception:
        momentum = 50.0
    try:
        strength = _stock_price_strength()
    except Exception:
        strength = 50.0
    try:
        volatility = _market_volatility(vix) if vix is not None and len(vix) >= 60 else 50.0
    except Exception:
        volatility = 50.0
    try:
        safe_haven = _safe_haven_demand(spx, tnx) if spx is not None and tnx is not None and len(spx) >= 25 and len(tnx) >= 25 else 50.0
    except Exception:
        safe_haven = 50.0

    sentiment_score = (
        (0.35 * momentum)
        + (0.25 * strength)
        + (0.25 * _invert_score(safe_haven))
        + (0.15 * _invert_score(volatility))
    )
    sentiment_score = int(round(clamp(sentiment_score)))
    regime = compute_market_regime(momentum, strength, volatility)
    confidence = _regime_confidence(regime, momentum, strength, volatility, safe_haven)
    positioning = _build_positioning(regime)

    return {
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_label(sentiment_score),
        "score": sentiment_score,
        "sentiment": sentiment_label(sentiment_score),
        "updated_at": now.isoformat() + "Z",
        "source": "InternalModel",
        "indicators": {
            "momentum": round(momentum),
            "strength": round(strength),
            "volatility": round(volatility),
            "safeHaven": round(safe_haven),
        },
        "weights": {
            "momentum": 0.35,
            "strength": 0.25,
            "safe_haven_inverse": 0.25,
            "volatility_inverse": 0.15,
        },
        "regime": regime,
        "confidence": confidence,
        "regime_interpretation": _regime_interpretation(regime),
        "positioning": {
            "overweight": positioning["overweight"],
            "neutral": positioning["neutral"],
            "underweight": positioning["underweight"],
        },
        "suggested_etfs": positioning["suggested_etfs"],
        "cnn_reference": {
            "score": None,
            "divergence": None,
        },
        "cnn_reference_score": None,
        "cnn_divergence": None,
        "methodology": {
            "mode": "internal_model_primary",
            "benchmark": "SP500 (Finnhub primary)",
            "momentum": "SP500 vs MA125",
            "strength": "% breadth universe above MA50",
            "volatility": "VIX relative to 50D average (fear metric; higher = more volatility)",
            "safe_haven": "Treasury proxy outperformance vs SP500 over 20D (fear metric; higher = more flight-to-safety)",
            "headline_score": "0.35*momentum + 0.25*strength + 0.25*(100-safe_haven) + 0.15*(100-volatility)",
            "regime_note": "Volatility calming does not imply bullish recovery when momentum and breadth remain weak.",
        },
    }


def compute_market_sentiment(force_refresh: bool = False) -> Dict[str, Any]:
    now = datetime.utcnow()
    if not force_refresh and _cache_data["payload"] is not None and now < _cache_data["expires_at"]:
        return _cache_data["payload"]

    internal_payload = None
    try:
        internal_payload = _compute_internal_indicators(now)
    except Exception:
        internal_payload = None

    cnn = _fetch_cnn_fear_greed()
    if internal_payload is None:
        raise ValueError("Unable to compute market sentiment from CNN and internal model")

    payload = dict(internal_payload)
    if cnn.get("ok"):
        cnn_score = int(clamp(cnn.get("score", 50)))
        divergence = int(round(float(payload["sentiment_score"]) - cnn_score))
        payload["cnn_reference"] = {
            "score": cnn_score,
            "divergence": divergence,
            "label": str(cnn.get("sentiment") or sentiment_label(cnn_score)),
            "fetched_at": cnn.get("fetched_at"),
            "endpoint": cnn.get("endpoint"),
        }
        payload["cnn_reference_score"] = cnn_score
        payload["cnn_divergence"] = divergence
        payload["source_detail"] = {
            "name": "CNN Fear & Greed Index",
            "endpoint": cnn.get("endpoint"),
            "fetched_at": cnn.get("fetched_at"),
        }
    else:
        payload["cnn_reference"] = {
            "score": None,
            "divergence": None,
            "label": None,
            "fetched_at": None,
            "endpoint": None,
        }
        payload["cnn_reference_score"] = None
        payload["cnn_divergence"] = None

    _cache_data["payload"] = payload
    _cache_data["expires_at"] = now + CACHE_TTL
    _append_regime_history(payload)
    return payload
