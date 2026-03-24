from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional


class MarketDataGateway:
    def __init__(
        self,
        *,
        get_stock_data: Callable[[str, str], Dict[str, Any]],
        get_stock_profile: Callable[[str], Dict[str, Any]],
        get_stock_details: Callable[[str], Dict[str, Any]],
        build_market_snapshot: Callable[[Any], Dict[str, Any]],
        rank_sector_etfs: Callable[[], Dict[str, Any]],
        market_engine: Optional[Any] = None,
    ) -> None:
        self._get_stock_data = get_stock_data
        self._get_stock_profile = get_stock_profile
        self._get_stock_details = get_stock_details
        self._build_market_snapshot = build_market_snapshot
        self._rank_sector_etfs = rank_sector_etfs
        self._market_engine = market_engine

    def get_market_context(self, context: Any) -> Dict[str, Any]:
        if isinstance(context, dict):
            context = SimpleNamespace(
                watchlist=context.get("watchlist") or [],
                portfolio=context.get("portfolio") or [],
                sentiment=context.get("sentiment"),
                recent_searches=context.get("recent_searches") or [],
                risk_profile=context.get("risk_profile"),
                selected_stock=context.get("selected_stock"),
                chat_state=context.get("chat_state") or {},
            )
        return self._build_market_snapshot(context)

    def get_sector_rankings(self) -> Dict[str, Any]:
        return self._rank_sector_etfs()

    def get_stock_history(self, symbol: str, range_value: str) -> Dict[str, Any]:
        if self._market_engine is not None:
            payload = self._market_engine.get_market_data(symbol, range_value)
            if payload.get("status") != "data_unavailable":
                return {
                    "name": symbol,
                    "price": payload.get("price"),
                    "previous_close": payload.get("previous_close"),
                    "history": payload.get("history", []),
                    "range": range_value,
                    "provider": payload.get("source"),
                    "provider_chain": (payload.get("meta") or {}).get("cross_verified_with") or [payload.get("source")],
                    "data_source_mode": payload.get("status"),
                    "stale_cache_used": payload.get("status") == "cached",
                    "cached_age_minutes": (payload.get("meta") or {}).get("cached_age_minutes"),
                }
        return self._get_stock_data(symbol, range_value)

    def get_stock_bundle(self, symbol: str) -> Dict[str, Any]:
        with ThreadPoolExecutor(max_workers=4) as executor:
            history_1m_future = executor.submit(self.get_stock_history, symbol, "1m")
            history_3m_future = executor.submit(self.get_stock_history, symbol, "3m")
            history_1y_future = executor.submit(self.get_stock_history, symbol, "1y")
            profile_future = executor.submit(self._get_stock_profile, symbol)
            details_future = executor.submit(self._get_stock_details, symbol)

            history_1m = history_1m_future.result()
            history_3m = history_3m_future.result()
            history_1y = history_1y_future.result()
            profile = profile_future.result()
            details = details_future.result()

        history_payloads = [history_1m, history_3m, history_1y]
        cached_rows = [payload for payload in history_payloads if (payload or {}).get("stale_cache_used")]
        provider_chain = []
        for payload in history_payloads:
            for tag in (payload or {}).get("provider_chain") or []:
                if tag and tag not in provider_chain:
                    provider_chain.append(tag)
            provider = (payload or {}).get("provider")
            if provider and provider not in provider_chain:
                provider_chain.append(provider)

        return {
            "symbol": symbol,
            "history_1m": history_1m,
            "history_3m": history_3m,
            "history_1y": history_1y,
            "profile": profile,
            "details": details,
            "meta": {
                "data_source_mode": "cached" if cached_rows else "live",
                "stale_cache_used": bool(cached_rows),
                "cached_age_minutes": max(
                    [float((payload or {}).get("cached_age_minutes") or 0.0) for payload in cached_rows],
                    default=0.0,
                ),
                "provider_chain": provider_chain,
                "sources": provider_chain,
            },
        }

    def get_many_3m_histories(self, symbols: List[str]) -> List[Dict[str, Any]]:
        def _fetch(sym: str) -> Dict[str, Any]:
            return self.get_stock_history(sym, "3m")

        with ThreadPoolExecutor(max_workers=min(6, max(1, len(symbols)))) as executor:
            return list(executor.map(_fetch, symbols))
