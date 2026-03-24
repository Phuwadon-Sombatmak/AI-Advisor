from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import yfinance as yf
from sqlalchemy import text

from init_db import engine


DEFAULT_TICKERS = [
    "NVDA",
    "MSFT",
    "AMZN",
    "UNH",
    "AMD",
    "GOOGL",
    "MU",
    "TSM",
    "NVO",
    "META",
    "AAPL",
    "TSLA",
    "PG",
    "KO",
    "JNJ",
]

_last_bootstrap_attempt: datetime | None = None


def _bootstrap_prices_if_needed() -> None:
    global _last_bootstrap_attempt
    now = datetime.utcnow()
    if _last_bootstrap_attempt and (now - _last_bootstrap_attempt) < timedelta(minutes=30):
        return
    _last_bootstrap_attempt = now

    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT COUNT(*) AS c, MAX(last_updated) AS max_ts FROM prices")
            ).mappings().first()
            total = int((row or {}).get("c") or 0)
            max_ts = (row or {}).get("max_ts")
    except Exception:
        return

    is_stale = True
    if max_ts is not None:
        ts = pd.to_datetime(max_ts, errors="coerce")
        if pd.notna(ts):
            py_ts = ts.to_pydatetime().replace(tzinfo=None)
            is_stale = (now - py_ts) > timedelta(days=2)

    if total >= 300 and not is_stale:
        return

    upsert_sql = text(
        """
        INSERT INTO prices (ticker, name, last_updated, open, high, low, close, volume)
        VALUES (:ticker, :name, :last_updated, :open, :high, :low, :close, :volume)
        ON CONFLICT (ticker, last_updated) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            name = EXCLUDED.name
        """
    )

    stock_upsert_sql = text(
        """
        INSERT INTO stocks (ticker, name, last_updated)
        VALUES (:ticker, :name, :last_updated)
        ON CONFLICT (ticker) DO UPDATE SET
            name = EXCLUDED.name,
            last_updated = EXCLUDED.last_updated
        """
    )

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_prices_ticker_ts
                    ON prices (ticker, last_updated)
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_stocks_ticker
                    ON stocks (ticker)
                    """
                )
            )

            for ticker in DEFAULT_TICKERS:
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="1y", auto_adjust=False)
                    if hist.empty:
                        continue
                    info = {}
                    try:
                        info = stock.info or {}
                    except Exception:
                        info = {}
                    name = info.get("longName") or info.get("shortName") or ticker

                    for ts, row in hist.iterrows():
                        conn.execute(
                            upsert_sql,
                            {
                                "ticker": ticker,
                                "name": name,
                                "last_updated": pd.to_datetime(ts).to_pydatetime().replace(tzinfo=None),
                                "open": float(row.get("Open", 0) or 0),
                                "high": float(row.get("High", 0) or 0),
                                "low": float(row.get("Low", 0) or 0),
                                "close": float(row.get("Close", 0) or 0),
                                "volume": int(float(row.get("Volume", 0) or 0)),
                            },
                        )

                    conn.execute(
                        stock_upsert_sql,
                        {
                            "ticker": ticker,
                            "name": name,
                            "last_updated": datetime.utcnow(),
                        },
                    )
                except Exception:
                    continue
    except Exception:
        return


def _load_close_df(days_back: int = 365) -> pd.DataFrame:
    query = text(
        """
        SELECT ticker, last_updated AS ts, close, name
        FROM prices
        WHERE last_updated >= :cutoff
        ORDER BY ticker, last_updated
        """
    )
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"cutoff": cutoff})
    except Exception:
        return pd.DataFrame(columns=["ticker", "ts", "close", "name"])
    if df.empty:
        return pd.DataFrame(columns=["ticker", "ts", "close", "name"])
    return df


def _compute_risk_ai(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values(["ticker", "ts"])

    metrics: List[Dict[str, Any]] = []
    for ticker, group in df.groupby("ticker"):
        if len(group) < 30:
            continue
        group = group.set_index("ts")
        closes = pd.to_numeric(group["close"], errors="coerce").dropna()
        if len(closes) < 30:
            continue

        daily_ret = closes.pct_change().dropna()
        if daily_ret.empty:
            continue

        vol90 = float(daily_ret.tail(90).std() * np.sqrt(252)) if len(daily_ret) >= 10 else None
        roll_max = closes.rolling(252, min_periods=1).max()
        mdd1y = float((closes / roll_max - 1.0).min())
        ret30 = float((closes.iloc[-1] / closes.iloc[-30]) - 1.0) if len(closes) >= 30 else None
        risk_score = None
        if vol90 is not None:
            risk_score = float(min(max((vol90 * 10.0) + (abs(mdd1y) * 10.0), 1.0), 10.0))

        metrics.append(
            {
                "Symbol": ticker,
                "company": str(group["name"].iloc[-1] or ticker),
                "last_close": float(closes.iloc[-1]),
                "ret30": ret30,
                "vol90": vol90,
                "mdd1y": mdd1y,
                "risk_score": risk_score,
            }
        )

    uni = pd.DataFrame(metrics)
    if uni.empty:
        return uni

    if uni["risk_score"].nunique(dropna=True) <= 1:
        base = float(uni["risk_score"].dropna().iloc[0]) if not uni["risk_score"].dropna().empty else 5.0
        uni["risk_score"] = [base + ((idx - len(uni) / 2) * 1e-6) for idx in range(len(uni))]

    q1 = uni["risk_score"].quantile(0.33)
    q2 = uni["risk_score"].quantile(0.66)

    def label_risk(score: Any) -> str:
        if pd.isna(score):
            return "MEDIUM"
        if score <= q1:
            return "LOW"
        if score >= q2:
            return "HIGH"
        return "MEDIUM"

    uni["risk_label"] = uni["risk_score"].apply(label_risk)
    return uni


def recommend_by_level(level: str, limit: int = 15) -> List[Dict[str, Any]]:
    level = str(level or "LOW").upper().strip()
    _bootstrap_prices_if_needed()
    df = _load_close_df(days_back=365)
    uni = _compute_risk_ai(df)
    if uni.empty:
        return []

    filtered = uni[uni["risk_label"] == level].copy()
    if filtered.empty:
        if level == "LOW":
            filtered = uni.sort_values("risk_score", ascending=True).head(limit)
        elif level == "HIGH":
            filtered = uni.sort_values("risk_score", ascending=False).head(limit)
        else:
            filtered = uni.sort_values("risk_score", ascending=True)
            start = max(0, (len(filtered) // 2) - (limit // 2))
            filtered = filtered.iloc[start : start + limit]

    rows: List[Dict[str, Any]] = []
    for _, row in filtered.head(limit).iterrows():
        rows.append(
            {
                "Symbol": row.get("Symbol"),
                "company": row.get("company"),
                "last_close": row.get("last_close"),
                "ret30": round(float(row.get("ret30") or 0) * 100, 2) if row.get("ret30") is not None else None,
                "vol90": round(float(row.get("vol90") or 0) * 100, 2) if row.get("vol90") is not None else None,
                "mdd1y": round(float(row.get("mdd1y") or 0) * 100, 2) if row.get("mdd1y") is not None else None,
                "risk_score": round(float(row.get("risk_score") or 0), 2) if row.get("risk_score") is not None else None,
                "risk_label": row.get("risk_label") or level,
            }
        )
    return rows
