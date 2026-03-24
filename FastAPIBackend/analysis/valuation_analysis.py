from __future__ import annotations

from typing import Any, Dict, Optional


def safe_float(value: Any) -> Optional[float]:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def extract_fundamentals(details: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pe_ratio": safe_float(details.get("peRatio") or details.get("pe_ratio")),
        "market_cap": details.get("marketCap") or details.get("market_cap"),
        "dividend_yield": safe_float(details.get("dividendYield") or details.get("dividend_yield")),
        "target_price": safe_float(details.get("targetPrice") or details.get("target_price")),
        "eps": safe_float(details.get("eps") or details.get("epsTTM")),
        "revenue_ttm": details.get("revenueTTM") or details.get("revenue_ttm"),
        "free_cash_flow": details.get("freeCashFlow") or details.get("free_cash_flow"),
    }


def compute_upside(current_price: Optional[float], target_price: Optional[float]) -> Optional[float]:
    if current_price in (None, 0) or target_price is None:
        return None
    return ((target_price - current_price) / current_price) * 100.0

