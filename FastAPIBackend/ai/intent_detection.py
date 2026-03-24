from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional


SECTOR_ALIASES: Dict[str, str] = {
    "technology": "XLK",
    "tech": "XLK",
    "เทคโนโลยี": "XLK",
    "เทค": "XLK",
    "xlk": "XLK",
    "energy": "XLE",
    "พลังงาน": "XLE",
    "xle": "XLE",
    "financials": "XLF",
    "financial": "XLF",
    "finance": "XLF",
    "การเงิน": "XLF",
    "ธนาคาร": "XLF",
    "xlf": "XLF",
    "healthcare": "XLV",
    "health care": "XLV",
    "เฮลธ์แคร์": "XLV",
    "สุขภาพ": "XLV",
    "การแพทย์": "XLV",
    "xlv": "XLV",
    "industrials": "XLI",
    "industrial": "XLI",
    "อุตสาหกรรม": "XLI",
    "xli": "XLI",
    "consumer staples": "XLP",
    "staples": "XLP",
    "สินค้าอุปโภคบริโภคจำเป็น": "XLP",
    "ของใช้จำเป็น": "XLP",
    "xlp": "XLP",
    "consumer discretionary": "XLY",
    "discretionary": "XLY",
    "สินค้าไม่จำเป็น": "XLY",
    "บริโภคไม่จำเป็น": "XLY",
    "xly": "XLY",
}

TICKER_STOPWORDS = {
    "HOW", "DO", "DOES", "DID", "IS", "ARE", "WAS", "WERE", "CAN", "COULD", "WOULD",
    "SHOULD", "WILL", "THE", "THIS", "THAT", "THESE", "THOSE", "WHAT", "WHEN", "WHERE",
    "WHY", "WHO", "WHICH", "COMPARE", "VERSUS", "VS", "WITH", "FROM", "INTO", "IN", "ON",
    "AT", "BY", "TO", "FOR", "AND", "OR", "NOT", "RISK", "RISKS", "MARKET", "MACRO",
    "PORTFOLIO", "SECTOR", "SECTORS", "STOCK", "STOCKS", "TODAY", "OVERALL", "STRONG",
    "WEAK", "BETTER", "GOOD", "INVESTMENT", "ANALYSIS", "SHOW", "TOP", "MOMENTUM",
    "TECHNOLOGY", "ENERGY", "FINANCIALS", "HEALTHCARE", "INDUSTRIALS", "STAPLES",
    "DISCRETIONARY",
}

COMPARISON_TERMS = ["compare", "vs", "versus", "better than", "relative to", "เทียบ", "เปรียบเทียบ"]


@dataclass
class IntentResult:
    intent: str
    intent_category: str
    entities: List[str] = field(default_factory=list)
    entity_kind: str = ""
    clarification: str = ""
    requires_live_data: bool = True
    query_scope: str = ""
    top_n: Optional[int] = None


NUMBER_WORDS: Dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


class IntentDetectionEngine:
    def _is_thai(self, question: str) -> bool:
        return any("\u0E00" <= char <= "\u0E7F" for char in str(question or ""))

    def _message(self, *, thai: bool, th: str, en: str) -> str:
        return th if thai else en

    def _extract_top_n(self, question: str) -> Optional[int]:
        q = str(question or "").lower()
        match = re.search(r"\btop\s+(\d{1,2})\b", q)
        if match:
            try:
                return max(1, min(10, int(match.group(1))))
            except Exception:
                return None
        for word, value in NUMBER_WORDS.items():
            if re.search(rf"\btop\s+{word}\b", q):
                return value
        if re.search(r"\btop\s+two\s+sectors\b", q) or re.search(r"\bcompare\s+the\s+top\s+two\b", q):
            return 2
        return None

    def _extract_sector_entities(self, question: str) -> List[str]:
        q = f" {str(question or '').lower()} "
        found: List[str] = []
        seen = set()
        for alias, etf in SECTOR_ALIASES.items():
            if f" {alias} " in q and etf not in seen:
                seen.add(etf)
                found.append(etf)
        return found

    def _extract_stock_entities(self, question: str) -> List[str]:
        tokens = re.findall(r"\b[A-Z]{2,5}(?:[.-][A-Z])?\b", str(question or "").upper())
        found: List[str] = []
        seen = set()
        for token in tokens:
            if token in TICKER_STOPWORDS:
                continue
            if token in SECTOR_ALIASES.values():
                continue
            if token not in seen:
                seen.add(token)
                found.append(token)
        return found

    def _is_comparison(self, q: str) -> bool:
        return any(term in q for term in COMPARISON_TERMS)

    def detect(self, question: str) -> IntentResult:
        q = (question or "").strip().lower()
        is_thai = self._is_thai(question)
        if not q:
            return IntentResult(
                intent="invalid_query",
                intent_category="Invalid Query",
                clarification=self._message(
                    thai=is_thai,
                    th="กรุณาถามเกี่ยวกับหุ้น กลุ่มอุตสาหกรรม พอร์ต หรือประเด็นมหภาคให้ชัดขึ้นอีกเล็กน้อย",
                    en="Please ask about a stock, sector, portfolio, or macro topic.",
                ),
                requires_live_data=False,
            )

        sector_entities = self._extract_sector_entities(question)
        stock_entities = self._extract_stock_entities(question)
        top_n = self._extract_top_n(question)

        stock_recommendation_terms = [
            "low risk stock", "low-risk stock", "defensive stock", "defensive stocks",
            "stable stock", "stable stocks", "safe stock", "safe stocks", "dividend stock",
            "quality stock", "blue chip", "blue-chip", "recommend a low risk stock",
            "recommend low risk", "lower risk stock", "defensive names",
            "หุ้นเสี่ยงต่ำ", "หุ้นความเสี่ยงต่ำ", "หุ้นปลอดภัย", "หุ้น defensive",
            "หุ้นปันผล", "หุ้นใหญ่เสี่ยงต่ำ", "หุ้นอะไรเสี่ยงต่ำ",
        ]
        open_recommendation_terms = [
            "recommend a stock", "recommend stock", "recommend some stocks", "recommend stocks",
            "stock ideas", "give me stock ideas", "what stock should i buy", "what stocks should i buy",
            "best stocks now", "best stock now", "top stock ideas", "suggest a stock", "suggest stocks",
            "แนะนำหุ้น", "ช่วยแนะนำหุ้น", "มีหุ้นอะไรแนะนำ", "หุ้นน่าสนใจ", "หุ้นไหนดี", "หุ้นตัวไหนดี",
        ]
        market_scanner_terms = [
            "what stocks are trending today", "show trending stocks", "show top movers",
            "most active stocks", "high momentum stocks", "market scanner", "scan the market",
            "top gainers", "top volume stocks", "stocks moving now", "discover stocks",
            "หุ้นอะไรเด่นวันนี้", "สแกนตลาด", "หุ้นที่น่าสนใจวันนี้", "หุ้นที่กำลังเป็นกระแส",
            "หุ้นตัวไหนกำลังมาแรง", "หุ้นตัวไหนกำลังแรง", "หุ้นที่กำลังมาแรง", "หุ้นตัวไหนกำลังมา",
        ]

        if any(term in q for term in stock_recommendation_terms):
            return IntentResult(
                intent="stock_recommendation",
                intent_category="Stock Recommendation",
                requires_live_data=False,
            )
        if any(term in q for term in open_recommendation_terms):
            return IntentResult(
                intent="open_recommendation",
                intent_category="Open Recommendation",
                requires_live_data=False,
            )
        if any(term in q for term in market_scanner_terms):
            return IntentResult(
                intent="market_scanner",
                intent_category="Market Scanner",
                requires_live_data=True,
            )

        if self._is_comparison(q):
            if (
                "sector" in q
                and "top" in q
                and any(term in q for term in ["compare", "vs", "versus"])
                and top_n
            ):
                return IntentResult(
                    intent="sector_comparison_top_n",
                    intent_category="Sector Comparison Top N",
                    requires_live_data=True,
                    query_scope="sector_comparison_top_n",
                    top_n=top_n,
                )
            if len(sector_entities) >= 2:
                if len(set(sector_entities[:2])) < 2:
                    return IntentResult(
                        intent="invalid_query",
                        intent_category="Invalid Query",
                        entities=sector_entities[:2],
                        entity_kind="sector",
                        clarification=self._message(
                            thai=is_thai,
                            th="การเปรียบเทียบนี้ใช้ไม่ได้ กรุณาเปรียบเทียบคนละกลุ่มหรือคนละหุ้น",
                            en="This comparison is not valid. Please compare two different sectors or stocks.",
                        ),
                        requires_live_data=False,
                    )
                return IntentResult(
                    intent="sector_comparison",
                    intent_category="Sector Comparison",
                    entities=sector_entities[:2],
                    entity_kind="sector",
                )
            if len(stock_entities) >= 2:
                if len(set(stock_entities[:2])) < 2:
                    return IntentResult(
                        intent="invalid_query",
                        intent_category="Invalid Query",
                        entities=stock_entities[:2],
                        entity_kind="stock",
                        clarification=self._message(
                            thai=is_thai,
                            th="การเปรียบเทียบนี้ใช้ไม่ได้ กรุณาเปรียบเทียบคนละกลุ่มหรือคนละหุ้น",
                            en="This comparison is not valid. Please compare two different sectors or stocks.",
                        ),
                        requires_live_data=False,
                    )
                return IntentResult(
                    intent="stock_comparison",
                    intent_category="Stock Comparison",
                    entities=stock_entities[:2],
                    entity_kind="stock",
                )
            if len(sector_entities) == 1:
                return IntentResult(
                    intent="invalid_query",
                    intent_category="Invalid Query",
                    entities=sector_entities,
                    entity_kind="sector",
                    clarification=self._message(
                        thai=is_thai,
                        th=f"คุณต้องการเปรียบเทียบ {sector_entities[0]} กับอีกกลุ่มหนึ่งใช่ไหม กรุณาระบุอีกกลุ่มเพิ่มเติม",
                        en=f"Do you mean {sector_entities[0]} versus another sector? Please name the second sector.",
                    ),
                    requires_live_data=False,
                )
            if len(stock_entities) == 1:
                return IntentResult(
                    intent="invalid_query",
                    intent_category="Invalid Query",
                    entities=stock_entities,
                    entity_kind="stock",
                    clarification=self._message(
                        thai=is_thai,
                        th=f"คุณต้องการเปรียบเทียบ {stock_entities[0]} กับหุ้นอีกตัวใช่ไหม กรุณาระบุอีกสัญลักษณ์เพิ่มเติม",
                        en=f"Do you want to compare {stock_entities[0]} with another stock? Please name the second symbol.",
                    ),
                    requires_live_data=False,
                )
            return IntentResult(
                intent="invalid_query",
                intent_category="Invalid Query",
                clarification=self._message(
                    thai=is_thai,
                    th="ผมต้องการหุ้นหรือกลุ่มอุตสาหกรรม 2 รายการที่ต่างกันเพื่อใช้เปรียบเทียบ",
                    en="I need two different sectors or stocks to compare.",
                ),
                requires_live_data=False,
            )

        if any(term in q for term in ["portfolio", "allocation", "holdings", "พอร์ต"]):
            return IntentResult(intent="portfolio_analysis", intent_category="Portfolio Analysis")
        global_sector_query_terms = [
            "sector momentum", "sector ranking", "sector rankings", "show sector momentum ranking",
            "show all sector rankings", "which sectors are strongest", "which sectors have strong momentum",
            "which sectors have the strongest momentum", "leading sectors", "top sectors", "sector leaderboard",
            "กลุ่มไหนแข็งแรง", "จัดอันดับ sector", "จัดอันดับกลุ่ม", "กลุ่มไหน momentum ดี",
            "sector ไหนแรง", "sector ไหนเด่น", "กลุ่มไหนแรง", "กลุ่มไหนเด่น", "จัดอันดับโมเมนตัมกลุ่ม",
        ]
        global_market_overview_terms = [
            "market overview", "market trends", "market trend", "show market overview",
            "global market", "overall market", "broad market", "market dashboard",
            "ภาพรวมตลาด", "แนวโน้มตลาด", "ตลาดเป็นยังไง", "ตลาดเป็นยังไงวันนี้", "ตลาดวันนี้เป็นยังไง",
        ]
        global_sector_compare_terms = [
            "compare the top two sectors",
            "compare top two sectors",
            "compare the top 2 sectors",
            "compare top 2 sectors",
            "compare the top sectors now",
            "top two sectors now",
        ]
        if any(term in q for term in global_sector_compare_terms):
            return IntentResult(
                intent="sector_comparison_top_n",
                intent_category="Sector Comparison Top N",
                query_scope="sector_comparison_top_n",
                top_n=top_n or 2,
                requires_live_data=True,
            )
        if any(term in q for term in global_sector_query_terms):
            return IntentResult(
                intent="global_market_query",
                intent_category="Global Market Query",
                query_scope="sector_ranking",
                requires_live_data=True,
            )
        if any(term in q for term in global_market_overview_terms):
            return IntentResult(
                intent="global_market_query",
                intent_category="Global Market Query",
                query_scope="market_overview",
                requires_live_data=True,
            )
        macro_terms = [
            "market", "macro", "fear", "greed", "vix", "rates", "rate hike", "fed", "fomc",
            "cpi", "inflation", "yield", "treasury", "recession", "gdp", "jobs report",
            "oil", "crude", "war", "iran", "middle east", "geopolitic", "geopolitical",
            "sanction", "tariff", "conflict", "missile", "strait of hormuz", "energy shock",
            "ตลาด", "ภาพรวม", "สงคราม", "อิหร่าน", "น้ำมัน", "ภูมิรัฐศาสตร์", "เงินเฟ้อ", "ดอกเบี้ย",
        ]
        if any(term in q for term in macro_terms):
            return IntentResult(intent="macro_analysis", intent_category="Macro Analysis")
        if sector_entities:
            return IntentResult(intent="sector_analysis", intent_category="Sector Analysis", entities=sector_entities, entity_kind="sector")
        if stock_entities:
            return IntentResult(intent="stock_analysis", intent_category="Stock Analysis", entities=stock_entities, entity_kind="stock")
        return IntentResult(
            intent="invalid_query",
            intent_category="Invalid Query",
            clarification=self._message(
                thai=is_thai,
                th="ผมยังจับหุ้นหรือกลุ่มอุตสาหกรรมที่ชัดเจนจากคำถามนี้ไม่ได้ ลองระบุเพิ่มอีกนิดได้ไหม",
                en="I could not identify a valid stock or sector in that question.",
            ),
            requires_live_data=False,
        )
