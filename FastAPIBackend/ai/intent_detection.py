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
    "DISCRETIONARY", "THEN", "ABOUT", "OIL", "WAR",
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
    confidence: float = 0.0


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
    MACRO_TERMS = [
        "market", "macro", "fear", "greed", "vix", "rates", "rate hike", "fed", "fomc",
        "cpi", "inflation", "yield", "treasury", "recession", "gdp", "jobs report",
        "oil", "crude", "war", "iran", "middle east", "geopolitic", "geopolitical",
        "sanction", "tariff", "conflict", "missile", "strait of hormuz", "energy shock",
        "ตลาด", "ภาพรวม", "สงคราม", "อิหร่าน", "น้ำมัน", "ภูมิรัฐศาสตร์", "เงินเฟ้อ", "ดอกเบี้ย",
    ]
    IMPACT_TERMS = [
        "impact", "effect", "affect", "what happens to", "what does this mean for",
        "ผลกระทบ", "กระทบ", "มีผลต่อ", "ส่งผลต่อ", "จะเกิดอะไรกับ",
    ]
    FOLLOW_UP_TERMS = [
        "then", "what about", "how about", "and what about", "next", "after that",
        "แล้ว", "ล่ะ", "ต่อ", "แล้วถ้า", "แล้วผล", "แล้วกระทบ", "ทีนี้",
    ]
    WINNER_TERMS = [
        "benefit", "benefits", "beneficiary", "beneficiaries", "winner", "winners",
        "who benefits", "who wins", "which sector benefits", "which sectors benefit",
        "ได้ประโยชน์", "กลุ่มไหนได้ประโยชน์", "ใครได้ประโยชน์", "ตัวไหนได้ประโยชน์", "ผู้ชนะ",
    ]

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
        q = str(question or "").lower()
        found: List[str] = []
        seen = set()
        for alias, etf in SECTOR_ALIASES.items():
            alias_q = alias.lower()
            matched = False
            if any("\u0E00" <= char <= "\u0E7F" for char in alias_q):
                matched = alias_q in q
            else:
                matched = re.search(rf"\b{re.escape(alias_q)}\b", q) is not None
            if matched and etf not in seen:
                seen.add(etf)
                found.append(etf)
        return found

    def _is_sector_stock_picker(self, q: str, sector_entities: List[str]) -> bool:
        if not sector_entities:
            return False
        picker_terms = [
            "energy stocks", "tech stocks", "technology stocks", "healthcare stocks", "financial stocks",
            "utility stocks", "consumer staples stocks", "best energy stocks", "best tech stocks",
            "pick energy stocks", "pick tech stocks", "sector stock picks",
            "หุ้นพลังงาน", "หุ้นกลุ่มพลังงาน", "หุ้นเทค", "หุ้นเทคโนโลยี", "หุ้นสุขภาพ", "หุ้นการเงิน",
            "หุ้นธนาคาร", "หุ้นสาธารณูปโภค", "หุ้น defensive", "หุ้นกลุ่ม", "แนะนำหุ้นพลังงาน",
            "แนะนำหุ้นเทค", "แนะนำหุ้นเทคโนโลยี", "แนะนำหุ้นสุขภาพ", "แนะนำหุ้นการเงิน",
            "แนะนำหุ้นธนาคาร", "แนะนำหุ้นกลุ่ม",
        ]
        return any(term in q for term in picker_terms)

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

    def _is_follow_up(self, query: str) -> bool:
        q = (query or "").strip().lower()
        return any(term in q for term in self.FOLLOW_UP_TERMS)

    def _has_winner_intent(self, query: str) -> bool:
        q = (query or "").strip().lower()
        return any(term in q for term in self.WINNER_TERMS)

    def should_override_context(self, query: str) -> bool:
        q = (query or "").strip().lower()
        explicit_new_target_terms = [
            "which sector", "which sectors", "who benefits", "who wins", "winners",
            "beneficiaries", "benefit", "what benefits", "oil winners",
            "กลุ่มไหน", "sector ไหน", "ใครได้ประโยชน์", "ได้ประโยชน์", "ตัวไหนได้ประโยชน์",
        ]
        if any(term in q for term in explicit_new_target_terms):
            return True
        return bool(self._extract_sector_entities(query) or self._extract_stock_entities(query))

    def _extract_event_from_text(self, text: str) -> Optional[str]:
        q = (text or "").strip().lower()
        if any(term in q for term in ["war", "iran", "middle east", "conflict", "sanction", "missile", "strait of hormuz", "สงคราม", "อิหร่าน", "ภูมิรัฐศาสตร์"]):
            return "war"
        if any(term in q for term in ["oil", "crude", "น้ำมัน"]):
            return "oil"
        if any(term in q for term in ["inflation", "cpi", "เงินเฟ้อ"]):
            return "inflation"
        if any(term in q for term in ["yield", "treasury", "rates", "fed", "ดอกเบี้ย"]):
            return "rates"
        return None

    def _extract_target_from_text(self, text: str, sector_entities: Optional[List[str]] = None, stock_entities: Optional[List[str]] = None) -> Optional[str]:
        q = (text or "").strip().lower()
        if sector_entities:
            etf = sector_entities[0]
            reverse_map = {
                "XLK": "tech stocks",
                "XLE": "energy stocks",
                "XLF": "financial stocks",
                "XLV": "healthcare stocks",
                "XLI": "industrial stocks",
                "XLP": "consumer staples stocks",
                "XLY": "consumer discretionary stocks",
            }
            return reverse_map.get(etf, etf)
        if stock_entities:
            return stock_entities[0]
        if any(term in q for term in ["tech", "technology", "หุ้นเทค", "หุ้นเทคโนโลยี"]):
            return "tech stocks"
        if any(term in q for term in ["energy", "พลังงาน"]):
            return "energy stocks"
        return None

    def resolve_full_context(self, query: str, history: Optional[List[str]] = None) -> Dict[str, Optional[str]]:
        history = [str(item or "").strip() for item in (history or []) if str(item or "").strip()]
        latest_history = history[-2:] if history else []
        query_sector_entities = self._extract_sector_entities(query)
        query_stock_entities = self._extract_stock_entities(query)
        override_context = self.should_override_context(query)
        winner_intent = self._has_winner_intent(query)

        event = self._extract_event_from_text(query)
        target = self._extract_target_from_text(query, query_sector_entities, query_stock_entities)

        if winner_intent and not target:
            q = (query or "").strip().lower()
            if any(term in q for term in ["oil", "energy", "น้ำมัน", "พลังงาน"]):
                target = "energy beneficiaries"
            elif any(term in q for term in ["tech", "technology", "หุ้นเทค", "หุ้นเทคโนโลยี"]):
                target = "technology winners"

        if latest_history:
            history_blob = " ".join(latest_history)
            event = event or self._extract_event_from_text(history_blob)
            if not override_context:
                target = target or self._extract_target_from_text(history_blob, self._extract_sector_entities(history_blob), self._extract_stock_entities(history_blob))

        context_type = None
        if winner_intent and event and target:
            context_type = "sector_winners_analysis"
        elif event and target:
            context_type = "macro_to_sector_impact"
        elif event:
            context_type = "macro_impact"
        elif target:
            context_type = "target_follow_up"

        return {
            "event": event,
            "target": target,
            "type": context_type,
            "is_follow_up": self._is_follow_up(query),
            "override_context": override_context,
        }

    def classify_intent(self, query: str, history: Optional[List[str]] = None) -> Dict[str, object]:
        q = (query or "").strip().lower()
        sector_entities = self._extract_sector_entities(query)
        stock_entities = self._extract_stock_entities(query)
        has_impact = any(term in q for term in self.IMPACT_TERMS)
        has_macro = any(term in q for term in self.MACRO_TERMS)
        has_winner_intent = self._has_winner_intent(query)
        resolved = self.resolve_full_context(query, history)
        is_follow_up = bool(resolved.get("is_follow_up"))
        if resolved.get("type") == "sector_winners_analysis":
            return {
                "type": "sector_winners_analysis",
                "entity": resolved.get("target"),
                "entity_kind": "sector_winners",
                "confidence": 0.96,
            }
        if is_follow_up and resolved.get("event") and resolved.get("target"):
            return {
                "type": "macro_analysis",
                "entity": resolved.get("target"),
                "entity_kind": "macro_to_sector_impact",
                "confidence": 0.97,
            }

        if stock_entities:
            return {
                "type": "stock_analysis",
                "entity": stock_entities[0],
                "entity_kind": "stock",
                "confidence": 0.95 if not has_impact else 0.98,
            }
        if sector_entities:
            if has_winner_intent:
                return {
                    "type": "sector_winners_analysis",
                    "entity": sector_entities[0],
                    "entity_kind": "sector_winners",
                    "confidence": 0.95,
                }
            if self._is_sector_stock_picker(q, sector_entities):
                return {
                    "type": "sector_stock_picker",
                    "entity": sector_entities[0],
                    "entity_kind": "sector",
                    "confidence": 0.94,
                }
            return {
                "type": "sector_analysis" if not has_impact else "macro_analysis",
                "entity": sector_entities[0],
                "entity_kind": "sector",
                "confidence": 0.86 if not has_impact else 0.9,
            }
        if has_macro or has_impact:
            return {
                "type": "macro_analysis",
                "entity": None,
                "entity_kind": "macro",
                "confidence": 0.78 if has_macro else 0.62,
            }
        return {
            "type": "knowledge_guidance",
            "entity": None,
            "entity_kind": "",
            "confidence": 0.2,
        }

    def detect(self, question: str, history: Optional[List[str]] = None) -> IntentResult:
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
                confidence=0.0,
            )

        sector_entities = self._extract_sector_entities(question)
        stock_entities = self._extract_stock_entities(question)
        top_n = self._extract_top_n(question)
        resolved = self.resolve_full_context(question, history)
        if resolved.get("type") == "sector_winners_analysis":
            return IntentResult(
                intent="sector_stock_picker",
                intent_category="Sector Winners Analysis",
                entities=[str(resolved.get("target"))],
                entity_kind="sector_winners",
                confidence=0.96,
            )
        if resolved.get("is_follow_up") and resolved.get("event") and resolved.get("target"):
            return IntentResult(
                intent="macro_analysis",
                intent_category="Macro Analysis",
                entities=[str(resolved.get("target"))],
                entity_kind="macro_to_sector_impact",
                confidence=0.97,
            )

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

        if self._is_sector_stock_picker(q, sector_entities):
            return IntentResult(
                intent="sector_stock_picker",
                intent_category="Sector Stock Picker",
                entities=sector_entities[:1],
                entity_kind="sector",
                requires_live_data=True,
                confidence=0.94,
            )

        if any(term in q for term in stock_recommendation_terms):
            return IntentResult(
                intent="stock_recommendation",
                intent_category="Stock Recommendation",
                requires_live_data=False,
                confidence=0.82,
            )
        if any(term in q for term in open_recommendation_terms):
            if sector_entities:
                return IntentResult(
                    intent="sector_stock_picker",
                    intent_category="Sector Stock Picker",
                    entities=sector_entities[:1],
                    entity_kind="sector",
                    requires_live_data=True,
                    confidence=0.9,
                )
            return IntentResult(
                intent="open_recommendation",
                intent_category="Open Recommendation",
                requires_live_data=False,
                confidence=0.72,
            )
        if any(term in q for term in market_scanner_terms):
            return IntentResult(
                intent="market_scanner",
                intent_category="Market Scanner",
                requires_live_data=True,
                confidence=0.78,
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
                    confidence=0.93,
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
                        confidence=0.15,
                    )
                return IntentResult(
                    intent="sector_comparison",
                    intent_category="Sector Comparison",
                    entities=sector_entities[:2],
                    entity_kind="sector",
                    confidence=0.96,
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
                        confidence=0.15,
                    )
                return IntentResult(
                    intent="stock_comparison",
                    intent_category="Stock Comparison",
                    entities=stock_entities[:2],
                    entity_kind="stock",
                    confidence=0.96,
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
                    confidence=0.2,
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
                    confidence=0.2,
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
                confidence=0.1,
            )

        if any(term in q for term in ["portfolio", "allocation", "holdings", "พอร์ต"]):
            return IntentResult(intent="portfolio_analysis", intent_category="Portfolio Analysis", confidence=0.86)
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
                confidence=0.92,
            )
        if any(term in q for term in global_sector_query_terms):
            return IntentResult(
                intent="global_market_query",
                intent_category="Global Market Query",
                query_scope="sector_ranking",
                requires_live_data=True,
                confidence=0.84,
            )
        if any(term in q for term in global_market_overview_terms):
            return IntentResult(
                intent="global_market_query",
                intent_category="Global Market Query",
                query_scope="market_overview",
                requires_live_data=True,
                confidence=0.82,
            )
        if any(term in q for term in self.MACRO_TERMS) or any(term in q for term in self.IMPACT_TERMS):
            return IntentResult(intent="macro_analysis", intent_category="Macro Analysis", confidence=0.8)
        if sector_entities:
            return IntentResult(intent="sector_analysis", intent_category="Sector Analysis", entities=sector_entities, entity_kind="sector", confidence=0.8)
        if stock_entities:
            return IntentResult(intent="stock_analysis", intent_category="Stock Analysis", entities=stock_entities, entity_kind="stock", confidence=0.92)
        return IntentResult(
            intent="invalid_query",
            intent_category="Invalid Query",
            clarification=self._message(
                thai=is_thai,
                th="ผมยังจับหุ้นหรือกลุ่มอุตสาหกรรมที่ชัดเจนจากคำถามนี้ไม่ได้ ลองระบุเพิ่มอีกนิดได้ไหม",
                en="I could not identify a valid stock or sector in that question.",
            ),
            requires_live_data=False,
            confidence=0.0,
        )
