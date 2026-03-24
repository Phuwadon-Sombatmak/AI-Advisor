from __future__ import annotations

from typing import Any, Optional


def safe_float(value: Any) -> Optional[float]:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def compute_risk_level(*, fear_greed: Optional[float], momentum_score: Optional[float], technical_score: Optional[float]) -> str:
    risk_score = 0.0
    if fear_greed is not None:
        risk_score += (100.0 - fear_greed) * 0.45
    if momentum_score is not None:
        risk_score += (100.0 - momentum_score) * 0.30
    if technical_score is not None:
        risk_score += (100.0 - technical_score) * 0.25
    if risk_score >= 60:
        return "High"
    if risk_score >= 35:
        return "Medium"
    return "Low"

