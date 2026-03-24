from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Body

from ai.intent_detection import IntentDetectionEngine
from ai.advisor_reasoning import InvestmentReasoningEngine


class AdvisorEndpointService:
    def __init__(self, *, reasoning_engine: InvestmentReasoningEngine, intent_engine: Optional[IntentDetectionEngine] = None) -> None:
        self.reasoning_engine = reasoning_engine
        self.intent_engine = intent_engine or IntentDetectionEngine()

    def handle(self, question: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        intent_result = self.intent_engine.detect(question)
        selected_stock = str(context.get("selected_stock") or "").upper().strip()
        is_thai = any("\u0E00" <= char <= "\u0E7F" for char in str(question or ""))
        augmented_context = {
            **(context or {}),
            "user_question": question,
            "response_language": "th" if is_thai else "en",
        }

        if intent_result.intent == "invalid_query":
            return {
                "intent": "invalid_query",
                "analysis_type": "query_validation",
                "analysis_engine": "intent_detection_engine",
                "answer": intent_result.clarification or ("กรุณาระบุคำถามให้ชัดขึ้นอีกเล็กน้อย" if is_thai else "Please clarify your question."),
                "confidence": 0,
                "sources": ["Internal Intent Router"],
                "data_validation": {"price_data": False, "news_data": False, "technical_data": False},
                "answer_schema": {
                    "intent": "invalid_query",
                    "direct_answer": intent_result.clarification or ("กรุณาระบุคำถามให้ชัดขึ้นอีกเล็กน้อย" if is_thai else "Please clarify your question."),
                    "entities": intent_result.entities,
                    "entity_kind": intent_result.entity_kind,
                    "source_tags": ["Internal Intent Router"],
                },
                "followups": [
                    *(
                        [
                            "เปรียบเทียบ NVDA กับ AMD",
                            "เปรียบเทียบ Technology กับ Energy",
                            "แสดงการจัดอันดับ Sector Momentum",
                        ]
                        if is_thai else
                        [
                            "Compare NVDA vs AMD",
                            "Compare Technology vs Energy",
                            "Show sector momentum ranking",
                        ]
                    )
                ],
                "status": {
                    "online": True,
                    "message": "พร้อมใช้งาน" if is_thai else "Connected",
                    "live_data_ready": True,
                    "market_context_loaded": True,
                },
            }

        if intent_result.intent == "stock_recommendation":
            return self.reasoning_engine.analyze_stock_recommendation(question, augmented_context)
        if intent_result.intent == "open_recommendation":
            return self.reasoning_engine.analyze_open_recommendation(question, augmented_context)
        if intent_result.intent == "knowledge_guidance":
            return self.reasoning_engine.analyze_knowledge_guidance(question, augmented_context)

        if intent_result.intent == "stock_analysis" and selected_stock:
            return self.reasoning_engine.analyze_stock(selected_stock, augmented_context)
        if intent_result.intent == "stock_analysis" and intent_result.entities:
            return self.reasoning_engine.analyze_stock(intent_result.entities[0], augmented_context)
        if intent_result.intent == "stock_comparison":
            return self.reasoning_engine.analyze_comparison(question, augmented_context)
        if intent_result.intent == "sector_comparison":
            comparison_context = {**augmented_context, "comparison_sectors": intent_result.entities}
            return self.reasoning_engine.analyze_sector(question, comparison_context)
        if intent_result.intent == "sector_comparison_top_n":
            comparison_context = {
                **augmented_context,
                "compare_top_n": True,
                "top_n": intent_result.top_n or 2,
            }
            return self.reasoning_engine.analyze_sector(question, comparison_context)
        if intent_result.intent in {"risk_explanation", "sector_explanation"}:
            return self.reasoning_engine.analyze_risk(question, augmented_context)
        if intent_result.intent == "sector_stock_picker":
            return self.reasoning_engine.analyze_sector_stock_picker(question, augmented_context)
        if intent_result.intent == "global_market_query":
            if intent_result.query_scope == "sector_ranking":
                return self.reasoning_engine.analyze_sector(question, augmented_context)
            return self.reasoning_engine.analyze_market(augmented_context)
        if intent_result.intent == "sector_analysis":
            return self.reasoning_engine.analyze_sector(question, augmented_context)
        if intent_result.intent == "macro_analysis":
            return self.reasoning_engine.analyze_macro(question, augmented_context)
        if intent_result.intent == "market_scanner":
            return self.reasoning_engine.analyze_trending(augmented_context)
        if intent_result.intent == "trending_stock_discovery":
            return self.reasoning_engine.analyze_trending(augmented_context)
        if intent_result.intent == "portfolio_analysis":
            return self.reasoning_engine.analyze_portfolio(augmented_context)
        return None


def create_advisor_router(
    handler: Callable[[Any], Dict[str, Any]],
    health_handler: Optional[Callable[[], Dict[str, Any]]] = None,
) -> APIRouter:
    router = APIRouter()

    @router.post("/ai-advisor")
    @router.post("/api/ai-advisor")
    def advisor_entrypoint(payload: Dict[str, Any] = Body(...)):
        return handler(payload)

    @router.get("/ai-advisor/health")
    @router.get("/api/ai-advisor/health")
    def advisor_health():
        if health_handler:
            return health_handler()
        return {
            "ok": True,
            "service": "ai_advisor",
            "message": "Health handler not configured",
        }

    return router
