from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


SIGNAL_TO_POSITION = {
    "STRONG BUY": 1.0,
    "BUY": 0.5,
    "HOLD": 0.0,
    "HOLD (BULLISH BIAS)": 0.0,
    "HOLD (BEARISH BIAS)": 0.0,
    "SELL": -0.5,
    "STRONG SELL": -1.0,
}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        numeric = float(value)
        if math.isnan(numeric) or math.isinf(numeric):
            return None
        return numeric
    except Exception:
        return None


def _normalize_signal_label(label: Any) -> str:
    return str(label or "HOLD").strip().upper()


def signal_to_position(label: Any) -> float:
    return SIGNAL_TO_POSITION.get(_normalize_signal_label(label), 0.0)


def _to_timestamp(value: Any) -> Optional[pd.Timestamp]:
    if value in (None, ""):
        return None
    try:
        ts = pd.to_datetime(value, utc=False)
        if pd.isna(ts):
            return None
        return pd.Timestamp(ts).normalize()
    except Exception:
        return None


def history_to_price_frame(history_rows: Iterable[Dict[str, Any]], column_name: str) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for row in history_rows or []:
        ts = _to_timestamp(row.get("date"))
        close = _safe_float(row.get("close"))
        if ts is None or close is None or close <= 0:
            continue
        rows.append({"date": ts, column_name: close})
    if not rows:
        return pd.DataFrame(columns=[column_name])
    frame = pd.DataFrame(rows).drop_duplicates(subset=["date"], keep="last").sort_values("date")
    return frame.set_index("date")


def signals_to_frame(signals: Iterable[Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for item in signals or []:
        ts = _to_timestamp(item.get("timestamp") or item.get("date"))
        symbol = str(item.get("symbol") or "").strip().upper()
        recommendation = _normalize_signal_label(item.get("recommendation"))
        if ts is None or not symbol:
            continue
        rows.append({
            "date": ts,
            "symbol": symbol,
            "recommendation": recommendation,
            "target_weight": signal_to_position(recommendation),
        })
    if not rows:
        return pd.DataFrame(columns=["symbol", "recommendation", "target_weight"])
    frame = pd.DataFrame(rows).sort_values(["symbol", "date"]).drop_duplicates(subset=["symbol", "date"], keep="last")
    return frame


def _position_series_for_symbol(price_index: pd.DatetimeIndex, symbol_signals: pd.DataFrame) -> pd.Series:
    if symbol_signals.empty:
        return pd.Series(0.0, index=price_index)
    weights = symbol_signals.set_index("date")["target_weight"].reindex(price_index)
    # Rebalance on close; next session return uses the signal.
    return weights.ffill().fillna(0.0).shift(1).fillna(0.0)


def _clip_gross_exposure(position_frame: pd.DataFrame) -> pd.DataFrame:
    if position_frame.empty:
        return position_frame
    gross = position_frame.abs().sum(axis=1)
    scale = gross.where(gross > 1.0, 1.0)
    scale = 1.0 / scale
    scale = scale.where(gross > 1.0, 1.0)
    return position_frame.mul(scale, axis=0)


def _annualized_return(total_return: float, periods: int) -> float:
    if periods <= 0:
        return 0.0
    years = periods / 252.0
    if years <= 0:
        return 0.0
    return ((1.0 + total_return) ** (1.0 / years) - 1.0) * 100.0


def _sharpe_ratio(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return 0.0
    std = float(daily_returns.std(ddof=0) or 0.0)
    if std <= 1e-12:
        return 0.0
    mean = float(daily_returns.mean())
    return (mean / std) * math.sqrt(252.0)


def _max_drawdown(equity_curve: pd.Series) -> float:
    if equity_curve.empty:
        return 0.0
    running_max = equity_curve.cummax()
    drawdown = (equity_curve / running_max) - 1.0
    return float(drawdown.min()) * 100.0


def _extract_trades(price_frame: pd.DataFrame, position_frame: pd.DataFrame) -> List[Dict[str, Any]]:
    trades: List[Dict[str, Any]] = []
    for symbol in position_frame.columns:
        positions = position_frame[symbol].fillna(0.0)
        prices = price_frame[symbol].dropna()
        if prices.empty:
            continue
        current_trade: Optional[Dict[str, Any]] = None
        prev_weight = 0.0
        for date, weight in positions.items():
            if date not in prices.index:
                continue
            price = float(prices.loc[date])
            if prev_weight == 0.0 and weight != 0.0:
                current_trade = {
                    "symbol": symbol,
                    "entry_date": date,
                    "entry_price": price,
                    "weight": weight,
                }
            elif prev_weight != 0.0 and weight != prev_weight:
                if current_trade is not None:
                    gross_return = (price / current_trade["entry_price"]) - 1.0
                    weighted_return = gross_return * current_trade["weight"]
                    trades.append({
                        **current_trade,
                        "exit_date": date,
                        "exit_price": price,
                        "trade_return": weighted_return * 100.0,
                    })
                current_trade = None
                if weight != 0.0:
                    current_trade = {
                        "symbol": symbol,
                        "entry_date": date,
                        "entry_price": price,
                        "weight": weight,
                    }
            prev_weight = weight
        if current_trade is not None:
            last_date = prices.index[-1]
            last_price = float(prices.iloc[-1])
            gross_return = (last_price / current_trade["entry_price"]) - 1.0
            weighted_return = gross_return * current_trade["weight"]
            trades.append({
                **current_trade,
                "exit_date": last_date,
                "exit_price": last_price,
                "trade_return": weighted_return * 100.0,
            })
    return trades


@dataclass
class BacktestResult:
    total_return: float
    annualized_return: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    average_trade_return: float
    vs_spy: float
    benchmark_return: float
    periods: int
    start_date: Optional[str]
    end_date: Optional[str]
    trades: int
    equity_curve: List[Dict[str, Any]]
    benchmark_curve: List[Dict[str, Any]]
    positions: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_return": round(self.total_return, 2),
            "annualized_return": round(self.annualized_return, 2),
            "sharpe": round(self.sharpe, 3),
            "max_drawdown": round(self.max_drawdown, 2),
            "win_rate": round(self.win_rate, 2),
            "average_trade_return": round(self.average_trade_return, 2),
            "vs_spy": round(self.vs_spy, 2),
            "benchmark_return": round(self.benchmark_return, 2),
            "periods": self.periods,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "trades": self.trades,
            "equity_curve": self.equity_curve,
            "benchmark_curve": self.benchmark_curve,
            "positions": self.positions,
        }


def run_backtest(
    price_histories: Dict[str, List[Dict[str, Any]]],
    signals: Iterable[Dict[str, Any]],
    benchmark_history: List[Dict[str, Any]],
    initial_capital: float = 100000.0,
) -> BacktestResult:
    signal_frame = signals_to_frame(signals)
    if signal_frame.empty:
        raise ValueError("No valid AI signals were provided for backtesting.")

    symbols = sorted(signal_frame["symbol"].unique().tolist())
    price_frames: List[pd.DataFrame] = []
    for symbol in symbols:
        history = price_histories.get(symbol) or []
        frame = history_to_price_frame(history, symbol)
        if frame.empty:
            raise ValueError(f"Historical price data is missing for {symbol}.")
        price_frames.append(frame)

    price_frame = pd.concat(price_frames, axis=1, join="outer").sort_index().ffill().dropna(how="all")
    if price_frame.empty:
        raise ValueError("Price history could not be aligned for the requested symbols.")

    benchmark_frame = history_to_price_frame(benchmark_history, "SPY")
    if benchmark_frame.empty:
        raise ValueError("Benchmark history is missing for SPY.")

    combined_index = price_frame.index.intersection(benchmark_frame.index)
    if combined_index.empty:
        raise ValueError("No overlapping dates between signal universe and SPY benchmark.")

    price_frame = price_frame.reindex(combined_index).ffill().dropna(how="all")
    benchmark_frame = benchmark_frame.reindex(combined_index).ffill().dropna()
    combined_index = price_frame.index.intersection(benchmark_frame.index)
    price_frame = price_frame.reindex(combined_index)
    benchmark_frame = benchmark_frame.reindex(combined_index)
    if len(combined_index) < 2:
        raise ValueError("Not enough overlapping history to run the backtest.")

    position_series = {}
    for symbol in symbols:
        symbol_signals = signal_frame[signal_frame["symbol"] == symbol]
        position_series[symbol] = _position_series_for_symbol(price_frame.index, symbol_signals)
    position_frame = pd.DataFrame(position_series, index=price_frame.index).fillna(0.0)
    position_frame = _clip_gross_exposure(position_frame)

    asset_returns = price_frame.pct_change().fillna(0.0)
    portfolio_returns = (position_frame * asset_returns).sum(axis=1).fillna(0.0)
    equity_curve = (1.0 + portfolio_returns).cumprod() * initial_capital

    spy_returns = benchmark_frame["SPY"].pct_change().fillna(0.0)
    benchmark_curve = (1.0 + spy_returns).cumprod() * initial_capital

    total_return = (float(equity_curve.iloc[-1]) / initial_capital) - 1.0
    benchmark_return = (float(benchmark_curve.iloc[-1]) / initial_capital) - 1.0
    trades = _extract_trades(price_frame, position_frame)
    trade_returns = [float(trade["trade_return"]) for trade in trades]
    win_rate = ((sum(1 for value in trade_returns if value > 0) / len(trade_returns)) * 100.0) if trade_returns else 0.0
    average_trade_return = (sum(trade_returns) / len(trade_returns)) if trade_returns else 0.0

    return BacktestResult(
        total_return=total_return * 100.0,
        annualized_return=_annualized_return(total_return, len(portfolio_returns)),
        sharpe=_sharpe_ratio(portfolio_returns),
        max_drawdown=_max_drawdown(equity_curve),
        win_rate=win_rate,
        average_trade_return=average_trade_return,
        vs_spy=(total_return - benchmark_return) * 100.0,
        benchmark_return=benchmark_return * 100.0,
        periods=len(portfolio_returns),
        start_date=str(combined_index[0].date()) if len(combined_index) else None,
        end_date=str(combined_index[-1].date()) if len(combined_index) else None,
        trades=len(trades),
        equity_curve=[
            {"date": str(idx.date()), "equity": round(float(value), 2), "daily_return": round(float(portfolio_returns.loc[idx]) * 100.0, 4)}
            for idx, value in equity_curve.items()
        ],
        benchmark_curve=[
            {"date": str(idx.date()), "equity": round(float(value), 2), "daily_return": round(float(spy_returns.loc[idx]) * 100.0, 4)}
            for idx, value in benchmark_curve.items()
        ],
        positions=[
            {"date": str(idx.date()), **{symbol: round(float(position_frame.loc[idx, symbol]), 4) for symbol in position_frame.columns}}
            for idx in position_frame.index
        ],
    )
