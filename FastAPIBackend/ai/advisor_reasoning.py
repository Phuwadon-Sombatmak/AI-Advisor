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


class InvestmentReasoningEngine:
    def __init__(self, *, market_data, news_data, macro_data) -> None:
        self.market_data = market_data
        self.news_data = news_data
        self.macro_data = macro_data

    def analyze_macro(self, question: str, context: Any) -> Dict[str, Any]:
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
                "top_sector": None,
                "risk_outlook": None,
            }
        try:
            sector_rankings = (self.market_data.get_sector_rankings() or {}).get("rankings", [])
        except Exception:
            sector_rankings = []
        q = (question or "").strip()
        q_lower = q.lower()

        is_energy_shock = any(
            term in q_lower
            for term in [
                "iran", "war", "middle east", "oil", "crude", "geopolitic",
                "geopolitical", "sanction", "conflict", "strait of hormuz",
            ]
        )
        top_sector = sector_rankings[0].get("sector") if sector_rankings else ("Energy" if is_energy_shock else "Defensive sectors")
        top_three = sector_rankings[:3]
        fear_greed = _safe_float(macro.get("fear_greed_index"))
        market_sentiment = macro.get("market_sentiment") or ("Cautious" if is_energy_shock else "Mixed")

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
            answer = (
                "ภาพรวมตลาด\n"
                + (
                    f"- Fear & Greed Index: {round(fear_greed, 1)} ({market_sentiment})\n"
                    if fear_greed is not None else
                    f"- ภาวะตลาดปัจจุบัน: {market_sentiment}\n"
                )
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
            answer = (
                "Market Context\n"
                + (
                    f"- Fear & Greed Index: {round(fear_greed, 1)} ({market_sentiment})\n"
                    if fear_greed is not None else
                    f"- Market sentiment: {market_sentiment}\n"
                )
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

        return {
            "intent": "macro_analysis",
            "analysis_type": "macro_analysis",
            "analysis_engine": "macro_reasoning_engine",
            "answer": answer,
            "confidence": 74 if is_energy_shock else 70,
            "sources": ["Macro knowledge base", "Market sentiment model", "Sector ETF model"],
            "data_validation": {"price_data": bool(sector_rankings), "news_data": False, "technical_data": bool(sector_rankings)},
            "summary": {
                "market_sentiment": market_sentiment,
                "fear_greed_score": fear_greed,
                "trending_sector": top_sector,
                "risk_outlook": macro.get("risk_outlook"),
            },
            "answer_schema": {
                "intent": "macro_analysis",
                "answer_title": "การวิเคราะห์มหภาคและภูมิรัฐศาสตร์" if lang == "th" else "Macro and Geopolitical Analysis",
                "direct_answer": lead,
                "market_context": {
                    "market_regime": market_sentiment,
                    "fear_greed_index": fear_greed,
                    "points": [
                        f"Fear & Greed: {round(fear_greed, 1)} ({market_sentiment})" if fear_greed is not None else f"Market sentiment: {market_sentiment}",
                        f"Leading sector now: {top_sector}",
                    ] + ranking_lines,
                },
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
                    "text": conclusion,
                    "confidence": 74 if is_energy_shock else 70,
                    "forecast_horizon": {},
                },
                "sources": ["Macro knowledge base", "Market sentiment model", "Sector ETF model"],
                "source_tags": _source_tags("Macro Knowledge Base", "Fear & Greed", "Sector ETF Model", "Market Snapshot Cache"),
                "overview": overview_line,
                "rationale": key_drivers,
                "summary_points": key_drivers,
                "risks": ui_risks,
                "actionable_view": actionable_view,
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
            }

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
                + (
                    f"Fear & Greed Index อยู่ที่ {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')}).\n\n"
                    if macro.get("fear_greed_index") is not None else
                    "ยังไม่มีข้อมูล Fear & Greed ที่ยืนยันได้ในขณะนี้\n\n"
                )
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
                + (
                    f"Fear & Greed Index: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')}).\n\n"
                    if macro.get("fear_greed_index") is not None else
                    "Fear & Greed Index: Data unavailable for this signal.\n\n"
                )
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
                "fear_greed_score": macro.get("fear_greed_index"),
                "trending_sector": "Consumer Staples / Healthcare",
                "risk_outlook": "Lower risk equity ideas",
            },
            "answer_schema": {
                "intent": "stock_recommendation",
                "answer_title": _pick_lang(lang, "ไอเดียหุ้นความเสี่ยงต่ำ", "Low-Risk Stock Ideas"),
                "direct_answer": direct_answer,
                "market_context": {
                    "market_regime": macro.get("market_sentiment"),
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "points": [
                        (
                            f"Fear & Greed: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})"
                            if macro.get("fear_greed_index") is not None
                            else "Fear & Greed: Data unavailable for this signal."
                        ),
                        "Defensive sectors usually include Consumer Staples, Utilities, and Healthcare.",
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
                    "text": "KO, PG, and JNJ are practical lower-risk starting points because they sit in defensive sectors and tend to show steadier earnings and cash-flow behavior than typical growth names.",
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
                    "ให้น้ำหนักมากกว่าตลาดใน Consumer Staples / Healthcare, ถือเป็นกลาง Utilities, และให้น้ำหนักต่ำกว่า High-beta Growth",
                    "Overweight Consumer Staples / Healthcare, stay Neutral Utilities, and Underweight high-beta Growth.",
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
                "top_sector": None,
            }

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
                + (
                    f"Fear & Greed Index อยู่ที่ {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')}).\n"
                    if macro.get("fear_greed_index") is not None else
                    "ยังไม่มีข้อมูล Fear & Greed ที่ยืนยันได้ในขณะนี้\n"
                )
                + f"กลุ่มที่นำตลาดตอนนี้: {macro.get('top_sector') or 'ยังไม่มีข้อมูลยืนยัน'}\n\n"
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
                + (
                    f"Fear & Greed Index: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')}).\n"
                    if macro.get("fear_greed_index") is not None else
                    "Fear & Greed Index: Data unavailable for this signal.\n"
                )
                + f"Current leading sector: {macro.get('top_sector') or 'Data unavailable for this signal.'}\n\n"
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
                "fear_greed_score": macro.get("fear_greed_index"),
                "trending_sector": macro.get("top_sector"),
                "risk_outlook": "Balanced default stock ideas",
            },
            "answer_schema": {
                "intent": "open_recommendation",
                "answer_title": _pick_lang(lang, "ไอเดียหุ้นพื้นฐานดีสำหรับเริ่มต้น", "Default Stock Ideas"),
                "direct_answer": direct_answer,
                "market_context": {
                    "market_regime": macro.get("market_sentiment"),
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "points": [
                        (
                            f"Fear & Greed: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})"
                            if macro.get("fear_greed_index") is not None
                            else "Fear & Greed: Data unavailable for this signal."
                        ),
                        f"Leading sector now: {macro.get('top_sector') or 'Data unavailable for this signal.'}",
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
                    "text": "AAPL and MSFT are practical core ideas for quality and cash-flow durability, while NVDA is a stronger-growth but higher-risk addition.",
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
                    "ให้น้ำหนักมากกว่าตลาดในหุ้นคุณภาพขนาดใหญ่แบบคัดตัว โดยใช้ AAPL/MSFT เป็นแกน และเพิ่ม NVDA เฉพาะส่วนที่รับความผันผวนได้",
                    "Overweight selectively in quality large caps, using AAPL/MSFT as core exposure and adding NVDA only where higher volatility is acceptable.",
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
            f"{macro.get('market_sentiment') or 'Relevant data is not available'}"
            + (
                f" with a Fear & Greed index of {round(_safe_float(macro.get('fear_greed_index')), 1)}.\n\n"
                if macro.get("fear_greed_index") is not None else ".\n\n"
            )
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
                    "market_regime": macro.get("market_sentiment"),
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "points": [
                        f"Fear & Greed: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})"
                        if macro.get("fear_greed_index") is not None else "Fear & Greed: Relevant data is not available.",
                        f"Top sector: {macro.get('top_sector') or 'Relevant data is not available'}",
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
                    "Momentum can reverse quickly if the broader market weakens or rates move against high-multiple names.",
                    "Earnings and news flow can change the setup faster than technicals alone suggest.",
                ],
                "time_horizon": _time_horizon_payload(
                    short_term=f"Short term: momentum is {momentum_label.lower()} and the technical trend is {trend.lower()}.",
                    medium_term="Medium term: sustainability depends on earnings support, sentiment persistence, and the broader rate backdrop.",
                ),
                "actionable_view": (
                    "Overweight selectively if technical and sentiment confirmation improves; stay Neutral on mixed signals; move Underweight if momentum and macro conditions deteriorate."
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
            + (
                f"Fear & Greed Index: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})\n\n"
                if macro.get("fear_greed_index") is not None else
                "Fear & Greed Index: Data unavailable for this signal.\n\n"
            )
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
                "fear_greed_score": macro.get("fear_greed_index"),
                "trending_sector": top_sector,
                "risk_outlook": macro.get("risk_outlook"),
            },
            "answer_schema": {
                "intent": "sector_analysis",
                "overview": direct_answer,
                "rationale": [
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
                    "market_regime": macro.get("market_sentiment"),
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "points": [
                        f"Fear & Greed: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})"
                        if macro.get("fear_greed_index") is not None else "Fear & Greed: Data unavailable for this signal.",
                        f"Strongest sector now: {top_sector} ({top.get('etf')})",
                        f"Decision label: {decision_label}",
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
                    "text": final_decision,
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
                "actionable_view": f"Overweight {top_sector}, stay Neutral defensives, and Underweight weaker rate-sensitive or cyclical laggards until leadership changes.",
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
                "change_pct": round(change, 2),
                "month_return": round(ret_1m, 2) if ret_1m is not None else None,
                "reason": "High recent activity and notable price movement.",
            })
        items.sort(key=lambda row: (abs(row.get("change_pct") or 0.0), abs(row.get("month_return") or 0.0)), reverse=True)
        items = items[:5]
        stale_cache_used = False
        if items:
            TRENDING_CACHE["items"] = items
        else:
            cached_items = TRENDING_CACHE.get("items") or []
            if cached_items:
                items = cached_items
                stale_cache_used = True
        source_tags = _source_tags("Finnhub", "Internal TA Engine", "Market Snapshot Cache")
        if not items:
            return {
                "intent": "market_scanner",
                "analysis_type": "market_scanner",
                "analysis_engine": "modular_market_scanner_engine",
                "answer": "Trending stocks today are temporarily unavailable because live and cached scanner results are not available.",
                "confidence": 0,
                "sources": ["Market scanner unavailable"],
                "data_validation": {"price_data": False, "news_data": False, "technical_data": False},
                "answer_schema": {
                    "intent": "market_scanner",
                    "direct_answer": _pick_lang(lang, "ตัวสแกนตลาดยังไม่พร้อมในขณะนี้", "Market scanner data is temporarily unavailable."),
                    "trending_stocks": [],
                    "overview": _pick_lang(lang, "ตัวสแกนตลาดยังไม่พร้อมในขณะนี้", "Market scanner is temporarily unavailable."),
                    "rationale": [_pick_lang(lang, "ยังไม่มีทั้งข้อมูลสดและ cache ที่ใช้ยืนยันการสแกนตลาดได้", "Neither live nor cached scanner output is available right now.")],
                    "risks": [_pick_lang(lang, "ยังไม่ควรสรุปหุ้นเด่นโดยไม่มีรายการสแกนที่ยืนยันได้", "No confirmed scanner output is available for a reliable trending list.")],
                    "actionable_view": _pick_lang(lang, "รอสัญญาณ scanner รอบถัดไป หรือถามแบบ sector/stock เฉพาะเจาะจง", "Wait for the next scanner run or ask a sector/stock-specific question."),
                    "source_tags": ["Market scanner unavailable"],
                },
                "followups": (
                    [
                        "แสดงการจัดอันดับโมเมนตัมของแต่ละกลุ่ม",
                        "ตอนนี้กลุ่มไหนแรงที่สุด?",
                        "ช่วยแนะนำหุ้นให้หน่อย",
                    ] if lang == "th" else [
                        "Show sector momentum ranking",
                        "What sectors are strong now?",
                        "Recommend a stock",
                    ]
                ),
                "status": {
                    "online": True,
                    "message": "ตัวสแกนตลาดยังไม่พร้อม" if lang == "th" else "Scanner unavailable",
                    "live_data_ready": False,
                    "market_context_loaded": True,
                },
            }
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
        sector_rankings = self.market_data.get_sector_rankings().get("rankings", [])
        top_sector = sector_rankings[0].get("sector") if sector_rankings else "Relevant data is not available"
        answer = (
            ("ภาพรวมตลาด\n" if lang == "th" else "Market Context\n")
            + (
                _pick_lang(lang, f"Fear & Greed Index อยู่ที่ {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})\n\n", f"Fear & Greed Index: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})\n\n")
                if macro.get("fear_greed_index") is not None else
                _pick_lang(lang, "ยังไม่มีข้อมูล Fear & Greed ที่ยืนยันได้\n\n", "Fear & Greed Index: Data unavailable for this signal.\n\n")
            )
            + _pick_lang(lang, "ข้อมูลที่ใช้\n- แบบจำลองความเชื่อมั่นตลาด\n- โมเมนตัมของ Sector ETF\n\n", "Data Used\n- Market sentiment model\n- Sector ETF momentum\n\n")
            + _pick_lang(lang, "บทวิเคราะห์\n", "Analysis\n")
            + _pick_lang(lang, f"- ภาวะตลาดปัจจุบัน: {macro.get('market_sentiment') or 'ยังไม่มีข้อมูลยืนยัน'}\n", f"- Current market sentiment: {macro.get('market_sentiment') or 'Relevant data is not available'}\n")
            + _pick_lang(lang, f"- กลุ่มที่นำตลาด: {top_sector}\n", f"- Leading sector: {top_sector}\n")
            + _pick_lang(lang, f"- มุมมองความเสี่ยง: {macro.get('risk_outlook') or 'ยังไม่มีข้อมูลยืนยัน'}\n\n", f"- Risk outlook: {macro.get('risk_outlook') or 'Relevant data is not available'}\n\n")
            + _pick_lang(lang, "มุมมองตามเวลา\n- ระยะสั้น: sentiment และ sector leadership เป็นตัวขับตลาดหลัก\n- ระยะกลาง: ตลาดจะขึ้นกับว่าเงินเฟ้อและดอกเบี้ยไปทางไหนต่อ\n\nการวางน้ำหนัก\n", "Time Horizon\n- Short-term: sentiment and sector leadership are the main drivers.\n- Medium-term: the market path depends on inflation and rate direction.\n\nPositioning\n")
            + _pick_lang(lang, f"- ให้น้ำหนัก: {top_sector}\n- ถือเป็นกลาง: Defensive\n- ให้น้ำหนักต่ำกว่า: กลุ่มที่ไวต่อดอกเบี้ยถ้า macro ยังไม่ชัด\n\n", f"- Overweight: {top_sector}\n- Neutral: Defensive\n- Underweight: rate-sensitive groups if the macro path stays unclear\n\n")
            + _pick_lang(lang, "ข้อสรุป\n", "Conclusion\n")
            + _pick_lang(lang, f"ภาพรวมตลาดยังค่อนข้างระมัดระวัง โดย {top_sector} ยังเป็นกลุ่มที่นำตลาดในเชิงเปรียบเทียบ", f"Market conditions remain cautious, with {top_sector} currently leading on a relative basis.")
        )
        source_tags = _source_tags("Fear & Greed", "Sector ETF Model", "Market Snapshot Cache")
        overview = _pick_lang(
            lang,
            f"ภาวะตลาด {macro.get('market_sentiment') or 'ยังไม่มีข้อมูลยืนยัน'} • กลุ่มนำ {top_sector} • ระดับความเสี่ยง {macro.get('risk_outlook') or 'ยังไม่มีข้อมูลยืนยัน'}",
            f"Market sentiment is {macro.get('market_sentiment') or 'mixed'}; {top_sector} leads, and the current risk outlook is {macro.get('risk_outlook') or 'not fully confirmed'}.",
        )
        rationale = [
            _pick_lang(lang, "ตลาดอ่านผ่าน Fear & Greed เพื่อวัด appetite ของสินทรัพย์เสี่ยง", "Fear & Greed helps frame current risk appetite."),
            _pick_lang(lang, "sector ที่นำตลาดสะท้อนว่ากระแสเงินกำลังไหลไปทางไหน", "The leading sector shows where capital is rotating."),
            _pick_lang(lang, "risk outlook ช่วยกำหนดว่าควร aggressive หรือ selective แค่ไหน", "Risk outlook determines whether positioning should be aggressive or selective."),
        ]
        risks = [
            _pick_lang(lang, "ถ้า sentiment เปลี่ยนเร็ว ผู้นำตลาดอาจสลับได้ทันที", "Leadership can change quickly if sentiment shifts."),
            _pick_lang(lang, "bond yield และข้อมูลเงินเฟ้อยังเป็นตัวแปรกดดัน valuation", "Bond yields and inflation data still pressure valuations."),
            _pick_lang(lang, "sector breadth ที่แคบทำให้ตลาดเปราะกว่าที่ headline index สะท้อน", "Narrow market breadth can make the market more fragile than the headline index suggests."),
        ]
        actionable_view = _pick_lang(
            lang,
            f"ให้น้ำหนักตามกลุ่มนำ {top_sector} แบบ selective และคงการคุมความเสี่ยงตามภาวะ {macro.get('market_sentiment') or 'ตลาดปัจจุบัน'}",
            f"Stay selectively aligned with {top_sector} leadership while sizing risk to the current {macro.get('market_sentiment') or 'market'} regime.",
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
                    "market_regime": macro.get("market_sentiment"),
                    "fear_greed_index": macro.get("fear_greed_index"),
                    "points": [
                        f"Fear & Greed: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})"
                        if macro.get("fear_greed_index") is not None else "Fear & Greed: Data unavailable for this signal.",
                        f"Leading sector: {top_sector}",
                        f"Risk outlook: {macro.get('risk_outlook') or 'Relevant data is not available'}",
                    ],
                },
                "investment_interpretation": {
                    "recommendation": "Selective positioning",
                    "text": f"Market conditions remain cautious, with {top_sector} currently leading on a relative basis.",
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
        sector_rankings = self.market_data.get_sector_rankings().get("rankings", [])
        sector_lookup = {str(row.get("sector") or "").lower(): row for row in sector_rankings}
        q = (question or "").lower()
        requested_sector = next((row.get("sector") for row in sector_rankings if str(row.get("sector") or "").lower() in q), None)
        if not requested_sector:
            requested_sector = (macro.get("top_sector") or (sector_rankings[0].get("sector") if sector_rankings else None) or "Technology")
        sector_snapshot = sector_lookup.get(str(requested_sector).lower(), {})
        etf = sector_snapshot.get("etf")
        stock_rows = sector_snapshot.get("top_stocks") or []
        if not stock_rows:
            stock_rows = sector_snapshot.get("constituents") or []
        normalized_rows = []
        for row in stock_rows[:5]:
            symbol = row.get("symbol") or row.get("ticker")
            if not symbol:
                continue
            price = _safe_float(row.get("price"))
            ret_3m = _safe_float(row.get("return_3m_pct"))
            normalized_rows.append({
                "symbol": symbol,
                "name": row.get("name") or symbol,
                "price": round(price, 2) if price is not None else None,
                "return_3m_pct": round(ret_3m, 2) if ret_3m is not None else None,
                "momentum": row.get("momentum") or ("Strong" if (ret_3m or 0) > 10 else "Moderate" if (ret_3m or 0) > 0 else "Weak"),
                "reason": row.get("reason") or (
                    "Strong relative trend within the sector."
                    if (ret_3m or 0) > 10 else "Holding up better than peers on current price action."
                ),
            })

        if not normalized_rows:
            direct_answer = _pick_lang(lang, f"ตอนนี้ยังไม่มี ranking รายชื่อหุ้นที่ยืนยันได้ในกลุ่ม {requested_sector}", f"Stock-level ranking data is temporarily unavailable for {requested_sector}.")
            confidence = 42
        else:
            direct_answer = _pick_lang(lang, f"หุ้นโมเมนตัมเด่นในกลุ่ม {requested_sector} ตอนนี้คือ {', '.join([row['symbol'] for row in normalized_rows[:5]])}", f"Top momentum stocks in {requested_sector}: {', '.join([row['symbol'] for row in normalized_rows[:5]])}.")
            confidence = 74

        source_tags = _source_tags("Finnhub", "Sector ETF Model", "Internal TA Engine", "Market Snapshot Cache")
        overview = _pick_lang(
            lang,
            f"กลุ่ม {requested_sector} อยู่ในเรดาร์ของตลาด • ETF {etf or 'ยังไม่มีข้อมูลยืนยัน'} • การคัดชื่อหุ้นครั้งนี้เน้น momentum ภายในกลุ่ม",
            f"{requested_sector} is on the market radar; ETF {etf or 'not fully confirmed'} anchors the sector view, and the stock list focuses on internal momentum leadership.",
        )
        rationale = [row["reason"] for row in normalized_rows[:4]] or [
            _pick_lang(lang, "ยังไม่มี ranking ระดับหุ้นที่ยืนยันได้ในขณะนี้", "No confirmed stock-level ranking is available right now.")
        ]
        risks = [
            _pick_lang(lang, f"ผู้นำของกลุ่ม {requested_sector} อาจอ่อนลงเร็วถ้า sector rotation เปลี่ยน", f"{requested_sector} leadership can fade quickly if sector rotation shifts."),
            _pick_lang(lang, "หุ้น momentum สูงมักผันผวนมากกว่าค่าเฉลี่ย", "High-momentum names often carry higher volatility."),
            _pick_lang(lang, "ผลตอบแทนระยะสั้นอาจไม่ยั่งยืนหากไม่มีแรงหนุนจากกำไรหรือข่าว", "Short-term momentum may not persist without earnings or news support."),
        ]
        actionable_view = _pick_lang(
            lang,
            f"เน้นติดตาม 2–3 ตัวบนสุดใน {requested_sector} แบบทยอยดูจังหวะ ไม่ควรไล่ราคาเป็นชุดใหญ่",
            f"Focus on the top 2–3 names in {requested_sector} and add selectively rather than chasing the whole group aggressively.",
        )
        answer = (
            "Market Context\n"
            + (
                f"Fear & Greed Index: {round(_safe_float(macro.get('fear_greed_index')), 1)} ({macro.get('market_sentiment')})\n\n"
                if macro.get("fear_greed_index") is not None else
                "Fear & Greed Index: Data unavailable for this signal.\n\n"
            )
            + "Data Used\n- Sector ETF momentum\n- Stock-level price action within the sector\n\n"
            + "Analysis\n"
            + ("\n".join([
                f"{idx + 1}. {row['name']} ({row['symbol']}): "
                + (f"${row['price']:.2f}, " if row.get("price") is not None else "")
                + (f"3M return {row['return_3m_pct']:+.2f}%, " if row.get("return_3m_pct") is not None else "")
                + f"momentum {row['momentum']}"
                for idx, row in enumerate(normalized_rows[:5])
            ]) if normalized_rows else "Stock-level ranking data unavailable.")
            + "\n\nTime Horizon\n"
            + f"- Short-term: the leading names in {requested_sector} are benefiting from current sector momentum and relative strength.\n"
            + "- Medium-term: continuation depends on earnings support, sector rotation persistence, and whether the ETF leadership remains intact.\n\n"
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
                    "market_regime": macro.get("market_sentiment"),
                },
                "sector_stock_picker": {
                    "sector": requested_sector,
                    "etf": etf,
                    "stocks": normalized_rows[:5],
                },
                "why_these_names": {
                    "points": [row["reason"] for row in normalized_rows[:5]],
                },
                "risks": [
                    f"{requested_sector} leadership can reverse quickly if sector rotation fades.",
                    "Higher momentum names can stay volatile in weak macro regimes.",
                ],
                "overview": overview,
                "rationale": rationale,
                "summary_points": rationale,
                "actionable_view": actionable_view,
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
