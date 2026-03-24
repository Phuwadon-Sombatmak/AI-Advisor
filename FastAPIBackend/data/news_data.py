from __future__ import annotations

from typing import Any, Callable, Dict, List


def _coerce_sentiment_score(item: Dict[str, Any]) -> float:
    raw = item.get("sentiment_score")
    if raw is not None:
        try:
            return float(raw)
        except Exception:
            pass
    label = str(item.get("sentiment") or item.get("sentiment_label") or "").lower()
    if "bullish" in label or "positive" in label:
        return 0.6
    if "bearish" in label or "negative" in label:
        return -0.6
    return 0.0


class NewsDataGateway:
    def __init__(self, *, get_news_batch: Callable[[List[str], int, int], List[Dict[str, Any]]]) -> None:
        self._get_news_batch = get_news_batch

    def get_symbol_news(self, symbol: str, days_back: int = 7, limit: int = 12) -> Dict[str, Any]:
        rows = self._get_news_batch([symbol], limit_per_symbol=limit, days_back=days_back) or []
        items = ((rows[0] or {}).get("news") if rows else []) or []
        scores = [_coerce_sentiment_score(item) for item in items]
        bullish = len([s for s in scores if s > 0.15])
        bearish = len([s for s in scores if s < -0.15])
        neutral = max(0, len(scores) - bullish - bearish)
        avg = sum(scores) / len(scores) if scores else None
        return {
            "items": items,
            "sentiment": {
                "bullish": bullish,
                "neutral": neutral,
                "bearish": bearish,
                "average": round(avg, 3) if avg is not None else None,
            },
        }

