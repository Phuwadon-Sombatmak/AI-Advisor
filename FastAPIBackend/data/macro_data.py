from __future__ import annotations

from typing import Any, Dict, Optional


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


class MacroDataGateway:
    def build_macro_snapshot(self, market_context: Dict[str, Any]) -> Dict[str, Any]:
        sector = (market_context.get("sector_momentum") or {}).get("sector")
        momentum = (market_context.get("sector_momentum") or {}).get("momentum")
        meta = market_context.get("market_meta") or {}
        regime = market_context.get("regime")
        confidence = market_context.get("confidence")
        positioning = market_context.get("positioning") or {
            "overweight": [],
            "neutral": [],
            "underweight": [],
        }
        suggested_etfs = market_context.get("suggested_etfs") or []
        return {
            "market_sentiment": market_context.get("market_label"),
            "fear_greed_index": _safe_float(market_context.get("market_score")),
            "market_regime": regime,
            "regime_confidence": confidence,
            "positioning": positioning,
            "suggested_etfs": suggested_etfs,
            "top_sector": sector,
            "top_sector_momentum": momentum,
            "risk_outlook": market_context.get("risk_outlook"),
            "volatility": meta.get("volatility") or market_context.get("risk_outlook"),
            "vix": _safe_float(meta.get("vix")),
            "treasury_yield_10y": _safe_float(meta.get("treasury_yield_10y")),
            "cpi": _safe_float(meta.get("cpi")),
            "source": meta.get("source") or "Internal Market Context",
        }
