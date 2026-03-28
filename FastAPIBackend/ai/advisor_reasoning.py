from __future__ import annotations

from typing import Any, Dict, List, Optional

from analysis.momentum_analysis import (
    classify_momentum,
    classify_trend,
    close_series,
    compute_macd,
    compute_return_pct,
    compute_rsi,
    momentum_score,
    moving_average,
    technical_score,
)
from analysis.risk_analysis import compute_risk_level
from analysis.valuation_analysis import compute_upside, extract_fundamentals

TRENDING_CACHE: Dict[str, Any] = {}
REGIME_MEMORY: List[Dict[str, Any]] = []


def _is_thai_text(text: str) -> bool:
    return any("\u0E00" <= char <= "\u0E7F" for char in str(text or ""))


def _lang_for(question: str) -> str:
    return "th" if _is_thai_text(question) else "en"


def _pick_lang(lang: str, thai_text: str, english_text: str) -> str:
    return thai_text if lang == "th" else english_text


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value in ("", None):
            return None
        return float(value)
    except Exception:
        return None


def _signal_confidence(*values: Optional[float]) -> int:
    available = len([value for value in values if value is not None])
    return int(max(35, min(92, 40 + available * 12)))


def _coverage_score(*flags: bool) -> int:
    return len([flag for flag in flags if flag])


def _data_mode_confidence(*, stale_cache_used: bool, coverage_points: int) -> int:
    if coverage_points <= 0:
        return 0
    if stale_cache_used:
        if coverage_points >= 3:
            return 80
        if coverage_points == 2:
            return 70
        return 60
    if coverage_points >= 3:
        return 100
    if coverage_points == 2:
        return 88
    return 72


def _source_tags(*tags: str) -> List[str]:
    seen = set()
    output: List[str] = []
    for tag in tags:
        if tag and tag not in seen:
            seen.add(tag)
            output.append(tag)
    return output


def _time_horizon_payload(*, short_term: str, medium_term: str) -> Dict[str, str]:
    return {
        "short_term": short_term,
        "medium_term": medium_term,
    }


def _sector_strength_label(*, rank: int, momentum: Optional[float], fear_greed: Optional[float]) -> str:
    if rank != 1 or momentum is None:
        return "Weak" if momentum is not None and momentum < 2 else "Moderate"
    if momentum >= 8:
        if fear_greed is not None and fear_greed <= 24:
            return "Strong but High Risk"
        return "Strong"
    if momentum >= 2:
        if fear_greed is not None and fear_greed <= 24:
            return "Moderate but High Risk"
        return "Moderate"
    return "Weak"


def _default_positioning() -> Dict[str, List[str]]:
    return {
        "overweight": ["Balanced allocation"],
        "neutral": ["Healthcare", "Industrials", "Quality large caps"],
        "underweight": [],
    }


SECTOR_ALIASES: Dict[str, str] = {
    "energy": "Energy",
    "พลังงาน": "Energy",
    "oil": "Energy",
    "น้ำมัน": "Energy",
    "tech": "Technology",
    "technology": "Technology",
    "เทค": "Technology",
    "เทคโนโลยี": "Technology",
    "semiconductor": "Semiconductors",
    "semiconductors": "Semiconductors",
    "chip": "Semiconductors",
    "chips": "Semiconductors",
    "เซมิคอนดักเตอร์": "Semiconductors",
    "health": "Healthcare",
    "healthcare": "Healthcare",
    "เฮลท์แคร์": "Healthcare",
    "สุขภาพ": "Healthcare",
    "finance": "Finance",
    "financial": "Finance",
    "bank": "Finance",
    "banks": "Finance",
    "ธนาคาร": "Finance",
    "การเงิน": "Finance",
    "utility": "Utilities",
    "utilities": "Utilities",
    "สาธารณูปโภค": "Utilities",
    "consumer staples": "Consumer Staples",
    "staples": "Consumer Staples",
    "ของใช้จำเป็น": "Consumer Staples",
}

SECTOR_STOCK_UNIVERSE: Dict[str, List[str]] = {
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "OXY"],
    "Technology": ["MSFT", "AAPL", "AMZN", "GOOGL", "META", "ORCL"],
    "Semiconductors": ["NVDA", "AMD", "AVGO", "TSM", "INTC", "MU"],
    "Healthcare": ["LLY", "JNJ", "UNH", "MRK", "PFE", "ABT"],
    "Finance": ["JPM", "BAC", "GS", "MS", "WFC", "C"],
    "Utilities": ["NEE", "DUK", "SO", "AEP", "XEL", "SRE"],
    "Consumer Staples": ["PG", "KO", "PEP", "WMT", "COST", "MO"],
}

SYMBOL_SECTOR_MAP: Dict[str, str] = {
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy", "EOG": "Energy", "OXY": "Energy",
    "MSFT": "Technology", "AAPL": "Technology", "AMZN": "Technology", "GOOGL": "Technology", "META": "Technology", "ORCL": "Technology",
    "NVDA": "Semiconductors", "AMD": "Semiconductors", "AVGO": "Semiconductors", "TSM": "Semiconductors", "INTC": "Semiconductors", "MU": "Semiconductors",
    "LLY": "Healthcare", "JNJ": "Healthcare", "UNH": "Healthcare", "MRK": "Healthcare", "PFE": "Healthcare", "ABT": "Healthcare",
    "JPM": "Finance", "BAC": "Finance", "GS": "Finance", "MS": "Finance", "WFC": "Finance", "C": "Finance",
    "NEE": "Utilities", "DUK": "Utilities", "SO": "Utilities", "AEP": "Utilities", "XEL": "Utilities", "SRE": "Utilities",
    "PG": "Consumer Staples", "KO": "Consumer Staples", "PEP": "Consumer Staples", "WMT": "Consumer Staples", "COST": "Consumer Staples", "MO": "Consumer Staples",
}

SYMBOL_NAME_MAP: Dict[str, str] = {
    "XOM": "Exxon Mobil",
    "CVX": "Chevron",
    "COP": "ConocoPhillips",
    "SLB": "SLB",
    "EOG": "EOG Resources",
    "OXY": "Occidental Petroleum",
    "MSFT": "Microsoft",
    "AAPL": "Apple",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "META": "Meta Platforms",
    "ORCL": "Oracle",
    "NVDA": "NVIDIA",
    "AMD": "AMD",
    "AVGO": "Broadcom",
    "TSM": "Taiwan Semiconductor",
    "INTC": "Intel",
    "MU": "Micron",
    "LLY": "Eli Lilly",
    "JNJ": "Johnson & Johnson",
    "UNH": "UnitedHealth Group",
    "MRK": "Merck",
    "PFE": "Pfizer",
    "ABT": "Abbott Laboratories",
    "JPM": "JPMorgan Chase",
    "BAC": "Bank of America",
    "GS": "Goldman Sachs",
    "MS": "Morgan Stanley",
    "WFC": "Wells Fargo",
    "C": "Citigroup",
    "NEE": "NextEra Energy",
    "DUK": "Duke Energy",
    "SO": "Southern Company",
    "AEP": "American Electric Power",
    "XEL": "Xcel Energy",
    "SRE": "Sempra",
    "PG": "Procter & Gamble",
    "KO": "Coca-Cola",
    "PEP": "PepsiCo",
    "WMT": "Walmart",
    "COST": "Costco",
    "MO": "Altria",
    "XLE": "Energy Select Sector SPDR Fund",
    "XLU": "Utilities Select Sector SPDR Fund",
    "XLP": "Consumer Staples Select Sector SPDR Fund",
    "XLV": "Health Care Select Sector SPDR Fund",
    "XLI": "Industrial Select Sector SPDR Fund",
    "QQQ": "Invesco QQQ Trust",
    "SPY": "SPDR S&P 500 ETF Trust",
}

SECTOR_CORE_SYMBOLS: Dict[str, List[str]] = {
    "Energy": ["XOM", "CVX", "COP"],
    "Technology": ["MSFT", "AAPL", "GOOGL"],
    "Semiconductors": ["NVDA", "AVGO", "TSM"],
    "Healthcare": ["LLY", "JNJ", "UNH"],
    "Finance": ["JPM", "BAC", "GS"],
    "Utilities": ["NEE", "DUK", "SO"],
    "Consumer Staples": ["PG", "KO", "PEP"],
}

SECTOR_HIGH_BETA_SYMBOLS: Dict[str, List[str]] = {
    "Energy": ["OXY", "SLB"],
    "Technology": ["META", "AMZN"],
    "Semiconductors": ["AMD", "MU"],
    "Healthcare": ["PFE"],
    "Finance": ["MS", "C"],
    "Utilities": [],
    "Consumer Staples": ["MO"],
}

ENERGY_SUBSECTOR_MAP: Dict[str, Dict[str, Any]] = {
    "upstream": {
        "strength": "high",
        "why": "Direct revenue exposure to higher oil prices makes upstream names the clearest early winners.",
        "symbols": ["XOM", "CVX", "COP", "EOG", "OXY"],
    },
    "midstream": {
        "strength": "medium",
        "why": "Midstream cash flow is more volume-driven, so the benefit is steadier and less sensitive than pure producers.",
        "symbols": ["KMI", "WMB", "EPD"],
    },
    "downstream": {
        "strength": "conditional",
        "why": "Refiners can benefit, but the result depends on crack spreads rather than crude alone.",
        "symbols": ["VLO", "MPC", "PSX"],
    },
    "oil_services": {
        "strength": "delayed_positive",
        "why": "Services usually benefit later as producers increase capex and drilling activity.",
        "symbols": ["SLB", "HAL", "BKR"],
    },
}

SECTOR_TRENDING_FALLBACKS: Dict[str, List[Dict[str, str]]] = {
    "Energy": [
        {"symbol": "XOM", "name": "Exxon Mobil", "role": "energy leader"},
        {"symbol": "CVX", "name": "Chevron", "role": "oil major"},
        {"symbol": "SLB", "name": "SLB", "role": "services leader"},
    ],
    "Technology": [
        {"symbol": "NVDA", "name": "NVIDIA", "role": "AI infrastructure leader"},
        {"symbol": "MSFT", "name": "Microsoft", "role": "software and cloud leader"},
        {"symbol": "AMD", "name": "AMD", "role": "semiconductor momentum name"},
    ],
    "Semiconductors": [
        {"symbol": "NVDA", "name": "NVIDIA", "role": "AI chip leader"},
        {"symbol": "AMD", "name": "AMD", "role": "high-beta chip leader"},
        {"symbol": "AVGO", "name": "Broadcom", "role": "infrastructure semiconductor leader"},
    ],
    "Healthcare": [
        {"symbol": "LLY", "name": "Eli Lilly", "role": "earnings leader"},
        {"symbol": "JNJ", "name": "Johnson & Johnson", "role": "defensive quality leader"},
        {"symbol": "UNH", "name": "UnitedHealth Group", "role": "managed care leader"},
    ],
    "Finance": [
        {"symbol": "JPM", "name": "JPMorgan Chase", "role": "money-center bank leader"},
        {"symbol": "GS", "name": "Goldman Sachs", "role": "capital markets leader"},
        {"symbol": "MS", "name": "Morgan Stanley", "role": "brokerage leader"},
    ],
    "Utilities": [
        {"symbol": "NEE", "name": "NextEra Energy", "role": "utilities leader"},
        {"symbol": "DUK", "name": "Duke Energy", "role": "defensive yield name"},
        {"symbol": "SO", "name": "Southern Company", "role": "regulated utility leader"},
    ],
    "Consumer Staples": [
        {"symbol": "PG", "name": "Procter & Gamble", "role": "defensive staple leader"},
        {"symbol": "KO", "name": "Coca-Cola", "role": "global staple compounder"},
        {"symbol": "PEP", "name": "PepsiCo", "role": "defensive cash-flow name"},
    ],
}

ETF_DECOMPOSITION: Dict[str, List[str]] = {
    "XLE": ["XOM", "CVX", "SLB"],
    "XLU": ["NEE", "DUK", "SO"],
    "XLP": ["PG", "KO", "PEP"],
    "XLV": ["LLY", "JNJ", "UNH"],
    "XLI": ["CAT", "GE", "HON"],
    "QQQ": ["MSFT", "NVDA", "AAPL"],
    "SPY": ["MSFT", "AAPL", "NVDA"],
}


def _extract_requested_sector(question: str) -> Optional[str]:
    q = (question or "").lower()
    for alias, sector in SECTOR_ALIASES.items():
        if alias in q:
            return sector
    return None


def _sector_for_symbol(symbol: str) -> Optional[str]:
    return SYMBOL_SECTOR_MAP.get(str(symbol or "").upper())


def _score_trending_stock(symbol: str, *, sector: str, regime: str) -> Dict[str, Any]:
    sector_strength_map = {
        "Energy": 86,
        "Technology": 78,
        "Semiconductors": 80,
        "Healthcare": 74,
        "Finance": 70,
        "Utilities": 72,
        "Consumer Staples": 71,
    }
    momentum_map = {
        "XOM": 78, "CVX": 72, "SLB": 76, "NVDA": 82, "MSFT": 68, "AMD": 74,
        "LLY": 70, "JNJ": 58, "UNH": 57, "JPM": 65, "GS": 62, "MS": 61,
        "NEE": 56, "DUK": 50, "SO": 49, "PG": 52, "KO": 48, "PEP": 47,
    }
    risk_map = {
        "XOM": 70, "CVX": 76, "SLB": 54, "NVDA": 45, "MSFT": 68, "AMD": 50,
        "LLY": 66, "JNJ": 82, "UNH": 70, "JPM": 63, "GS": 57, "MS": 55,
        "NEE": 80, "DUK": 84, "SO": 84, "PG": 83, "KO": 86, "PEP": 84,
    }
    regime_alignment_base = {
        "Risk-Off": {
            "Energy": 82, "Utilities": 84, "Consumer Staples": 84, "Healthcare": 76,
            "Finance": 55, "Technology": 34, "Semiconductors": 28,
        },
        "Late Risk-Off": {
            "Energy": 78, "Utilities": 80, "Consumer Staples": 79, "Healthcare": 74,
            "Finance": 58, "Technology": 42, "Semiconductors": 38,
        },
        "Risk-On": {
            "Energy": 64, "Utilities": 45, "Consumer Staples": 44, "Healthcare": 58,
            "Finance": 66, "Technology": 84, "Semiconductors": 88,
        },
        "Neutral": {
            "Energy": 72, "Utilities": 62, "Consumer Staples": 60, "Healthcare": 66,
            "Finance": 64, "Technology": 68, "Semiconductors": 70,
        },
    }

    normalized_symbol = str(symbol or "").upper()
    normalized_regime = str(regime or "Neutral")
    sector_strength = sector_strength_map.get(sector, 68)
    momentum_proxy = momentum_map.get(normalized_symbol, 62)
    risk_score = risk_map.get(normalized_symbol, 60)
    regime_alignment = regime_alignment_base.get(normalized_regime, regime_alignment_base["Neutral"]).get(sector, 60)
    raw_score = 0.40 * sector_strength + 0.20 * momentum_proxy + 0.20 * risk_score + 0.20 * regime_alignment
    score = int(round(max(0.0, min(100.0, raw_score))))

    tags: List[str] = []
    if regime_alignment >= 78 and risk_score >= 70:
        tags.append("High Conviction")
    if momentum_proxy >= 74:
        tags.append("Momentum Leader")
    if risk_score >= 80 and sector in {"Utilities", "Consumer Staples", "Healthcare"}:
        tags.append("Defensive Play")
    if not tags and regime_alignment >= 72:
        tags.append("Regime Aligned")

    return {
        "score": score,
        "tags": tags,
        "sector_strength_score": sector_strength,
        "momentum_proxy_score": momentum_proxy,
        "risk_score": risk_score,
        "regime_alignment_score": regime_alignment,
    }


def _infer_trending_stocks(sector: Optional[str], regime: Optional[str], suggested_etfs: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    normalized_sector = str(sector or "").strip() or "Energy"
    regime_text = str(regime or "Neutral")
    picks = list(SECTOR_TRENDING_FALLBACKS.get(normalized_sector, []))

    if not picks and suggested_etfs:
        for etf in suggested_etfs:
            for symbol in ETF_DECOMPOSITION.get(str(etf).upper(), []):
                picks.append({
                    "symbol": symbol,
                    "name": SYMBOL_NAME_MAP.get(symbol, symbol),
                    "role": f"top holding via {str(etf).upper()}",
                })

    if not picks:
        fallback_sector = "Consumer Staples" if "Risk-Off" in regime_text else "Technology"
        picks = list(SECTOR_TRENDING_FALLBACKS.get(fallback_sector, []))

    seen = set()
    inferred: List[Dict[str, Any]] = []
    for item in picks:
        symbol = str(item.get("symbol") or "").upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        score_payload = _score_trending_stock(symbol, sector=normalized_sector, regime=regime_text)
        inferred.append({
            "symbol": symbol,
            "name": item.get("name") or SYMBOL_NAME_MAP.get(symbol, symbol),
            "price": None,
            "daily_change": None,
            "return_1m": None,
            "reason": f"Estimated leader based on {normalized_sector} strength and {str(item.get('role') or 'sector leadership')}.",
            "inferred": True,
            "confidence_label": "Estimated leaders based on sector strength",
            **score_payload,
        })
    inferred.sort(key=lambda row: row.get("score") or 0, reverse=True)
    return inferred[:5]


def _canonical_name(symbol: str, fallback: Optional[str] = None) -> str:
    ticker = str(symbol or "").upper().strip()
    return SYMBOL_NAME_MAP.get(ticker) or str(fallback or ticker)


def _bucket_for_sector_pick(sector: str, symbol: str) -> str:
    ticker = str(symbol or "").upper()
    if ticker in set(SECTOR_CORE_SYMBOLS.get(sector, [])):
        return "core"
    if ticker in set(SECTOR_HIGH_BETA_SYMBOLS.get(sector, [])):
        return "high_beta"
    return "momentum"


def _energy_subsector_payload(confidence: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for sub_sector, meta in ENERGY_SUBSECTOR_MAP.items():
        rows.append({
            "type": sub_sector,
            "strength": meta["strength"],
            "reason": meta["why"],
            "examples": list(meta["symbols"][:3]) if confidence >= 65 else [],
        })
    return rows


def _reasoning_confidence_label(*, regime_available: bool, sector_count: int, sentiment_available: bool) -> str:
    aligned = 0
    if regime_available:
        aligned += 1
    if sector_count > 0:
        aligned += 1
    if sentiment_available:
        aligned += 1
    if aligned >= 3:
        return "high"
    if aligned >= 2:
        return "medium"
    return "low"


def _confidence_split_payload(*, data_confidence: str, reasoning_confidence: str) -> Dict[str, str]:
    return {
        "data_confidence": str(data_confidence or "low").lower(),
        "reasoning_confidence": str(reasoning_confidence or "low").lower(),
    }


class InvestmentReasoningEngine:
    def __init__(self, *, market_data, news_data, macro_data) -> None:
        self.market_data = market_data
        self.news_data = news_data
        self.macro_data = macro_data

    def _market_regime_context(self, macro: Dict[str, Any]) -> Dict[str, Any]:
        available = bool(macro.get("market_regime"))
        regime = str(macro.get("market_regime") or "Neutral")
        confidence = str(macro.get("regime_confidence") or "low").lower()
        positioning = macro.get("positioning") or _default_positioning()
        positioning = {
            "overweight": list(positioning.get("overweight") or []),
            "neutral": list(positioning.get("neutral") or []),
            "underweight": list(positioning.get("underweight") or []),
        }
        suggested_etfs = list(macro.get("suggested_etfs") or [])
        return {
            "available": available,
            "regime": regime,
            "confidence": confidence,
            "positioning": positioning,
            "suggested_etfs": suggested_etfs,
        }

    def _regime_interpretation(self, regime_ctx: Dict[str, Any], lang: str) -> str:
        if not regime_ctx.get("available"):
            return _pick_lang(
                lang,
                "ยังไม่สามารถยืนยัน market regime ได้ จึงใช้สมมติฐานแบบ Neutral เพื่อหลีกเลี่ยงการสรุปเชิงรุกเกินไป",
                "Market regime is unavailable right now, so the analysis falls back to a Neutral stance to avoid overstating conviction.",
            )
        regime = regime_ctx.get("regime")
        if regime == "Risk-Off":
            return _pick_lang(
                lang,
                "ตลาดอยู่ในโหมดป้องกันความเสี่ยง กระแสเงินมักไหลไปหากลุ่ม Defensive และพลังงาน ขณะที่หุ้น Growth ที่ผันผวนสูงมักถูกกดดัน",
                "The market is in a defensive regime, so capital usually favors energy and defensive sectors while higher-beta growth names face tighter risk budgets.",
            )
        if regime == "Risk-On":
            return _pick_lang(
                lang,
                "ตลาดอยู่ในโหมดรับความเสี่ยงมากขึ้น หุ้นเทค เซมิคอนดักเตอร์ และหุ้น momentum มักได้เปรียบกว่ากลุ่ม Defensive",
                "The market is in a risk-seeking regime, so technology, semiconductors, and momentum leaders usually have a better tailwind than defensive sectors.",
            )
        return _pick_lang(
            lang,
            "ตลาดยังอยู่ในช่วงค่อนข้างสมดุล จึงเหมาะกับการจัดพอร์ตแบบ balanced และคัดเลือกหุ้นรายตัวมากกว่าการไล่ซื้อเชิงรุก",
            "The market is in a more balanced regime, so a diversified posture and selective stock picking make more sense than aggressive directional bets.",
        )

    def _positioning_text(self, regime_ctx: Dict[str, Any], lang: str) -> str:
        positioning = regime_ctx.get("positioning") or _default_positioning()
        overweight = ", ".join(positioning.get("overweight") or []) or _pick_lang(lang, "ไม่มีข้อมูลยืนยัน", "Not confirmed")
        underweight = ", ".join(positioning.get("underweight") or []) or _pick_lang(lang, "ไม่มีน้ำหนักต่ำกว่าที่เด่นชัด", "No strong underweight call")
        neutral = ", ".join(positioning.get("neutral") or []) or _pick_lang(lang, "สมดุล", "Balanced")
        if lang == "th":
            return (
                f"- Overweight: {overweight}\n"
                f"- Neutral: {neutral}\n"
                f"- Underweight: {underweight}\n"
            )
        return (
            f"- Overweight: {overweight}\n"
            f"- Neutral: {neutral}\n"
            f"- Underweight: {underweight}\n"
        )

    def _stock_regime_application(self, *, symbol: str, sector: str, regime_ctx: Dict[str, Any], lang: str) -> str:
        sector_lower = str(sector or "").lower()
        risk_on_sector = any(token in sector_lower for token in ["technology", "semiconductor", "communication"])
        defensive_sector = any(token in sector_lower for token in ["energy", "utilities", "consumer staples", "healthcare"])
        regime = regime_ctx.get("regime")
        if not regime_ctx.get("available"):
            return _pick_lang(
                lang,
                f"{symbol} จะถูกประเมินภายใต้สมมติฐาน Neutral เพราะ market regime ยังไม่พร้อม จึงควรใช้ขนาดสถานะสมดุลและรอ confirmation เพิ่ม",
                f"{symbol} is being judged under a Neutral fallback because market regime is unavailable, so position sizing should stay balanced until confirmation improves.",
            )
        if regime == "Risk-Off":
            if risk_on_sector:
                return _pick_lang(
                    lang,
                    f"{symbol} อยู่ในกลุ่ม {sector} ซึ่งมักไม่สอดคล้องกับโหมด Risk-Off มากนัก จึงเหมาะกับการรอจังหวะหรือใช้ขนาดสถานะเล็กลง",
                    f"{symbol} sits in {sector}, which is less aligned with a Risk-Off backdrop, so waiting or using a smaller position size is usually more consistent with the regime.",
                )
            if defensive_sector:
                return _pick_lang(
                    lang,
                    f"{symbol} อยู่ในกลุ่ม {sector} ที่ค่อนข้างสอดคล้องกับโหมด Risk-Off จึงเหมาะกับการถือแบบ selective มากกว่าหุ้นเติบโตเชิงรุก",
                    f"{symbol} sits in {sector}, which is relatively aligned with a Risk-Off regime, so it fits selective exposure better than aggressive growth positions.",
                )
            return _pick_lang(
                lang,
                f"{symbol} ควรถูกประเมินแบบระวัง เพราะโหมด Risk-Off มักลด appetite ต่อหุ้นที่ไม่ใช่กลุ่มป้องกันความเสี่ยง",
                f"{symbol} should be treated cautiously because a Risk-Off regime usually reduces appetite for non-defensive exposure.",
            )
        if regime == "Risk-On":
            if risk_on_sector:
                return _pick_lang(
                    lang,
                    f"{symbol} อยู่ในกลุ่ม {sector} ซึ่งสอดคล้องกับโหมด Risk-On และมีโอกาสได้แรงหนุนจาก sector rotation มากกว่าปกติ",
                    f"{symbol} sits in {sector}, which aligns well with a Risk-On backdrop and can benefit more directly from pro-growth sector rotation.",
                )
            if defensive_sector:
                return _pick_lang(
                    lang,
                    f"{symbol} อยู่ในกลุ่ม {sector} ซึ่งอาจทำหน้าที่ถ่วงสมดุลพอร์ตได้ แต่มีโอกาส underperform ถ้าเงินไหลกลับเข้าหา growth/momentum",
                    f"{symbol} sits in {sector}, which can still diversify a portfolio, but it may lag if capital rotates aggressively back into growth and momentum leaders.",
                )
        return _pick_lang(
            lang,
            f"{symbol} ควรดูผ่านภาพตลาดแบบสมดุล โดยให้ความสำคัญกับปัจจัยเฉพาะตัวและการจัดพอร์ตที่ไม่สุดโต่งเกินไป",
            f"{symbol} should be viewed through a balanced market regime, where company-specific signals matter more than an extreme macro stance.",
        )

    def _macro_regime_application(self, regime_ctx: Dict[str, Any], lang: str) -> str:
        regime = regime_ctx.get("regime")
        if not regime_ctx.get("available"):
            return _pick_lang(
                lang,
                "ตอนนี้ยังไม่มี market regime ที่ยืนยันได้ จึงควรใช้การจัดพอร์ตแบบสมดุลและติดตามการหมุนของ sector เพิ่มเติม",
                "Market regime is temporarily unavailable, so the safest macro read-through is to stay balanced and wait for clearer sector rotation confirmation.",
            )
        if regime == "Risk-Off":
            return _pick_lang(
                lang,
                "ภายใต้โหมด Risk-Off การหมุนของตลาดมักเอื้อให้ Energy, Utilities และ Consumer Staples เด่นขึ้น ขณะที่ Technology และ Growth ถูกลดน้ำหนัก",
                "Under Risk-Off conditions, sector rotation usually favors Energy, Utilities, and Consumer Staples while Technology and broader Growth exposure are de-emphasized.",
            )
        if regime == "Risk-On":
            return _pick_lang(
                lang,
                "ภายใต้โหมด Risk-On ตลาดมักเปิดรับ Technology, Semiconductors และหุ้น momentum มากขึ้น ขณะที่กลุ่ม Defensive อาจกลายเป็นตัวถ่วงผลตอบแทน",
                "Under Risk-On conditions, the market usually rewards Technology, Semiconductors, and momentum-led exposure while Defensive sectors become less compelling.",
            )
        return _pick_lang(
            lang,
            "ภายใต้โหมด Neutral การจัดพอร์ตควรสมดุลมากขึ้น และเลือก sector ที่มีแรงส่งเฉพาะตัวชัดกว่าการไล่ตาม risk trade ด้านเดียว",
            "Under a Neutral regime, allocation should stay more balanced, with a focus on sectors showing genuine relative strength rather than one-way risk chasing.",
        )

    def generate_market_reasoning(self, *, regime_ctx: Dict[str, Any], top_sector: str, market_sentiment: str, lang: str) -> Dict[str, Any]:
        interpretation = self._regime_interpretation(regime_ctx, lang)
        positioning_text = self._positioning_text(regime_ctx, lang)
        application_text = self._macro_regime_application(regime_ctx, lang)
        headline = _pick_lang(
            lang,
            f"Regime {regime_ctx.get('regime')} ({regime_ctx.get('confidence')}) • กลุ่มนำ {top_sector} • ภาวะตลาด {market_sentiment}",
            f"Regime {regime_ctx.get('regime')} ({regime_ctx.get('confidence')}) • Leading sector {top_sector} • Market tone {market_sentiment}",
        )
        return {
            "headline": headline,
            "market_context": interpretation,
            "positioning_text": positioning_text,
            "application_text": application_text,
        }

    def _remember_regime(self, regime_ctx: Dict[str, Any]) -> Dict[str, Any]:
        regime = str(regime_ctx.get("regime") or "Neutral")
        confidence = str(regime_ctx.get("confidence") or "low").lower()
        REGIME_MEMORY.append({"regime": regime, "confidence": confidence})
        del REGIME_MEMORY[:-10]
        recent = REGIME_MEMORY[-3:]
        consistent = len(recent) >= 3 and len({row["regime"] for row in recent}) == 1
        return {
            "recent": recent,
            "consistent": consistent,
            "count": len(recent),
        }

    def analyze_macro_factors(self, *, event: str, macro: Dict[str, Any], regime_ctx: Dict[str, Any], top_sector: str) -> Dict[str, Any]:
        nominal_yield = _safe_float(macro.get("treasury_yield_10y"))
        inflation_expectation = _safe_float(macro.get("cpi"))
        real_yield = None
        if nominal_yield is not None and inflation_expectation is not None:
            real_yield = round(nominal_yield - inflation_expectation, 2)

        event_lower = str(event or "").lower()
        oil_shock = event_lower in {"war", "oil"}
        top_sector_lower = str(top_sector or "").lower()
        regime = str(regime_ctx.get("regime") or "").lower()

        if oil_shock:
            oil_trend = "rising"
        elif "energy" in top_sector_lower:
            oil_trend = "firm"
        else:
            oil_trend = "mixed"

        if inflation_expectation is not None:
            if inflation_expectation >= 3.0:
                inflation_signal = "elevated"
            elif inflation_expectation >= 2.0:
                inflation_signal = "moderate"
            else:
                inflation_signal = "contained"
        else:
            inflation_signal = "proxy-limited"

        if nominal_yield is not None:
            if nominal_yield >= 4.5:
                nominal_signal = "restrictive"
            elif nominal_yield >= 3.5:
                nominal_signal = "firm"
            else:
                nominal_signal = "easy"
        else:
            nominal_signal = "proxy-limited"

        if real_yield is not None:
            if real_yield >= 1.5:
                real_yield_signal = "rising_real_yield_pressure"
                tech_impact = "negative"
            elif real_yield <= 0.0:
                real_yield_signal = "easing_real_yield_support"
                tech_impact = "positive"
            else:
                real_yield_signal = "mixed_real_yield"
                tech_impact = "mixed"
        else:
            real_yield_signal = "limited"
            tech_impact = "cautious" if oil_shock else "mixed"

        if regime in {"risk-off", "late risk-off"} and oil_shock:
            liquidity = "tightening"
        elif regime in {"risk-off", "late risk-off"}:
            liquidity = "cautious"
        else:
            liquidity = "stable"

        return {
            "oil_trend": oil_trend,
            "inflation_expectation": inflation_expectation,
            "inflation_signal": inflation_signal,
            "nominal_yield": nominal_yield,
            "nominal_yield_signal": nominal_signal,
            "real_yield": real_yield,
            "real_yield_signal": real_yield_signal,
            "liquidity": liquidity,
            "tech_impact_bias": tech_impact,
            "proxy_note": "Inflation expectation uses CPI as an available proxy." if inflation_expectation is not None else "Inflation expectation proxy is limited in this response.",
        }

    def _factor_analysis_lines(self, *, factors: Dict[str, Any], lang: str) -> List[str]:
        nominal_yield = factors.get("nominal_yield")
        inflation_expectation = factors.get("inflation_expectation")
        real_yield = factors.get("real_yield")
        liquidity = str(factors.get("liquidity") or "stable")
        tech_impact = str(factors.get("tech_impact_bias") or "mixed")
        proxy_note = str(factors.get("proxy_note") or "")

        if lang == "th":
            lines = [
                f"Oil trend: {factors.get('oil_trend')}",
                (
                    f"Inflation expectation proxy (CPI): {inflation_expectation:.2f}%"
                    if inflation_expectation is not None else
                    "Inflation expectation proxy: ข้อมูลจำกัด"
                ),
                (
                    f"Nominal yield (10Y): {nominal_yield:.2f}%"
                    if nominal_yield is not None else
                    "Nominal yield (10Y): ข้อมูลจำกัด"
                ),
                (
                    f"Real yield proxy = nominal yield - inflation proxy = {real_yield:.2f}%"
                    if real_yield is not None else
                    "Real yield proxy: คำนวณไม่ได้เพราะข้อมูลไม่ครบ"
                ),
                (
                    "Real yield สูงขึ้นมักกด valuation หุ้นเทค เพราะ discount rate สูงขึ้น"
                    if tech_impact == "negative" else
                    "Real yield ที่ต่ำลงหรือผ่อนคลายลงมักช่วย valuation หุ้นเทค"
                    if tech_impact == "positive" else
                    "ผลต่อหุ้นเทคยังเป็นแบบผสม เพราะ real yield ยังไม่ชี้ชัด"
                ),
                (
                    "สภาพคล่องมีแนวโน้มตึงตัว ทำให้หุ้น duration ยาวถูกกดดัน"
                    if liquidity == "tightening" else
                    "สภาพคล่องยังระวังตัว ตลาดยังไม่พร้อมกลับไป risk-on เต็มที่"
                    if liquidity == "cautious" else
                    "สภาพคล่องยังไม่ตึงขึ้นชัด แต่ยังต้องดูทิศทาง yield ต่อ"
                ),
            ]
        else:
            lines = [
                f"Oil trend: {factors.get('oil_trend')}",
                (
                    f"Inflation expectation proxy (CPI): {inflation_expectation:.2f}%"
                    if inflation_expectation is not None else
                    "Inflation expectation proxy: data limited"
                ),
                (
                    f"Nominal yield (10Y): {nominal_yield:.2f}%"
                    if nominal_yield is not None else
                    "Nominal yield (10Y): data limited"
                ),
                (
                    f"Real yield proxy = nominal yield - inflation proxy = {real_yield:.2f}%"
                    if real_yield is not None else
                    "Real yield proxy cannot be computed cleanly with current inputs"
                ),
                (
                    "Higher real yields usually pressure tech valuations because the discount rate rises."
                    if tech_impact == "negative" else
                    "Lower or easing real yields usually support tech valuations."
                    if tech_impact == "positive" else
                    "Real-yield signal is mixed, so tech pressure should not be overstated."
                ),
                (
                    "Liquidity conditions look tighter, which usually hurts long-duration assets first."
                    if liquidity == "tightening" else
                    "Liquidity is still cautious, which argues against calling a clean bullish recovery too early."
                    if liquidity == "cautious" else
                    "Liquidity is relatively stable, but yield direction still matters."
                ),
            ]
        if proxy_note:
            lines.append(proxy_note)
        return lines

    def analyze_market_pricing(
        self,
        *,
        fear_greed: Optional[float],
        regime_ctx: Dict[str, Any],
        factors: Dict[str, Any],
        target_sector: str,
        sector_rankings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        target_sector_lower = str(target_sector or "").lower()
        target_row = next((row for row in sector_rankings if str(row.get("sector") or "").lower() == target_sector_lower), None)
        target_1m = _safe_float((target_row or {}).get("return_1m_pct"))
        target_3m = _safe_float((target_row or {}).get("return_3m_pct"))
        tech_pressure = str(factors.get("tech_impact_bias") or "mixed")

        if fear_greed is not None and fear_greed < 20:
            priced_in = True
            explanation = "Sentiment is already at an extreme-fear level, so part of the inflation and yield shock is likely reflected in prices."
            label = "partially priced in"
        elif target_sector_lower == "technology" and tech_pressure == "negative" and target_1m is not None and target_1m <= -8:
            priced_in = True
            explanation = "Technology has already absorbed a meaningful drawdown, so the macro shock is at least partly reflected in sector pricing."
            label = "partially priced in"
        elif str(regime_ctx.get("regime") or "").lower() in {"risk-off", "late risk-off"} and target_3m is not None and target_3m > 0:
            priced_in = False
            explanation = "The regime is still defensive, but the target sector has not fully reset, so valuation pressure may not be fully priced in yet."
            label = "not fully priced in"
        else:
            priced_in = False
            explanation = "The market does not yet show a full capitulation signal, so investors should assume the shock is only partially reflected."
            label = "unclear / partial"

        return {
            "is_priced_in": priced_in,
            "label": label,
            "explanation": explanation,
            "target_1m_return": target_1m,
            "target_3m_return": target_3m,
        }

    def analyze_positioning(
        self,
        *,
        fear_greed: Optional[float],
        regime_ctx: Dict[str, Any],
        target_sector: str,
        sector_rankings: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        target_sector_lower = str(target_sector or "").lower()
        target_row = next((row for row in sector_rankings if str(row.get("sector") or "").lower() == target_sector_lower), None)
        target_momentum = _safe_float((target_row or {}).get("momentum_score"))
        regime = str(regime_ctx.get("regime") or "Neutral")

        if fear_greed is not None and fear_greed <= 20:
            stance = "panic / defensive"
            explanation = "Positioning looks defensive rather than fully crowded long because sentiment is already in extreme fear territory."
        elif target_sector_lower in {"energy", "utilities", "consumer staples"} and target_momentum is not None and target_momentum >= 8:
            stance = "crowded long"
            explanation = f"{target_sector} already has strong relative momentum, so part of the market is likely crowded into the current leader."
        elif target_sector_lower in {"technology", "semiconductors"} and regime.lower() in {"risk-off", "late risk-off"}:
            stance = "crowded short"
            explanation = "Growth exposure is being de-emphasized in the current regime, so the market is leaning underweight or short relative to recent winners."
        else:
            stance = "neutral"
            explanation = "Positioning looks mixed rather than one-way, so confirmation should come from rates and relative strength rather than sentiment alone."

        return {
            "stance": stance,
            "explanation": explanation,
            "target_momentum": target_momentum,
        }

    def generate_entry_trigger(
        self,
        *,
        factors: Dict[str, Any],
        regime_ctx: Dict[str, Any],
        pricing: Dict[str, Any],
        positioning: Dict[str, Any],
        target_sector: str,
        lang: str,
    ) -> Dict[str, Any]:
        tech_target = str(target_sector or "").lower() in {"technology", "tech", "semiconductors"}
        real_yield = factors.get("real_yield")
        regime = str(regime_ctx.get("regime") or "Neutral")
        priced_in = bool(pricing.get("is_priced_in"))
        stance = str(positioning.get("stance") or "neutral")

        if lang == "th":
            if tech_target:
                conditions = [
                    "10Y yield หยุดเร่งขึ้นและเริ่มแกว่งในกรอบแคบ",
                    "ความผันผวนลดลงต่อเนื่อง ไม่ใช่แค่เด้งลงวันเดียว",
                    "Technology หยุด underperform เทียบกับ SPY อย่างน้อยหลาย session",
                ]
                action = (
                    "เริ่มทยอยสะสม Tech แบบแบ่งไม้"
                    if priced_in or stance == "crowded short" or (real_yield is not None and real_yield <= 1.0)
                    else "รอให้ yield และ volatility ยืนยันก่อน แล้วค่อยกลับเข้า Tech"
                )
            else:
                conditions = [
                    "bond yield ไม่เร่งขึ้นต่อ",
                    "ความผันผวนลดลงและ sector leader ยังรักษา relative strength ได้",
                    f"regime ยังไม่แย่ลงจาก {regime}",
                ]
                action = "ทยอยเพิ่มน้ำหนักใน sector ที่นำตลาดเมื่อ trigger ยืนยัน"
        else:
            if tech_target:
                conditions = [
                    "10Y yield stabilises instead of making fresh upside breaks",
                    "Volatility keeps falling rather than just one-day cooling",
                    "Technology stops underperforming versus SPY for several sessions",
                ]
                action = (
                    "Start scaling into tech in tranches"
                    if priced_in or stance == "crowded short" or (real_yield is not None and real_yield <= 1.0)
                    else "Wait for yield and volatility confirmation before rebuilding tech exposure"
                )
            else:
                conditions = [
                    "Bond yields stop repricing higher",
                    "Volatility falls while the leading sector keeps relative strength",
                    f"The regime does not deteriorate beyond {regime}",
                ]
                action = "Add exposure gradually once those triggers confirm"

        return {
            "condition_1": conditions[0],
            "condition_2": conditions[1],
            "condition_3": conditions[2],
            "action": action,
        }

    def analyze_macro(self, question: str, context: Any) -> Dict[str, Any]:
        lang = _lang_for(question)
        resolved_context = context.get("resolved_context") if isinstance(context, dict) else {}
        resolved_event = str((resolved_context or {}).get("event") or "").lower()
        resolved_target = str((resolved_context or {}).get("target") or "").lower()
        try:
            market = self.market_data.get_market_context(context)
        except Exception:
            market = {}
        try:
            macro = self.macro_data.build_macro_snapshot(market)
        except Exception:
            macro = {
                "market_sentiment": None,
                "fear_greed_index": None,
                "market_regime": None,
                "regime_confidence": None,
                "positioning": _default_positioning(),
                "suggested_etfs": [],
                "top_sector": None,
                "risk_outlook": None,
            }
        regime_ctx = self._market_regime_context(macro)
        try:
            sector_rankings = (self.market_data.get_sector_rankings() or {}).get("rankings", [])
        except Exception:
            sector_rankings = []
        q = (question or "").strip()
        q_lower = q.lower()
        is_tech_impact_question = any(
            term in q_lower
            for term in [
                "tech", "technology stocks", "technology stock", "tech stocks",
                "หุ้นเทค", "หุ้นเทคโนโลยี", "ผลกระทบต่อหุ้นเทค", "กระทบหุ้นเทค",
                "impact on tech", "effect on tech", "impact on technology", "effect on technology",
            ]
        ) or ("tech" in resolved_target or "technology" in resolved_target)

        is_energy_shock = any(
            term in q_lower
            for term in [
                "iran", "war", "middle east", "oil", "crude", "geopolitic",
                "geopolitical", "sanction", "conflict", "strait of hormuz",
            ]
        ) or resolved_event in {"war", "oil"}
        top_sector = sector_rankings[0].get("sector") if sector_rankings else ("Energy" if is_energy_shock else "Defensive sectors")
        top_three = sector_rankings[:3]
        fear_greed = _safe_float(macro.get("fear_greed_index"))
        market_sentiment = macro.get("market_sentiment") or ("Cautious" if is_energy_shock else "Mixed")
        reasoning_block = self.generate_market_reasoning(
            regime_ctx=regime_ctx,
            top_sector=str(top_sector),
            market_sentiment=str(market_sentiment),
            lang=lang,
        )
        regime_memory = self._remember_regime(regime_ctx)
        factor_event = resolved_event or ("war" if is_energy_shock else "")
        factors = self.analyze_macro_factors(
            event=factor_event,
            macro=macro,
            regime_ctx=regime_ctx,
            top_sector=str(top_sector),
        )
        factor_lines = self._factor_analysis_lines(factors=factors, lang=lang)
        target_sector_for_pricing = "Technology" if is_tech_impact_question else str(top_sector)
        pricing = self.analyze_market_pricing(
            fear_greed=fear_greed,
            regime_ctx=regime_ctx,
            factors=factors,
            target_sector=target_sector_for_pricing,
            sector_rankings=top_three if top_three else sector_rankings,
        )
        positioning_state = self.analyze_positioning(
            fear_greed=fear_greed,
            regime_ctx=regime_ctx,
            target_sector=target_sector_for_pricing,
            sector_rankings=top_three if top_three else sector_rankings,
        )
        entry_trigger = self.generate_entry_trigger(
            factors=factors,
            regime_ctx=regime_ctx,
            pricing=pricing,
            positioning=positioning_state,
            target_sector=target_sector_for_pricing,
            lang=lang,
        )
        interpretation_text = reasoning_block["market_context"]
        positioning_text = reasoning_block["positioning_text"]
        application_text = reasoning_block["application_text"]

        if is_energy_shock:
            direct_effects = [
                "Oil prices typically rise first because markets price in supply disruption risk and higher shipping or insurance costs.",
                "US equity volatility often increases as investors shift toward safe-haven assets and reduce cyclical exposure.",
            ]
            indirect_effects = [
                "Higher energy prices can feed into inflation expectations, which may pressure bond yields and rate-sensitive growth stocks.",
                "Rising fuel and input costs can compress margins for transport, airlines, industrials, and discretionary businesses.",
            ]
            sector_effects = [
                "Energy usually benefits first because higher crude prices can improve revenue expectations.",
                "Defense and some commodity-linked industries may also hold up better than the broad market.",
                "Airlines, transports, consumer discretionary, and other fuel-sensitive sectors usually face more pressure.",
            ]
            market_behavior = [
                "The first market response is often a risk-off move: weaker equities, stronger oil, stronger defensive positioning, and wider volatility.",
                "If the conflict remains contained, equity markets often stabilize after the initial shock.",
                "If the disruption broadens into inflation or supply-chain stress, the drawdown can last longer and become more sector-specific.",
            ]
            risk_scenarios = [
                "Contained conflict: a short-lived volatility spike with Energy outperforming the broad market.",
                "Oil shock scenario: broader inflation pressure, weaker consumer sectors, and tighter financial conditions.",
                "Escalation scenario: wider risk-off behavior across global equities, especially in high-beta sectors.",
            ]
            lead = (
                "A potential Iran-related conflict would usually affect the US stock market first through oil, inflation expectations, and a broader risk-off reaction."
            )
            conclusion = (
                "The most likely first-order market effect is higher oil and higher volatility. Energy can outperform on a relative basis, but the broader US equity market usually becomes more defensive until the geopolitical risk path is clearer."
            )
            if lang == "th":
                direct_effects = [
                    "ผลกระทบระยะแรกมักเริ่มที่ราคาน้ำมัน เพราะตลาดจะรีบสะท้อนความเสี่ยงด้านอุปทาน การขนส่ง และค่าประกันภัย",
                    "ความผันผวนของหุ้นสหรัฐมักสูงขึ้น เพราะเงินทุนจะไหลเข้าสินทรัพย์ปลอดภัยและลดน้ำหนักหุ้นวัฏจักร",
                ]
                indirect_effects = [
                    "เมื่อน้ำมันสูงขึ้น ตลาดมักยกคาดการณ์เงินเฟ้อขึ้นตาม ซึ่งกดดันอัตราผลตอบแทนพันธบัตรและหุ้น Growth ที่ไวต่อดอกเบี้ย",
                    "ต้นทุนพลังงานและวัตถุดิบที่สูงขึ้นจะบีบ margin ของสายการบิน ขนส่ง อุตสาหกรรม และค้าปลีกบางส่วน",
                ]
                sector_effects = [
                    "กลุ่ม Energy มักได้ประโยชน์ก่อน เพราะรายได้และ margin มีโอกาสดีขึ้นตามราคาน้ำมัน",
                    "กลุ่ม Defense และ commodity-linked บางส่วนมักทนแรงขายได้ดีกว่าตลาด",
                    "กลุ่ม Airlines, Consumer Discretionary และหุ้นที่พึ่งต้นทุนพลังงานสูงมักถูกกดดันมากกว่า",
                ]
                market_behavior = [
                    "ระยะสั้นตลาดมักเข้าสู่ภาวะ risk-off: หุ้นอ่อนตัวลง น้ำมันขึ้น และเงินไหลเข้ากลุ่มป้องกันความเสี่ยง",
                    "ถ้าเหตุการณ์จำกัดวง ตลาดมักเริ่มนิ่งขึ้นหลังแรงกระแทกแรกผ่านไป",
                    "แต่ถ้าเหตุการณ์ลุกลามจนกดดันเงินเฟ้อหรือ supply chain ต่อเนื่อง การปรับฐานอาจยาวและกระจายเป็นราย sector มากขึ้น",
                ]
                risk_scenarios = [
                    "กรณีจำกัดวง: ความผันผวนพุ่งชั่วคราว และ Energy มีโอกาส outperform ตลาด",
                    "กรณีน้ำมันช็อก: เงินเฟ้อสูงขึ้น กดดันกลุ่มผู้บริโภคและเงื่อนไขการเงิน",
                    "กรณียกระดับความขัดแย้ง: ตลาดเสี่ยงทั่วโลกอาจเข้าสู่โหมด risk-off ชัดเจน โดยเฉพาะหุ้น beta สูง",
                ]
        else:
            direct_effects = [
                "Macro shocks usually affect asset prices first through growth expectations, inflation expectations, and policy-rate expectations.",
                "The immediate market reaction is often strongest in rate-sensitive sectors and high-beta equities.",
            ]
            indirect_effects = [
                "Changes in yields, credit conditions, and sector rotation can reshape equity leadership even when headline index moves are moderate.",
                "Macro uncertainty can reduce valuation multiples before it clearly changes earnings expectations.",
            ]
            sector_effects = [
                f"Current sector leadership still matters: {top_sector} is leading on the current ranking set.",
                "Defensive sectors usually hold up better when macro uncertainty rises, while cyclical sectors become more path-dependent.",
            ]
            market_behavior = [
                "Markets usually reprice macro shocks in two stages: the initial headline reaction, then a slower earnings and valuation adjustment.",
                "High uncertainty regimes often create wider sector dispersion rather than a single uniform market move.",
            ]
            risk_scenarios = [
                "Soft-landing scenario: sector leadership broadens and risk appetite recovers.",
                "Sticky inflation scenario: rate-sensitive growth remains under pressure.",
                "Growth scare scenario: defensives outperform while cyclical leadership fades.",
            ]
            lead = (
                "Macro developments affect US equities mainly through growth, inflation, rates, and sector rotation rather than through a single one-step market response."
            )
            conclusion = (
                f"The market backdrop remains {str(market_sentiment).lower()}, so macro shocks should be read through both the rate path and current sector leadership, with {top_sector} still the relative leader in the latest sector ranking."
            )
            if lang == "th":
                direct_effects = [
                    "แรงกระแทกทางมหภาคมักส่งผลต่อราคาสินทรัพย์ผ่านคาดการณ์การเติบโต เงินเฟ้อ และเส้นทางดอกเบี้ยนโยบายก่อน",
                    "แรงตอบสนองระยะแรกมักเห็นชัดในหุ้นที่ไวต่อดอกเบี้ยและหุ้น beta สูง",
                ]
                indirect_effects = [
                    "การเปลี่ยนแปลงของ bond yield, credit conditions และการหมุนของ sector สามารถเปลี่ยนผู้นำตลาดได้ แม้ดัชนีหลักจะยังไม่ขยับมาก",
                    "ความไม่แน่นอนทางมหภาคสามารถกด valuation ได้ก่อนที่กำไรจะถูกปรับลดอย่างชัดเจน",
                ]
                sector_effects = [
                    f"ต้องดู sector leadership ปัจจุบันควบคู่กันไป โดยตอนนี้ {top_sector} ยังนำในชุด ranking ล่าสุด",
                    "ในภาวะมหภาคไม่แน่นอน กลุ่ม Defensive มักยืนได้ดีกว่า ขณะที่กลุ่มวัฏจักรจะขึ้นกับทิศทางเศรษฐกิจมากกว่า",
                ]
                market_behavior = [
                    "ตลาดมักตอบสนองเป็นสองช่วง: แรงกระแทกจาก headline ก่อน แล้วค่อยปรับ valuation และประมาณการกำไรตามมา",
                    "ในภาวะไม่แน่นอนสูง มักเห็นการกระจายผลตอบแทนระหว่าง sector มากกว่าการเคลื่อนที่ไปทิศเดียวทั้งตลาด",
                ]
                risk_scenarios = [
                    "Soft landing: ภาวะรับความเสี่ยงฟื้นและผู้นำตลาดกระจายกว้างขึ้น",
                    "Sticky inflation: หุ้น Growth ที่ไวต่อดอกเบี้ยยังถูกกดดันต่อ",
                    "Growth scare: กลุ่ม Defensive มักชนะกลุ่มวัฏจักร",
                ]

        ranking_lines = [
            f"{idx + 1}. {row.get('sector')} ({row.get('etf')}): 1M {(_safe_float(row.get('return_1m_pct')) or 0):+.2f}% | "
            f"3M {(_safe_float(row.get('return_3m_pct')) or 0):+.2f}% | "
            + (
                f"6M {(_safe_float(row.get('return_6m_pct')) or 0):+.2f}% | "
                if row.get("return_6m_pct") is not None else "6M not fully confirmed | "
            )
            + f"Momentum {(_safe_float(row.get('momentum_score')) or 0):+.2f}%"
            for idx, row in enumerate(top_three)
        ]
        if not ranking_lines:
            ranking_lines = (
                [
                    "1. Energy (XLE): market usually prices geopolitical supply risk through oil first.",
                    "2. Defense-linked cyclicals: relative resilience often improves in risk-off macro regimes.",
                    "3. Airlines / consumer discretionary: typically more exposed to fuel-cost and demand pressure.",
                ]
                if lang == "en" else
                [
                    "1. Energy (XLE): ตลาดมักสะท้อนความเสี่ยงด้านอุปทานผ่านราคาน้ำมันก่อน",
                    "2. กลุ่มที่เชื่อมกับ defense: มักทนแรงขายได้ดีกว่าในภาวะ risk-off",
                    "3. Airlines / Consumer Discretionary: มักถูกกดดันจากต้นทุนพลังงานและอุปสงค์ที่อ่อนลง",
                ]
            )

        if is_tech_impact_question:
            if lang == "th":
                direct_effects = [
                    "สงครามหรือความตึงเครียดทางภูมิรัฐศาสตร์มักดันราคาน้ำมันขึ้นก่อน และทำให้ตลาดยกคาดการณ์เงินเฟ้อสูงขึ้น",
                    "เมื่อเงินเฟ้อเสี่ยงสูงขึ้น อัตราผลตอบแทนพันธบัตรมักขยับขึ้นตาม และต้นทุนเงินทุนของตลาดก็สูงขึ้น",
                ]
                indirect_effects = [
                    "bond yield ที่สูงขึ้นทำให้ discount rate สูงขึ้น ซึ่งกด valuation ของหุ้นเทคโดยเฉพาะกลุ่ม Growth ที่มองกำไรไกลในอนาคต",
                    "ในเวลาเดียวกัน เม็ดเงินมักหมุนจาก Tech ไปหา Energy และกลุ่ม Defensive ทำให้ผลตอบแทนเชิงเปรียบเทียบของหุ้นเทคอ่อนลง",
                ]
                sector_effects = [
                    "กลุ่ม Technology มัก underperform ระยะสั้น เพราะ valuation ถูกกดจากทั้งดอกเบี้ยและ risk-off sentiment",
                    f"กลุ่มที่นำตลาดตอนนี้คือ {top_sector} ซึ่งมักได้เปรียบเชิงกระแสเงินมากกว่ากลุ่ม Technology ในภาวะนี้",
                    "การฟื้นตัวของหุ้นเทคในระยะกลางมักขึ้นกับว่า bond yield จะเริ่มนิ่งลงหรือไม่",
                ]
                market_behavior = [
                    "ช่วงแรกตลาดมักขายหุ้น Growth ก่อน เพราะความเสี่ยงด้านเงินเฟ้อและดอกเบี้ยกลับมาเด่นกว่าธีมการเติบโต",
                    "ถ้า yield ยังไม่หยุดขึ้น หุ้นเทคมักฟื้นได้ช้ากว่ากลุ่มพลังงานและกลุ่ม Defensive",
                    "ความผันผวนที่เริ่มนิ่งลงอย่างเดียว ยังไม่แปลว่าหุ้นเทคกลับมาเป็นผู้นำทันที",
                ]
                risk_scenarios = [
                    "กรณี yield ขึ้นต่อ: หุ้นเทคอาจถูกกด valuation ต่อเนื่อง แม้กำไรยังไม่เสียหายมาก",
                    "กรณี yield เริ่มนิ่ง: หุ้นเทคคุณภาพสูงอาจกลับมาน่าสนใจแบบค่อยเป็นค่อยไป",
                    "กรณีราคาน้ำมันย่อลงแรง: แรงกดดันต่อเงินเฟ้ออาจลดลง และช่วยให้ sentiment ต่อหุ้นเทคดีขึ้น",
                ]
                lead = "หุ้นเทคมักถูกกดดันเมื่อสงครามดันราคาน้ำมัน เงินเฟ้อคาดการณ์ และ bond yield สูงขึ้นพร้อมกัน"
                conclusion = "ระยะสั้นหุ้นเทคมีโอกาส underperform ส่วนระยะกลางจะขึ้นกับว่า bond yield เริ่มนิ่งลงและแรงกดดันเชิง valuation คลี่คลายหรือไม่"
            else:
                direct_effects = [
                    "War or geopolitical stress tends to push oil prices higher first and lift inflation expectations.",
                    "As inflation risk rises, bond yields usually move higher and capital becomes more expensive.",
                ]
                indirect_effects = [
                    "Higher bond yields raise the discount rate, which compresses tech valuations, especially for long-duration growth assets.",
                    "At the same time, capital typically rotates away from Technology into Energy and defensive sectors, weakening Tech on a relative basis.",
                ]
                sector_effects = [
                    "Technology usually underperforms in the short term because both valuation pressure and risk-off positioning work against it.",
                    f"{top_sector} is leading the market right now, which gives it stronger flow support than Technology in the current regime.",
                    "Medium-term recovery for Tech depends on whether bond yields stabilize and valuation pressure starts to ease.",
                ]
                market_behavior = [
                    "Markets often sell Growth first because inflation and rates temporarily matter more than long-term growth narratives.",
                    "If yields keep rising, Technology typically lags Energy and defensive sectors.",
                    "Cooling volatility alone does not automatically mean Tech leadership is back.",
                ]
                risk_scenarios = [
                    "If yields keep rising, Technology can remain under pressure even with solid fundamentals.",
                    "If yields stabilize, higher-quality Tech names can recover before higher-beta growth names.",
                    "If oil retraces sharply, inflation pressure can ease and Tech sentiment can improve.",
                ]
                lead = "Technology stocks usually come under pressure when war pushes oil, inflation expectations, and bond yields higher at the same time."
                conclusion = "Short term, Technology is likely to underperform. Medium term, recovery depends on yield stabilization and easing valuation pressure."
                if factors.get("tech_impact_bias") == "positive":
                    actionable = "The better setup is gradual re-entry into higher-quality Technology once real yields start easing and nominal yields stabilize, rather than an immediate all-clear for speculative growth."
                    conclusion = "Tech can recover sooner than the headline war narrative implies if real yields start to ease and valuation pressure relaxes."
                elif factors.get("tech_impact_bias") == "mixed":
                    actionable = "A balanced stance makes more sense than an outright bearish call on Tech when the real-yield signal is mixed. Wait for cleaner confirmation from yields before adding aggressive growth."
                    conclusion = "The impact on Tech is conditional rather than automatic because the real-yield response is still mixed."

        if lang == "th":
            pricing_lines = [
                f"Pricing status: {pricing.get('label')}",
                pricing.get("explanation"),
            ]
            positioning_lines = [
                f"Positioning: {positioning_state.get('stance')}",
                positioning_state.get("explanation"),
            ]
            trigger_lines = [
                entry_trigger.get("condition_1"),
                entry_trigger.get("condition_2"),
                entry_trigger.get("condition_3"),
                f"Action: {entry_trigger.get('action')}",
            ]
        else:
            pricing_lines = [
                f"Pricing status: {pricing.get('label')}",
                pricing.get("explanation"),
            ]
            positioning_lines = [
                f"Positioning: {positioning_state.get('stance')}",
                positioning_state.get("explanation"),
            ]
            trigger_lines = [
                entry_trigger.get("condition_1"),
                entry_trigger.get("condition_2"),
                entry_trigger.get("condition_3"),
                f"Action: {entry_trigger.get('action')}",
            ]

        if lang == "th":
            actionable = (
                "มุมมองเชิงกลยุทธ์คือให้น้ำหนักมากกว่าตลาดใน Energy แบบเลือกตัวและคงมุมมองระวังต่อ Airlines, Consumer Discretionary และ growth ที่ไวต่ออัตราดอกเบี้ย"
                if is_energy_shock else
                f"มุมมองเชิงกลยุทธ์คือให้น้ำหนักตาม sector ที่ยังมีแรงส่งเด่น โดยเฉพาะ {top_sector} แต่ควรคุมขนาดสถานะตามภาวะมหภาค"
            )
            overview_line = (
                f"ตลาดอยู่ในโหมด {market_sentiment} • กลุ่มเด่น {top_sector} • ความเสี่ยงสูงจากแรงส่งด้านน้ำมันและเงินเฟ้อ"
                if is_energy_shock else
                f"ภาวะตลาด {market_sentiment} • กลุ่มนำ {top_sector} • ความเสี่ยงขึ้นกับทิศทางดอกเบี้ยและการหมุนของ sector"
            )
            key_drivers = [
                "ราคาน้ำมันมีแนวโน้มตอบสนองก่อน เพราะตลาดกังวลความเสี่ยงด้านอุปทาน",
                "เมื่อน้ำมันขึ้น ตลาดมักยกคาดการณ์เงินเฟ้อขึ้นตาม",
                "เงินเฟ้อที่สูงขึ้นเพิ่มโอกาสที่ดอกเบี้ยจะอยู่ระดับสูงนานขึ้น",
                "ดอกเบี้ยสูงและ risk-off ทำให้เงินทุนหมุนจาก Growth ไปยัง Energy และ Defensive",
            ] if is_energy_shock else [
                "ปัจจัยมหภาคเปลี่ยนคาดการณ์การเติบโตและเงินเฟ้อพร้อมกัน",
                "เส้นทางดอกเบี้ยเป็นตัวกำหนด valuation ของหุ้น Growth เทียบกับ Defensive",
                "การหมุนของ sector เป็นสัญญาณสำคัญกว่าการมอง headline index เพียงอย่างเดียว",
                f"{top_sector} ยังนำอยู่ใน ranking ล่าสุด จึงยังเป็นแกนหลักของการจัดพอร์ต",
            ]
            ui_risks = [
                "margin ของกลุ่มที่ใช้พลังงานสูงอาจถูกกดดัน",
                "หุ้น Growth ที่ไวต่อดอกเบี้ยมีโอกาส underperform",
                "ความผันผวนของตลาดโลกอาจเร่งขึ้นหากเหตุการณ์ยืดเยื้อ",
                "sector leadership อาจกลับทิศเร็วถ้าราคาน้ำมันย่อตัวแรง",
            ] if is_energy_shock else [
                "valuation ของหุ้น Growth ยังเสี่ยงต่อแรงกดดันจาก bond yield",
                "ตลาดอาจแกว่งแรงหากข้อมูลเงินเฟ้อหรือเศรษฐกิจออกมาผิดคาด",
                "การหมุนของ sector อาจเปลี่ยนเร็วในช่วงที่ macro regime ไม่ชัดเจน",
                "หุ้นวัฏจักรยังเสี่ยงหากการเติบโตอ่อนกว่าที่ตลาดคาด",
            ]
            actionable_view = (
                "Overweight: Energy | Neutral: Defensive | Underweight: Growth / Consumer Discretionary"
                if is_energy_shock else
                f"Overweight: {top_sector} | Neutral: Defensive | Underweight: Rate-sensitive Growth"
            )
            if is_tech_impact_question:
                actionable = "กลยุทธ์คือ ลดน้ำหนัก Overweight ในหุ้นเทคก่อน รอให้ bond yield เริ่มนิ่ง แล้วค่อยกลับเข้าแบบเลือกตัว โดยเน้นหุ้นเทคคุณภาพสูงมากกว่าหุ้น growth ที่ผันผวนสูง"
                overview_line = f"Regime {regime_ctx['regime']} ({regime_ctx['confidence']}) • หุ้นเทคยังถูกกดดันจากเงินเฟ้อคาดการณ์ ดอกเบี้ย และแรงหมุนเงินไปยัง {top_sector}"
                key_drivers = [
                    "สงครามหรือความเสี่ยงภูมิรัฐศาสตร์ดันราคาน้ำมันและเงินเฟ้อคาดการณ์ขึ้น",
                    "เงินเฟ้อที่สูงขึ้นกดดัน bond yield และ discount rate",
                    "หุ้นเทคเป็นสินทรัพย์ที่อ่อนไหวต่อ discount rate จึงมักถูกกด valuation ก่อน",
                    f"เงินทุนหมุนไปยัง {top_sector} และกลุ่ม Defensive มากกว่ากลุ่ม Technology",
                ]
                ui_risks = [
                    "bond yield ที่ขึ้นต่อยังเป็นความเสี่ยงหลักต่อ valuation หุ้นเทค",
                    "หุ้น growth beta สูงอาจอ่อนกว่าหุ้นเทคคุณภาพสูง",
                    "การลดลงของ volatility เพียงอย่างเดียว ยังไม่ยืนยันว่าหุ้นเทคกลับมาเป็นผู้นำ",
                    "ถ้าเงินเฟ้อไม่ชะลอ การ re-rating ของหุ้นเทคอาจถูกจำกัด",
                ]
                actionable_view = "ลดน้ำหนัก Tech ชั่วคราว | รอ yield stabilization | กลับเข้าแบบคัดตัวเมื่อ valuation reset"
                if factors.get("tech_impact_bias") == "positive":
                    actionable = "กลยุทธ์คือเริ่มกลับเข้า Tech แบบค่อยเป็นค่อยไปได้ ถ้า real yield ผ่อนคลายและ bond yield เริ่มนิ่ง โดยยังเน้นหุ้นเทคคุณภาพสูงก่อนหุ้น growth beta สูง"
                    conclusion = "แม้ตลาดยังระวังความเสี่ยง แต่ถ้า real yield เริ่มผ่อนคลาย หุ้นเทคคุณภาพสูงจะกลับมาน่าสนใจเร็วกว่าหุ้น growth ที่เก็งกำไร"
                elif factors.get("tech_impact_bias") == "mixed":
                    actionable = "กลยุทธ์คือคงน้ำหนัก Tech แบบสมดุล รอการยืนยันจาก real yield และ bond yield ก่อนเพิ่มความเสี่ยง เพราะสงครามไม่ได้แปลว่าหุ้นเทคจะอ่อนเสมอไปถ้าอัตราผลตอบแทนไม่เร่งขึ้น"
                    conclusion = "ผลต่อหุ้นเทคยังเป็นแบบผสม เพราะต้องดูว่าความเสี่ยงเงินเฟ้อจะดัน real yield ต่อจริงหรือไม่"
            answer = (
                "ภาพรวมตลาด\n"
                + f"- Regime: {regime_ctx['regime']}\n- Confidence: {regime_ctx['confidence']}\n"
                + (
                    f"- CNN Fear & Greed (reference): {round(fear_greed, 1)} ({market_sentiment})\n"
                    if fear_greed is not None else
                    "- Market regime unavailable: using Neutral fallback\n"
                )
                + "\nการตีความ\n"
                + f"- {interpretation_text}\n\n"
                + "การวางน้ำหนัก\n"
                + positioning_text
                + "\nการประยุกต์กับคำถามนี้\n"
                + f"- {application_text}\n\n"
                + "FACTOR ANALYSIS\n"
                + "\n".join([f"- {line}" for line in factor_lines])
                + "\n\n"
                + "POSITIONING\n"
                + "\n".join([f"- {line}" for line in positioning_lines if line])
                + "\n\n"
                + "PRICING\n"
                + "\n".join([f"- {line}" for line in pricing_lines if line])
                + "\n\n"
                + "ENTRY TRIGGER\n"
                + "\n".join([f"- {line}" for line in trigger_lines if line])
                + "\n\n"
                + "- การอ่านภาพมหภาคครั้งนี้เน้นผลต่อราคาน้ำมัน เงินเฟ้อ ดอกเบี้ย และการหมุนของ sector\n\n"
                + "ข้อมูลที่ใช้\n"
                + "\n".join([f"- {line}" for line in ranking_lines])
                + "\n\nผลกระทบทางตรง\n"
                + "\n".join([f"- {point}" for point in direct_effects])
                + "\n\nผลกระทบทางอ้อม\n"
                + "\n".join([f"- {point}" for point in indirect_effects])
                + "\n\nผลกระทบต่อแต่ละกลุ่มอุตสาหกรรม\n"
                + "\n".join([f"- {point}" for point in sector_effects])
                + "\n\nพฤติกรรมตลาด\n"
                + "\n".join([f"- {point}" for point in market_behavior])
                + "\n\nกรณีความเสี่ยง\n"
                + "\n".join([f"- {point}" for point in risk_scenarios])
                + "\n\nข้อสรุปเชิงกลยุทธ์\n"
                + actionable
            )
            lead = (
                "ความขัดแย้งด้านภูมิรัฐศาสตร์มักกระทบตลาดหุ้นสหรัฐผ่านราคาน้ำมัน เงินเฟ้อคาดการณ์ และบรรยากาศ risk-off"
                if is_energy_shock else
                "ปัจจัยมหภาคมักกระทบตลาดหุ้นผ่านการเปลี่ยนแปลงของอัตราดอกเบี้ย เงินเฟ้อ และการหมุนของกลุ่มอุตสาหกรรม"
            )
            conclusion = (
                "ให้น้ำหนักเชิงเลือกใน Energy และกลุ่มป้องกันความเสี่ยง พร้อมลดน้ำหนักกลุ่มที่ไวต่อต้นทุนพลังงานและ valuation"
                if is_energy_shock else
                f"รักษามุมมองตาม sector leadership ปัจจุบัน โดยดูว่าปัจจัยมหภาคจะเปลี่ยนเส้นทางดอกเบี้ยและการหมุนของ sector หรือไม่"
            )
        else:
            actionable = (
                "Positioning should lean overweight Energy and selective defense exposure, while remaining underweight airlines, fuel-sensitive consumer names, and duration-sensitive growth until the oil and volatility path stabilizes."
                if is_energy_shock else
                f"Positioning should stay aligned with current sector leadership, with a neutral-to-overweight stance on {top_sector} and tighter risk controls on rate-sensitive or high-beta laggards."
            )
            overview_line = (
                f"Market sentiment is {market_sentiment}; Energy is the key sector, and risk is elevated because oil, inflation, and rates are moving in the same direction."
                if is_energy_shock else
                f"Market sentiment is {market_sentiment}; {top_sector} remains the leading sector, while rate direction still drives overall risk."
            )
            key_drivers = [
                "Oil tends to move first as markets price supply disruption risk.",
                "Higher oil feeds into inflation expectations.",
                "Higher inflation expectations keep rate expectations tighter for longer.",
                "That rate and risk-off mix drives sector rotation away from growth and toward Energy and defensives.",
            ] if is_energy_shock else [
                "Macro shocks first reset growth and inflation expectations.",
                "Rate expectations then reprice equity valuations, especially in growth.",
                "Sector rotation becomes the clearest market expression of the macro regime.",
                f"{top_sector} still leads the latest ranking, so it remains the main relative-strength reference point.",
            ]
            ui_risks = [
                "Margin compression can hit fuel-sensitive sectors quickly.",
                "Growth stocks remain vulnerable to higher-for-longer rates.",
                "Global equity volatility can spike if the conflict broadens.",
                "Sector leadership can reverse quickly if oil retraces sharply.",
            ] if is_energy_shock else [
                "Growth valuations remain sensitive to bond-yield moves.",
                "Equity volatility can rise if inflation or macro data surprise to the upside.",
                "Sector leadership can rotate quickly when the macro regime shifts.",
                "Cyclicals remain exposed if growth expectations deteriorate.",
            ]
            actionable_view = (
                "Overweight: Energy | Neutral: Defensive | Underweight: Growth / Consumer Discretionary"
                if is_energy_shock else
                f"Overweight: {top_sector} | Neutral: Defensive | Underweight: Rate-sensitive Growth"
            )
            if is_tech_impact_question:
                if factors.get("tech_impact_bias") == "positive":
                    actionable = "The better setup is gradual re-entry into higher-quality Technology once real yields start easing and nominal yields stabilize, rather than an immediate all-clear for speculative growth."
                elif factors.get("tech_impact_bias") == "mixed":
                    actionable = "A balanced stance makes more sense than an outright bearish call on Tech when the real-yield signal is mixed. Wait for cleaner confirmation from yields before adding aggressive growth."
            answer = (
                "Market Context\n"
                + f"- Regime: {regime_ctx['regime']}\n- Confidence: {regime_ctx['confidence']}\n"
                + (
                    f"- CNN Fear & Greed (reference): {round(fear_greed, 1)} ({market_sentiment})\n"
                    if fear_greed is not None else
                    "- Market regime unavailable: using Neutral fallback\n"
                )
                + "\nInterpretation\n"
                + f"- {interpretation_text}\n\n"
                + "Positioning\n"
                + positioning_text
                + "\nApplication to This Question\n"
                + f"- {application_text}\n\n"
                + "FACTOR ANALYSIS\n"
                + "\n".join([f"- {line}" for line in factor_lines])
                + "\n\n"
                + "POSITIONING\n"
                + "\n".join([f"- {line}" for line in positioning_lines if line])
                + "\n\n"
                + "PRICING\n"
                + "\n".join([f"- {line}" for line in pricing_lines if line])
                + "\n\n"
                + "ENTRY TRIGGER\n"
                + "\n".join([f"- {line}" for line in trigger_lines if line])
                + "\n\n"
                + "- This macro read-through focuses on oil, inflation expectations, rates, and cross-sector positioning.\n\n"
                + "Data Used\n"
                + "\n".join([f"- {line}" for line in ranking_lines])
                + "\n\nDirect Impact\n"
                + "\n".join([f"- {point}" for point in direct_effects])
                + "\n\nIndirect Impact\n"
                + "\n".join([f"- {point}" for point in indirect_effects])
                + "\n\nSector-Level Effects\n"
                + "\n".join([f"- {point}" for point in sector_effects])
                + "\n\nMarket Behavior\n"
                + "\n".join([f"- {point}" for point in market_behavior])
                + "\n\nRisk Scenarios\n"
                + "\n".join([f"- {point}" for point in risk_scenarios])
                + "\n\nConclusion (Actionable)\n"
                + actionable
            )

        final_confidence = min(92, (74 if is_energy_shock else 70) + (4 if regime_memory.get("consistent") else 0))

        return {
            "intent": "macro_analysis",
            "analysis_type": "macro_analysis",
            "analysis_engine": "macro_reasoning_engine",
            "answer": answer,
            "confidence": final_confidence,
            "sources": ["Macro knowledge base", "Market sentiment model", "Sector ETF model"],
            "data_validation": {"price_data": bool(sector_rankings), "news_data": False, "technical_data": bool(sector_rankings)},
            "summary": {
                "market_sentiment": market_sentiment,
                "market_regime": regime_ctx["regime"],
                "regime_confidence": regime_ctx["confidence"],
                "fear_greed_score": fear_greed,
                "trending_sector": top_sector,
                "risk_outlook": macro.get("risk_outlook"),
                "real_yield": factors.get("real_yield"),
                "liquidity": factors.get("liquidity"),
                "pricing_status": pricing.get("label"),
                "positioning_state": positioning_state.get("stance"),
            },
            "answer_schema": {
                "intent": "macro_analysis",
                "answer_title": "การวิเคราะห์มหภาคและภูมิรัฐศาสตร์" if lang == "th" else "Macro and Geopolitical Analysis",
                "direct_answer": lead,
                "market_context": {
                    "market_regime": regime_ctx["regime"],
                    "confidence": regime_ctx["confidence"],
                    "fear_greed_index": fear_greed,
                    "positioning": regime_ctx["positioning"],
                    "suggested_etfs": regime_ctx["suggested_etfs"],
                    "points": [
                        f"Regime: {regime_ctx['regime']} ({regime_ctx['confidence']} confidence)",
                        (
                            f"CNN Fear & Greed (reference): {round(fear_greed, 1)} ({market_sentiment})"
                            if fear_greed is not None else "Market regime unavailable: using Neutral fallback."
                        ),
                        f"Leading sector now: {top_sector}",
                    ] + ranking_lines,
                },
                "factor_analysis": {
                    "event": factor_event or "general_macro",
                    "oil_trend": factors.get("oil_trend"),
                    "inflation_expectation": factors.get("inflation_expectation"),
                    "nominal_yield": factors.get("nominal_yield"),
                    "real_yield": factors.get("real_yield"),
                    "liquidity": factors.get("liquidity"),
                    "tech_impact_bias": factors.get("tech_impact_bias"),
                    "points": factor_lines,
                },
                "positioning_analysis": {
                    "stance": positioning_state.get("stance"),
                    "points": positioning_lines,
                },
                "pricing_analysis": {
                    "is_priced_in": pricing.get("is_priced_in"),
                    "label": pricing.get("label"),
                    "points": pricing_lines,
                },
                "entry_trigger": entry_trigger,
                "fundamental_drivers": {
                    "points": direct_effects + indirect_effects,
                },
                "sector_analysis": {
                    "sector_rankings": top_three,
                    "points": ranking_lines,
                },
                "risk_factors": {
                    "points": risk_scenarios,
                },
                "investment_interpretation": {
                    "recommendation": (
                        "ให้น้ำหนักเชิงเลือกใน Energy / Defensive"
                        if is_energy_shock else
                        f"Neutral ถึง Overweight ใน {top_sector}"
                    ),
                    "text": f"{application_text} | Pricing: {pricing.get('label')} | Positioning: {positioning_state.get('stance')} | Trigger: {entry_trigger.get('action')}",
                    "confidence": final_confidence,
                    "forecast_horizon": {},
                },
                "sources": ["Macro knowledge base", "Market sentiment model", "Sector ETF model"],
                "source_tags": _source_tags("Macro Knowledge Base", "Fear & Greed", "Sector ETF Model", "Market Snapshot Cache"),
                "overview": overview_line,
                "rationale": key_drivers,
                "summary_points": key_drivers,
                "risks": ui_risks,
                "actionable_view": f"{application_text} | {entry_trigger.get('action')}",
                "regime_memory": {
                    "consistent": regime_memory.get("consistent"),
                    "recent": regime_memory.get("recent"),
                },
            },
            "followups": (
                [
                    "กลุ่มไหนมักได้ประโยชน์เมื่อราคาน้ำมันพุ่ง?",
                    "น้ำมันแพงขึ้นจะกดดันเงินเฟ้อยังไง?",
                    "แล้วจะกระทบหุ้นเทคอย่างไร?",
                ] if lang == "th" else [
                    "Which sectors usually benefit from an oil shock?",
                    "How would higher oil prices affect inflation?",
                    "What could this mean for technology stocks?",
                ]
            ),
            "status": {
                "online": True,
                "message": "พร้อมใช้งาน" if lang == "th" else "Connected",
                "live_data_ready": bool(sector_rankings),
                "market_context_loaded": True,
            },
        }

    def analyze_stock_recommendation(self, question: str, context: Any) -> Dict[str, Any]:
        lang = _lang_for(question)
        try:
            market = self.market_data.get_market_context(context)
        except Exception:
            market = {}
        try:
            macro = self.macro_data.build_macro_snapshot(market)
        except Exception:
            macro = {
                "market_sentiment": None,
                "fear_greed_index": None,
                "market_regime": None,
                "regime_confidence": None,
                "positioning": _default_positioning(),
                "suggested_etfs": [],
            }
        regime_ctx = self._market_regime_context(macro)
        interpretation_text = self._regime_interpretation(regime_ctx, lang)
        positioning_text = self._positioning_text(regime_ctx, lang)
        application_text = self._macro_regime_application(regime_ctx, lang)

        ideas = [
            {
                "ticker": "KO",
                "name": "Coca-Cola",
                "sector": "Consumer Staples",
                "reasons": [
                    "Stable global demand and repeat-purchase consumer base.",
                    "Strong dividend history and lower volatility than typical growth stocks.",
                    "Cash-flow resilience tends to support downside protection in weaker macro regimes.",
                ],
                "risk_note": "Can underperform when investors rotate aggressively into high-beta growth stocks.",
            },
            {
                "ticker": "PG",
                "name": "Procter & Gamble",
                "sector": "Consumer Staples",
                "reasons": [
                    "Defensive household-products franchise with steady demand.",
                    "Consistent earnings profile and strong brand portfolio.",
                    "Usually fits lower-risk screens because revenue is less cyclical than industrial or tech names.",
                ],
                "risk_note": "Margin pressure can rise if commodity or input costs move sharply higher.",
            },
            {
                "ticker": "JNJ",
                "name": "Johnson & Johnson",
                "sector": "Healthcare",
                "reasons": [
                    "Diversified healthcare exposure with resilient cash flows.",
                    "Healthcare demand is generally less tied to the business cycle.",
                    "Large-cap quality profile typically aligns with lower-volatility positioning.",
                ],
                "risk_note": "Healthcare regulation and litigation can still create stock-specific event risk.",
            },
        ]

        direct_answer = _pick_lang(
            lang,
            "หุ้นความเสี่ยงต่ำที่น่าสนใจตอนนี้ ได้แก่ Coca-Cola (KO), Procter & Gamble (PG) และ Johnson & Johnson (JNJ)",
            "Here are 3 low-risk stock ideas: Coca-Cola (KO), Procter & Gamble (PG), and Johnson & Johnson (JNJ).",
        )
        if lang == "th":
            answer = (
                "ภาพรวมตลาด\n"
                + f"- Regime: {regime_ctx['regime']}\n- Confidence: {regime_ctx['confidence']}\n"
                + (
                    f"- CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})\n\n"
                    if macro.get("fear_greed_index") is not None else
                    "- Market regime unavailable: using Neutral fallback\n\n"
                )
                + "การตีความ\n"
                + f"- {interpretation_text}\n\n"
                + "การวางน้ำหนัก\n"
                + positioning_text
                + "\nการประยุกต์กับคำถามนี้\n"
                + f"- {application_text}\n\n"
                + "เกณฑ์คัดเลือก\n"
                + "- มูลค่าตลาดขนาดใหญ่\n"
                + "- กำไรค่อนข้างสม่ำเสมอ\n"
                + "- ความผันผวนต่ำกว่าหุ้นเติบโตทั่วไป\n"
                + "- มีกระแสเงินสดหรือประวัติปันผลที่ค่อนข้างแข็งแรง\n\n"
                + "หุ้นแนะนำ\n"
                + "\n".join(
                    [
                        f"{idx + 1}. {idea['name']} ({idea['ticker']})\n"
                        + ("\n".join(
                            [
                                f"- {'รายได้ค่อนข้างสม่ำเสมอและความต้องการสินค้าไม่ผันผวนมาก' if idea['ticker'] == 'KO' else ''}",
                                f"- {'เป็นผู้นำสินค้าอุปโภคบริโภคจำเป็นและกำไรค่อนข้างเสถียร' if idea['ticker'] == 'PG' else ''}",
                                f"- {'ธุรกิจสุขภาพหลากหลายและกระแสเงินสดแข็งแรง' if idea['ticker'] == 'JNJ' else ''}",
                            ]
                        ).replace("\n\n", "\n").strip())
                        + f"\n- ข้อควรระวัง: {('อาจให้ผลตอบแทนช้ากว่าหุ้น Growth ในช่วงตลาดขาขึ้น' if idea['ticker'] == 'KO' else 'ต้นทุนวัตถุดิบที่สูงขึ้นอาจกดดัน margin' if idea['ticker'] == 'PG' else 'ความเสี่ยงด้านกฎระเบียบและคดีความยังมีอยู่')}\n"
                        for idx, idea in enumerate(ideas)
                    ]
                )
                + "\nหมายเหตุความเสี่ยง\n"
                + "หุ้นความเสี่ยงต่ำไม่ได้แปลว่าไม่มีความเสี่ยง เพียงแต่โดยทั่วไปมักผันผวนน้อยกว่าหุ้นเติบโตสูง\n\n"
                + "มุมมองตามเวลา\n"
                + "- ระยะสั้น: กลุ่ม Defensive มักยืนได้ดีกว่าเมื่อ sentiment ตลาดระวังตัวหรือ bond yield แกว่งขึ้น\n"
                + "- ระยะกลาง: ผลตอบแทนจะขึ้นกับว่ากระแส risk-on กลับมาหรือไม่ เพราะหุ้นเสี่ยงต่ำอาจช้ากว่าตลาดในช่วงขาขึ้นแรง\n\n"
                + "การวางน้ำหนัก\n"
                + "- ให้น้ำหนัก: Consumer Staples / Healthcare\n"
                + "- ถือเป็นกลาง: Utilities\n"
                + "- ให้น้ำหนักต่ำกว่า: High-beta Growth ถ้าตลาดยังไม่เสถียร\n\n"
                + "ข้อสรุป\n"
                + "ถ้าต้องการเริ่มจากหุ้นความเสี่ยงต่ำ ให้โฟกัสหุ้นขนาดใหญ่ในกลุ่ม Consumer Staples และ Healthcare ก่อน แล้วค่อยตรวจ valuation และแนวโน้มล่าสุดอีกครั้งก่อนตัดสินใจ"
            )
        else:
            answer = (
                "Market Context\n"
                + f"- Regime: {regime_ctx['regime']}\n- Confidence: {regime_ctx['confidence']}\n"
                + (
                    f"- CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')}).\n\n"
                    if macro.get("fear_greed_index") is not None else
                    "- Market regime unavailable: using Neutral fallback.\n\n"
                )
                + "Interpretation\n"
                + f"- {interpretation_text}\n\n"
                + "Positioning\n"
                + positioning_text
                + "\nApplication to This Question\n"
                + f"- {application_text}\n\n"
                + "Selection Logic\n"
                + "- Large market capitalization\n"
                + "- Stable earnings profile\n"
                + "- Lower volatility than typical growth stocks\n"
                + "- Strong dividend or cash-flow resilience\n\n"
                + "Recommended Stocks\n"
                + "\n".join(
                    [
                        f"{idx + 1}. {idea['name']} ({idea['ticker']})\n"
                        + "\n".join([f"- {reason}" for reason in idea["reasons"]])
                        + f"\n- Risk note: {idea['risk_note']}\n"
                        for idx, idea in enumerate(ideas)
                    ]
                )
                + "\nRisk Note\n"
                + "Low-risk does not mean no risk. These stocks may underperform in strong bull markets or when investors rotate into higher-beta growth names.\n\n"
                + "Time Horizon\n"
                + "- Short-term: Defensive large caps usually hold up better when sentiment is cautious or yields are unstable.\n"
                + "- Medium-term: Relative performance depends on whether markets stay defensive or rotate back toward higher-beta growth.\n\n"
                + "Positioning\n"
                + "- Overweight: Consumer Staples / Healthcare\n"
                + "- Neutral: Utilities\n"
                + "- Underweight: High-beta Growth if the market remains unstable\n\n"
                + "Conclusion\n"
                + "For a lower-risk starting list, focus on large-cap defensive names in Consumer Staples and Healthcare, then verify current valuation and trend before acting."
            )
        return {
            "intent": "stock_recommendation",
            "analysis_type": "stock_recommendation",
            "analysis_engine": "defensive_stock_recommendation_engine",
            "answer": answer,
            "confidence": 76,
            "sources": ["Historical market behavior", "Sector characteristics", "Risk profile model"],
            "data_validation": {"price_data": False, "news_data": False, "technical_data": False},
            "summary": {
                "market_sentiment": macro.get("market_sentiment"),
                "market_regime": regime_ctx["regime"],
                "regime_confidence": regime_ctx["confidence"],
                "fear_greed_score": macro.get("fear_greed_index"),
                "trending_sector": "Consumer Staples / Healthcare",
                "risk_outlook": "Lower risk equity ideas",
            },
            "answer_schema": {
                "intent": "stock_recommendation",
                "answer_title": _pick_lang(lang, "ไอเดียหุ้นความเสี่ยงต่ำ", "Low-Risk Stock Ideas"),
                "direct_answer": direct_answer,
                "market_context": {
                    "market_regime": regime_ctx["regime"],
                    "confidence": regime_ctx["confidence"],
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "positioning": regime_ctx["positioning"],
                    "suggested_etfs": regime_ctx["suggested_etfs"],
                    "points": [
                        f"Regime: {regime_ctx['regime']} ({regime_ctx['confidence']} confidence)",
                        (
                            f"CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})"
                            if macro.get("fear_greed_index") is not None
                            else "Market regime unavailable: using Neutral fallback."
                        ),
                        f"Overweight sectors: {', '.join(regime_ctx['positioning'].get('overweight') or ['Balanced allocation'])}",
                        f"Underweight sectors: {', '.join(regime_ctx['positioning'].get('underweight') or ['No strong underweight call'])}",
                    ],
                },
                "recommended_stocks": ideas,
                "fundamental_drivers": {
                    "points": [
                        "Lower-risk candidates typically combine large market capitalization, resilient earnings, and steadier demand.",
                        "Dividend history and lower volatility often matter more than maximum upside in a low-risk screen.",
                    ],
                },
                "risk_factors": {
                    "points": [
                        "Low-risk does not mean no risk.",
                        "These names can lag when investors prefer high-beta growth or cyclical rebound trades.",
                        "Rates, regulation, and margin pressure can still affect defensive sectors.",
                    ],
                },
                "investment_interpretation": {
                    "recommendation": "Defensive large-cap ideas",
                    "text": f"{interpretation_text} {application_text}",
                    "confidence": 76,
                    "forecast_horizon": {},
                },
                "cause_effect_chain": [
                    _pick_lang(lang, "ภาวะระวังความเสี่ยง → เงินไหลเข้ากลุ่ม Defensive → รายได้เสถียรช่วยลด drawdown", "Risk-off market tone -> capital rotates into defensives -> steadier earnings help limit drawdowns."),
                    _pick_lang(lang, "bond yield ผันผวน → หุ้น growth แกว่งมากกว่า → หุ้นปันผลและ consumer staples มักดูปลอดภัยกว่า", "Yield volatility -> growth multiples become more fragile -> dividend and staple names often look safer."),
                ],
                "time_horizon": _time_horizon_payload(
                    short_term=_pick_lang(lang, "ระยะสั้น Defensive มักยืนได้ดีกว่าเมื่อ sentiment ยังระวัง", "In the short term, defensive stocks tend to hold up better while sentiment remains cautious."),
                    medium_term=_pick_lang(lang, "ระยะกลางจะขึ้นกับว่าตลาดยังป้องกันความเสี่ยงต่อหรือหมุนกลับไปหา growth", "In the medium term, relative performance depends on whether the market stays defensive or rotates back toward growth."),
                ),
                "actionable_view": _pick_lang(
                    lang,
                    f"{application_text} ให้น้ำหนักมากกว่าตลาดใน Consumer Staples / Healthcare, ถือเป็นกลาง Utilities, และให้น้ำหนักต่ำกว่า High-beta Growth",
                    f"{application_text} Overweight Consumer Staples / Healthcare, stay Neutral Utilities, and Underweight high-beta Growth.",
                ),
                "source_tags": _source_tags("Historical Market Behavior", "Sector Characteristics", "Risk Profile Model"),
            },
            "followups": [
                *(
                    [
                        "ใน 3 ตัวนี้ ตัวไหนปันผลเด่นสุด?",
                        "เปรียบเทียบ KO กับ PG",
                        "มีหุ้น Healthcare ที่เสี่ยงต่ำอีกไหม?",
                    ]
                    if lang == "th" else
                    [
                        "Which of these has the strongest dividend profile?",
                        "Compare KO vs PG",
                        "Show lower-risk healthcare stocks",
                    ]
                )
            ],
            "status": {
                "online": True,
                "message": "คำแนะนำเชิงความรู้" if lang == "th" else "Knowledge-based recommendation",
                "live_data_ready": False,
                "market_context_loaded": True,
            },
        }

    def analyze_open_recommendation(self, question: str, context: Any) -> Dict[str, Any]:
        lang = _lang_for(question)
        try:
            market = self.market_data.get_market_context(context)
        except Exception:
            market = {}
        try:
            macro = self.macro_data.build_macro_snapshot(market)
        except Exception:
            macro = {
                "market_sentiment": None,
                "fear_greed_index": None,
                "market_regime": None,
                "regime_confidence": None,
                "positioning": _default_positioning(),
                "suggested_etfs": [],
                "top_sector": None,
            }
        regime_ctx = self._market_regime_context(macro)
        interpretation_text = self._regime_interpretation(regime_ctx, lang)
        positioning_text = self._positioning_text(regime_ctx, lang)

        ideas = [
            {
                "ticker": "AAPL",
                "name": "Apple",
                "sector": "Technology",
                "reasons": [
                    "Market leader with strong free cash flow and a resilient installed base.",
                    "High-quality balance sheet and ecosystem strength support earnings durability.",
                    "Large-cap leadership makes it a practical default core holding idea.",
                ],
                "risk_note": "Can lag when hardware demand weakens or valuation compresses during rate shocks.",
            },
            {
                "ticker": "MSFT",
                "name": "Microsoft",
                "sector": "Technology",
                "reasons": [
                    "Cloud and enterprise software model supports recurring revenue and high margins.",
                    "Strong balance sheet and diversified business mix reduce single-product risk.",
                    "Often screens well as a high-quality large-cap compounder.",
                ],
                "risk_note": "Enterprise spending slowdowns and multiple compression can still pressure returns.",
            },
            {
                "ticker": "NVDA",
                "name": "NVIDIA",
                "sector": "Technology",
                "reasons": [
                    "AI infrastructure leadership continues to support data-center demand.",
                    "Revenue growth and strategic positioning remain strong versus many peers.",
                    "It represents higher upside potential than a purely defensive name set.",
                ],
                "risk_note": "Valuation and sentiment can swing sharply, so this is not the lowest-risk choice in the list.",
            },
        ]

        direct_answer = _pick_lang(
            lang,
            "ถ้าถามแบบกว้าง ๆ ตอนนี้ผมจะเริ่มจาก Apple (AAPL), Microsoft (MSFT) และ NVIDIA (NVDA) ก่อน แล้วค่อยปรับตามสไตล์ที่คุณต้องการ เช่น เสี่ยงต่ำ เติบโต หรือปันผล",
            "Here are 3 strong default stock ideas: Apple (AAPL), Microsoft (MSFT), and NVIDIA (NVDA). If you want, I can narrow this to low-risk, growth, or dividend stocks next.",
        )
        if lang == "th":
            answer = (
                "ภาพรวมตลาด\n"
                + f"- Regime: {regime_ctx['regime']}\n- Confidence: {regime_ctx['confidence']}\n"
                + (
                    f"- CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})\n"
                    if macro.get("fear_greed_index") is not None else
                    "- Market regime unavailable: using Neutral fallback\n"
                )
                + f"- กลุ่มที่นำตลาดตอนนี้: {macro.get('top_sector') or 'ยังไม่มีข้อมูลยืนยัน'}\n\n"
                + "การตีความ\n"
                + f"- {interpretation_text}\n\n"
                + "การวางน้ำหนัก\n"
                + positioning_text
                + "\nการประยุกต์กับคำถามนี้\n"
                + f"- {self._stock_regime_application(symbol='NVDA', sector='Technology', regime_ctx=regime_ctx, lang=lang)}\n\n"
                + "กลยุทธ์เริ่มต้น\n"
                + "- เลือกหุ้นขนาดใหญ่ที่เป็นผู้นำตลาด\n"
                + "- เน้นธุรกิจที่พื้นฐานแข็งแรง\n"
                + "- กำไรมีคุณภาพและค่อนข้างสม่ำเสมอ\n"
                + "- มีความได้เปรียบทางการแข่งขันชัดเจน\n\n"
                + "หุ้นแนะนำ\n"
                + "1. Apple (AAPL)\n- กระแสเงินสดแข็งแรง\n- ecosystem แข็งแกร่ง\n- เหมาะเป็น core holding\n\n"
                + "2. Microsoft (MSFT)\n- รายได้ recurring สูง\n- ธุรกิจ cloud และ software margin ดี\n- คุณภาพกิจการเด่นในระยะยาว\n\n"
                + "3. NVIDIA (NVDA)\n- ผู้นำด้าน AI infrastructure\n- อุปสงค์จาก data center ยังเด่น\n- upside สูงกว่า แต่ความผันผวนสูงกว่าด้วย\n\n"
                + "ข้อควรระวัง\n"
                + "AAPL และ MSFT เหมาะกับมุมมองคุณภาพระยะยาว ส่วน NVDA เหมาะกับนักลงทุนที่รับความผันผวนได้มากกว่า\n\n"
                + "มุมมองตามเวลา\n"
                + "- ระยะสั้น: หุ้นคุณภาพขนาดใหญ่ยังได้เปรียบเมื่อสภาพคล่องและ sentiment ตลาดยังไม่แน่นอน\n"
                + "- ระยะกลาง: ถ้า AI capex และกำไรเทคยังเร่งต่อ NVDA จะมี upside สูงกว่า แต่ถ้าดอกเบี้ยกด valuation หุ้นคุณภาพอย่าง AAPL/MSFT จะเสถียรกว่า\n\n"
                + "การวางน้ำหนัก\n"
                + "- ให้น้ำหนัก: Quality Large Cap / Software / AI Infrastructure แบบคัดตัว\n"
                + "- ถือเป็นกลาง: กลุ่ม Defensive\n"
                + "- ให้น้ำหนักต่ำกว่า: Cyclical ที่อ่อนไหวต่อเศรษฐกิจ ถ้า macro ยังไม่ชัด\n\n"
                + "ถ้าต้องการให้แนะนำแบบตรงสไตล์มากขึ้น บอกได้เลยว่าต้องการหุ้นเสี่ยงต่ำ หุ้นเติบโต หรือหุ้นปันผล"
            )
        else:
            answer = (
                "Market Context\n"
                + f"- Regime: {regime_ctx['regime']}\n- Confidence: {regime_ctx['confidence']}\n"
                + (
                    f"- CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')}).\n"
                    if macro.get("fear_greed_index") is not None else
                    "- Market regime unavailable: using Neutral fallback.\n"
                )
                + f"- Current leading sector: {macro.get('top_sector') or 'Data unavailable for this signal.'}\n\n"
                + "Interpretation\n"
                + f"- {interpretation_text}\n\n"
                + "Positioning\n"
                + positioning_text
                + "\nApplication to This Question\n"
                + f"- {self._stock_regime_application(symbol='NVDA', sector='Technology', regime_ctx=regime_ctx, lang=lang)}\n\n"
                + "Default Strategy\n"
                + "- Large-cap market leaders\n"
                + "- Strong fundamentals\n"
                + "- Stable earnings quality\n"
                + "- Durable competitive advantages\n\n"
                + "Recommended Stocks\n"
                + "\n".join(
                    [
                        f"{idx + 1}. {idea['name']} ({idea['ticker']})\n"
                        + "\n".join([f"- {reason}" for reason in idea["reasons"]])
                        + f"\n- Risk note: {idea['risk_note']}\n"
                        for idx, idea in enumerate(ideas)
                    ]
                )
                + "\nClarification\n"
                + "If you want a more specific list, tell me whether you prefer low-risk, growth, or dividend stocks.\n\n"
                + "Time Horizon\n"
                + "- Short-term: High-quality large caps tend to hold up better when liquidity and sentiment are unstable.\n"
                + "- Medium-term: If AI capex and software spending stay firm, NVDA can offer more upside, while AAPL and MSFT remain steadier if rates pressure valuations.\n\n"
                + "Positioning\n"
                + "- Overweight: Quality Large Cap / Software / AI Infrastructure selectively\n"
                + "- Neutral: Defensive sectors\n"
                + "- Underweight: Macro-sensitive cyclicals if the macro path is still unclear\n\n"
                + "Conclusion\n"
                + "For a broad default recommendation, AAPL and MSFT fit high-quality core holdings, while NVDA adds stronger growth exposure with higher volatility."
            )
        return {
            "intent": "open_recommendation",
            "analysis_type": "open_recommendation",
            "analysis_engine": "default_stock_recommendation_engine",
            "answer": answer,
            "confidence": 74,
            "sources": ["Historical market behavior", "Quality factor heuristics", "Sector leadership context"],
            "data_validation": {"price_data": False, "news_data": False, "technical_data": False},
            "summary": {
                "market_sentiment": macro.get("market_sentiment"),
                "market_regime": regime_ctx["regime"],
                "regime_confidence": regime_ctx["confidence"],
                "fear_greed_score": macro.get("fear_greed_index"),
                "trending_sector": macro.get("top_sector"),
                "risk_outlook": "Balanced default stock ideas",
            },
            "answer_schema": {
                "intent": "open_recommendation",
                "answer_title": _pick_lang(lang, "ไอเดียหุ้นพื้นฐานดีสำหรับเริ่มต้น", "Default Stock Ideas"),
                "direct_answer": direct_answer,
                "market_context": {
                    "market_regime": regime_ctx["regime"],
                    "confidence": regime_ctx["confidence"],
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "positioning": regime_ctx["positioning"],
                    "suggested_etfs": regime_ctx["suggested_etfs"],
                    "points": [
                        f"Regime: {regime_ctx['regime']} ({regime_ctx['confidence']} confidence)",
                        (
                            f"CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})"
                            if macro.get("fear_greed_index") is not None
                            else "Market regime unavailable: using Neutral fallback."
                        ),
                        f"Overweight sectors: {', '.join(regime_ctx['positioning'].get('overweight') or ['Balanced allocation'])}",
                        f"Underweight sectors: {', '.join(regime_ctx['positioning'].get('underweight') or ['No strong underweight call'])}",
                    ],
                },
                "recommended_stocks": ideas,
                "fundamental_drivers": {
                    "points": [
                        "Default open-ended recommendations prioritize large-cap quality and strong business durability.",
                        "AAPL and MSFT fit core quality screens, while NVDA adds higher-growth upside with more volatility.",
                    ],
                },
                "risk_factors": {
                    "points": [
                        "Open-ended recommendations are a starting point, not a personalized allocation.",
                        "NVDA carries materially higher volatility than AAPL or MSFT.",
                        "Even large-cap leaders can underperform during valuation resets or macro shocks.",
                    ],
                },
                "investment_interpretation": {
                    "recommendation": "Balanced large-cap leaders",
                    "text": f"{interpretation_text} {self._stock_regime_application(symbol='NVDA', sector='Technology', regime_ctx=regime_ctx, lang='en')}",
                    "confidence": 74,
                    "forecast_horizon": {},
                },
                "cause_effect_chain": [
                    _pick_lang(lang, "สภาพคล่องและดอกเบี้ย → valuation ของหุ้นคุณภาพ/หุ้นเติบโต → การกระจายน้ำหนักระหว่าง AAPL, MSFT และ NVDA", "Liquidity and rates -> quality/growth valuation sensitivity -> capital allocation across AAPL, MSFT, and NVDA."),
                    _pick_lang(lang, "AI capex และ demand ฝั่ง data center → โมเมนตัมของ NVDA สูงขึ้น แต่ความผันผวนก็สูงขึ้นตาม", "AI capex and data-center demand -> stronger NVDA momentum, but also higher volatility."),
                ],
                "time_horizon": _time_horizon_payload(
                    short_term=_pick_lang(lang, "ระยะสั้น หุ้นคุณภาพขนาดใหญ่ยังได้เปรียบเมื่อ sentiment ตลาดยังไม่แน่นอน", "In the short term, quality large caps tend to outperform while sentiment remains uncertain."),
                    medium_term=_pick_lang(lang, "ระยะกลาง ถ้า AI และ cloud spending ยังแข็งแรง หุ้นเทคคุณภาพยังมีโอกาสนำตลาดต่อ", "In the medium term, quality tech can stay in leadership if AI and cloud spending remain strong."),
                ),
                "actionable_view": _pick_lang(
                    lang,
                    f"{self._stock_regime_application(symbol='NVDA', sector='Technology', regime_ctx=regime_ctx, lang='th')} ให้น้ำหนักมากกว่าตลาดในหุ้นคุณภาพขนาดใหญ่แบบคัดตัว โดยใช้ AAPL/MSFT เป็นแกน และเพิ่ม NVDA เฉพาะส่วนที่รับความผันผวนได้",
                    f"{self._stock_regime_application(symbol='NVDA', sector='Technology', regime_ctx=regime_ctx, lang='en')} Overweight selectively in quality large caps, using AAPL/MSFT as core exposure and adding NVDA only where higher volatility is acceptable.",
                ),
                "source_tags": _source_tags("Historical Market Behavior", "Quality Factor Heuristics", "Sector Leadership Context"),
            },
            "followups": [
                *(
                    [
                        "คุณอยากได้หุ้นเสี่ยงต่ำ หุ้นเติบโต หรือหุ้นปันผล?",
                        "เปรียบเทียบ AAPL กับ MSFT",
                        "ขอรายชื่อหุ้นที่เสี่ยงต่ำกว่านี้",
                    ]
                    if lang == "th" else
                    [
                        "Do you prefer low-risk, growth, or dividend stocks?",
                        "Compare AAPL vs MSFT",
                        "Show lower-risk stock ideas instead",
                    ]
                )
            ],
            "status": {
                "online": True,
                "message": "คำแนะนำเชิงความรู้" if lang == "th" else "Knowledge-based recommendation",
                "live_data_ready": False,
                "market_context_loaded": True,
            },
        }

    def analyze_stock(self, symbol: str, context: Any) -> Dict[str, Any]:
        bundle = self.market_data.get_stock_bundle(symbol)
        bundle_meta = bundle.get("meta") or {}
        history_1m = close_series((bundle.get("history_1m") or {}).get("history", []))
        history_3m = close_series((bundle.get("history_3m") or {}).get("history", []))
        history_1y = close_series((bundle.get("history_1y") or {}).get("history", []))
        details = bundle.get("details") or {}
        profile = bundle.get("profile") or {}
        market = self.market_data.get_market_context(context)
        macro = self.macro_data.build_macro_snapshot(market)
        regime_ctx = self._market_regime_context(macro)
        news = self.news_data.get_symbol_news(symbol, days_back=7, limit=12)
        stale_cache_used = bool(bundle_meta.get("stale_cache_used"))
        cached_age_minutes = _safe_float(bundle_meta.get("cached_age_minutes"))
        provider_chain = [tag for tag in (bundle_meta.get("provider_chain") or []) if tag]

        if not any([
            (bundle.get("history_1m") or {}).get("history"),
            (bundle.get("history_3m") or {}).get("history"),
            (bundle.get("history_1y") or {}).get("history"),
        ]):
            return {
                "intent": "single_stock_analysis",
                "analysis_type": "stock_analysis",
                "analysis_engine": "modular_stock_analysis_engine",
                "answer": "Live data is temporarily unavailable. Unable to verify market data.",
                "confidence": 0,
                "sources": ["Live data unavailable"],
                "data_validation": {
                    "price_data": False,
                    "news_data": False,
                    "technical_data": False,
                },
                "answer_schema": {
                    "intent": "single_stock_analysis",
                    "answer_title": f"{symbol} Analysis Unavailable",
                    "direct_answer": "Live data is temporarily unavailable. Unable to verify market data.",
                    "sources": ["Live data unavailable"],
                    "source_tags": ["Live data unavailable"],
                },
                "followups": [
                    f"Try {symbol} again in a moment",
                    "Show market sentiment instead",
                    "What sectors have strong momentum?",
                ],
                "status": {
                    "online": True,
                    "message": "Live data unavailable",
                    "live_data_ready": False,
                    "market_context_loaded": False,
                },
            }

        current_price = _safe_float((bundle.get("history_1m") or {}).get("price")) or (history_1m[-1] if history_1m else None)
        ret_30d = compute_return_pct(history_1m[0], history_1m[-1]) if len(history_1m) >= 2 else None
        ret_90d = compute_return_pct(history_3m[0], history_3m[-1]) if len(history_3m) >= 2 else None
        ma50 = moving_average(history_1y, 50)
        ma200 = moving_average(history_1y, 200)
        rsi = compute_rsi(history_1y or history_3m or history_1m)
        macd_payload = compute_macd(history_1y or history_3m or history_1m)
        tech_score = technical_score(rsi, macd_payload["macd"], macd_payload["signal"], ma50, ma200)
        mom_score = momentum_score(ret_30d, ret_90d, ret_90d)
        sentiment_avg = news["sentiment"]["average"]
        fundamentals = extract_fundamentals(details)
        base_score = round(
            (tech_score * 0.40)
            + (mom_score * 0.25)
            + (((sentiment_avg or 0.0) + 1.0) / 2.0 * 100.0 * 0.20)
            + ((50.0 if fundamentals.get("pe_ratio") is not None else 40.0) * 0.15),
            1,
        )
        recommendation = "BUY" if base_score >= 70 else ("HOLD" if base_score >= 40 else "SELL")
        risk_level = compute_risk_level(
            fear_greed=_safe_float(macro.get("fear_greed_index")),
            momentum_score=mom_score,
            technical_score=tech_score,
        )
        trend = classify_trend(ma50, ma200, rsi, macd_payload["macd"], macd_payload["signal"])
        momentum_label = classify_momentum(ret_30d, ret_90d, ret_90d)
        upside = compute_upside(current_price, fundamentals.get("target_price"))
        coverage_points = _coverage_score(
            current_price is not None,
            any(v is not None for v in [rsi, macd_payload["macd"], ma50, ma200]),
            sentiment_avg is not None,
            fundamentals.get("pe_ratio") is not None or fundamentals.get("market_cap") is not None,
        )
        confidence = min(
            _signal_confidence(rsi, macd_payload["macd"], ma50, ma200, ret_30d, ret_90d, sentiment_avg),
            _data_mode_confidence(stale_cache_used=stale_cache_used, coverage_points=coverage_points),
        )
        data_source_note = (
            f"Live data is temporarily unavailable. Using cached market data from {cached_age_minutes:.1f} minutes ago.\n\n"
            if stale_cache_used and cached_age_minutes is not None else ""
        )
        sector_name = profile.get("industry") or profile.get("sector") or "Relevant data is not available"
        market_context_text = (
            f"- Regime: {regime_ctx['regime']}\n"
            f"- Confidence: {regime_ctx['confidence']}\n"
        )
        if not regime_ctx["available"]:
            market_context_text += "- Market regime unavailable: using Neutral fallback\n"
        if macro.get("fear_greed_index") is not None:
            market_context_text += (
                f"- CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} "
                f"({macro.get('market_sentiment')})\n"
            )
        interpretation_text = self._regime_interpretation(regime_ctx, "en")
        positioning_text = self._positioning_text(regime_ctx, "en")
        application_text = self._stock_regime_application(
            symbol=symbol,
            sector=sector_name,
            regime_ctx=regime_ctx,
            lang="en",
        )

        direct_answer = (
            f"{profile.get('name') or symbol} ({symbol}) currently looks {recommendation.lower()} based on the available technical, momentum, and sentiment signals."
        )
        if stale_cache_used and cached_age_minutes is not None:
            direct_answer = (
                f"Using cached market data from {cached_age_minutes:.1f} minutes ago, "
                + direct_answer[0].lower()
                + direct_answer[1:]
            )
        answer = (
            data_source_note
            + f"Market Context\n"
            + market_context_text
            + "\nInterpretation\n"
            + f"- {interpretation_text}\n\n"
            + "Positioning\n"
            + positioning_text
            + "\nApplication to This Question\n"
            + f"- {application_text}\n\n"
            + "Data Used\n"
            + (f"- Market feed mode: cached ({cached_age_minutes:.1f} minutes old)\n" if stale_cache_used and cached_age_minutes is not None else "- Market feed mode: live\n")
            + (f"- Data providers: {' · '.join(provider_chain)}\n" if provider_chain else "")
            + f"- Price data: {'available' if current_price is not None else 'data unavailable'}\n"
            + f"- Technical indicators: {'available' if rsi is not None or macd_payload['macd'] is not None else 'data unavailable'}\n"
            + f"- News sentiment: {'available' if sentiment_avg is not None else 'data unavailable'}\n\n"
            + "Analysis\n"
            + (
                f"- Market data: Price ${current_price:.2f}\n"
                if current_price is not None else "- Market data: Data unavailable for this signal.\n"
            )
            + (
                f"- Market cap: {fundamentals.get('market_cap')}\n"
                if fundamentals.get("market_cap") else "- Market cap: Data unavailable for this signal.\n"
            )
            + (
                f"- PE ratio: {fundamentals.get('pe_ratio')}\n"
                if fundamentals.get("pe_ratio") is not None else "- PE ratio: Data unavailable for this signal.\n"
            )
            + (
                f"- Revenue (TTM): {fundamentals.get('revenue_ttm')}\n"
                if fundamentals.get("revenue_ttm") else "- Revenue (TTM): Data unavailable for this signal.\n"
            )
            + f"- Technical trend: {trend}\n"
            + f"- Momentum: {momentum_label}\n"
            + (
                f"- MA50 vs MA200: {'Bullish' if ma50 > ma200 else 'Bearish'}\n"
                if ma50 is not None and ma200 is not None else "- MA50 vs MA200: Data unavailable for this signal.\n"
            )
            + (
                f"- News sentiment: {sentiment_avg:+.2f}\n"
                if sentiment_avg is not None else "- News sentiment: Data unavailable for this signal.\n"
            )
            + (f"- Analyst target upside: {upside:+.2f}%\n" if upside is not None else "")
            + "\nTime Horizon\n"
            + f"- Short-term: momentum is {momentum_label.lower()} and the stock is currently in a {trend.lower()} technical regime.\n"
            + "- Medium-term: the path depends on whether earnings/news flow can sustain sentiment and whether rates remain supportive for this valuation profile.\n"
            + "\nPositioning\n"
            + (
                "- Overweight selectively if trend and sentiment continue to confirm.\n- Neutral if signals stay mixed.\n- Underweight if momentum weakens and macro conditions deteriorate.\n"
            )
            + "\nConclusion\n"
            + f"Recommendation: {recommendation}\nAI Score: {base_score:.1f}/100\nRisk Level: {risk_level}"
        )
        source_tags = _source_tags(*(provider_chain or ["Yahoo Finance"]), "NewsAPI", "Internal TA Engine", "Market Snapshot Cache", "Cached Market Data" if stale_cache_used else "")
        return {
            "intent": "single_stock_analysis",
            "analysis_type": "stock_analysis",
            "analysis_engine": "modular_stock_analysis_engine",
            "answer": answer,
            "confidence": confidence,
            "sources": ["Market data", "Technical analysis", "News sentiment"] + (["Cached market data"] if stale_cache_used else []),
            "data_validation": {
                "price_data": current_price is not None,
                "news_data": sentiment_avg is not None,
                "technical_data": any(v is not None for v in [rsi, macd_payload["macd"], ma50, ma200]),
            },
            "summary": {
                "market_sentiment": macro.get("market_sentiment"),
                "market_regime": regime_ctx["regime"],
                "regime_confidence": regime_ctx["confidence"],
                "fear_greed_score": macro.get("fear_greed_index"),
                "trending_sector": macro.get("top_sector"),
                "risk_outlook": risk_level,
            },
            "answer_schema": {
                "intent": "single_stock_analysis",
                "answer_title": f"{profile.get('name') or symbol} ({symbol})",
                "direct_answer": direct_answer,
                "stock_overview": {
                    "company_name": profile.get("name") or symbol,
                    "ticker": symbol,
                    "sector": profile.get("industry") or "Relevant data is not available",
                    "industry": profile.get("industry") or "Relevant data is not available",
                    "price": round(current_price, 2) if current_price is not None else None,
                    "market_data_mode": "cached" if stale_cache_used else "live",
                    "cached_age_minutes": cached_age_minutes,
                },
                "market_context": {
                    "market_regime": regime_ctx["regime"],
                    "confidence": regime_ctx["confidence"],
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "positioning": regime_ctx["positioning"],
                    "suggested_etfs": regime_ctx["suggested_etfs"],
                    "points": [
                        f"Regime: {regime_ctx['regime']} ({regime_ctx['confidence']} confidence)",
                        (
                            f"CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})"
                            if macro.get("fear_greed_index") is not None
                            else "Market regime unavailable: using Neutral fallback."
                        ),
                        f"Overweight sectors: {', '.join(regime_ctx['positioning'].get('overweight') or ['Balanced allocation'])}",
                        f"Underweight sectors: {', '.join(regime_ctx['positioning'].get('underweight') or ['No strong underweight call'])}",
                    ],
                },
                "technical_signals_section": {
                    "trend": trend,
                    "momentum": momentum_label,
                    "points": [
                        f"RSI: {round(rsi, 2)}" if rsi is not None else "RSI: Data unavailable for this signal.",
                        (
                            f"MACD: {round(macd_payload['macd'], 3)} vs signal {round(macd_payload['signal'], 3)}"
                            if macd_payload["macd"] is not None and macd_payload["signal"] is not None
                            else "MACD: Data unavailable for this signal."
                        ),
                        (
                            f"MA50 vs MA200: {'Bullish' if ma50 > ma200 else 'Bearish'}"
                            if ma50 is not None and ma200 is not None else "MA50 vs MA200: Data unavailable for this signal."
                        ),
                    ],
                },
                "fundamental_drivers": {
                    "points": [
                        f"PE ratio: {fundamentals['pe_ratio']}" if fundamentals.get("pe_ratio") is not None else "PE ratio: Data unavailable for this signal.",
                        f"Market cap: {fundamentals['market_cap']}" if fundamentals.get("market_cap") else "Market cap: Data unavailable for this signal.",
                        f"Revenue (TTM): {fundamentals['revenue_ttm']}" if fundamentals.get("revenue_ttm") else "Revenue (TTM): Data unavailable for this signal.",
                        f"Analyst target: {fundamentals['target_price']}" if fundamentals.get("target_price") is not None else "Analyst target: Data unavailable for this signal.",
                    ],
                },
                "risk_factors": {
                    "points": [
                        "Momentum remains vulnerable to broader market pullbacks." if mom_score < 45 else "Momentum remains constructive but still market-sensitive.",
                        "Valuation and sentiment can change quickly after earnings/news flow.",
                    ],
                },
                "investment_interpretation": {
                    "recommendation": recommendation,
                    "text": f"Signals currently point to a {recommendation} stance with {risk_level.lower()} to medium conviction depending on follow-through in momentum and sentiment.",
                    "confidence": confidence,
                    "forecast_horizon": {
                        "30d": round(ret_30d, 2) if ret_30d is not None else None,
                        "90d": round(ret_90d, 2) if ret_90d is not None else None,
                    },
                },
                "cause_effect_chain": [
                    f"Momentum and technical trend -> market appetite for the stock -> recommendation shifts between {recommendation}, HOLD, or SELL.",
                    "News sentiment and macro regime -> valuation sensitivity -> follow-through in price action.",
                ],
                "overview": direct_answer,
                "rationale": [
                    f"Current market regime is {regime_ctx['regime']} with {regime_ctx['confidence']} confidence.",
                    f"Technical trend is {trend.lower()} with momentum currently {momentum_label.lower()}.",
                    (
                        f"News sentiment score is {sentiment_avg:+.2f}, which {'supports' if (sentiment_avg or 0) >= 0 else 'pressures'} the current setup."
                        if sentiment_avg is not None else
                        "News sentiment is limited, so the setup depends more heavily on technical and macro context."
                    ),
                    (
                        f"Analyst target implies {upside:+.2f}% upside from the current price."
                        if upside is not None else
                        "Analyst target data is unavailable, so valuation upside cannot be confirmed from the live payload."
                    ),
                ],
                "summary_points": [
                    f"Market regime is {regime_ctx['regime']} with {regime_ctx['confidence']} confidence.",
                    f"Technical trend is {trend.lower()} with momentum currently {momentum_label.lower()}.",
                    (
                        f"News sentiment score is {sentiment_avg:+.2f}, which {'supports' if (sentiment_avg or 0) >= 0 else 'pressures'} the current setup."
                        if sentiment_avg is not None else
                        "News sentiment is limited, so the setup depends more heavily on technical and macro context."
                    ),
                    (
                        f"Analyst target implies {upside:+.2f}% upside from the current price."
                        if upside is not None else
                        "Analyst target data is unavailable, so valuation upside cannot be confirmed from the live payload."
                    ),
                ],
                "risks": [
                    application_text,
                    "Momentum can reverse quickly if the broader market weakens or rates move against high-multiple names.",
                    "Earnings and news flow can change the setup faster than technicals alone suggest.",
                ],
                "time_horizon": _time_horizon_payload(
                    short_term=f"Short term: momentum is {momentum_label.lower()} and the technical trend is {trend.lower()}.",
                    medium_term="Medium term: sustainability depends on earnings support, sentiment persistence, and the broader rate backdrop.",
                ),
                "actionable_view": (
                    f"{application_text} Overweight selectively if technical and sentiment confirmation improves; stay Neutral on mixed signals; move Underweight if momentum and macro conditions deteriorate."
                ),
                "sources": ["Market data", "Technical analysis", "News sentiment"],
                "source_tags": source_tags,
            },
            "followups": [
                f"What are the downside risks for {symbol}?",
                f"Compare {symbol} vs AMD",
                f"Show {symbol} technical picture",
            ],
            "status": {
                "online": True,
                "message": "Using cached market data" if stale_cache_used else "Connected",
                "live_data_ready": not stale_cache_used,
                "market_context_loaded": True,
                "degraded": stale_cache_used,
            },
        }

    def analyze_knowledge_guidance(self, question: str, context: Any) -> Dict[str, Any]:
        market = self.market_data.get_market_context(context)
        macro = self.macro_data.build_macro_snapshot(market)
        direct_answer = (
            "Low-risk stock ideas are usually found in defensive sectors such as Consumer Staples, Healthcare, and Utilities."
        )
        answer = (
            "Market Context\n"
            + (
                f"Fear & Greed Index: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')}).\n\n"
                if macro.get("fear_greed_index") is not None else
                "Fear & Greed Index: Data unavailable for this signal.\n\n"
            )
            + "Data Used\n"
            + "- Historical sector behavior\n"
            + "- Defensive equity characteristics\n"
            + "- Known risk profiles of low-volatility businesses\n\n"
            + "Analysis\n"
            + "- Consumer Staples, Utilities, and Healthcare often hold up better during risk-off markets because demand tends to be steadier.\n"
            + "- Lower-risk names typically show durable cash flow, large market capitalization, and lower earnings volatility than high-growth stocks.\n"
            + "- Representative examples include Procter & Gamble (PG), Coca-Cola (KO), and Johnson & Johnson (JNJ).\n\n"
            + "Risk Factors\n"
            + "- These stocks can still underperform if bond yields rise sharply or if investors rotate into higher-beta growth names.\n"
            + "- Defensive stocks are usually less volatile, not risk-free.\n\n"
            + "Conclusion\n"
            + "If you want lower-risk ideas without relying on live feeds, start with defensive large caps in Consumer Staples, Healthcare, or Utilities, then verify valuation and current trend when live data is available."
        )
        return {
            "intent": "knowledge_guidance",
            "analysis_type": "knowledge_guidance",
            "analysis_engine": "knowledge_guidance_engine",
            "answer": answer,
            "confidence": 72,
            "sources": ["Historical market behavior", "Risk profile heuristics", "Sector characteristics"],
            "data_validation": {"price_data": False, "news_data": False, "technical_data": False},
            "summary": {
                "market_sentiment": macro.get("market_sentiment"),
                "fear_greed_score": macro.get("fear_greed_index"),
                "trending_sector": "Consumer Staples / Healthcare / Utilities",
                "risk_outlook": "Lower risk guidance",
            },
            "answer_schema": {
                "intent": "knowledge_guidance",
                "answer_title": "Low-Risk Stock Guidance",
                "direct_answer": direct_answer,
                "market_context": {
                    "market_regime": macro.get("market_sentiment"),
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "points": [
                        (
                            f"Fear & Greed: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})"
                            if macro.get("fear_greed_index") is not None
                            else "Fear & Greed: Data unavailable for this signal."
                        )
                    ],
                },
                "fundamental_drivers": {
                    "points": [
                        "Stable cash flows and resilient demand usually support lower-risk profiles.",
                        "Large-cap defensive names often have lower drawdown risk than cyclical growth stocks.",
                    ],
                },
                "risk_factors": {
                    "points": [
                        "Defensive stocks can still fall during broad market stress.",
                        "Interest-rate moves can pressure dividend and defensive sectors.",
                    ],
                },
                "investment_interpretation": {
                    "recommendation": "Defensive sectors first",
                    "text": "For lower-risk ideas, start with Consumer Staples, Healthcare, and Utilities, then verify live valuation and trend before acting.",
                    "confidence": 72,
                    "forecast_horizon": {},
                },
                "source_tags": _source_tags("Historical Market Behavior", "Sector Characteristics", "Risk Profile Model"),
            },
            "followups": [
                "Which sectors look most defensive now?",
                "Compare Consumer Staples vs Healthcare",
                "Show lower-risk large-cap ideas",
            ],
            "status": {
                "online": True,
                "message": "Knowledge-based guidance",
                "live_data_ready": False,
                "market_context_loaded": True,
            },
        }

    def analyze_sector(self, question: str, context: Any) -> Dict[str, Any]:
        lang = _lang_for(question)
        market = self.market_data.get_market_context(context)
        macro = self.macro_data.build_macro_snapshot(market)
        regime_ctx = self._market_regime_context(macro)
        sector_rankings = self.market_data.get_sector_rankings()
        rankings = sector_rankings.get("rankings", [])
        if not rankings:
            return {
                "intent": "sector_analysis",
                "analysis_type": "sector_analysis",
                "analysis_engine": "modular_sector_analysis_engine",
                "answer": "Live data temporarily unavailable",
                "confidence": 35,
                "sources": ["Market data"],
                "data_validation": {"price_data": False, "news_data": False, "technical_data": False},
                "followups": ["Try again in a few minutes", "Ask about a specific stock instead"],
                "status": {"online": True, "message": "Connected", "live_data_ready": False, "market_context_loaded": True},
            }
        compare_top_n = bool(context.get("compare_top_n")) if isinstance(context, dict) else False
        requested_top_n = int(context.get("top_n") or 2) if isinstance(context, dict) else 2
        requested_top_n = max(2, min(requested_top_n, len(rankings)))
        if compare_top_n:
            compare_rows = rankings[:requested_top_n]
            if len(compare_rows) >= 2:
                leader = compare_rows[0]
                runner_up = compare_rows[1]
                leader_score = _safe_float(leader.get("momentum_score")) or 0.0
                runner_up_score = _safe_float(runner_up.get("momentum_score")) or 0.0
                spread = leader_score - runner_up_score
                ranking_lines = [
                    f"{idx + 1}. {row.get('sector')} ({row.get('etf')}): "
                    f"1M {(_safe_float(row.get('return_1m_pct')) or 0):+.2f}% | "
                    f"3M {(_safe_float(row.get('return_3m_pct')) or 0):+.2f}% | "
                    + (
                        f"6M {(_safe_float(row.get('return_6m_pct')) or 0):+.2f}% | "
                        if row.get("return_6m_pct") is not None else "6M Data unavailable | "
                    )
                    + f"Momentum {(_safe_float(row.get('momentum_score')) or 0):+.2f}%"
                    for idx, row in enumerate(compare_rows)
                ]
                risk_overlay = (
                    f"Fear & Greed is {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})."
                    if macro.get("fear_greed_index") is not None else
                    "Macro sentiment data is unavailable, so risk should be sized conservatively."
                )
                answer = (
                    f"Top {requested_top_n} Sectors by Momentum\n"
                    + "\n".join(ranking_lines)
                    + "\n\nComparison\n"
                    + f"{leader.get('sector')} is outperforming {runner_up.get('sector')} by {spread:+.2f} percentage points on the current momentum score."
                    + ("\n" + f"It also remains ahead of " + ", ".join([f"{row.get('sector')} ({(_safe_float(row.get('momentum_score')) or 0):+.2f}%)" for row in compare_rows[2:]]) + "." if len(compare_rows) > 2 else "")
                    + "\n\nDrivers\n"
                    + f"- {leader.get('sector')} leads because its 1M return of {(_safe_float(leader.get('return_1m_pct')) or 0):+.2f}% and 3M return of {(_safe_float(leader.get('return_3m_pct')) or 0):+.2f}% produce the strongest blended momentum score.\n"
                    + f"- {runner_up.get('sector')} is the closest challenger with a momentum score of {runner_up_score:+.2f}%."
                    + "\n\nRisk\n"
                    + f"- {risk_overlay}\n"
                    + "- Sector leadership can reverse quickly during macro shocks or abrupt rotation.\n"
                )
                return {
                    "intent": "sector_comparison_top_n",
                    "analysis_type": "sector_comparison_top_n",
                    "analysis_engine": "modular_sector_comparison_top_n_engine",
                    "answer": answer,
                    "confidence": 80,
                    "sources": ["Market data", "Sector ETF model", "Internal TA Engine"],
                    "data_validation": {"price_data": True, "news_data": False, "technical_data": True},
                    "answer_schema": {
                        "intent": "sector_comparison_top_n",
                        "overview": f"Top {requested_top_n} momentum sectors right now are " + ", ".join([f"{row.get('sector')} ({row.get('etf')})" for row in compare_rows]) + ".",
                        "rationale": [
                            f"{leader.get('sector')} leads on the blended momentum score with {leader_score:+.2f}%.",
                            f"{runner_up.get('sector')} is next at {runner_up_score:+.2f}%, so the spread is {spread:+.2f} points.",
                            "The ranking blends 1M and 3M sector ETF returns, so leadership reflects both recent and intermediate trend strength.",
                        ],
                        "summary_points": [
                            f"{leader.get('sector')} leads on the blended momentum score with {leader_score:+.2f}%.",
                            f"{runner_up.get('sector')} is next at {runner_up_score:+.2f}%, so the spread is {spread:+.2f} points.",
                            "The ranking blends 1M and 3M sector ETF returns, so leadership reflects both recent and intermediate trend strength.",
                        ],
                        "risks": [
                            risk_overlay,
                            "Sector leadership can reverse quickly during macro shocks or abrupt rotation.",
                        ],
                        "direct_answer": f"Top {requested_top_n} momentum sectors right now are " + ", ".join([f"{row.get('sector')} ({row.get('etf')})" for row in compare_rows]) + ".",
                        "sector_analysis": {
                            "sector_rankings": compare_rows,
                            "points": ranking_lines,
                        },
                        "comparison": {
                            "top_n": requested_top_n,
                            "leader": leader.get("sector"),
                            "runner_up": runner_up.get("sector"),
                            "spread": round(spread, 2),
                        },
                        "risk_factors": {
                            "points": [
                                risk_overlay,
                                "Leadership sectors can mean-revert quickly during macro stress.",
                            ],
                        },
                        "source_tags": _source_tags("Yahoo Finance", "Alpha Vantage", "Finnhub", "Polygon", "Sector ETF Model", "Internal TA Engine", "Market Snapshot Cache"),
                    },
                    "followups": [
                        f"Why is {leader.get('sector')} leading right now?",
                        f"Show top momentum stocks in {leader.get('sector')}",
                        "Show full sector momentum ranking",
                    ],
                    "status": {
                        "online": True,
                        "message": "Connected",
                        "live_data_ready": True,
                        "market_context_loaded": True,
                    },
                }
        comparison_sectors = [str(item).upper() for item in (context.get("comparison_sectors") or []) if str(item).strip()] if isinstance(context, dict) else []
        if len(comparison_sectors) >= 2:
            compare_rows = [row for row in rankings if str(row.get("etf", "")).upper() in comparison_sectors][:2]
            if len(compare_rows) == 2:
                left, right = compare_rows
                left_score = _safe_float(left.get("momentum_score")) or 0.0
                right_score = _safe_float(right.get("momentum_score")) or 0.0
                winner = left if left_score >= right_score else right
                return {
                    "intent": "sector_comparison",
                    "analysis_type": "sector_comparison",
                    "analysis_engine": "modular_sector_comparison_engine",
                    "answer": (
                        "Sector Ranking Comparison\n"
                        f"1. {left.get('sector')} ({left.get('etf')}): 1M {(_safe_float(left.get('return_1m_pct')) or 0):+.2f}% | 3M {(_safe_float(left.get('return_3m_pct')) or 0):+.2f}% | Momentum {left_score:+.2f}%\n"
                        f"2. {right.get('sector')} ({right.get('etf')}): 1M {(_safe_float(right.get('return_1m_pct')) or 0):+.2f}% | 3M {(_safe_float(right.get('return_3m_pct')) or 0):+.2f}% | Momentum {right_score:+.2f}%\n\n"
                        "Interpretation\n"
                        f"{winner.get('sector')} currently has the stronger momentum profile on the tracked sector formula.\n\n"
                        "Risk Overlay\n"
                        + (
                            f"Fear & Greed Index: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')}).\n\n"
                            if macro.get("fear_greed_index") is not None else
                            "Fear & Greed Index: Data unavailable for this signal.\n\n"
                        )
                        + "Final Decision\n"
                        f"{winner.get('sector')} is the stronger sector today, but macro risk should still guide position sizing."
                    ),
                    "confidence": 78,
                    "sources": ["Market data", "Sector ETF model", "Internal TA Engine"],
                    "data_validation": {"price_data": True, "news_data": False, "technical_data": True},
                    "answer_schema": {
                        "intent": "sector_comparison",
                        "overview": f"{winner.get('sector')} currently has the stronger momentum profile versus {right.get('sector') if winner is left else left.get('sector')}.",
                        "rationale": [
                            f"{left.get('sector')} scores {left_score:+.2f}% on the tracked momentum formula.",
                            f"{right.get('sector')} scores {right_score:+.2f}% on the same formula.",
                            f"The current edge belongs to {winner.get('sector')} because its 1M/3M return mix is stronger.",
                        ],
                        "summary_points": [
                            f"{left.get('sector')} scores {left_score:+.2f}% on the tracked momentum formula.",
                            f"{right.get('sector')} scores {right_score:+.2f}% on the same formula.",
                            f"The current edge belongs to {winner.get('sector')} because its 1M/3M return mix is stronger.",
                        ],
                        "risks": [
                            "Relative sector leadership can change quickly when macro conditions shift.",
                            "Both sectors remain sensitive to rotation and risk sentiment changes.",
                        ],
                        "direct_answer": f"{winner.get('sector')} currently has the stronger momentum profile versus {right.get('sector') if winner is left else left.get('sector')}.",
                        "comparison": {
                            "left_sector": left.get("sector"),
                            "left_etf": left.get("etf"),
                            "left_momentum_score": round(left_score, 2),
                            "right_sector": right.get("sector"),
                            "right_etf": right.get("etf"),
                            "right_momentum_score": round(right_score, 2),
                            "winner": winner.get("sector"),
                        },
                        "source_tags": _source_tags("Yahoo Finance", "Alpha Vantage", "Finnhub", "Polygon", "Sector ETF Model", "Internal TA Engine", "Market Snapshot Cache"),
                    },
                    "followups": [
                        f"What risks could weaken {winner.get('sector')}?",
                        f"Show top momentum stocks in {winner.get('sector')}",
                        "Show all sector rankings",
                    ],
                    "status": {
                        "online": True,
                        "message": "Connected",
                        "live_data_ready": True,
                        "market_context_loaded": True,
                    },
                }

        top = rankings[0]
        top_sector = top.get("sector", "Unknown")
        top_three = rankings[:3]
        fear_greed = _safe_float(macro.get("fear_greed_index"))
        interpretation_text = self._regime_interpretation(regime_ctx, lang)
        positioning_text = self._positioning_text(regime_ctx, lang)
        application_text = self._macro_regime_application(regime_ctx, lang)
        top_momentum = _safe_float(top.get("momentum_score"))
        top_rank = 1
        decision_label = _sector_strength_label(rank=top_rank, momentum=top_momentum, fear_greed=fear_greed)
        risk_overlay = (
            "High macro risk due to Extreme Fear conditions."
            if fear_greed is not None and fear_greed <= 24
            else ("Elevated macro risk." if fear_greed is not None and fear_greed < 45 else "Macro risk is moderate.")
        )
        final_decision = (
            f"{top_sector} remains the leading sector, but positioning should be selective due to the current risk regime."
            if decision_label == "Strong but High Risk"
            else (
                f"{top_sector} is the strongest sector on current momentum data and has the clearest confirmation."
                if decision_label == "Strong"
                else (
                    f"{top_sector} is currently leading, but confirmation is only moderate and should be monitored closely."
                    if decision_label.startswith("Moderate")
                    else f"{top_sector} does not have strong momentum confirmation right now."
                )
            )
        )
        source_tags = _source_tags("Yahoo Finance", "Alpha Vantage", "Finnhub", "Polygon", "Sector ETF Model", "Internal TA Engine", "Market Snapshot Cache")
        direct_answer = (
            f"ตอนนี้กลุ่มที่มีโมเมนตัมเด่นคือ "
            + ", ".join(
                [f"{row.get('sector')} ({row.get('etf')} {(_safe_float(row.get('momentum_score')) or 0):+.2f}%)" for row in top_three]
            )
            + f" โดย {top_sector} อยู่ในสถานะ '{decision_label}' จากทั้งอันดับ โมเมนตัม และความเสี่ยงมหภาค"
            if lang == "th" else
            f"Top momentum sectors right now are "
            + ", ".join(
                [f"{row.get('sector')} ({row.get('etf')} {(_safe_float(row.get('momentum_score')) or 0):+.2f}%)" for row in top_three]
            )
            + f". {top_sector} is currently labeled '{decision_label}' based on ranking, momentum, and macro risk."
        )
        answer = (
            "Sector Ranking\n"
            + "\n".join(
                [
                    f"{idx + 1}. {row.get('sector')} ({row.get('etf')}): "
                    f"1M {(_safe_float(row.get('return_1m_pct')) or 0):+.2f}% | "
                    f"3M {(_safe_float(row.get('return_3m_pct')) or 0):+.2f}% | "
                    f"6M "
                    + (
                        f"{(_safe_float(row.get('return_6m_pct')) or 0):+.2f}%"
                        if row.get("return_6m_pct") is not None
                        else "Data unavailable"
                    )
                    + f" | Momentum {(_safe_float(row.get('momentum_score')) or 0):+.2f}%"
                    for idx, row in enumerate(rankings)
                ]
            )
            + "\n\nMarket Context\n"
            + f"- Regime: {regime_ctx['regime']}\n- Confidence: {regime_ctx['confidence']}\n"
            + (
                f"- CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})\n\n"
                if macro.get("fear_greed_index") is not None else
                "- Market regime unavailable: using Neutral fallback.\n\n"
            )
            + "Interpretation\n"
            + f"- {interpretation_text}\n\n"
            + "Positioning\n"
            + positioning_text
            + "\nApplication to This Question\n"
            + f"- {application_text}\n\n"
            + "Data Used\n"
            + "- Sector ETF prices (XLE, XLK, XLF, XLV, XLI, XLP, XLY)\n"
            + "- 1M return\n- 3M return\n- 6M return\n"
            + "- Momentum score = (0.4 × 1M return) + (0.6 × 3M return)\n\n"
            + "Analysis\n"
            + (
                f"{top_sector} ranks #1 with 1M return of {(_safe_float(top.get('return_1m_pct')) or 0):+.2f}%, "
                f"3M return of {(_safe_float(top.get('return_3m_pct')) or 0):+.2f}%, "
                f"and momentum score of {(top_momentum or 0):+.2f}%."
            )
            + (
                f" It outperforms {top_three[1].get('sector')} ({(_safe_float(top_three[1].get('momentum_score')) or 0):+.2f}%) "
                f"and {top_three[2].get('sector')} ({(_safe_float(top_three[2].get('momentum_score')) or 0):+.2f}%)."
                if len(top_three) >= 3 else ""
            )
            + "\n\nRisk Overlay\n"
            + f"- Decision label: {decision_label}\n"
            + f"- {risk_overlay}\n\n"
            + "Time Horizon\n"
            + f"- Short-term: {top_sector} is leading because its current 1M and 3M returns are strongest in the tracked universe.\n"
            + "- Medium-term: leadership depends on whether inflation, rates, and macro positioning continue to favor the same sector.\n\n"
            + "Positioning\n"
            + (
                f"- Overweight: {top_sector}\n- Neutral: Defensive sectors\n- Underweight: Rate-sensitive laggards / weaker cyclicals\n\n"
            )
            + "Final Decision\n"
            + (
                final_decision
            )
        )
        return {
            "intent": "sector_analysis",
            "analysis_type": "sector_analysis",
            "analysis_engine": "modular_sector_analysis_engine",
            "answer": answer,
            "confidence": 76,
            "sources": ["Market data", "Sector ETF model", "Internal TA Engine"],
            "data_validation": {"price_data": True, "news_data": False, "technical_data": True},
            "summary": {
                "market_sentiment": macro.get("market_sentiment"),
                "market_regime": regime_ctx["regime"],
                "regime_confidence": regime_ctx["confidence"],
                "fear_greed_score": macro.get("fear_greed_index"),
                "trending_sector": top_sector,
                "risk_outlook": macro.get("risk_outlook"),
            },
            "answer_schema": {
                "intent": "sector_analysis",
                "overview": direct_answer,
                "rationale": [
                    f"Market regime is {regime_ctx['regime']} with {regime_ctx['confidence']} confidence.",
                    f"{top_sector} ranks first because its blended 1M and 3M return profile is strongest in the tracked sector ETF universe.",
                    (
                        f"It currently leads {top_three[1].get('sector')} and {top_three[2].get('sector')} on the same momentum formula."
                        if len(top_three) >= 3 else
                        "Leadership confirmation versus the next sectors is limited by the available ranking depth."
                    ),
                    f"Macro overlay is {risk_overlay.lower()}",
                ],
                "summary_points": [
                    f"{top_sector} ranks first because its blended 1M and 3M return profile is strongest in the tracked sector ETF universe.",
                    (
                        f"It currently leads {top_three[1].get('sector')} and {top_three[2].get('sector')} on the same momentum formula."
                        if len(top_three) >= 3 else
                        "Leadership confirmation versus the next sectors is limited by the available ranking depth."
                    ),
                    f"Macro overlay is {risk_overlay.lower()}",
                ],
                "risks": [
                    risk_overlay,
                    "Sector rotation can reverse quickly during macro shocks.",
                    "Leadership sectors often experience sharper drawdowns when momentum fades.",
                ],
                "direct_answer": direct_answer,
                "market_context": {
                    "market_regime": regime_ctx["regime"],
                    "confidence": regime_ctx["confidence"],
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "positioning": regime_ctx["positioning"],
                    "suggested_etfs": regime_ctx["suggested_etfs"],
                    "points": [
                        f"Regime: {regime_ctx['regime']} ({regime_ctx['confidence']} confidence)",
                        (
                            f"CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})"
                            if macro.get("fear_greed_index") is not None else "Market regime unavailable: using Neutral fallback."
                        ),
                        f"Strongest sector now: {top_sector} ({top.get('etf')})",
                        f"Decision label: {decision_label}",
                        f"Overweight sectors: {', '.join(regime_ctx['positioning'].get('overweight') or ['Balanced allocation'])}",
                        f"Underweight sectors: {', '.join(regime_ctx['positioning'].get('underweight') or ['No strong underweight call'])}",
                    ],
                },
                "sector_analysis": {
                    "sector": top_sector,
                    "etf": top.get("etf"),
                    "momentum_label": decision_label,
                    "sector_rankings": rankings,
                    "points": [
                        f"#{idx + 1} {row.get('sector')} ({row.get('etf')}): 1M {(_safe_float(row.get('return_1m_pct')) or 0):+.2f}% | 3M {(_safe_float(row.get('return_3m_pct')) or 0):+.2f}% | 6M "
                        + (
                            f"{(_safe_float(row.get('return_6m_pct')) or 0):+.2f}%"
                            if row.get("return_6m_pct") is not None
                            else "Data unavailable"
                        )
                        + f" | Momentum {(_safe_float(row.get('momentum_score')) or 0):+.2f}%"
                        for idx, row in enumerate(rankings)
                    ],
                },
                "fundamental_drivers": {
                    "points": [
                        f"{top_sector} ranks first because its 1M and 3M ETF returns produce the highest momentum score in the tracked sector universe.",
                        (
                            f"It remains ahead of {top_three[1].get('sector')} and {top_three[2].get('sector')} on the same momentum formula."
                            if len(top_three) >= 3 else
                            "Comparison with the next sectors is limited by available ranking data."
                        ),
                    ],
                },
                "risk_factors": {
                    "points": [
                        risk_overlay,
                        "Sector rotation can reverse quickly during macro shocks.",
                        "Leadership sectors often see sharper drawdowns when momentum fades.",
                    ],
                },
                "investment_interpretation": {
                    "recommendation": decision_label,
                    "text": application_text,
                    "confidence": 76,
                    "forecast_horizon": {},
                },
                "cause_effect_chain": [
                    f"1M and 3M returns -> momentum score -> sector ranking leadership for {top_sector}.",
                    "Macro regime and Fear & Greed -> sector rotation -> whether leadership persists or reverses.",
                ],
                "time_horizon": _time_horizon_payload(
                    short_term=f"Short term: {top_sector} has the strongest confirmed momentum in the current ranking set.",
                    medium_term="Medium term: persistence depends on inflation, rates, and whether capital keeps rotating into the same sector leadership.",
                ),
                "actionable_view": application_text,
                "sources": ["Market data", "Sector ETF model", "Internal TA Engine"],
                "source_tags": source_tags,
            },
            "followups": (
                [
                    f"ขอดูหุ้นโมเมนตัมเด่นในกลุ่ม {top_sector}",
                    f"อะไรคือความเสี่ยงที่อาจทำให้ {top_sector} อ่อนลง?",
                    "เปรียบเทียบ 2 กลุ่มที่เด่นสุดตอนนี้",
                ] if lang == "th" else [
                    f"Show top momentum stocks in {top_sector}",
                    f"What risks could weaken {top_sector}?",
                    "Compare the top two sectors now",
                ]
            ),
            "status": {
                "online": True,
                "message": "พร้อมใช้งาน" if lang == "th" else "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
        }

    def analyze_trending(self, context: Any) -> Dict[str, Any]:
        lang = _lang_for(str((context or {}).get("user_question") or "")) if isinstance(context, dict) else "en"
        market = self.market_data.get_market_context(context)
        macro = self.macro_data.build_macro_snapshot(market)
        rankings = self.market_data.get_sector_rankings().get("rankings", [])
        top_sector = rankings[0].get("sector") if rankings else None
        tracked_symbols = ["NVDA", "TSLA", "META", "AAPL", "MSFT"]
        histories = self.market_data.get_many_3m_histories(tracked_symbols)

        def _normalize_trending_item(item: Dict[str, Any], provider: str) -> Optional[Dict[str, Any]]:
            symbol_value = str(item.get("symbol") or "").strip().upper()
            name_value = str(item.get("name") or "").strip()
            if not symbol_value:
                logger.warning(f"[advisor_trending] dropped item missing symbol provider={provider} raw={item}")
                return None
            if not name_value:
                logger.warning(f"[advisor_trending] dropped item missing name provider={provider} symbol={symbol_value} raw={item}")
                return None

            price_value = _safe_float(item.get("price"))
            if price_value is None:
                logger.warning(f"[advisor_trending] dropped item missing price provider={provider} symbol={symbol_value}")
                return None

            daily_change = _safe_float(item.get("daily_change"))
            if daily_change is None:
                daily_change = _safe_float(item.get("change_pct"))
            return_1m = _safe_float(item.get("return_1m"))
            if return_1m is None:
                return_1m = _safe_float(item.get("month_return"))

            normalized = {
                "symbol": symbol_value,
                "name": name_value,
                "price": round(price_value, 2),
                "daily_change": round(daily_change, 2) if daily_change is not None else None,
                "return_1m": round(return_1m, 2) if return_1m is not None else None,
                "reason": str(item.get("reason") or "High recent activity and notable price movement.").strip(),
            }
            normalized["change_pct"] = normalized["daily_change"]
            normalized["month_return"] = normalized["return_1m"]
            return normalized

        def _fallback_trending_response() -> Dict[str, Any]:
            top_sectors = [row.get("sector") for row in rankings[:2] if row.get("sector")]
            leading_sector = top_sectors[0] if top_sectors else (top_sector or "Energy")
            second_sector = top_sectors[1] if len(top_sectors) > 1 else ("Utilities" if lang == "en" else "สาธารณูปโภค")
            market_regime = str(macro.get("market_regime") or macro.get("market_sentiment") or "Neutral")
            regime_conf = str(macro.get("regime_confidence") or "low")
            risk_outlook = str(macro.get("risk_outlook") or "High")
            confidence_split = _confidence_split_payload(
                data_confidence="low",
                reasoning_confidence=_reasoning_confidence_label(
                    regime_available=bool(macro.get("market_regime")),
                    sector_count=len(top_sectors),
                    sentiment_available=macro.get("market_sentiment") is not None or macro.get("fear_greed_index") is not None,
                ),
            )
            suggested_etfs = list((macro.get("suggested_etfs") or [])[:3])
            if not suggested_etfs:
                suggested_etfs = ["XLE", "XLU", "XLP"] if "Risk-Off" in market_regime else ["SPY", "QQQ", "XLI"]
            inferred_items = _infer_trending_stocks(leading_sector, market_regime, suggested_etfs)
            key_drivers = (
                [
                    "Risk-off positioning is dominating capital flows.",
                    "Elevated volatility supports defensive rotation.",
                    "Weak market breadth limits aggressive stock chasing.",
                ] if lang == "en" else [
                    "กระแสเงินยังอยู่ในโหมดป้องกันความเสี่ยง",
                    "ความผันผวนที่สูงยังสนับสนุนการหมุนเข้า defensive sectors",
                    "market breadth ที่อ่อนทำให้ไม่ควรไล่ซื้อหุ้นรายตัวแรงเกินไป",
                ]
            )
            rationale = (
                [
                    f"Top sectors right now are {leading_sector} and {second_sector}.",
                    f"Current regime is {market_regime} with {regime_conf} confidence.",
                    "Recent sentiment and breadth still favor sector-level rotation over single-name chasing.",
                ] if lang == "en" else [
                    f"กลุ่มที่เด่นที่สุดตอนนี้คือ {leading_sector} และ {second_sector}",
                    f"regime ตอนนี้คือ {market_regime} และมีความเชื่อมั่นระดับ {regime_conf}",
                    "sentiment และ breadth ล่าสุดยังสนับสนุนการเลือกเล่นระดับ sector มากกว่าการไล่ซื้อหุ้นรายตัว",
                ]
            )
            actionable = (
                f"Focus on sector ETFs such as {', '.join(suggested_etfs)} and avoid chasing individual names until trend confirmation improves."
                if lang == "en" else
                f"เน้นดู sector ETFs เช่น {', '.join(suggested_etfs)} และหลีกเลี่ยงการไล่ซื้อหุ้นรายตัวจนกว่าจะมีสัญญาณยืนยันมากขึ้น"
            )
            estimated_block = "\n".join(
                [
                    f"{idx + 1}. {row['symbol']} (Score: {row.get('score', 'N/A')}) - {', '.join(row.get('tags') or ['Estimated'])}"
                    if lang == "en" else
                    f"{idx + 1}. {row['symbol']} ({row['name']}) - คะแนน {row.get('score', 'N/A')}"
                    for idx, row in enumerate(inferred_items)
                ]
            )
            answer = (
                "Trending Stocks Today (Estimated)\n"
                "- Estimated leaders based on sector strength\n"
                + (estimated_block + "\n\n" if estimated_block else "\n")
                + f"Alternative Insight\n- Top sectors right now: {leading_sector}"
                + (f"\n- Secondary strength: {second_sector}" if second_sector else "")
                + f"\n\nInterpretation\n- Market is in {market_regime} regime ({regime_conf} confidence)\n"
                + f"- Capital is rotating into {'defensive sectors' if 'Risk-Off' in market_regime else 'relative strength sectors'}\n"
                + ("\n- Elevated volatility and weak breadth argue against chasing individual names" if risk_outlook.lower() == "high" else "\n- Breadth is still selective, so sector confirmation matters")
                + "\n\nActionable View\n- "
                + actionable
            ) if lang == "en" else (
                "หุ้นเด่นวันนี้ (ประมาณการ)\n"
                "- รายชื่อประมาณการจากความแข็งแกร่งของ sector\n"
                + (estimated_block + "\n\n" if estimated_block else "\n")
                + f"ทางเลือกในการตีความ\n- กลุ่มที่เด่นตอนนี้: {leading_sector}"
                + (f"\n- กลุ่มรองที่ยังแข็งแรง: {second_sector}" if second_sector else "")
                + f"\n\nการตีความ\n- ตลาดอยู่ใน regime {market_regime} (confidence {regime_conf})\n"
                + "- เงินทุนกำลังหมุนเข้า sector เชิงป้องกันมากกว่าการไล่หุ้นรายตัว\n"
                + ("\n- ความผันผวนสูงและ breadth อ่อน ทำให้ไม่ควรไล่ราคาหุ้นเดี่ยว" if risk_outlook.lower() == "high" else "\n- breadth ยังเลือกเป็นรายกลุ่ม จึงควรรอการยืนยันจาก sector ก่อน")
                + "\n\nมุมมองเชิงปฏิบัติ\n- "
                + actionable
            )
            return {
                "intent": "market_scanner",
                "analysis_type": "market_scanner",
                "analysis_engine": "modular_market_scanner_engine",
                "answer": answer,
                "confidence": 52,
                **confidence_split,
                "sources": ["Sector momentum ranking", "Market sentiment model", "Macro snapshot"],
                "data_validation": {"price_data": False, "news_data": True, "technical_data": True},
                "answer_schema": {
                    "intent": "market_scanner",
                    "status": "degraded",
                    "message": "Trending data inferred from sector strength",
                    "direct_answer": _pick_lang(lang, "live scanner ยังไม่พร้อม แต่ยังสรุปภาวะหมุน sector ให้ได้", "Live scanner is unavailable, but sector rotation still provides a useful market read."),
                    "trending_stocks": inferred_items,
                    "items": inferred_items,
                    "overview": _pick_lang(lang, f"ตลาดอยู่ใน {market_regime} และกลุ่มที่เด่นคือ {leading_sector}", f"Market is in a {market_regime} regime with {leading_sector} leading."),
                    "alternative_insight": {
                        "top_sectors": [sector for sector in top_sectors if sector],
                        "market_regime": market_regime,
                        "confidence": regime_conf,
                        "suggested_etfs": suggested_etfs,
                    },
                    "rationale": rationale,
                    "risks": key_drivers,
                    "actionable_view": actionable,
                    **confidence_split,
                    "confidence_split": confidence_split,
                    "source_tags": ["Sector momentum", "Market regime", "Macro context"],
                    "confidence_label": _pick_lang(lang, "รายชื่อประมาณการจากความแข็งแกร่งของ sector", "Estimated leaders based on sector strength"),
                    "ranking_model": {
                        "weights": {
                            "sector_strength": 0.40,
                            "momentum_proxy": 0.20,
                            "volatility_risk": 0.20,
                            "regime_alignment": 0.20,
                        }
                    },
                },
                "followups": (
                    [
                        f"Show top stocks in {leading_sector}",
                        "Show sector momentum ranking",
                        "What sectors look defensive now?",
                    ] if lang == "en" else [
                        f"แสดงหุ้นเด่นในกลุ่ม {leading_sector}",
                        "แสดงการจัดอันดับ momentum ของแต่ละกลุ่ม",
                        "ตอนนี้กลุ่ม defensive มีอะไรบ้าง?",
                    ]
                ),
                "status": {
                    "online": True,
                    "message": "Scanner unavailable, using sector fallback" if lang == "en" else "scanner ยังไม่พร้อม ใช้ sector fallback แทน",
                    "live_data_ready": False,
                    "market_context_loaded": True,
                    "degraded": True,
                },
                "summary": {
                    "market_sentiment": macro.get("market_sentiment"),
                    "market_regime": market_regime,
                    "regime_confidence": regime_conf,
                    "fear_greed_score": macro.get("fear_greed_index"),
                    "trending_sector": leading_sector,
                    "risk_outlook": risk_outlook,
                    "signal": "Sector rotation fallback",
                    "suggested_etfs": suggested_etfs,
                    "estimated_leaders": [row["symbol"] for row in inferred_items],
                    "estimated_scores": {row["symbol"]: row.get("score") for row in inferred_items},
                },
            }

        items = []
        for history_payload in histories:
            symbol = history_payload.get("symbol")
            history = close_series(history_payload.get("history", []))
            if len(history) < 2:
                continue
            change = compute_return_pct(history[-2], history[-1]) or 0.0
            ret_1m = compute_return_pct(history[0], history[-1])
            items.append({
                "symbol": symbol,
                "name": symbol,
                "price": round(history[-1], 2),
                "daily_change": round(change, 2),
                "return_1m": round(ret_1m, 2) if ret_1m is not None else None,
                "reason": "High recent activity and notable price movement.",
            })
        items.sort(key=lambda row: (abs(row.get("daily_change") or 0.0), abs(row.get("return_1m") or 0.0)), reverse=True)
        items = [
            normalized for normalized in (
                _normalize_trending_item(item, "market_data_gateway") for item in items[:5]
            ) if normalized is not None
        ]
        stale_cache_used = False
        if items:
            TRENDING_CACHE["items"] = items
        else:
            cached_items = TRENDING_CACHE.get("items") or []
            if cached_items:
                items = [
                    normalized for normalized in (
                        _normalize_trending_item(item, "cache") for item in cached_items
                    ) if normalized is not None
                ]
                stale_cache_used = True
        source_tags = _source_tags("Finnhub", "Internal TA Engine", "Market Snapshot Cache")
        if not items:
            return _fallback_trending_response()
        return {
            "intent": "market_scanner",
            "analysis_type": "market_scanner",
            "analysis_engine": "modular_market_scanner_engine",
            "answer": (
                ("กำลังใช้รายการหุ้นเด่นจาก market scanner รอบล่าสุด\n\n" if lang == "th" else "Using cached top movers from the latest scanner run.\n\n")
                if stale_cache_used else ""
            )
            + ("หุ้นเด่นวันนี้\n" if lang == "th" else "Trending Stocks Today\n")
            + "\n".join(
                [
                    f"{idx + 1}. {row['name']} ({row['symbol']})\n"
                    + (_pick_lang(lang, f"- ราคา ${row['price']:.2f}", f"- Price ${row['price']:.2f}"))
                    + (_pick_lang(lang, f"\n- การเปลี่ยนแปลงรายวัน {row['change_pct']:+.2f}%", f"\n- Daily move {row['change_pct']:+.2f}%") if row.get("change_pct") is not None else "")
                    + (_pick_lang(lang, f"\n- ผลตอบแทน 1 เดือน {row['month_return']:+.2f}%", f"\n- 1M return {row['month_return']:+.2f}%") if row.get("month_return") is not None else "")
                    + _pick_lang(lang, f"\n- เหตุผลที่กำลังเด่น: {row['reason']}\n", f"\n- Why it is trending: {row['reason']}\n")
                    for idx, row in enumerate(items)
                ]
            )
            + _pick_lang(lang, "\nภาพรวมตลาด\n", "\nMarket Context\n")
            + (
                _pick_lang(lang, f"- Fear & Greed: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})\n", f"- Fear & Greed: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})\n")
                if macro.get("fear_greed_index") is not None else
                _pick_lang(lang, "- ยังไม่มีข้อมูล Fear & Greed ที่ยืนยันได้\n", "- Fear & Greed: Data unavailable for this signal.\n")
            )
            + _pick_lang(lang, f"- กลุ่มนำตลาด: {top_sector or 'ยังไม่มีข้อมูลยืนยัน'}", f"- Leading sector: {top_sector or 'Data unavailable for this signal.'}")
            + _pick_lang(
                lang,
                "\n\nมุมมองตามเวลา\n- ระยะสั้น: หุ้นที่กำลังเด่นมักได้แรงหนุนจาก volume และ momentum ระยะสั้น\n- ระยะกลาง: ต้องดูว่ากำไร ข่าว และแรงหมุนของ sector รองรับต่อหรือไม่\n\nการวางน้ำหนัก\n- ให้น้ำหนักเฉพาะตัวที่สัญญาณต่อเนื่อง\n- ถือเป็นกลางต่อรายชื่อที่ขึ้นมาจากกระแสเก็งกำไรล้วน\n- ให้น้ำหนักต่ำกว่าหุ้นที่ volume ลดลงเร็ว",
                "\n\nTime Horizon\n- Short-term: trending names are usually driven by volume and short-term momentum.\n- Medium-term: persistence depends on earnings, news flow, and sector rotation support.\n\nPositioning\n- Overweight only the names with sustained confirmation.\n- Stay Neutral on purely speculative movers.\n- Underweight names where volume leadership fades quickly.",
            ),
            "confidence": 80 if stale_cache_used else 68,
            "sources": ["Market data", "Technical analysis"],
            "data_validation": {"price_data": True, "news_data": False, "technical_data": True},
            "summary": {
                "market_sentiment": macro.get("market_sentiment"),
                "fear_greed_score": macro.get("fear_greed_index"),
                "trending_sector": top_sector,
                "risk_outlook": macro.get("risk_outlook"),
            },
            "answer_schema": {
                "intent": "market_scanner",
                "direct_answer": _pick_lang(lang, "นี่คือหุ้นที่เด่นที่สุดจาก market scanner ตอนนี้", "Here are the stocks showing the strongest recent activity in the current market scanner."),
                "market_context": {
                    "market_sentiment": macro.get("market_sentiment"),
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "top_sector": top_sector,
                },
                "items": items,
                "trending_stocks": items,
                "overview": _pick_lang(
                    lang,
                    f"ภาวะตลาด {macro.get('market_sentiment') or 'ยังไม่มีข้อมูลยืนยัน'} • กลุ่มนำ {top_sector or 'ยังไม่มีข้อมูลยืนยัน'} • รายชื่อด้านล่างคือหุ้นที่มี activity เด่นสุดตอนนี้",
                    f"Market sentiment is {macro.get('market_sentiment') or 'mixed'}; {top_sector or 'the leading sector'} is in focus, and the names below show the strongest recent activity.",
                ),
                "rationale": [
                    _pick_lang(lang, "หุ้นที่ติดรายการนี้มีการเคลื่อนไหวรายวันเด่นหรือ momentum ระยะสั้นสูง", "These names show either strong daily moves or notable short-term momentum."),
                    _pick_lang(lang, "ตลาดมักให้ความสำคัญกับหุ้นที่มี volume/activity สูงกว่าปกติ", "Market attention tends to concentrate in names with unusual volume or activity."),
                    _pick_lang(lang, f"sector ที่นำตลาดตอนนี้คือ {top_sector or 'ยังไม่มีข้อมูลยืนยัน'}", f"The current leadership sector is {top_sector or 'not fully confirmed'}."), 
                ],
                "risks": [
                    _pick_lang(lang, "หุ้นที่กำลังเด่นมักผันผวนสูงและกลับทิศได้เร็ว", "Trending names can reverse quickly and are often more volatile."),
                    _pick_lang(lang, "แรงเก็งกำไรระยะสั้นอาจทำให้ราคาหลุดจากพื้นฐานได้ง่าย", "Short-term speculation can disconnect price action from fundamentals."),
                    _pick_lang(lang, "ถ้า market breadth แคบ รายชื่อเด่นอาจกระจุกตัวเกินไป", "If market breadth is narrow, the trending list can become overly concentrated."),
                ],
                "actionable_view": _pick_lang(
                    lang,
                    f"เน้นติดตาม {items[0]['symbol']} และกลุ่ม {top_sector or 'ที่นำตลาด'} แต่ควรใช้ขนาดสถานะเล็กกว่าปกติ",
                    f"Focus on {items[0]['symbol']} and leadership in {top_sector or 'the leading sector'}, but size positions conservatively.",
                ),
                "cause_effect_chain": [
                    _pick_lang(lang, "volume/activity สูงขึ้น → attention ของตลาดเพิ่ม → หุ้นเข้าสู่รายชื่อเด่น", "Higher volume/activity -> more market attention -> inclusion in the trending list."),
                    _pick_lang(lang, "momentum ระยะสั้น + sector leadership → การไหลของเงินระยะสั้น → ความผันผวนสูงขึ้น", "Short-term momentum + sector leadership -> fast capital flows -> higher volatility."),
                ],
                "time_horizon": _time_horizon_payload(
                    short_term=_pick_lang(lang, "ระยะสั้นรายชื่อเด่นสะท้อนแรงซื้อขายและ momentum ปัจจุบัน", "Short term, the list reflects current trading activity and momentum."),
                    medium_term=_pick_lang(lang, "ระยะกลางต้องดูว่าข่าว กำไร และ sector rotation ยังหนุนต่อหรือไม่", "Medium term, persistence depends on news, earnings, and ongoing sector rotation."),
                ),
                "source_tags": source_tags,
                "scanner_mode": "cached" if stale_cache_used else "live",
            },
            "followups": (
                [
                    "เปรียบเทียบ 2 หุ้นที่เด่นสุดตอนนี้",
                    "ความเสี่ยงหลักของหุ้นที่เด่นสุดคืออะไร?",
                    "ตอนนี้ sector ไหนโมเมนตัมดีที่สุด?",
                ] if lang == "th" else [
                    "Compare the top two trending names",
                    "What are the downside risks for the top trending stock?",
                    "Which sectors have the strongest momentum now?",
                ]
            ),
            "status": {
                "online": True,
                "message": ("กำลังใช้ข้อมูล scanner ที่ cache ไว้" if stale_cache_used else "พร้อมใช้งาน") if lang == "th" else ("Using cached scanner data" if stale_cache_used else "Connected"),
                "live_data_ready": not stale_cache_used,
                "market_context_loaded": True,
                "degraded": stale_cache_used,
            },
        }

    def analyze_market(self, context: Any) -> Dict[str, Any]:
        lang = _lang_for(str((context or {}).get("user_question") or "")) if isinstance(context, dict) else "en"
        market = self.market_data.get_market_context(context)
        macro = self.macro_data.build_macro_snapshot(market)
        regime_ctx = self._market_regime_context(macro)
        sector_rankings = self.market_data.get_sector_rankings().get("rankings", [])
        top_sector = sector_rankings[0].get("sector") if sector_rankings else "Relevant data is not available"
        interpretation_text = self._regime_interpretation(regime_ctx, lang)
        positioning_text = self._positioning_text(regime_ctx, lang)
        application_text = self._macro_regime_application(regime_ctx, lang)
        answer = (
            ("ภาพรวมตลาด\n" if lang == "th" else "Market Context\n")
            + _pick_lang(lang, f"- Regime: {regime_ctx['regime']}\n- Confidence: {regime_ctx['confidence']}\n", f"- Regime: {regime_ctx['regime']}\n- Confidence: {regime_ctx['confidence']}\n")
            + (
                _pick_lang(lang, f"- CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})\n\n", f"- CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})\n\n")
                if macro.get("fear_greed_index") is not None else
                _pick_lang(lang, "- Market regime unavailable: using Neutral fallback\n\n", "- Market regime unavailable: using Neutral fallback.\n\n")
            )
            + _pick_lang(lang, "การตีความ\n", "Interpretation\n")
            + f"- {interpretation_text}\n\n"
            + _pick_lang(lang, "การวางน้ำหนัก\n", "Positioning\n")
            + positioning_text
            + "\n"
            + _pick_lang(lang, "การประยุกต์กับคำถามนี้\n", "Application to This Question\n")
            + f"- {application_text}\n\n"
            + _pick_lang(lang, "ข้อมูลที่ใช้\n- แบบจำลองความเชื่อมั่นตลาด\n- โมเมนตัมของ Sector ETF\n\n", "Data Used\n- Market sentiment model\n- Sector ETF momentum\n\n")
            + _pick_lang(lang, "บทวิเคราะห์\n", "Analysis\n")
            + _pick_lang(lang, f"- ภาวะตลาดอ้างอิงจาก external benchmark: {macro.get('market_sentiment') or 'ยังไม่มีข้อมูลยืนยัน'}\n", f"- External benchmark sentiment: {macro.get('market_sentiment') or 'Relevant data is not available'}\n")
            + _pick_lang(lang, f"- กลุ่มที่นำตลาด: {top_sector}\n", f"- Leading sector: {top_sector}\n")
            + _pick_lang(lang, f"- มุมมองความเสี่ยง: {macro.get('risk_outlook') or 'ยังไม่มีข้อมูลยืนยัน'}\n\n", f"- Risk outlook: {macro.get('risk_outlook') or 'Relevant data is not available'}\n\n")
            + _pick_lang(lang, "มุมมองตามเวลา\n- ระยะสั้น: sentiment และ sector leadership เป็นตัวขับตลาดหลัก\n- ระยะกลาง: ตลาดจะขึ้นกับว่าเงินเฟ้อและดอกเบี้ยไปทางไหนต่อ\n\n", "Time Horizon\n- Short-term: sentiment and sector leadership are the main drivers.\n- Medium-term: the market path depends on inflation and rate direction.\n\n")
            + _pick_lang(lang, "ข้อสรุป\n", "Conclusion\n")
            + application_text
        )
        source_tags = _source_tags("Fear & Greed", "Sector ETF Model", "Market Snapshot Cache")
        overview = _pick_lang(
            lang,
            f"Regime {regime_ctx['regime']} • ความเชื่อมั่น {regime_ctx['confidence']} • กลุ่มนำ {top_sector}",
            f"Regime is {regime_ctx['regime']} with {regime_ctx['confidence']} confidence; {top_sector} remains the leading sector.",
        )
        rationale = [
            _pick_lang(lang, f"market regime ปัจจุบันคือ {regime_ctx['regime']} และมีความเชื่อมั่น {regime_ctx['confidence']}", f"The current market regime is {regime_ctx['regime']} with {regime_ctx['confidence']} confidence."),
            interpretation_text,
            _pick_lang(lang, "sector ที่นำตลาดสะท้อนว่ากระแสเงินกำลังไหลไปทางไหน", "The leading sector shows where capital is rotating."),
        ]
        risks = [
            _pick_lang(lang, "ถ้า sentiment เปลี่ยนเร็ว ผู้นำตลาดอาจสลับได้ทันที", "Leadership can change quickly if sentiment shifts."),
            _pick_lang(lang, "bond yield และข้อมูลเงินเฟ้อยังเป็นตัวแปรกดดัน valuation", "Bond yields and inflation data still pressure valuations."),
            _pick_lang(lang, "sector breadth ที่แคบทำให้ตลาดเปราะกว่าที่ headline index สะท้อน", "Narrow market breadth can make the market more fragile than the headline index suggests."),
        ]
        actionable_view = _pick_lang(
            lang,
            application_text,
            application_text,
        )
        return {
            "intent": "market_overview",
            "analysis_type": "market_overview",
            "analysis_engine": "modular_market_overview_engine",
            "answer": answer,
            "confidence": 72,
            "sources": ["Market sentiment model", "Sector ETF model"],
            "data_validation": {"price_data": True, "news_data": True, "technical_data": True},
            "summary": {
                "market_sentiment": macro.get("market_sentiment"),
                "market_regime": regime_ctx["regime"],
                "regime_confidence": regime_ctx["confidence"],
                "fear_greed_score": macro.get("fear_greed_index"),
                "trending_sector": top_sector,
                "risk_outlook": macro.get("risk_outlook"),
            },
            "answer_schema": {
                "intent": "market_overview",
                "direct_answer": _pick_lang(
                    lang,
                    f"ภาพรวมตลาดยังค่อนข้างระมัดระวัง โดย {top_sector} ยังเป็นกลุ่มที่นำตลาดในเชิงเปรียบเทียบ",
                    f"Market conditions remain cautious, with {top_sector} currently leading on a relative basis.",
                ),
                "market_context": {
                    "market_regime": regime_ctx["regime"],
                    "confidence": regime_ctx["confidence"],
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "positioning": regime_ctx["positioning"],
                    "suggested_etfs": regime_ctx["suggested_etfs"],
                    "points": [
                        f"Regime: {regime_ctx['regime']} ({regime_ctx['confidence']} confidence)",
                        (
                            f"CNN Fear & Greed (reference): {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})"
                            if macro.get("fear_greed_index") is not None else "Market regime unavailable: using Neutral fallback."
                        ),
                        f"Leading sector: {top_sector}",
                        f"Overweight sectors: {', '.join(regime_ctx['positioning'].get('overweight') or ['Balanced allocation'])}",
                        f"Underweight sectors: {', '.join(regime_ctx['positioning'].get('underweight') or ['No strong underweight call'])}",
                    ],
                },
                "investment_interpretation": {
                    "recommendation": "Selective positioning",
                    "text": application_text,
                    "confidence": 72,
                    "forecast_horizon": {},
                },
                "sources": ["Market sentiment model", "Sector ETF model"],
                "overview": overview,
                "rationale": rationale,
                "summary_points": rationale,
                "risks": risks,
                "actionable_view": actionable_view,
                "cause_effect_chain": [
                    _pick_lang(lang, "sentiment ตลาด → appetite ต่อสินทรัพย์เสี่ยง → sector leadership", "Market sentiment -> risk appetite -> sector leadership."),
                    _pick_lang(lang, "เงินเฟ้อและดอกเบี้ย → valuation pressure → การหมุนของเงินระหว่าง Growth, Defensive และ Cyclical", "Inflation and rates -> valuation pressure -> rotation between Growth, Defensive, and Cyclical sectors."),
                ],
                "time_horizon": _time_horizon_payload(
                    short_term=_pick_lang(lang, "ระยะสั้น sentiment และ sector leadership เป็นตัวกำหนดโทนตลาด", "Short term, sentiment and sector leadership set the market tone."),
                    medium_term=_pick_lang(lang, "ระยะกลาง ตลาดจะขึ้นกับว่าดอกเบี้ยและเงินเฟ้อจะผ่อนคลายหรือกดดันต่อ", "Medium term, the market depends on whether rates and inflation ease or stay restrictive."),
                ),
                "source_tags": source_tags,
            },
            "followups": (
                [
                    "ตอนนี้กลุ่มไหนแข็งแรงที่สุด?",
                    "ความเสี่ยงหลักของตลาดตอนนี้คืออะไร?",
                    f"ขอดูหุ้นโมเมนตัมเด่นในกลุ่ม {top_sector}",
                ] if lang == "th" else [
                    "Which sectors are strongest now?",
                    "What are the biggest market risks now?",
                    "Show top momentum stocks in the leading sector",
                ]
            ),
            "status": {
                "online": True,
                "message": "พร้อมใช้งาน" if lang == "th" else "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
        }

    def analyze_portfolio(self, context: Dict[str, Any]) -> Dict[str, Any]:
        holdings = context.get("portfolio") or []
        lang = str(context.get("response_language") or "en")
        count = len(holdings)
        sectors: Dict[str, float] = {}
        for holding in holdings:
            sector = str(holding.get("sector") or "Unknown")
            weight = float(holding.get("weight") or holding.get("market_value") or 0)
            sectors[sector] = sectors.get(sector, 0.0) + weight
        top_sector = max(sectors, key=sectors.get) if sectors else "Relevant data is not available"
        concentration = round(sectors.get(top_sector, 0.0), 2) if sectors else None
        answer = (
            "Market Context\nPortfolio review uses current holdings and concentration mix.\n\n"
            "Data Used\n- Holdings\n- Position concentration\n\n"
            "Analysis\n"
            + (f"- Largest concentration: {top_sector} ({concentration})\n" if concentration is not None else "- Holdings data unavailable.\n")
            + f"- Number of positions: {count}\n\n"
            + "Time Horizon\n"
            + "- Short-term: concentration risk matters most when one sector drives the portfolio's daily swings.\n"
            + "- Medium-term: drawdown risk depends on diversification, correlation, and whether macro conditions hit the dominant sector.\n\n"
            + "Positioning\n"
            + "- Overweight: diversified exposure\n- Neutral: balanced sector weights\n- Underweight: concentrated single-theme exposure\n\n"
            + "Conclusion\n"
            + ("Portfolio concentration looks elevated in one area; diversification is worth reviewing." if concentration and concentration > 35 else "Portfolio concentration appears reasonably balanced from current holdings data.")
        )
        source_tags = _source_tags("Portfolio Data", "Internal Portfolio Model", "Market Snapshot Cache")
        overview = _pick_lang(
            lang,
            f"พอร์ตมี {count} ตำแหน่ง • sector ใหญ่สุดคือ {top_sector} • ความเสี่ยงหลักอยู่ที่ระดับ concentration",
            f"The portfolio has {count} holdings; {top_sector} is the largest sector exposure, and concentration is the main risk driver.",
        )
        rationale = [
            _pick_lang(lang, "จำนวนหุ้นในพอร์ตมีผลต่อการกระจายความเสี่ยง", "Position count affects diversification."),
            _pick_lang(lang, "น้ำหนักที่กระจุกใน sector เดียวเพิ่ม drawdown risk", "A large single-sector weight increases drawdown risk."),
            _pick_lang(lang, "ความสัมพันธ์กันของหุ้นในพอร์ตสำคัญพอ ๆ กับจำนวนชื่อหุ้น", "Correlation between holdings matters as much as the number of names."),
        ]
        risks = [
            _pick_lang(lang, "การกระจุกตัวสูงทำให้พอร์ตไวต่อข่าวหรือ shock เฉพาะกลุ่ม", "High concentration makes the portfolio vulnerable to sector-specific shocks."),
            _pick_lang(lang, "ถ้าหุ้นในพอร์ตมีความสัมพันธ์สูง ผลของการกระจายความเสี่ยงจะลดลง", "High correlation reduces diversification benefits."),
            _pick_lang(lang, "พอร์ตที่มีชื่อหุ้นน้อยเกินไปมักแกว่งแรงกว่าตลาด", "Too few holdings can increase volatility versus the market."),
        ]
        actionable_view = _pick_lang(
            lang,
            "ทบทวน concentration risk และกระจายน้ำหนักหาก sector เดียวใหญ่เกินไป",
            "Review concentration risk and diversify if one sector dominates the portfolio.",
        )
        return {
            "intent": "portfolio_advice",
            "analysis_type": "portfolio_analysis",
            "analysis_engine": "modular_portfolio_analysis_engine",
            "answer": answer,
            "confidence": 66 if count else 40,
            "sources": ["Portfolio data", "Internal portfolio model"],
            "data_validation": {"price_data": bool(count), "news_data": False, "technical_data": bool(count)},
            "answer_schema": {
                "intent": "portfolio_advice",
                "direct_answer": _pick_lang(
                    lang,
                    "การวิเคราะห์พอร์ตครั้งนี้ดูจากการกระจุกตัวของน้ำหนักและระดับการกระจายความเสี่ยงของพอร์ตปัจจุบัน",
                    "Portfolio analysis is based on current holdings concentration and diversification.",
                ),
                "portfolio_overview": {
                    "position_count": count,
                    "largest_sector": top_sector,
                    "largest_sector_weight": concentration,
                },
                "portfolio_analysis": {
                    "points": [
                        f"Largest sector concentration: {top_sector}" if top_sector else "Largest sector concentration: Data unavailable",
                        f"Number of holdings: {count}",
                    ],
                },
                "risk_factors": {
                    "points": [
                        "High concentration can increase drawdown risk.",
                        "Correlation between similar holdings can reduce diversification benefits.",
                    ],
                },
                "investment_interpretation": {
                    "recommendation": _pick_lang(lang, "ทบทวนความเสี่ยงจากการกระจุกตัว", "Review concentration risk"),
                    "text": _pick_lang(
                        lang,
                        "ความเสี่ยงหลักของพอร์ตนี้มาจากระดับการกระจุกตัวและสมดุลของการกระจายความเสี่ยงระหว่างสินทรัพย์ที่ถืออยู่",
                        "Portfolio risk is driven primarily by concentration and diversification balance in the current holdings set.",
                    ),
                    "confidence": 66 if count else 40,
                    "forecast_horizon": {},
                },
                "sources": ["Portfolio data", "Internal portfolio model"],
                "overview": overview,
                "rationale": rationale,
                "summary_points": rationale,
                "risks": risks,
                "actionable_view": actionable_view,
                "cause_effect_chain": [
                    _pick_lang(lang, "sector ที่มีน้ำหนักมาก → shock เฉพาะกลุ่ม → drawdown ของพอร์ต", "A dominant sector weight -> sector-specific shock -> portfolio drawdown."),
                    _pick_lang(lang, "ความสัมพันธ์ของหุ้นในพอร์ตสูง → การกระจายความเสี่ยงลดลง → ความผันผวนรวมเพิ่มขึ้น", "High holding correlation -> weaker diversification -> higher portfolio volatility."),
                ],
                "time_horizon": _time_horizon_payload(
                    short_term=_pick_lang(lang, "ระยะสั้นความเสี่ยงมักมาจาก sector ที่มีน้ำหนักสูงสุด", "Short term, risk usually comes from the largest sector weight."),
                    medium_term=_pick_lang(lang, "ระยะกลางผลตอบแทนขึ้นกับระดับการกระจายความเสี่ยงและความสัมพันธ์ของสินทรัพย์ในพอร์ต", "Medium term, outcomes depend on diversification and correlation across the portfolio."),
                ),
                "source_tags": source_tags,
            },
            "followups": (
                [
                    "ความเสี่ยงจากการกระจุกตัวของพอร์ตอยู่ตรงไหนมากที่สุด?",
                    "ควรกระจายพอร์ตอย่างไรดี?",
                    "ตัวไหนในพอร์ตดูอ่อนแอที่สุดตอนนี้?",
                ] if lang == "th" else [
                    "Where is my concentration risk highest?",
                    "How can I diversify this portfolio?",
                    "Which holdings look weakest now?",
                ]
            ),
            "status": {
                "online": True,
                "message": "พร้อมใช้งาน" if lang == "th" else "Connected",
                "live_data_ready": bool(count),
                "market_context_loaded": True,
            },
        }

    def analyze_sector_stock_picker(self, question: str, context: Any) -> Dict[str, Any]:
        lang = _lang_for(question)
        market = self.market_data.get_market_context(context)
        macro = self.macro_data.build_macro_snapshot(market)
        regime_ctx = self._market_regime_context(macro)
        sector_rankings = self.market_data.get_sector_rankings().get("rankings", [])
        sector_lookup = {str(row.get("sector") or "").lower(): row for row in sector_rankings}
        requested_sector = _extract_requested_sector(question)
        resolved_context = context.get("resolved_context") if isinstance(context, dict) else {}
        resolved_target = str((resolved_context or {}).get("target") or "").lower()
        if not requested_sector:
            if "energy" in resolved_target or "oil" in resolved_target:
                requested_sector = "Energy"
            elif "tech" in resolved_target or "technology" in resolved_target:
                requested_sector = "Technology"
            elif "financial" in resolved_target or "bank" in resolved_target:
                requested_sector = "Finance"
            elif "health" in resolved_target:
                requested_sector = "Healthcare"
        if not requested_sector:
            q = (question or "").lower()
            requested_sector = next((row.get("sector") for row in sector_rankings if str(row.get("sector") or "").lower() in q), None)
        if not requested_sector:
            requested_sector = (macro.get("top_sector") or (sector_rankings[0].get("sector") if sector_rankings else None) or "Technology")
        sector_snapshot = sector_lookup.get(str(requested_sector).lower(), {})
        etf = sector_snapshot.get("etf")
        allowed_symbols = set(SECTOR_STOCK_UNIVERSE.get(requested_sector, []))
        stock_rows = sector_snapshot.get("top_stocks") or []
        if not stock_rows:
            stock_rows = sector_snapshot.get("constituents") or []
        normalized_rows = []
        seen_symbols = set()
        for row in stock_rows[:5]:
            symbol = row.get("symbol") or row.get("ticker")
            if not symbol:
                continue
            symbol = str(symbol).upper().strip()
            inferred_sector = _sector_for_symbol(symbol)
            if inferred_sector and inferred_sector != requested_sector:
                continue
            if allowed_symbols and symbol not in allowed_symbols and inferred_sector != requested_sector:
                continue
            if symbol in seen_symbols:
                continue
            price = _safe_float(row.get("price"))
            ret_3m = _safe_float(row.get("return_3m_pct"))
            normalized_rows.append({
                "symbol": symbol,
                "name": _canonical_name(symbol, row.get("name") or symbol),
                "price": round(price, 2) if price is not None else None,
                "return_3m_pct": round(ret_3m, 2) if ret_3m is not None else None,
                "momentum": row.get("momentum") or ("Strong" if (ret_3m or 0) > 10 else "Moderate" if (ret_3m or 0) > 0 else "Weak"),
                "reason": row.get("reason") or (
                    "Strong relative trend within the sector."
                    if (ret_3m or 0) > 10 else "Holding up better than peers on current price action."
                ),
            })
            seen_symbols.add(symbol)

        if len(normalized_rows) < 3:
            for symbol in SECTOR_STOCK_UNIVERSE.get(requested_sector, []):
                if symbol in seen_symbols:
                    continue
                try:
                    bundle = self.market_data.get_stock_bundle(symbol)
                    profile = bundle.get("profile") or {}
                    profile_sector = (
                        profile.get("sector")
                        or profile.get("industry")
                        or _sector_for_symbol(symbol)
                        or requested_sector
                    )
                    profile_sector_text = str(profile_sector).lower()
                    requested_sector_text = str(requested_sector).lower()
                    if requested_sector_text not in profile_sector_text and (_sector_for_symbol(symbol) or requested_sector) != requested_sector:
                        continue
                    history_3m = (bundle.get("history_3m") or {}).get("history") or []
                    closes = [ _safe_float(row.get("close")) for row in history_3m if _safe_float(row.get("close")) and _safe_float(row.get("close")) > 0 ]
                    first = closes[0] if closes else None
                    last = closes[-1] if closes else None
                    ret_3m = ((last - first) / first) * 100.0 if first and last and first > 0 else None
                    price = _safe_float((bundle.get("history_3m") or {}).get("price")) or last
                    normalized_rows.append({
                        "symbol": symbol,
                        "name": _canonical_name(symbol, profile.get("name") or symbol),
                        "price": round(price, 2) if price is not None else None,
                        "return_3m_pct": round(ret_3m, 2) if ret_3m is not None else None,
                        "momentum": "Strong" if (ret_3m or 0) > 10 else "Moderate" if (ret_3m or 0) > 0 else "Weak",
                        "reason": (
                            "Strong relative trend within the sector."
                            if (ret_3m or 0) > 10 else "Holding up better than peers on current price action."
                        ),
                    })
                    seen_symbols.add(symbol)
                except Exception:
                    continue

        normalized_rows.sort(key=lambda row: (_safe_float(row.get("return_3m_pct")) or -999.0), reverse=True)
        normalized_rows = normalized_rows[:5]

        picks: List[Dict[str, Any]] = []
        for row in normalized_rows:
            symbol = row["symbol"]
            bucket = _bucket_for_sector_pick(requested_sector, symbol)
            conviction = "high" if (_safe_float(row.get("return_3m_pct")) or 0) >= 8 else ("medium" if (_safe_float(row.get("return_3m_pct")) or 0) >= 2 else "selective")
            picks.append({
                **row,
                "bucket": bucket,
                "conviction": conviction,
            })

        bucket_priority = {"core": 0, "momentum": 1, "high_beta": 2}
        picks.sort(key=lambda row: (bucket_priority.get(str(row.get("bucket")), 9), -((_safe_float(row.get("return_3m_pct")) or -999.0))))
        picks = picks[:5]

        core_picks = [row for row in picks if row.get("bucket") == "core"]
        momentum_picks = [row for row in picks if row.get("bucket") == "momentum"]
        high_beta_picks = [row for row in picks if row.get("bucket") == "high_beta"]

        spy_return_3m = None
        try:
            spy_bundle = self.market_data.get_stock_bundle("SPY")
            spy_history_3m = (spy_bundle.get("history_3m") or {}).get("history") or []
            spy_closes = [_safe_float(row.get("close")) for row in spy_history_3m if _safe_float(row.get("close")) and _safe_float(row.get("close")) > 0]
            if len(spy_closes) >= 2:
                spy_return_3m = ((spy_closes[-1] - spy_closes[0]) / spy_closes[0]) * 100.0
        except Exception:
            spy_return_3m = None

        requested_sector_rank = next((idx + 1 for idx, row in enumerate(sector_rankings) if str(row.get("sector") or "").lower() == str(requested_sector).lower()), None)
        second_sector = sector_rankings[1] if len(sector_rankings) > 1 else None
        sector_return_3m = _safe_float(sector_snapshot.get("return_3m_pct"))
        sector_vs_spy = None
        if sector_return_3m is not None and spy_return_3m is not None:
            sector_vs_spy = sector_return_3m - spy_return_3m

        if requested_sector == "Energy":
            if regime_ctx.get("regime") == "Risk-Off":
                regime_alignment = _pick_lang(
                    lang,
                    "ภายใต้ Risk-Off กลุ่มพลังงานยังควรถูกเน้นมากกว่าปกติ เพราะเป็นหนึ่งในกลุ่มที่ตลาดยอมรับได้ในเชิงป้องกันความเสี่ยงมากกว่า growth",
                    "Under Risk-Off conditions, Energy deserves more emphasis because it remains one of the few sectors that can still attract capital while growth risk budgets are being cut.",
                )
            elif regime_ctx.get("regime") == "Neutral":
                regime_alignment = _pick_lang(
                    lang,
                    "ภายใต้ Neutral กลุ่มพลังงานควรถูกมองเป็นหนึ่งในกลุ่มเด่น ไม่ใช่คำตอบเดียวของตลาด จึงควรเทียบกับผู้นำกลุ่มอื่นก่อนเพิ่มน้ำหนักมากเกินไป",
                    "Under a Neutral regime, Energy should be treated as one of several strong sectors rather than the only answer, so compare it with other leaders before overweighting too aggressively.",
                )
            else:
                regime_alignment = _pick_lang(
                    lang,
                    "ภายใต้ Risk-On ยังถือว่าพลังงานใช้ได้ แต่แรงส่งอาจสู้กลุ่ม growth หรือ semis ไม่ได้ถ้าตลาดเปิดรับความเสี่ยงเต็มตัว",
                    "Under Risk-On conditions, Energy can still work, but it may not lead if markets are fully rewarding growth and semiconductors again.",
                )
            oil_driver = _pick_lang(
                lang,
                "Macro driver: ราคาน้ำมันเป็นตัวแปรสำคัญของธีมนี้ แม้ระบบจะไม่มี live oil quote ในคำตอบนี้ แต่ sector leadership และภาวะเงินเฟ้อ/ภูมิรัฐศาสตร์ยังเป็น proxy หลัก",
                "Macro driver: oil is the key macro variable for this theme. Even when a live oil quote is unavailable in this response, sector leadership plus inflation and geopolitical context still act as the main proxy.",
            )
            sub_sector_breakdown = _energy_subsector_payload(78 if picks else 42)
            sub_sector_lines = (
                [
                    "Upstream: positive สูงสุด เพราะรายได้ผูกกับราคาน้ำมันโดยตรง",
                    "Midstream: บวกแบบเสถียรกว่า เพราะขับเคลื่อนด้วย volume และสัญญาระยะยาว",
                    "Downstream: ขึ้นกับ crack spread จึงไม่ได้บวกอัตโนมัติทุกครั้ง",
                    "Oil services: บวกแบบตามหลัง เพราะต้องรอ capex cycle ของผู้ผลิต",
                ]
                if lang == "th" else
                [
                    "Upstream: strongest positive because revenue is directly linked to higher oil prices.",
                    "Midstream: steadier positive because the business is more volume-driven.",
                    "Downstream: conditional because refiners depend on crack spreads, not crude alone.",
                    "Oil services: delayed positive because the benefit arrives through the capex cycle.",
                ]
            )
            best_positioning_text = _pick_lang(
                lang,
                "Best positioning: ให้เงินไหลเข้าฝั่ง Upstream ก่อน ตามด้วย Services เมื่อเห็น capex cycle เริ่มตามมา ส่วน Refiners ถือแบบ selective เท่านั้น",
                "Best positioning: put core capital into upstream first, add services as capex follows through, and keep refiners selective because the edge is conditional.",
            )
        else:
            regime_alignment = _pick_lang(
                lang,
                f"การให้น้ำหนักกลุ่ม {requested_sector} ควรสอดคล้องกับ regime ปัจจุบันและเทียบกับผู้นำกลุ่มอื่นเสมอ",
                f"Exposure to {requested_sector} should stay aligned with the current regime and be judged relative to other sector leaders.",
            )
            oil_driver = _pick_lang(
                lang,
                "Macro driver: ใช้ sector leadership และ market regime เป็นตัวนำมากกว่าปัจจัยสินค้าโภคภัณฑ์เฉพาะตัว",
                "Macro driver: sector leadership and market regime matter more here than a single commodity driver.",
            )
            sub_sector_breakdown = []
            sub_sector_lines = []
            best_positioning_text = _pick_lang(
                lang,
                f"Best positioning: เน้นผู้นำหลักของ {requested_sector} ก่อน แล้วค่อยเติม momentum names แบบ selective",
                f"Best positioning: keep capital in the strongest core leaders inside {requested_sector} before adding selective momentum names.",
            )

        if requested_sector == "Energy":
            allocation_text = _pick_lang(
                lang,
                "Allocation suggestion: core 50–60% / momentum 25–35% / high beta 10–15%",
                "Allocation suggestion: core 50–60% / momentum 25–35% / high beta 10–15%",
            )
            entry_timing = _pick_lang(
                lang,
                "Entry timing: รอเข้าหลังย่อตัวหรือเมื่อราคายืนเหนือค่าเฉลี่ยระยะสั้นพร้อม volume สนับสนุน",
                "Entry timing: prefer entries on pullbacks or when price reclaims short-term moving averages with volume confirmation.",
            )
            exit_conditions = _pick_lang(
                lang,
                "Exit conditions: ลดน้ำหนักถ้าแรงนำของกลุ่มพลังงานอ่อนลง, ราคาน้ำมันหลุดแนวโน้ม, หรือหุ้นตัวนั้น underperform ETF กลุ่มต่อเนื่อง",
                "Exit conditions: trim if energy leadership weakens, oil loses trend support, or the name persistently underperforms the sector ETF.",
            )
        else:
            allocation_text = _pick_lang(
                lang,
                "Allocation suggestion: core 50–60% / momentum 25–35% / high beta 10–15%",
                "Allocation suggestion: core 50–60% / momentum 25–35% / high beta 10–15%",
            )
            entry_timing = _pick_lang(
                lang,
                "Entry timing: รอการยืนยันแนวโน้มของกลุ่มและเข้าทีละส่วนเมื่อผู้นำยังรักษา relative strength ได้",
                "Entry timing: scale in only after sector trend confirmation and while leaders keep their relative strength.",
            )
            exit_conditions = _pick_lang(
                lang,
                "Exit conditions: ลดน้ำหนักเมื่อ sector rotation เปลี่ยน, momentum แตก, หรือหุ้นหลุดจากกลุ่มผู้นำ",
                "Exit conditions: reduce exposure when sector rotation shifts, momentum breaks, or the stock drops out of the leadership group.",
            )

        if not picks:
            direct_answer = _pick_lang(lang, f"ตอนนี้ยังไม่มี ranking รายชื่อหุ้นที่ยืนยันได้ในกลุ่ม {requested_sector}", f"Stock-level ranking data is temporarily unavailable for {requested_sector}.")
            confidence = 42
        else:
            direct_answer = _pick_lang(
                lang,
                f"หุ้น conviction สูงในกลุ่ม {requested_sector} ตอนนี้คือ {', '.join([row['symbol'] for row in picks[:5]])}",
                f"High-conviction picks in {requested_sector} right now are {', '.join([row['symbol'] for row in picks[:5]])}.",
            )
            confidence = 78

        source_tags = _source_tags("Finnhub", "Sector ETF Model", "Internal TA Engine", "Market Snapshot Cache")
        overview = _pick_lang(
            lang,
            f"กลุ่ม {requested_sector} อยู่ในเรดาร์ของตลาด • ETF {etf or 'ยังไม่มีข้อมูลยืนยัน'} • รายชื่อนี้คัดเฉพาะหุ้น conviction สูง 3–5 ตัวในกลุ่มเดียวกัน",
            f"{requested_sector} is on the market radar; ETF {etf or 'not fully confirmed'} anchors the view, and this list is narrowed to 3–5 high-conviction names from the same sector only.",
        )
        rationale = list(dict.fromkeys([row["reason"] for row in picks[:4]])) or [
            _pick_lang(lang, "ยังไม่มี ranking ระดับหุ้นที่ยืนยันได้ในขณะนี้", "No confirmed stock-level ranking is available right now.")
        ]
        risks = [
            _pick_lang(lang, f"ผู้นำของกลุ่ม {requested_sector} อาจอ่อนลงเร็วถ้า sector rotation เปลี่ยน", f"{requested_sector} leadership can fade quickly if sector rotation shifts."),
            _pick_lang(lang, "หุ้น momentum สูงมักผันผวนมากกว่าค่าเฉลี่ย", "High-momentum names often carry higher volatility."),
            _pick_lang(lang, "ผลตอบแทนระยะสั้นอาจไม่ยั่งยืนหากไม่มีแรงหนุนจากกำไรหรือข่าว", "Short-term momentum may not persist without earnings or news support."),
        ]
        actionable_view = _pick_lang(
            lang,
            f"โฟกัส 2–3 ตัวหลักใน {requested_sector} ก่อน แบ่งไม้เข้าตามจังหวะ และใช้ high beta เป็นสัดส่วนเล็กเท่านั้น",
            f"Focus on the top 2–3 names in {requested_sector}, scale in selectively, and keep high-beta exposure as a smaller satellite position only.",
        )
        grouped_lines = []
        if core_picks:
            grouped_lines.append(
                ("Core: " if lang == "en" else "Core: ")
                + ", ".join([f"{row['name']} ({row['symbol']})" for row in core_picks[:3]])
            )
        if momentum_picks:
            grouped_lines.append(
                ("Momentum: " if lang == "en" else "Momentum: ")
                + ", ".join([f"{row['name']} ({row['symbol']})" for row in momentum_picks[:2]])
            )
        if high_beta_picks:
            grouped_lines.append(
                ("High beta: " if lang == "en" else "High beta: ")
                + ", ".join([f"{row['name']} ({row['symbol']})" for row in high_beta_picks[:2]])
            )
        answer = (
            "Market Context\n"
            + (
                f"Fear & Greed Index: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})\n\n"
                if macro.get("fear_greed_index") is not None else
                "Fear & Greed Index: Data unavailable for this signal.\n\n"
            )
            + "Data Used\n- Sector ETF momentum\n- Stock-level price action within the requested sector only\n\n"
            + "Sector Comparison\n"
            + (
                f"- {requested_sector} sector rank: #{requested_sector_rank}\n" if requested_sector_rank is not None else ""
            )
            + (
                f"- Relative performance vs SPY (3M): {sector_vs_spy:+.2f}%\n" if sector_vs_spy is not None else "- Relative performance vs SPY (3M): N/A\n"
            )
            + (
                f"- Next sector to compare: {second_sector.get('sector')} ({_safe_float(second_sector.get('return_3m_pct')):+.2f}% 3M)\n\n" if second_sector else "\n"
            )
            + "Macro Driver\n"
            + f"- {oil_driver}\n\n"
            + (
                "SUB-SECTOR BREAKDOWN\n"
                + "\n".join([f"- {line}" for line in sub_sector_lines])
                + "\n\n"
                if sub_sector_lines else ""
            )
            + "Analysis\n"
            + ("\n".join([
                f"{idx + 1}. {row['name']} ({row['symbol']}): "
                + (f"${row['price']:.2f}, " if row.get("price") is not None else "")
                + (f"3M return {row['return_3m_pct']:+.2f}%, " if row.get("return_3m_pct") is not None else "")
                + f"momentum {row['momentum']} [{row['bucket']}]"
                for idx, row in enumerate(picks[:5])
            ]) if picks else "Stock-level ranking data unavailable.")
            + "\n\nMarket Context\n"
            + f"- Regime: {regime_ctx['regime']} ({regime_ctx['confidence']})\n"
            + f"- Preferred sectors: {', '.join((regime_ctx.get('positioning') or {}).get('overweight') or ['Balanced allocation'])}\n"
            + f"- Regime alignment: {regime_alignment}\n"
            + "\n\nTime Horizon\n"
            + f"- Short-term: the leading names in {requested_sector} are benefiting from current sector momentum and relative strength.\n"
            + "- Medium-term: continuation depends on earnings support, sector rotation persistence, and whether the ETF leadership remains intact.\n\n"
            + "Grouped Picks\n"
            + ("\n".join([f"- {line}" for line in grouped_lines]) if grouped_lines else "- Data unavailable")
            + "\n\nImplementation\n"
            + f"- {allocation_text}\n"
            + f"- {entry_timing}\n"
            + f"- {exit_conditions}\n"
            + (
                f"- {best_positioning_text}\n"
                if best_positioning_text else ""
            )
            + "\n"
            + "Positioning\n"
            + f"- Overweight: top 2–3 confirmed names in {requested_sector}\n- Neutral: the broader sector basket\n- Underweight: weaker laggards without confirmed momentum\n"
            + "\n\nConclusion\n"
            + direct_answer
        )
        return {
            "intent": "sector_stock_picker",
            "analysis_type": "sector_stock_picker",
            "analysis_engine": "modular_sector_stock_picker_engine",
            "answer": answer,
            "confidence": confidence,
            "sources": ["Market data", "Sector ETF model", "Technical analysis"],
            "data_validation": {
                "price_data": bool(normalized_rows),
                "news_data": False,
                "technical_data": bool(sector_snapshot),
            },
            "summary": {
                "market_sentiment": macro.get("market_sentiment"),
                "market_regime": regime_ctx["regime"],
                "regime_confidence": regime_ctx["confidence"],
                "fear_greed_score": macro.get("fear_greed_index"),
                "trending_sector": requested_sector,
                "risk_outlook": macro.get("risk_outlook"),
            },
            "answer_schema": {
                "intent": "sector_stock_picker",
                "answer_title": _pick_lang(lang, f"หุ้นเด่นในกลุ่ม {requested_sector}", f"{requested_sector} Top Momentum Stocks"),
                "direct_answer": direct_answer,
                "sector_overview": {
                    "sector": requested_sector,
                    "etf": etf,
                    "context": f"{requested_sector} is currently one of the stronger sectors based on available ETF momentum data.",
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "market_regime": regime_ctx["regime"],
                    "regime_confidence": regime_ctx["confidence"],
                    "regime_alignment": regime_alignment,
                    "sector_rank": requested_sector_rank,
                    "sector_return_3m": round(sector_return_3m, 2) if sector_return_3m is not None else None,
                    "spy_return_3m": round(spy_return_3m, 2) if spy_return_3m is not None else None,
                    "relative_vs_spy_3m": round(sector_vs_spy, 2) if sector_vs_spy is not None else None,
                    "comparison_sector": second_sector.get("sector") if second_sector else None,
                },
                "sector_stock_picker": {
                    "sector": requested_sector,
                    "etf": etf,
                    "stocks": picks[:5],
                    "grouped": {
                        "core": core_picks[:3],
                        "momentum": momentum_picks[:2],
                        "high_beta": high_beta_picks[:2],
                    },
                    "winners": sub_sector_breakdown,
                },
                "why_these_names": {
                    "points": list(dict.fromkeys([row["reason"] for row in picks[:5]])),
                },
                "sub_sector_breakdown": {
                    "points": sub_sector_lines,
                    "winners": sub_sector_breakdown,
                    "best_positioning": best_positioning_text,
                },
                "sector_comparison": {
                    "sector_rank": requested_sector_rank,
                    "relative_vs_spy_3m": round(sector_vs_spy, 2) if sector_vs_spy is not None else None,
                    "comparison_sector": second_sector.get("sector") if second_sector else None,
                    "comparison_sector_return_3m": round(_safe_float(second_sector.get("return_3m_pct")), 2) if second_sector and _safe_float(second_sector.get("return_3m_pct")) is not None else None,
                },
                "macro_driver": {
                    "theme": "oil_price" if requested_sector == "Energy" else "sector_rotation",
                    "text": oil_driver,
                },
                "risks": [
                    f"{requested_sector} leadership can reverse quickly if sector rotation fades.",
                    "Higher momentum names can stay volatile in weak macro regimes.",
                ],
                "overview": overview,
                "rationale": rationale,
                "summary_points": rationale,
                "actionable_view": actionable_view,
                "implementation": {
                    "allocation_suggestion": allocation_text,
                    "entry_timing": entry_timing,
                    "exit_conditions": exit_conditions,
                },
                "cause_effect_chain": [
                    _pick_lang(lang, f"ETF ของกลุ่ม {requested_sector} แข็งแรง → เงินไหลเข้ากลุ่ม → หุ้นผู้นำในกลุ่มเด่นขึ้น", f"Stronger {requested_sector} ETF momentum -> capital rotates into the sector -> leading names outperform."),
                    _pick_lang(lang, "relative strength ระดับหุ้น → การกระจุกตัวของผู้นำ → รายชื่อ top picks ชัดขึ้น", "Stock-level relative strength -> leadership concentration -> clearer top-pick hierarchy."),
                ],
                "time_horizon": _time_horizon_payload(
                    short_term=_pick_lang(lang, f"ระยะสั้นผู้นำในกลุ่ม {requested_sector} ได้แรงหนุนจาก momentum ของกลุ่ม", f"Short term, leaders in {requested_sector} are benefiting from sector momentum."),
                    medium_term=_pick_lang(lang, "ระยะกลางต้องดูว่ากำไรและ sector rotation ยังสนับสนุนต่อหรือไม่", "Medium term, persistence depends on earnings and whether sector rotation continues."),
                ),
                "sources": ["Market data", "Sector ETF model", "Technical analysis"],
                "source_tags": source_tags,
            },
            "followups": (
                [
                    f"อะไรคือความเสี่ยงที่อาจทำให้กลุ่ม {requested_sector} อ่อนลง?",
                    f"ตอนนี้กลุ่ม {requested_sector} ยังน่าสนใจอยู่ไหม?",
                    f"เปรียบเทียบ {requested_sector} กับกลุ่มที่แรงรองลงมา",
                ] if lang == "th" else [
                    f"What risks could weaken {requested_sector}?",
                    f"Is {requested_sector} still attractive overall?",
                    f"Compare {requested_sector} vs the next strongest sector",
                ]
            ),
            "status": {
                "online": True,
                "message": "พร้อมใช้งาน" if lang == "th" else "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
        }

    def analyze_comparison(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        symbols = [str(symbol).upper() for symbol in (context.get("chat_state", {}) or {}).get("last_symbols", []) if symbol]
        if len(symbols) < 2:
            text_symbols = [token for token in str(question or "").upper().replace("VS", " ").replace("VERSUS", " ").split() if 1 < len(token) <= 5 and token.isalpha()]
            symbols = text_symbols[:2]
        if len(symbols) < 2:
            return {
                "intent": "stock_comparison",
                "analysis_type": "stock_comparison",
                "analysis_engine": "modular_stock_comparison_engine",
                "answer": "Live data is temporarily unavailable. Unable to verify market data.",
                "confidence": 0,
                "sources": ["Live data unavailable"],
                "data_validation": {"price_data": False, "news_data": False, "technical_data": False},
                "answer_schema": {
                    "intent": "stock_comparison",
                    "direct_answer": "Please provide two symbols for comparison.",
                    "source_tags": ["Live data unavailable"],
                },
                "followups": ["Compare NVDA vs AMD", "Compare AAPL vs MSFT"],
                "status": {"online": True, "message": "Live data unavailable", "live_data_ready": False, "market_context_loaded": False},
            }

        left_bundle = self.market_data.get_stock_bundle(symbols[0])
        right_bundle = self.market_data.get_stock_bundle(symbols[1])
        left_history = close_series((left_bundle.get("history_3m") or {}).get("history", []))
        right_history = close_series((right_bundle.get("history_3m") or {}).get("history", []))
        left_price = _safe_float((left_bundle.get("history_1m") or {}).get("price")) or (left_history[-1] if left_history else None)
        right_price = _safe_float((right_bundle.get("history_1m") or {}).get("price")) or (right_history[-1] if right_history else None)
        left_ret = compute_return_pct(left_history[0], left_history[-1]) if len(left_history) >= 2 else None
        right_ret = compute_return_pct(right_history[0], right_history[-1]) if len(right_history) >= 2 else None
        left_details = extract_fundamentals(left_bundle.get("details") or {})
        right_details = extract_fundamentals(right_bundle.get("details") or {})
        source_tags = _source_tags("Finnhub", "Internal TA Engine", "Market Snapshot Cache")
        better = symbols[0] if (left_ret or 0) >= (right_ret or 0) else symbols[1]
        answer = (
            "Market Context\nComparison uses current market data, recent price trends, and available fundamentals.\n\n"
            "Data Used\n- Price data\n- 3M returns\n- Fundamental snapshots\n\n"
            "Analysis\n"
            f"- {symbols[0]}: price " + (f"${left_price:.2f}" if left_price is not None else "data unavailable")
            + (f", 3M return {left_ret:+.2f}%" if left_ret is not None else "") + "\n"
            f"- {symbols[1]}: price " + (f"${right_price:.2f}" if right_price is not None else "data unavailable")
            + (f", 3M return {right_ret:+.2f}%" if right_ret is not None else "") + "\n\n"
            f"Conclusion\n{better} currently shows the stronger setup on the available comparison signals."
        )
        return {
            "intent": "stock_comparison",
            "analysis_type": "stock_comparison",
            "analysis_engine": "modular_stock_comparison_engine",
            "answer": answer,
            "confidence": 70,
            "sources": ["Market data", "Technical analysis", "Fundamental data"],
            "data_validation": {
                "price_data": left_price is not None and right_price is not None,
                "news_data": False,
                "technical_data": bool(left_history and right_history),
            },
            "answer_schema": {
                "intent": "stock_comparison",
                "direct_answer": f"{better} currently shows the stronger setup on the available comparison signals.",
                "comparison": {
                    "left_symbol": symbols[0],
                    "right_symbol": symbols[1],
                    "left_price": round(left_price, 2) if left_price is not None else None,
                    "right_price": round(right_price, 2) if right_price is not None else None,
                    "left_return_3m": round(left_ret, 2) if left_ret is not None else None,
                    "right_return_3m": round(right_ret, 2) if right_ret is not None else None,
                    "left_pe": left_details.get("pe_ratio"),
                    "right_pe": right_details.get("pe_ratio"),
                },
                "summary_points": [
                    f"{symbols[0]} 3M return: {left_ret:+.2f}%" if left_ret is not None else f"{symbols[0]} 3M return: Data unavailable",
                    f"{symbols[1]} 3M return: {right_ret:+.2f}%" if right_ret is not None else f"{symbols[1]} 3M return: Data unavailable",
                    f"{better} leads on current relative momentum.",
                ],
                "risks": [
                    "Relative leadership can reverse quickly after earnings or macro shocks.",
                    "Valuation and sentiment differences still matter beyond price momentum.",
                ],
                "actionable_view": f"Prefer {better} on current comparative signals",
                "source_tags": source_tags,
                "sources": ["Market data", "Technical analysis", "Fundamental data"],
            },
            "followups": [
                f"What are the downside risks for {symbols[0]}?",
                f"What are the downside risks for {symbols[1]}?",
                f"Compare valuation and risk for {symbols[0]} vs {symbols[1]}",
            ],
            "status": {
                "online": True,
                "message": "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
        }

    def analyze_risk(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        selected_stock = str(context.get("selected_stock") or "").upper().strip()
        last_sector = str((context.get("chat_state") or {}).get("last_sector") or "").strip()
        q = (question or "").lower()

        if selected_stock:
            stock_view = self.analyze_stock(selected_stock, context)
            schema = stock_view.get("answer_schema") or {}
            risks = ((schema.get("risk_factors") or {}).get("points")) or [
                "Relevant data is not available.",
            ]
            return {
                **stock_view,
                "intent": "risk_explanation",
                "analysis_type": "stock_risk_analysis",
                "analysis_engine": "modular_stock_risk_engine",
                "answer": (
                    f"Market Context\nRisk review for {selected_stock} uses current market and stock-level signals.\n\n"
                    "Data Used\n- Price trend\n- Technical indicators\n- News sentiment\n\n"
                    "Analysis\n"
                    + "\n".join([f"- {point}" for point in risks[:3]])
                    + f"\n\nConclusion\nKey risks for {selected_stock} are concentrated in momentum, sentiment, and market-regime sensitivity."
                ),
                "answer_schema": {
                    "intent": "risk_explanation",
                    "direct_answer": f"Key risks for {selected_stock} are concentrated in momentum, sentiment, and market-regime sensitivity.",
                    "summary_points": risks[:3],
                    "risks": risks[:4],
                    "source_tags": schema.get("source_tags") or _source_tags("Finnhub", "Internal TA Engine", "NewsAPI", "Market Snapshot Cache"),
                    "sources": schema.get("sources") or ["Market data", "Technical analysis", "News sentiment"],
                    "actionable_view": f"Monitor downside risk in {selected_stock}",
                },
            }

        sector_name = last_sector or ("sector" if "sector" in q else "")
        if sector_name:
            sector_view = self.analyze_sector(question, context)
            schema = sector_view.get("answer_schema") or {}
            risks = ((schema.get("risk_factors") or {}).get("points")) or [
                "Sector rotation can reverse quickly during macro shocks.",
            ]
            return {
                **sector_view,
                "intent": "risk_explanation",
                "analysis_type": "sector_risk_analysis",
                "analysis_engine": "modular_sector_risk_engine",
                "answer": (
                    "Market Context\nSector risk analysis uses current market regime and sector momentum data.\n\n"
                    "Data Used\n- Sector ETF momentum\n- Market regime\n\n"
                    "Analysis\n"
                    + "\n".join([f"- {point}" for point in risks[:3]])
                    + "\n\nConclusion\nSector downside risk remains tied to macro shocks and fast rotation."
                ),
                "answer_schema": {
                    "intent": "risk_explanation",
                    "direct_answer": "Sector downside risk remains tied to macro shocks and fast rotation.",
                    "summary_points": risks[:3],
                    "risks": risks[:4],
                    "source_tags": schema.get("source_tags") or _source_tags("Finnhub", "Sector ETF Model", "Market Snapshot Cache"),
                    "sources": schema.get("sources") or ["Market data", "Sector ETF model"],
                    "actionable_view": "Monitor sector rotation risk",
                },
            }

        market = self.market_data.get_market_context(context)
        macro = self.macro_data.build_macro_snapshot(market)
        source_tags = _source_tags("Fear & Greed", "Sector ETF Model", "Market Snapshot Cache")
        risks = [
            f"Fear & Greed remains at {macro.get('fear_greed_index')}, which signals fragile risk appetite." if macro.get("fear_greed_index") is not None else "Market sentiment data is temporarily limited.",
            "Leadership sectors can reverse quickly when volatility rises.",
            "Macro releases and rates can shift market positioning abruptly.",
        ]
        return {
            "intent": "risk_explanation",
            "analysis_type": "market_risk_analysis",
            "analysis_engine": "modular_market_risk_engine",
            "answer": (
                "Market Context\nCurrent risk analysis is based on market sentiment and sector leadership.\n\n"
                "Data Used\n- Fear & Greed\n- Sector momentum\n\n"
                "Analysis\n"
                + "\n".join([f"- {point}" for point in risks])
                + "\n\nConclusion\nCurrent downside risk remains elevated enough to justify selective exposure."
            ),
            "confidence": 70,
            "sources": ["Market sentiment model", "Sector ETF model"],
            "data_validation": {"price_data": True, "news_data": False, "technical_data": True},
            "answer_schema": {
                "intent": "risk_explanation",
                "direct_answer": "Current downside risk remains elevated enough to justify selective exposure.",
                "summary_points": risks,
                "risks": risks,
                "actionable_view": "Selective exposure remains appropriate",
                "source_tags": source_tags,
                "sources": ["Market sentiment model", "Sector ETF model"],
            },
            "followups": [
                "Which sectors look most defensive now?",
                "Show top momentum stocks in the leading sector",
                "What is the main market risk right now?",
            ],
            "status": {
                "online": True,
                "message": "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
        }
