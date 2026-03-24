from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def safe_float(value: Any) -> Optional[float]:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def close_series(history: Iterable[Dict[str, Any]]) -> List[float]:
    return [safe_float(row.get("close")) for row in history if safe_float(row.get("close")) not in (None, 0)]


def compute_return_pct(first_close: Optional[float], last_close: Optional[float]) -> Optional[float]:
    if first_close in (None, 0) or last_close is None:
        return None
    return ((last_close - first_close) / first_close) * 100.0


def moving_average(closes: List[float], window: int) -> Optional[float]:
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / float(window)


def compute_rsi(closes: List[float], period: int = 14) -> Optional[float]:
    if len(closes) <= period:
        return None
    gains: List[float] = []
    losses: List[float] = []
    for index in range(1, len(closes)):
        change = closes[index] - closes[index - 1]
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _ema(series: List[float], window: int) -> Optional[float]:
    if len(series) < window:
        return None
    multiplier = 2 / float(window + 1)
    ema = sum(series[:window]) / float(window)
    for value in series[window:]:
        ema = (value - ema) * multiplier + ema
    return ema


def compute_macd(closes: List[float]) -> Dict[str, Optional[float]]:
    fast = _ema(closes, 12)
    slow = _ema(closes, 26)
    if fast is None or slow is None:
        return {"macd": None, "signal": None}
    macd = fast - slow
    macd_series: List[float] = []
    for idx in range(26, len(closes) + 1):
        fast_i = _ema(closes[:idx], 12)
        slow_i = _ema(closes[:idx], 26)
        if fast_i is not None and slow_i is not None:
            macd_series.append(fast_i - slow_i)
    signal = _ema(macd_series, 9) if len(macd_series) >= 9 else None
    return {"macd": macd, "signal": signal}


def classify_trend(ma50: Optional[float], ma200: Optional[float], rsi: Optional[float], macd: Optional[float], signal: Optional[float]) -> str:
    bullish_signals = 0
    bearish_signals = 0
    if ma50 is not None and ma200 is not None:
        if ma50 > ma200:
            bullish_signals += 1
        elif ma50 < ma200:
            bearish_signals += 1
    if rsi is not None:
        if rsi >= 55:
            bullish_signals += 1
        elif rsi <= 45:
            bearish_signals += 1
    if macd is not None and signal is not None:
        if macd > signal:
            bullish_signals += 1
        elif macd < signal:
            bearish_signals += 1
    if bullish_signals > bearish_signals:
        return "Bullish"
    if bearish_signals > bullish_signals:
        return "Bearish"
    return "Neutral"


def classify_momentum(return_30d: Optional[float], return_90d: Optional[float], relative_strength: Optional[float]) -> str:
    score = momentum_score(return_30d, return_90d, relative_strength)
    if score >= 70:
        return "Strong"
    if score >= 45:
        return "Moderate"
    return "Weak"


def momentum_score(return_30d: Optional[float], return_90d: Optional[float], relative_strength: Optional[float]) -> float:
    components: List[float] = []
    if return_30d is not None:
        components.append(max(0.0, min(100.0, (return_30d + 20.0) / 40.0 * 100.0)))
    if return_90d is not None:
        components.append(max(0.0, min(100.0, (return_90d + 25.0) / 50.0 * 100.0)))
    if relative_strength is not None:
        components.append(max(0.0, min(100.0, (relative_strength + 15.0) / 30.0 * 100.0)))
    if not components:
        return 0.0
    return round(sum(components) / len(components), 2)


def technical_score(rsi: Optional[float], macd: Optional[float], signal: Optional[float], ma50: Optional[float], ma200: Optional[float]) -> float:
    score = 50.0
    if rsi is not None:
        if 45 <= rsi <= 65:
            score += 10
        elif rsi > 70 or rsi < 30:
            score -= 10
    if macd is not None and signal is not None:
        score += 12 if macd > signal else -12
    if ma50 is not None and ma200 is not None:
        score += 15 if ma50 > ma200 else -15
    return round(max(0.0, min(100.0, score)), 1)

