#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import smtplib
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib import error as urllib_error
from urllib import request as urllib_request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FASTAPI_ROOT = PROJECT_ROOT / "FastAPIBackend"
if str(FASTAPI_ROOT) not in sys.path:
    sys.path.insert(0, str(FASTAPI_ROOT))

try:
    from fastapi.testclient import TestClient
    import yfinance as yf

    import main as fastapi_main
    from ai.intent_detection import IntentDetectionEngine
    from data_sources.market_prices import UltimateMarketDataEngine
except Exception as exc:  # pragma: no cover - script should still explain import failure cleanly
    print(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "fatal_error": str(exc),
                "message": "Validation runner could not import the application. Check Python environment and dependencies.",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    raise


RESULTS_DIR = PROJECT_ROOT / "qa" / "results"
HISTORY_DIR = RESULTS_DIR / "history"
METRICS_FILE = RESULTS_DIR / "metrics.jsonl"
LATEST_FILE = RESULTS_DIR / "latest.json"
ALERTS_FILE = RESULTS_DIR / "alerts.json"
ALERT_HISTORY_LIMIT = 100
ALERT_THRESHOLDS = {
    "pass_rate": {"threshold": 90.0, "severity": "critical", "label": "Test pass rate"},
    "data_accuracy": {"threshold": 95.0, "severity": "warning", "label": "Data accuracy"},
    "ai_reliability": {"threshold": 80.0, "severity": "warning", "label": "AI reliability"},
}

DEFAULT_SYMBOLS = ["AAPL", "NVDA", "MSFT", "TSLA", "KO"]
RECOMMENDATION_SYMBOLS = ["AAPL", "NVDA", "TSLA", "KO", "MSFT"]


@dataclass
class ValidationResult:
    test_id: str
    status: str
    expected: str
    actual: str
    deviation: str
    notes: str


def _result(
    test_id: str,
    passed: bool,
    expected: str,
    actual: str,
    deviation: str = "",
    notes: str = "",
) -> ValidationResult:
    return ValidationResult(
        test_id=test_id,
        status="PASS" if passed else "FAIL",
        expected=expected,
        actual=actual,
        deviation=deviation,
        notes=notes,
    )


def _to_float(value: Any) -> Optional[float]:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def _pct_error(actual: Optional[float], reference: Optional[float]) -> Optional[float]:
    if actual is None or reference is None or reference == 0:
        return None
    return abs(actual - reference) / abs(reference) * 100.0


def _format_pct(value: Optional[float], digits: int = 2) -> str:
    if value is None or math.isnan(value) or math.isinf(value):
        return "n/a"
    return f"{value:.{digits}f}%"


def _format_num(value: Optional[float], digits: int = 4) -> str:
    if value is None or math.isnan(value) or math.isinf(value):
        return "n/a"
    return f"{value:.{digits}f}"


def _test_group(test_id: str) -> str:
    text = str(test_id or "").upper()
    if text.startswith("DATA_"):
        return "data"
    if text.startswith("DECISION_"):
        return "decision"
    if text.startswith("AI_"):
        return "ai"
    if text.startswith("INTENT_"):
        return "intent"
    if text.startswith("RESILIENCE_"):
        return "resilience"
    if text.startswith("FLOW_"):
        return "flow"
    return "other"


def _parse_deviation(value: Any) -> Optional[float]:
    raw = str(value or "").strip().lower()
    if not raw or raw == "n/a":
        return None
    try:
        normalized = (
            raw.replace("%", "")
            .replace("pts", "")
            .replace("point", "")
            .replace("points", "")
            .strip()
        )
        return float(normalized)
    except Exception:
        return None


def _qa_compute_data_accuracy(results: List[Dict[str, Any]]) -> Optional[float]:
    data_results = [row for row in results if _test_group(row.get("test_id")) == "data"]
    if not data_results:
        return None
    score = 100.0
    failures = sum(1 for row in data_results if str(row.get("status")).upper() != "PASS")
    score -= failures * 12.5
    deviations = [_parse_deviation(row.get("deviation")) for row in data_results]
    numeric_deviations = [value for value in deviations if value is not None]
    if numeric_deviations:
        score -= min(sum(numeric_deviations) / len(numeric_deviations), 20.0)
    return round(max(0.0, min(100.0, score)), 1)


def _qa_compute_ai_reliability(results: List[Dict[str, Any]]) -> Optional[float]:
    ai_results = [
        row for row in results
        if _test_group(row.get("test_id")) in {"decision", "ai", "intent"}
    ]
    if not ai_results:
        return None
    passed = sum(1 for row in ai_results if str(row.get("status")).upper() == "PASS")
    return round((passed / len(ai_results)) * 100.0, 1)


def _safe_json_read(path: Path) -> Any:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_jsonl_read(path: Path, limit: int = 500) -> List[Dict[str, Any]]:
    try:
        if not path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = str(line or "").strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows[-limit:]
    except Exception:
        return []


def _metric_below_threshold(row: Dict[str, Any], metric_key: str, threshold: float) -> bool:
    value = _to_float(row.get(metric_key))
    return value is not None and value < threshold


def _load_alert_state() -> Dict[str, Any]:
    payload = _safe_json_read(ALERTS_FILE)
    if isinstance(payload, dict):
        return payload
    return {"active": {}, "history": []}


def _save_alert_state(payload: Dict[str, Any]) -> None:
    ALERTS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _to_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _is_muted(alert: Dict[str, Any], reference_time: Optional[datetime] = None) -> bool:
    muted_until = _to_datetime(alert.get("muted_until"))
    if muted_until is None:
        return False
    current = reference_time or datetime.now(UTC).astimezone(muted_until.tzinfo)
    return muted_until > current


def _dispatch_slack_alert(alert: Dict[str, Any]) -> None:
    webhook = str(os.getenv("QA_ALERT_SLACK_WEBHOOK") or "").strip()
    if not webhook:
        return
    body = {
        "text": f"[QA Alert] {alert['state']} - {alert['label']} at {alert['value']}% (threshold {alert['threshold']}%)",
    }
    req = urllib_request.Request(
        webhook,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib_request.urlopen(req, timeout=5).read()
    except Exception:
        return


def _dispatch_email_alert(alert: Dict[str, Any]) -> None:
    smtp_host = str(os.getenv("QA_ALERT_SMTP_HOST") or "").strip()
    smtp_port = int(str(os.getenv("QA_ALERT_SMTP_PORT") or "587"))
    smtp_user = str(os.getenv("QA_ALERT_SMTP_USER") or "").strip()
    smtp_password = str(os.getenv("QA_ALERT_SMTP_PASSWORD") or "").strip()
    sender = str(os.getenv("QA_ALERT_EMAIL_FROM") or smtp_user).strip()
    recipient = str(os.getenv("QA_ALERT_EMAIL_TO") or "").strip()
    if not smtp_host or not sender or not recipient:
        return
    message = EmailMessage()
    message["Subject"] = f"[QA Alert] {alert['state']} - {alert['label']}"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"{alert['label']} is {alert['state']}.\n"
        f"Metric: {alert['metric']}\n"
        f"Value: {alert['value']}%\n"
        f"Threshold: {alert['threshold']}%\n"
        f"Timestamp: {alert['timestamp']}\n"
    )
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=5) as server:
            if smtp_user and smtp_password:
                server.starttls()
                server.login(smtp_user, smtp_password)
            server.send_message(message)
    except Exception:
        return


def _dispatch_alert_integrations(alert: Dict[str, Any]) -> None:
    _dispatch_slack_alert(alert)
    _dispatch_email_alert(alert)


def _evaluate_alerts(metrics_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    state = _load_alert_state()
    active = dict(state.get("active") or {})
    history = list(state.get("history") or [])
    latest = metrics_rows[-1] if metrics_rows else None
    previous = metrics_rows[-2] if len(metrics_rows) > 1 else None
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    for metric_key, config in ALERT_THRESHOLDS.items():
        threshold = config["threshold"]
        label = config["label"]
        persisted = active.get(metric_key)
        latest_below = bool(latest and _metric_below_threshold(latest, metric_key, threshold))
        previous_below = bool(previous and _metric_below_threshold(previous, metric_key, threshold))
        should_activate = latest_below and previous_below

        latest_value = _to_float(latest.get(metric_key)) if latest else None

        if should_activate and not persisted:
            alert = {
                "id": metric_key,
                "metric": metric_key,
                "label": label,
                "state": "ACTIVE",
                "severity": config["severity"],
                "threshold": threshold,
                "value": latest_value,
                "timestamp": latest.get("generated_at") if latest else now_iso,
                "triggered_at": now_iso,
                "resolved_at": None,
                "acknowledged": False,
                "acknowledged_by": None,
                "acknowledged_at": None,
                "muted_until": None,
            }
            active[metric_key] = alert
            history.append(dict(alert))
            if not _is_muted(alert):
                _dispatch_alert_integrations(alert)
        elif persisted and not latest_below:
            resolved = dict(persisted)
            resolved["state"] = "RESOLVED"
            resolved["value"] = latest_value
            resolved["timestamp"] = latest.get("generated_at") if latest else now_iso
            resolved["resolved_at"] = now_iso
            history.append(dict(resolved))
            active.pop(metric_key, None)
            if not _is_muted(resolved):
                _dispatch_alert_integrations(resolved)
        elif persisted:
            persisted["value"] = latest_value
            persisted["timestamp"] = latest.get("generated_at") if latest else now_iso
            active[metric_key] = persisted

    history = history[-ALERT_HISTORY_LIMIT:]
    payload = {"active": active, "history": history, "updated_at": now_iso}
    _save_alert_state(payload)
    return payload


def _normalize_recommendation(label: Any) -> str:
    text = str(label or "").strip()
    lower = text.lower()
    if lower.startswith("hold"):
        return "Hold"
    if "strong buy" in lower:
        return "Strong Buy"
    if lower == "buy":
        return "Buy"
    if "strong sell" in lower:
        return "Strong Sell"
    if lower == "sell":
        return "Sell"
    return text or "Unknown"


def _history_closes(history_rows: Iterable[Dict[str, Any]]) -> List[float]:
    closes: List[float] = []
    for row in history_rows:
        close = _to_float(row.get("close") if "close" in row else row.get("price"))
        if close is not None and close > 0:
            closes.append(close)
    return closes


def _moving_average(closes: List[float], window: int) -> Optional[float]:
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / float(window)


def _compute_rsi(closes: List[float], period: int = 14) -> Optional[float]:
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


def _compute_macd(closes: List[float]) -> Tuple[Optional[float], Optional[float]]:
    fast = _ema(closes, 12)
    slow = _ema(closes, 26)
    if fast is None or slow is None:
        return None, None
    macd = fast - slow
    macd_series: List[float] = []
    for idx in range(26, len(closes) + 1):
        fast_i = _ema(closes[:idx], 12)
        slow_i = _ema(closes[:idx], 26)
        if fast_i is not None and slow_i is not None:
            macd_series.append(fast_i - slow_i)
    signal = _ema(macd_series, 9) if len(macd_series) >= 9 else None
    return macd, signal


def _calculate_adjusted_total_return(df: Any) -> Optional[float]:
    if df is None or getattr(df, "empty", True):
        return None
    close_column = "Adj Close" if "Adj Close" in getattr(df, "columns", []) else "Close"
    if close_column not in df.columns:
        return None
    series = df[close_column].dropna()
    if len(series) < 2:
        return None
    first = float(series.iloc[0])
    last = float(series.iloc[-1])
    if first <= 0 or last <= 0:
        return None
    return (last / first - 1.0) * 100.0


def _reference_price(symbol: str) -> Tuple[Optional[float], str]:
    try:
        ticker = yf.Ticker(symbol)
        fast_info = getattr(ticker, "fast_info", None)
        if fast_info:
            for key in ("lastPrice", "last_price", "regularMarketPrice"):
                price = _to_float(getattr(fast_info, key, None) if not isinstance(fast_info, dict) else fast_info.get(key))
                if price and price > 0:
                    return price, f"yfinance.fast_info.{key}"
        for period, interval in [("1d", "1m"), ("5d", "1d")]:
            df = ticker.history(period=period, interval=interval, auto_adjust=False, prepost=False)
            if not df.empty:
                close = _to_float(df["Close"].dropna().iloc[-1])
                if close and close > 0:
                    return close, f"yfinance.history({period},{interval})"
    except Exception as exc:
        return None, f"reference error: {exc}"
    return None, "reference unavailable"


def _expected_recommendation(payload: Dict[str, Any]) -> str:
    upside = _to_float(payload.get("upside_pct"))
    technical = _to_float((payload.get("signals") or {}).get("technical_score"))
    momentum = _to_float((payload.get("signals") or {}).get("momentum_score"))
    forecast = _to_float((payload.get("signals") or {}).get("forecast_30d_pct"))
    news_dist = payload.get("news_sentiment_distribution") or {}
    bearish_pct = _to_float(news_dist.get("bearish"))
    bullish_pct = _to_float(news_dist.get("bullish"))
    sentiment_bearish = bearish_pct is not None and bullish_pct is not None and bearish_pct > bullish_pct
    indicators = payload.get("technical_indicators") or {}
    macd = _to_float(indicators.get("macd"))
    macd_signal = _to_float(indicators.get("macd_signal"))
    ma50 = _to_float(indicators.get("ma50"))
    ma200 = _to_float(indicators.get("ma200"))
    technical_bullish = bool(
        technical is not None and technical > 65
        and macd is not None and macd_signal is not None and macd > macd_signal
        and ma50 is not None and ma200 is not None and ma50 > ma200
    )
    technical_bearish = bool(
        technical is not None and technical < 40
        and macd is not None and macd_signal is not None and macd < macd_signal
        and ma50 is not None and ma200 is not None and ma50 < ma200
    )
    technical_very_bearish = bool(
        technical is not None and technical < 30
        and macd is not None and macd_signal is not None and macd < macd_signal
        and ma50 is not None and ma200 is not None and ma50 < ma200
    )
    momentum_positive = momentum is not None and momentum > 60
    momentum_very_negative = momentum is not None and momentum < 30
    forecast_positive = forecast is not None and forecast > 0
    forecast_negative = forecast is not None and forecast < 0
    forecast_very_negative = forecast is not None and forecast < -20

    bullish_flags = [
        upside is not None and upside > 15,
        technical is not None and technical >= 55,
        momentum is not None and momentum >= 50,
        forecast is not None and forecast > 0,
        bullish_pct is not None and bullish_pct >= 55,
    ]
    bearish_flags = [
        upside is not None and upside < 15,
        technical is not None and technical < 45,
        momentum is not None and momentum < 45,
        forecast is not None and forecast < 0,
        bearish_pct is not None and bearish_pct >= 50,
    ]
    bullish_count = sum(1 for flag in bullish_flags if flag)
    bearish_count = sum(1 for flag in bearish_flags if flag)

    if upside is not None and upside > 30 and technical is not None and technical > 65 and momentum_positive and forecast_positive:
        return "Strong Buy"
    if forecast_very_negative and technical_very_bearish and momentum_very_negative and sentiment_bearish and not (upside is not None and upside > 25):
        return "Strong Sell"
    if upside is not None and upside > 25 and technical_bearish and forecast_negative:
        return "Hold"
    if upside is not None and upside < 15 and technical is not None and technical < 40 and forecast_negative and not (upside is not None and upside > 25):
        return "Sell"
    if upside is not None and 15 <= upside <= 30 and not technical_bearish and not forecast_very_negative:
        return "Buy"
    if bullish_count > 0 and bearish_count > 0:
        return "Hold"
    if bearish_count >= 4:
        return "Strong Sell"
    if technical_bearish and forecast_negative:
        return "Sell"
    return "Hold"


class ValidationRunner:
    def __init__(self) -> None:
        self.client = TestClient(fastapi_main.app)
        self.intent_engine = IntentDetectionEngine()
        self.results: List[ValidationResult] = []

    def add(self, result: ValidationResult) -> None:
        self.results.append(result)

    def _get_json(self, path: str, *, params: Optional[Dict[str, Any]] = None) -> Tuple[int, Any]:
        response = self.client.get(path, params=params)
        try:
            payload = response.json()
        except Exception:
            payload = response.text
        return response.status_code, payload

    def _post_json(self, path: str, *, payload: Dict[str, Any]) -> Tuple[int, Any]:
        response = self.client.post(path, json=payload)
        try:
            body = response.json()
        except Exception:
            body = response.text
        return response.status_code, body

    def run(self) -> List[ValidationResult]:
        self.run_data_integrity_tests()
        self.run_decision_engine_tests()
        self.run_ai_response_tests()
        self.run_intent_tests()
        self.run_resilience_tests()
        self.run_end_to_end_tests()
        return self.results

    def run_data_integrity_tests(self) -> None:
        for symbol in DEFAULT_SYMBOLS[:3]:
            status, payload = self._get_json(f"/stock/{symbol}", params={"range": "1d"})
            if status != 200 or not isinstance(payload, dict):
                self.add(_result(
                    f"DATA_PRICE_{symbol}",
                    False,
                    "GET /stock/{symbol}?range=1d returns latest price and supports comparison against a reference feed",
                    f"HTTP {status}: {payload}",
                    notes="Endpoint unavailable for price parity validation.",
                ))
                continue
            app_price = _to_float(payload.get("latest_price"))
            ref_price, source_note = _reference_price(symbol)
            deviation = _pct_error(app_price, ref_price)
            passed = deviation is not None and deviation < 0.5
            self.add(_result(
                f"DATA_PRICE_{symbol}",
                passed,
                "Price deviation < 0.5% versus live reference",
                f"App={_format_num(app_price, 2)} Ref={_format_num(ref_price, 2)} Source={source_note}",
                deviation=_format_pct(deviation),
                notes="Latest price parity check against yfinance reference path.",
            ))

        for symbol in ["AAPL", "NVDA"]:
            status, payload = self._get_json(f"/stock/{symbol}", params={"range": "all"})
            if status != 200 or not isinstance(payload, dict):
                self.add(_result(
                    f"DATA_RETURN_{symbol}",
                    False,
                    "Adjusted total return should match reference within ±2%",
                    f"HTTP {status}: {payload}",
                    notes="Stock endpoint did not return payload for ALL return validation.",
                ))
                continue
            app_return = _to_float(payload.get("range_return_pct"))
            try:
                ref_df = yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=False, actions=False)
                ref_return = _calculate_adjusted_total_return(ref_df)
                deviation = abs(app_return - ref_return) if app_return is not None and ref_return is not None else None
                passed = deviation is not None and deviation <= 2.0
                self.add(_result(
                    f"DATA_RETURN_{symbol}",
                    passed,
                    "Total return deviation ≤ ±2 percentage points using adjusted close",
                    f"App={_format_pct(app_return)} Ref={_format_pct(ref_return)}",
                    deviation=f"{deviation:.2f} pts" if deviation is not None else "n/a",
                    notes="Reference uses adjusted close series and full history (period=max).",
                ))
            except Exception as exc:
                self.add(_result(
                    f"DATA_RETURN_{symbol}",
                    False,
                    "Adjusted total return should match reference within ±2%",
                    f"App={_format_pct(app_return)} Reference fetch failed",
                    notes=f"Reference fetch error: {exc}",
                ))

        for symbol in ["AAPL", "NVDA"]:
            stock_status, stock_payload = self._get_json(f"/stock/{symbol}", params={"range": "1y"})
            reco_status, reco_payload = self._get_json("/recommend", params={"symbol": symbol, "window_days": 30})
            if (
                stock_status != 200 or reco_status != 200
                or not isinstance(stock_payload, dict)
                or not isinstance(reco_payload, dict)
                or not reco_payload.get("available")
            ):
                self.add(_result(
                    f"DATA_TECHNICAL_{symbol}",
                    False,
                    "Technical indicators should align with recomputed values from 1Y price history",
                    f"stock={stock_status}, recommend={reco_status}, available={getattr(reco_payload, 'get', lambda *_: None)('available') if isinstance(reco_payload, dict) else 'n/a'}",
                    notes="Could not collect both stock history and recommendation payload.",
                ))
                continue
            closes = _history_closes(stock_payload.get("history") or [])
            ma50 = _moving_average(closes, 50)
            ma200 = _moving_average(closes, 200)
            rsi = _compute_rsi(closes)
            macd, macd_signal = _compute_macd(closes)
            technicals = reco_payload.get("technical_indicators") or {}
            app_ma50 = _to_float(technicals.get("ma50"))
            app_ma200 = _to_float(technicals.get("ma200"))
            app_rsi = _to_float(technicals.get("rsi"))
            app_macd = _to_float(technicals.get("macd"))
            app_signal = _to_float(technicals.get("macd_signal"))
            checks = [
                abs(app_ma50 - ma50) <= max(abs(ma50 or 0) * 0.01, 0.5) if app_ma50 is not None and ma50 is not None else False,
                abs(app_ma200 - ma200) <= max(abs(ma200 or 0) * 0.01, 0.5) if app_ma200 is not None and ma200 is not None else False,
                abs(app_rsi - rsi) <= 2.0 if app_rsi is not None and rsi is not None else False,
                abs(app_macd - macd) <= 0.5 if app_macd is not None and macd is not None else False,
                abs(app_signal - macd_signal) <= 0.5 if app_signal is not None and macd_signal is not None else False,
            ]
            passed = all(checks)
            actual = (
                f"MA50 app/ref={_format_num(app_ma50,2)}/{_format_num(ma50,2)}, "
                f"MA200 app/ref={_format_num(app_ma200,2)}/{_format_num(ma200,2)}, "
                f"RSI app/ref={_format_num(app_rsi,2)}/{_format_num(rsi,2)}, "
                f"MACD app/ref={_format_num(app_macd,4)}/{_format_num(macd,4)}"
            )
            self.add(_result(
                f"DATA_TECHNICAL_{symbol}",
                passed,
                "MA/RSI/MACD values remain internally consistent with recomputation from price history",
                actual,
                notes="Tolerance: MA within 1% or $0.50, RSI within 2 points, MACD within 0.5.",
            ))

    def run_decision_engine_tests(self) -> None:
        for symbol in RECOMMENDATION_SYMBOLS:
            status, payload = self._get_json("/recommend", params={"symbol": symbol, "window_days": 30})
            if status != 200 or not isinstance(payload, dict) or not payload.get("available"):
                self.add(_result(
                    f"DECISION_RECOMMEND_{symbol}",
                    False,
                    "Recommendation endpoint returns a meaningful 5-level decision",
                    f"HTTP {status}: {payload}",
                    notes="Recommendation payload unavailable for decision validation.",
                ))
                continue
            actual = _normalize_recommendation(payload.get("recommendation"))
            expected = _expected_recommendation(payload)
            passed = actual == expected
            signals = payload.get("signals") or {}
            self.add(_result(
                f"DECISION_RECOMMEND_{symbol}",
                passed,
                f"Expected recommendation={expected}",
                (
                    f"Actual={actual}; upside={payload.get('upside_pct')}, "
                    f"technical={signals.get('technical_score')}, "
                    f"momentum={signals.get('momentum_score')}, "
                    f"forecast={signals.get('forecast_30d_pct')}"
                ),
                notes="Normalized Hold subtypes to Hold for 5-level decision parity.",
            ))

        # Explicit conflict-rule coverage using live payloads when present.
        for symbol in RECOMMENDATION_SYMBOLS:
            status, payload = self._get_json("/recommend", params={"symbol": symbol, "window_days": 30})
            if status != 200 or not isinstance(payload, dict) or not payload.get("available"):
                continue
            upside = _to_float(payload.get("upside_pct"))
            forecast = _to_float((payload.get("signals") or {}).get("forecast_30d_pct"))
            technical = _to_float((payload.get("signals") or {}).get("technical_score"))
            indicators = payload.get("technical_indicators") or {}
            macd = _to_float(indicators.get("macd"))
            macd_signal = _to_float(indicators.get("macd_signal"))
            ma50 = _to_float(indicators.get("ma50"))
            ma200 = _to_float(indicators.get("ma200"))
            technical_bearish = bool(
                technical is not None and technical < 40
                and macd is not None and macd_signal is not None and macd < macd_signal
                and ma50 is not None and ma200 is not None and ma50 < ma200
            )
            if upside is not None and upside > 25 and technical_bearish and forecast is not None and forecast < 0:
                actual = _normalize_recommendation(payload.get("recommendation"))
                self.add(_result(
                    f"DECISION_CONFLICT_{symbol}",
                    actual == "Hold",
                    "Conflict rule: upside > 25% but bearish technical + negative forecast => Hold",
                    f"Actual={actual}; upside={upside}, technical={technical}, forecast={forecast}",
                    notes="Conflict case discovered in live payload and validated against rule.",
                ))
                break
        else:
            self.add(_result(
                "DECISION_CONFLICT_COVERAGE",
                True,
                "Conflict rule path should be testable when a live payload matches it",
                "No current live symbol in the sample set matched the conflict pattern",
                notes="This is informational coverage, not a logic failure.",
            ))

    def run_ai_response_tests(self) -> None:
        test_queries = [
            ("AI_STOCK_QUERY", "Is NVDA still a good investment?"),
            ("AI_SECTOR_QUERY", "Show sector momentum ranking"),
            ("AI_MACRO_QUERY_EN", "Iran war effect on market"),
            ("AI_MACRO_QUERY_TH", "สงครามอิหร่านมีผลอะไรกับตลาดหุ้น"),
        ]
        for test_id, question in test_queries:
            status, payload = self._post_json("/api/ai-advisor", payload={"question": question, "context": {}})
            schema = payload.get("answer_schema") if isinstance(payload, dict) else None
            structured = isinstance(schema, dict)
            direct_answer = bool((schema or {}).get("direct_answer"))
            overview = bool((schema or {}).get("overview"))
            rationale = bool((schema or {}).get("rationale") or (schema or {}).get("summary_points"))
            risks = bool((schema or {}).get("risks"))
            actionable = bool((schema or {}).get("actionable_view"))
            passed = status == 200 and structured and direct_answer and overview and rationale and risks and actionable
            self.add(_result(
                test_id,
                passed,
                "AI response includes Overview, Drivers/Rationale, Risks, and Actionable View",
                (
                    f"HTTP {status}; direct_answer={direct_answer}; overview={overview}; "
                    f"rationale={rationale}; risks={risks}; actionable={actionable}"
                ),
                notes=f"Question: {question}",
            ))

    def run_intent_tests(self) -> None:
        cases = [
            ("INTENT_STOCK_EN", "Is NVDA good?", "stock_analysis"),
            ("INTENT_SECTOR_EN", "Show sector momentum ranking", "global_market_query"),
            ("INTENT_SCANNER_TH", "หุ้นตัวไหนกำลังมาแรง", "market_scanner"),
            ("INTENT_RECO_TH", "หุ้นตัวไหนดี", "open_recommendation"),
            ("INTENT_LOW_RISK_TH", "หุ้นอะไรเสี่ยงต่ำ", "stock_recommendation"),
        ]
        for test_id, question, expected_intent in cases:
            intent = self.intent_engine.detect(question)
            self.add(_result(
                test_id,
                intent.intent == expected_intent,
                f"Intent should map to {expected_intent}",
                f"Detected={intent.intent}; entities={intent.entities}; top_n={intent.top_n}",
                notes=f"Question: {question}",
            ))

    def run_resilience_tests(self) -> None:
        logs: List[str] = []
        engine = UltimateMarketDataEngine(
            session=fastapi_main.session,
            timeout_seconds=0.1,
            finnhub_quote_fetcher=lambda symbol: (_ for _ in ()).throw(RuntimeError("finnhub down")),
            finnhub_history_fetcher=lambda symbol, range_value: (_ for _ in ()).throw(RuntimeError("finnhub down")),
            alpha_quote_fetcher=lambda symbol: (_ for _ in ()).throw(RuntimeError("alpha down")),
            alpha_history_fetcher=lambda symbol, range_value: (_ for _ in ()).throw(RuntimeError("alpha down")),
            polygon_quote_fetcher=lambda symbol: (_ for _ in ()).throw(RuntimeError("polygon down")),
            polygon_history_fetcher=lambda symbol, range_value: (_ for _ in ()).throw(RuntimeError("polygon down")),
            fmp_quote_fetcher=lambda symbol: (_ for _ in ()).throw(RuntimeError("fmp down")),
            fmp_history_fetcher=lambda symbol, range_value: (_ for _ in ()).throw(RuntimeError("fmp down")),
            yfinance_history_fetcher=lambda symbol, range_value: (_ for _ in ()).throw(RuntimeError("yfinance down")),
            log_func=logs.append,
        )

        cached_result = engine._build_result(
            symbol="CACHE",
            source="yfinance",
            price=101.0,
            previous_close=100.0,
            history=[
                {"date": "2026-03-19", "open": 99, "high": 101, "low": 98, "close": 100.0, "volume": 1000},
                {"date": "2026-03-20", "open": 100, "high": 102, "low": 99, "close": 101.0, "volume": 1100},
            ],
            volume=1100,
            confidence=100,
        )
        engine._cache_set("CACHE", "3mo", cached_result)
        cached_payload = engine.get_market_data("CACHE", "3mo")
        self.add(_result(
            "RESILIENCE_CACHE_FALLBACK",
            cached_payload.get("status") == "cached" and _to_float(cached_payload.get("price")) == 101.0,
            "If live providers fail and cache exists, system should return cached payload without crashing",
            f"status={cached_payload.get('status')}, source={cached_payload.get('source')}, price={cached_payload.get('price')}",
            notes="Simulated provider outage with cache available.",
        ))

        unavailable_payload = engine.get_market_data("NOPE", "3mo")
        self.add(_result(
            "RESILIENCE_ALL_PROVIDERS_FAIL",
            unavailable_payload.get("status") == "data_unavailable" and _to_float(unavailable_payload.get("confidence")) == 0.0,
            "If all providers and cache fail, system should return data_unavailable with confidence 0",
            f"status={unavailable_payload.get('status')}, confidence={unavailable_payload.get('confidence')}",
            notes="Simulated full provider failure without cache.",
        ))

    def run_end_to_end_tests(self) -> None:
        # Core API flow inside FastAPI app.
        prices_status, prices_payload = self._get_json("/api/prices", params={"symbols": "AAPL,NVDA"})
        stock_status, stock_payload = self._get_json("/stock/AAPL", params={"range": "3mo"})
        reco_status, reco_payload = self._get_json("/recommend", params={"symbol": "AAPL", "window_days": 30})
        ai_status, ai_payload = self._post_json("/api/ai-advisor", payload={"question": "Is AAPL still a good investment?", "context": {"selected_stock": "AAPL"}})
        passed = (
            prices_status == 200
            and stock_status == 200
            and reco_status == 200
            and ai_status == 200
            and isinstance(stock_payload, dict)
            and isinstance(reco_payload, dict)
            and isinstance(ai_payload, dict)
        )
        self.add(_result(
            "FLOW_CORE_STOCK_ANALYSIS",
            passed,
            "Search → Stock → Recommendation → AI Analysis flow should complete without crash",
            f"prices={prices_status}, stock={stock_status}, recommend={reco_status}, ai={ai_status}",
            notes="Backend API flow equivalent of the main user journey.",
        ))

        node_base = os.getenv("QA_NODE_BASE_URL", "http://localhost:5001")
        email = os.getenv("QA_TEST_EMAIL")
        password = os.getenv("QA_TEST_PASSWORD")
        if email and password:
            try:
                import requests

                response = requests.post(
                    f"{node_base.rstrip('/')}/api/login",
                    json={"email": email, "password": password},
                    timeout=5,
                )
                ok = response.status_code in {200, 400, 403}
                self.add(_result(
                    "FLOW_LOGIN_NODE",
                    ok,
                    "Login route should respond without server error",
                    f"HTTP {response.status_code}: {response.text[:180]}",
                    notes="Node/Express login route health check.",
                ))
            except Exception as exc:
                self.add(_result(
                    "FLOW_LOGIN_NODE",
                    False,
                    "Login route should respond without server error",
                    f"Request failed: {exc}",
                    notes="Set QA_NODE_BASE_URL, QA_TEST_EMAIL, and QA_TEST_PASSWORD for live login validation.",
                ))
        else:
            self.add(_result(
                "FLOW_LOGIN_NODE",
                True,
                "Optional live login validation can run when credentials are provided",
                "Skipped live login check because QA_TEST_EMAIL / QA_TEST_PASSWORD were not set",
                notes="Set QA_NODE_BASE_URL, QA_TEST_EMAIL, and QA_TEST_PASSWORD to include login in automated flow tests.",
            ))


def _save_results(results: List[ValidationResult]) -> Dict[str, Any]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    payload = {
        "generated_at": generated_at,
        "summary": {
            "total": len(results),
            "passed": sum(1 for result in results if result.status == "PASS"),
            "failed": sum(1 for result in results if result.status == "FAIL"),
        },
        "results": [asdict(result) for result in results],
    }
    data_accuracy_score = _qa_compute_data_accuracy(payload["results"])
    ai_reliability_score = _qa_compute_ai_reliability(payload["results"])

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    history_file = HISTORY_DIR / f"{timestamp}.json"
    history_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    LATEST_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_row = {
        "generated_at": generated_at,
        **payload["summary"],
        "data_accuracy": data_accuracy_score,
        "ai_reliability": ai_reliability_score,
    }
    with METRICS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(summary_row, ensure_ascii=False) + "\n")
    _evaluate_alerts(_safe_jsonl_read(METRICS_FILE, limit=500))
    return payload


def main() -> int:
    runner = ValidationRunner()
    results = runner.run()
    payload = _save_results(results)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
