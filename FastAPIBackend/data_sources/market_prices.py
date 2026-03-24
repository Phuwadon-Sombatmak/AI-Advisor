from __future__ import annotations

import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
import yfinance as yf


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in ("", None):
            return None
        parsed = float(value)
        if math.isnan(parsed) or math.isinf(parsed):
            return None
        return parsed
    except Exception:
        return None


def _is_valid_price(value: Any) -> bool:
    parsed = _safe_float(value)
    return parsed is not None and parsed > 0


def _history_return_pct(history: List[Dict[str, Any]]) -> Optional[float]:
    if len(history) < 2:
        return None
    first = _safe_float(history[0].get("close"))
    last = _safe_float(history[-1].get("close"))
    if not _is_valid_price(first) or not _is_valid_price(last):
        return None
    return ((last / first) - 1.0) * 100.0


def _moving_average(closes: List[float], window: int) -> Optional[float]:
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / float(window)


def _compute_rsi(closes: List[float], window: int = 14) -> Optional[float]:
    if len(closes) < window + 1:
        return None
    gains: List[float] = []
    losses: List[float] = []
    for idx in range(1, len(closes)):
        delta = closes[idx] - closes[idx - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[-window:]) / window
    avg_loss = sum(losses[-window:]) / window
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _normalize_history(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for row in rows or []:
        close = _safe_float(row.get("close"))
        if close is None or close <= 0:
            continue
        cleaned.append(
            {
                "date": str(row.get("date") or ""),
                "open": _safe_float(row.get("open")) or close,
                "high": _safe_float(row.get("high")) or close,
                "low": _safe_float(row.get("low")) or close,
                "close": close,
                "volume": int(float(row.get("volume") or 0)),
            }
        )
    return cleaned


def _decorate_history(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = _normalize_history(rows)
    closes = [float(row["close"]) for row in rows]
    for idx, row in enumerate(rows):
        subset = closes[: idx + 1]
        row["sma20"] = _moving_average(subset, 20)
        row["sma50"] = _moving_average(subset, 50)
        row["rsi"] = _compute_rsi(subset)
    return rows


def _parse_yfinance_history(ticker: str, range_value: str) -> Tuple[List[Dict[str, Any]], str]:
    interval = "1d"
    period = str(range_value or "3mo").lower()
    intraday = False
    if period == "1d":
        interval = "5m"
        intraday = True
    elif period == "5d":
        interval = "30m"
        intraday = True
    history = yf.Ticker(ticker).history(
        period=period,
        interval=interval,
        auto_adjust=False,
        prepost=False,
        actions=False,
    )
    close_field = "Close"
    if not intraday and "Adj Close" in history.columns:
        close_field = "Adj Close"
    rows: List[Dict[str, Any]] = []
    for idx, record in history.iterrows():
        rows.append(
            {
                "date": idx.strftime("%Y-%m-%d %H:%M") if intraday else idx.strftime("%Y-%m-%d"),
                "open": _safe_float(record.get("Open")),
                "high": _safe_float(record.get("High")),
                "low": _safe_float(record.get("Low")),
                "close": _safe_float(record.get(close_field)),
                "volume": int(record.get("Volume") or 0),
            }
        )
    return rows, period


@dataclass
class ProviderResult:
    symbol: str
    source: str
    status: str
    timestamp: str
    price: Optional[float]
    previous_close: Optional[float]
    volume: Optional[float]
    history: List[Dict[str, Any]]
    confidence: int
    technicals: Dict[str, Any]
    meta: Dict[str, Any]


class UltimateMarketDataEngine:
    def __init__(
        self,
        *,
        session: requests.Session,
        alpha_vantage_api_key: Optional[str] = None,
        finnhub_api_key: Optional[str] = None,
        polygon_api_key: Optional[str] = None,
        fmp_api_key: Optional[str] = None,
        twelvedata_api_key: Optional[str] = None,
        cache_ttl_seconds: int = 600,
        timeout_seconds: float = 2.0,
        finnhub_quote_fetcher: Optional[Callable[[str], Dict[str, Any]]] = None,
        finnhub_history_fetcher: Optional[Callable[[str, str], Tuple[List[Dict[str, Any]], str]]] = None,
        alpha_quote_fetcher: Optional[Callable[[str], Dict[str, Any]]] = None,
        alpha_history_fetcher: Optional[Callable[[str, str], Tuple[List[Dict[str, Any]], str]]] = None,
        polygon_quote_fetcher: Optional[Callable[[str], Dict[str, Any]]] = None,
        polygon_history_fetcher: Optional[Callable[[str, str], Tuple[List[Dict[str, Any]], str]]] = None,
        fmp_quote_fetcher: Optional[Callable[[str], Dict[str, Any]]] = None,
        fmp_history_fetcher: Optional[Callable[[str, str], Tuple[List[Dict[str, Any]], str]]] = None,
        yfinance_history_fetcher: Optional[Callable[[str, str], Tuple[List[Dict[str, Any]], str]]] = None,
        yfinance_previous_close_fetcher: Optional[Callable[[str], float]] = None,
        symbol_variants_fetcher: Optional[Callable[[str], List[str]]] = None,
        log_func: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.session = session
        self.alpha_vantage_api_key = alpha_vantage_api_key
        self.finnhub_api_key = finnhub_api_key
        self.polygon_api_key = polygon_api_key
        self.fmp_api_key = fmp_api_key
        self.twelvedata_api_key = twelvedata_api_key
        self.cache_ttl_seconds = cache_ttl_seconds
        self.timeout_seconds = timeout_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = threading.Lock()
        self._finnhub_quote_fetcher = finnhub_quote_fetcher
        self._finnhub_history_fetcher = finnhub_history_fetcher
        self._alpha_quote_fetcher = alpha_quote_fetcher
        self._alpha_history_fetcher = alpha_history_fetcher
        self._polygon_quote_fetcher = polygon_quote_fetcher
        self._polygon_history_fetcher = polygon_history_fetcher
        self._fmp_quote_fetcher = fmp_quote_fetcher
        self._fmp_history_fetcher = fmp_history_fetcher
        self._yfinance_history_fetcher = yfinance_history_fetcher or _parse_yfinance_history
        self._yfinance_previous_close_fetcher = yfinance_previous_close_fetcher
        self._symbol_variants_fetcher = symbol_variants_fetcher or (lambda symbol: [symbol])
        self._log = log_func or (lambda message: None)

    def _log_info(self, message: str) -> None:
        self._log(f"[INFO] {message}")

    def _log_fail(self, message: str) -> None:
        self._log(f"[FAIL] {message}")

    def _log_success(self, message: str) -> None:
        self._log(f"[SUCCESS] {message}")

    def _cache_key(self, symbol: str, range_value: str) -> str:
        return f"{str(symbol).upper().strip()}::{str(range_value or '3mo').lower().strip()}"

    def _cache_get(self, symbol: str, range_value: str) -> Optional[ProviderResult]:
        key = self._cache_key(symbol, range_value)
        with self._cache_lock:
            cached = self._cache.get(key)
        if not cached:
            return None
        age_seconds = time.time() - float(cached.get("ts", 0))
        if age_seconds >= self.cache_ttl_seconds:
            return None
        payload = dict(cached["payload"])
        payload["confidence"] = 80
        payload["status"] = "cached"
        payload["meta"] = {
            **dict(payload.get("meta") or {}),
            "cached_age_minutes": round(age_seconds / 60.0, 1),
            "cache_ttl_seconds": self.cache_ttl_seconds,
        }
        return ProviderResult(**payload)

    def _cache_get_stale(self, symbol: str, range_value: str) -> Optional[ProviderResult]:
        key = self._cache_key(symbol, range_value)
        with self._cache_lock:
            cached = self._cache.get(key)
        if not cached:
            return None
        age_seconds = time.time() - float(cached.get("ts", 0))
        payload = dict(cached["payload"])
        payload["confidence"] = 80 if age_seconds <= self.cache_ttl_seconds else 50
        payload["status"] = "cached"
        payload["meta"] = {
            **dict(payload.get("meta") or {}),
            "cached_age_minutes": round(age_seconds / 60.0, 1),
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "stale_cache_used": age_seconds > self.cache_ttl_seconds,
        }
        return ProviderResult(**payload)

    def _cache_set(self, symbol: str, range_value: str, result: ProviderResult) -> None:
        key = self._cache_key(symbol, range_value)
        with self._cache_lock:
            self._cache[key] = {
                "ts": time.time(),
                "payload": {
                    "symbol": result.symbol,
                    "source": result.source,
                    "status": result.status,
                    "timestamp": result.timestamp,
                    "price": result.price,
                    "previous_close": result.previous_close,
                    "volume": result.volume,
                    "history": result.history,
                    "confidence": result.confidence,
                    "technicals": result.technicals,
                    "meta": result.meta,
                },
            }

    def _validate_payload(self, price: Any, history: List[Dict[str, Any]]) -> bool:
        if not _is_valid_price(price):
            return False
        return bool(_normalize_history(history))

    def _build_result(
        self,
        *,
        symbol: str,
        source: str,
        price: Any,
        previous_close: Any,
        history: List[Dict[str, Any]],
        volume: Any = None,
        confidence: int = 100,
        status: str = "live",
    ) -> ProviderResult:
        rows = _decorate_history(history)
        closes = [float(row["close"]) for row in rows]
        sma20 = _moving_average(closes, 20)
        sma50 = _moving_average(closes, 50)
        rsi = _compute_rsi(closes)
        final_volume = _safe_float(volume)
        if final_volume is None and rows:
            final_volume = _safe_float(rows[-1].get("volume"))
        return ProviderResult(
            symbol=symbol,
            source=source,
            status=status,
            timestamp=datetime.utcnow().isoformat() + "Z",
            price=_safe_float(price),
            previous_close=_safe_float(previous_close),
            volume=final_volume,
            history=rows,
            confidence=confidence,
            technicals={
                "rsi": round(rsi, 2) if rsi is not None else None,
                "sma20": round(sma20, 2) if sma20 is not None else None,
                "sma50": round(sma50, 2) if sma50 is not None else None,
            },
            meta={},
        )

    def _prices_deviate(self, left: Optional[float], right: Optional[float]) -> bool:
        if not _is_valid_price(left) or not _is_valid_price(right):
            return False
        base = max(min(left, right), 1e-9)
        deviation = abs(left - right) / base
        return deviation > 0.10

    def _fetch_yfinance(self, symbol: str, range_value: str) -> ProviderResult:
        self._log_info(f"Trying yfinance for {symbol}")
        last_error = None
        for variant in self._symbol_variants_fetcher(symbol):
            try:
                history, _ = self._yfinance_history_fetcher(variant, range_value)
                rows = _normalize_history(history)
                if not rows:
                    raise RuntimeError("yfinance returned empty history")
                previous_close = None
                if self._yfinance_previous_close_fetcher:
                    previous_close = self._yfinance_previous_close_fetcher(variant)
                result = self._build_result(
                    symbol=symbol,
                    source="yfinance",
                    price=rows[-1]["close"],
                    previous_close=previous_close or (rows[-2]["close"] if len(rows) > 1 else rows[-1]["close"]),
                    history=rows,
                    volume=rows[-1].get("volume"),
                    confidence=100,
                )
                self._log_success(f"yfinance returned price for {symbol}")
                return result
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"yfinance failed for {symbol}: {last_error}")

    def _fetch_finnhub(self, symbol: str, range_value: str) -> ProviderResult:
        if not self._finnhub_quote_fetcher or not self._finnhub_history_fetcher:
            raise RuntimeError("Finnhub fetchers not configured")
        self._log_info(f"Trying Finnhub for {symbol}")
        quote = self._finnhub_quote_fetcher(symbol)
        history, _ = self._finnhub_history_fetcher(symbol, range_value)
        result = self._build_result(
            symbol=symbol,
            source="finnhub",
            price=quote.get("c") or quote.get("price"),
            previous_close=quote.get("pc") or quote.get("previous_close"),
            history=history,
            volume=(history[-1].get("volume") if history else None),
            confidence=95,
        )
        self._log_success(f"Finnhub returned price for {symbol}")
        return result

    def _fetch_alpha_vantage(self, symbol: str, range_value: str) -> ProviderResult:
        if not self._alpha_quote_fetcher or not self._alpha_history_fetcher:
            raise RuntimeError("Alpha Vantage fetchers not configured")
        self._log_info(f"Trying Alpha Vantage for {symbol}")
        quote = self._alpha_quote_fetcher(symbol)
        history, _ = self._alpha_history_fetcher(symbol, range_value)
        result = self._build_result(
            symbol=symbol,
            source="alpha_vantage",
            price=quote.get("price"),
            previous_close=quote.get("previous_close"),
            history=history,
            volume=(history[-1].get("volume") if history else None),
            confidence=90,
        )
        self._log_success(f"Alpha Vantage returned price for {symbol}")
        return result

    def _fetch_polygon(self, symbol: str, range_value: str) -> ProviderResult:
        if not self._polygon_quote_fetcher or not self._polygon_history_fetcher:
            raise RuntimeError("Polygon fetchers not configured")
        self._log_info(f"Trying Polygon for {symbol}")
        quote = self._polygon_quote_fetcher(symbol)
        history, _ = self._polygon_history_fetcher(symbol, range_value)
        result = self._build_result(
            symbol=symbol,
            source="polygon",
            price=quote.get("price"),
            previous_close=quote.get("previous_close"),
            history=history,
            volume=(history[-1].get("volume") if history else None),
            confidence=92,
        )
        self._log_success(f"Polygon returned price for {symbol}")
        return result

    def _fetch_fmp(self, symbol: str, range_value: str) -> ProviderResult:
        if not self._fmp_quote_fetcher or not self._fmp_history_fetcher:
            raise RuntimeError("FMP fetchers not configured")
        self._log_info(f"Trying FMP for {symbol}")
        quote = self._fmp_quote_fetcher(symbol)
        history, _ = self._fmp_history_fetcher(symbol, range_value)
        result = self._build_result(
            symbol=symbol,
            source="fmp",
            price=quote.get("price"),
            previous_close=quote.get("previous_close"),
            history=history,
            volume=(history[-1].get("volume") if history else None),
            confidence=88,
        )
        self._log_success(f"FMP returned price for {symbol}")
        return result

    def _fetch_twelvedata_indicators(self, symbol: str) -> Dict[str, Any]:
        if not self.twelvedata_api_key:
            raise RuntimeError("TwelveData API key not configured")
        self._log_info(f"Trying TwelveData indicators for {symbol}")
        base = "https://api.twelvedata.com"
        rsi_payload = self.session.get(
            f"{base}/rsi",
            params={"symbol": symbol, "interval": "1day", "time_period": 14, "apikey": self.twelvedata_api_key, "outputsize": 1},
            timeout=self.timeout_seconds,
        ).json()
        sma_payload = self.session.get(
            f"{base}/sma",
            params={"symbol": symbol, "interval": "1day", "time_period": 50, "apikey": self.twelvedata_api_key, "outputsize": 1},
            timeout=self.timeout_seconds,
        ).json()
        return {
            "rsi": _safe_float(((rsi_payload.get("values") or [{}])[0]).get("rsi")),
            "sma50": _safe_float(((sma_payload.get("values") or [{}])[0]).get("sma")),
        }

    def get_market_data(self, symbol: str, range_value: str = "3mo") -> Dict[str, Any]:
        fresh_cached = self._cache_get(symbol, range_value)
        if fresh_cached is not None:
            return self.to_dict(fresh_cached)

        primary_error = None
        try:
            primary = self._fetch_yfinance(symbol, range_value)
            self._cache_set(symbol, range_value, primary)
            return self.to_dict(primary)
        except Exception as exc:
            primary_error = exc
            self._log_fail(str(exc))

        secondary_fetchers = [self._fetch_finnhub, self._fetch_polygon]
        secondary_results: List[ProviderResult] = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(fetcher, symbol, range_value): fetcher.__name__ for fetcher in secondary_fetchers}
            for future in as_completed(futures, timeout=max(self.timeout_seconds * 2, 2.5)):
                try:
                    result = future.result(timeout=self.timeout_seconds)
                    secondary_results.append(result)
                except Exception as exc:
                    self._log_fail(f"{futures[future]} failed for {symbol}: {exc}")

        verified_secondary = self._pick_verified_result(primary=None, candidates=secondary_results)
        if verified_secondary is not None:
            self._cache_set(symbol, range_value, verified_secondary)
            return self.to_dict(verified_secondary)

        tertiary_fetchers = [self._fetch_alpha_vantage, self._fetch_fmp]
        tertiary_results: List[ProviderResult] = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(fetcher, symbol, range_value): fetcher.__name__ for fetcher in tertiary_fetchers}
            for future in as_completed(futures, timeout=max(self.timeout_seconds * 2, 2.5)):
                try:
                    result = future.result(timeout=self.timeout_seconds)
                    tertiary_results.append(result)
                except Exception as exc:
                    self._log_fail(f"{futures[future]} failed for {symbol}: {exc}")

        verified_tertiary = self._pick_verified_result(primary=None, candidates=secondary_results + tertiary_results)
        if verified_tertiary is not None:
            try:
                indicators = self._fetch_twelvedata_indicators(symbol)
                verified_tertiary.technicals = {
                    **verified_tertiary.technicals,
                    **{k: v for k, v in indicators.items() if v is not None},
                }
            except Exception as exc:
                self._log_fail(f"TwelveData indicators failed for {symbol}: {exc}")
            self._cache_set(symbol, range_value, verified_tertiary)
            return self.to_dict(verified_tertiary)

        stale_cached = self._cache_get_stale(symbol, range_value)
        if stale_cached is not None:
            self._log_info(f"Using cached data for {symbol}")
            return self.to_dict(stale_cached)

        self._log_fail(f"All providers failed for {symbol}: {primary_error}")
        return {
            "symbol": symbol,
            "status": "data_unavailable",
            "message": "Market data temporarily unavailable",
            "confidence": 0,
            "source": None,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "price": None,
            "volume": None,
            "history": [],
            "technicals": {
                "rsi": None,
                "sma20": None,
                "sma50": None,
            },
            "meta": {
                "providers_tried": ["yfinance", "finnhub", "polygon", "alpha_vantage", "fmp", "twelvedata", "cache"],
            },
        }

    def _pick_verified_result(self, primary: Optional[ProviderResult], candidates: List[ProviderResult]) -> Optional[ProviderResult]:
        valid_candidates = [candidate for candidate in candidates if self._validate_payload(candidate.price, candidate.history)]
        if not valid_candidates:
            return None
        if len(valid_candidates) == 1:
            return valid_candidates[0]
        baseline = valid_candidates[0]
        for candidate in valid_candidates[1:]:
            if not self._prices_deviate(baseline.price, candidate.price):
                preferred = baseline if baseline.confidence >= candidate.confidence else candidate
                preferred.meta = {
                    **preferred.meta,
                    "cross_verified_with": [baseline.source, candidate.source],
                }
                return preferred
        return max(valid_candidates, key=lambda item: item.confidence)

    @staticmethod
    def to_dict(result: ProviderResult) -> Dict[str, Any]:
        return {
            "symbol": result.symbol,
            "price": result.price,
            "source": result.source,
            "status": result.status,
            "timestamp": result.timestamp,
            "confidence": result.confidence,
            "previous_close": result.previous_close,
            "volume": result.volume,
            "history": result.history,
            "technicals": result.technicals,
            "meta": result.meta,
        }
