import pandas as pd
import numpy as np
from sqlalchemy import text
from datetime import datetime, timedelta
import os
import sys
import logging

# Set up Path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

try:
    from init_db import engine
except ImportError:
    from sqlalchemy import create_engine
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/stock_db")
    engine = create_engine(DATABASE_URL)

logger = logging.getLogger(__name__)

def get_ai_picks(strategy: str = "BALANCED", limit: int = 5):
    """
    คัดกรองหุ้นด้วย AI โดยอิงจาก Momentum (ผลตอบแทน), Volatility (ความเสี่ยง) และ Sentiment (ข่าว)
    strategy: BALANCED, AGGRESSIVE, DEFENSIVE
    """
    # ดึงข้อมูลย้อนหลัง 90 วัน
    cutoff_date = datetime.now() - timedelta(days=90)
    
    price_query = text("SELECT ticker, last_updated as ts, close FROM prices WHERE last_updated >= :cutoff")
    news_query = text("SELECT ticker, sentiment, sentiment_score FROM news WHERE published_at >= :cutoff")
    news_query_fallback = text("SELECT ticker, sentiment FROM news WHERE published_at >= :cutoff")
    news_column_probe = text(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'news' AND column_name = 'sentiment_score'
        LIMIT 1
        """
    )

    try:
        with engine.connect() as conn:
            df_prices = pd.read_sql(price_query, conn, params={"cutoff": cutoff_date})
            has_sentiment_score = not pd.read_sql(news_column_probe, conn).empty
            if has_sentiment_score:
                df_news = pd.read_sql(news_query, conn, params={"cutoff": cutoff_date})
            else:
                df_news = pd.read_sql(news_query_fallback, conn, params={"cutoff": cutoff_date})
    except Exception as e:
        logger.error(f"❌ Database Error in AI Picker: {e}")
        return []
    
    if df_prices.empty:
        return []

    # แปลงชนิดข้อมูลวันที่และเรียงลำดับเวลา
    df_prices['ts'] = pd.to_datetime(df_prices['ts'])
    df_prices = df_prices.sort_values(by=['ticker', 'ts'])
    
    stats = []
    
    # คำนวณสถิติของแต่ละหุ้น
    for ticker, group in df_prices.groupby('ticker'):
        if len(group) < 5:  # ข้ามหุ้นที่ข้อมูลไม่พอ
            continue
            
        first_price = group['close'].iloc[0]
        last_price = group['close'].iloc[-1]
        
        if first_price <= 0:
            continue
            
        ret30 = (last_price - first_price) / first_price
        
        # คำนวณ Volatility (Standard Deviation ของ Daily Returns)
        daily_ret = group['close'].pct_change().dropna()
        volatility = daily_ret.std() * np.sqrt(252) if not daily_ret.empty else 0.0
        
        # คำนวณ Sentiment เฉลี่ยจากข่าวจริงเท่านั้น (ถ้าไม่มีจะเป็น None)
        sentiment = None
        news_count = 0
        if not df_news.empty:
            ticker_news = df_news[df_news['ticker'] == ticker]
            news_count = int(len(ticker_news))
            if not ticker_news.empty:
                scores = []
                for _, news_row in ticker_news.iterrows():
                    raw_score = news_row.get("sentiment_score")
                    if pd.notna(raw_score):
                        try:
                            scores.append(float(raw_score))
                            continue
                        except Exception:
                            pass
                    raw_label = str(news_row.get("sentiment", "")).strip().lower()
                    if raw_label in {"bullish", "positive"}:
                        scores.append(0.6)
                    elif raw_label in {"bearish", "negative"}:
                        scores.append(-0.6)
                    elif raw_label in {"neutral"}:
                        scores.append(0.0)
                if scores:
                    sentiment = float(np.mean(scores))
                
        sentiment_available = sentiment is not None
        signal_count = 2 + (1 if sentiment_available else 0)  # ret30 + volatility + optional sentiment
        signal_coverage = signal_count / 3.0
        price_points = int(len(group))

        # Confidence should vary by ticker, based on both data coverage and signal quality.
        trend_strength = min(1.0, abs(float(ret30)) / 20.0)  # stronger trend => clearer signal
        sentiment_strength = min(1.0, abs(float(sentiment))) if sentiment is not None else 0.0
        volatility_quality = 1.0 - min(1.0, float(volatility) / 0.8)  # extreme volatility lowers confidence
        history_quality = min(1.0, price_points / 90.0)
        news_quality = min(1.0, news_count / 10.0)

        confidence = 35.0
        confidence += 22.0 * signal_coverage
        confidence += 14.0 * history_quality
        confidence += 8.0 * news_quality
        confidence += 12.0 * trend_strength
        confidence += 6.0 * sentiment_strength
        confidence += 8.0 * volatility_quality
        confidence = float(max(30.0, min(95.0, confidence)))

        stats.append({
            "ticker": ticker,
            "latest_price": float(last_price),
            "ret30": round(float(ret30) * 100, 2),  # แปลงเป็น % สำหรับ React UI
            "volatility": float(volatility),
            "sentiment": float(sentiment) if sentiment is not None else None,
            "news_count": news_count,
            "price_points": price_points,
            "signal_coverage": round(signal_coverage, 4),
            "confidence": confidence,
        })
        
    if not stats:
        return []

    df_stats = pd.DataFrame(stats)
    
    # คิดคะแนนตาม Strategy
    # ใช้เฉพาะสัญญาณที่มีจริงและ normalize น้ำหนักใหม่เมื่อข้อมูลบางส่วนหายไป
    def _weighted_raw_score(row):
        if strategy == "DEFENSIVE":
            weights = {"ret30": 0.10, "sentiment": 0.30, "volatility": 0.70}
        elif strategy == "AGGRESSIVE":
            weights = {"ret30": 0.60, "sentiment": 0.30, "volatility": 0.10}
        else:  # BALANCED
            weights = {"ret30": 0.40, "sentiment": 0.40, "volatility": 0.20}

        score = 0.0
        effective_weight = 0.0

        if pd.notna(row.get("ret30")):
            score += float(row["ret30"]) * weights["ret30"]
            effective_weight += weights["ret30"]

        if pd.notna(row.get("sentiment")):
            # sentiment in [-1,1], scale to percentage-like effect for consistency
            score += float(row["sentiment"]) * 100.0 * weights["sentiment"]
            effective_weight += weights["sentiment"]

        if pd.notna(row.get("volatility")):
            score += (-float(row["volatility"]) * 100.0) * weights["volatility"]
            effective_weight += weights["volatility"]

        if effective_weight <= 0:
            return np.nan
        return score / effective_weight

    df_stats["raw_score"] = df_stats.apply(_weighted_raw_score, axis=1)
    df_stats = df_stats[pd.notna(df_stats["raw_score"])].copy()
    if df_stats.empty:
        return []

    # ปรับสเกลคะแนนเป็น 0-100 (Min-Max Scaling)
    min_s, max_s = df_stats["raw_score"].min(), df_stats["raw_score"].max()
    if max_s > min_s:
        df_stats["ai_score"] = ((df_stats["raw_score"] - min_s) / (max_s - min_s)) * 100
    else:
        df_stats["ai_score"] = 50.0

    # สร้างเหตุผลประกอบ (Reason)
    def generate_reason(row):
        if pd.notna(row["sentiment"]) and row["sentiment"] > 0.25 and row["ret30"] > 5.0:
            return "Positive News & Strong Uptrend"
        elif pd.notna(row["sentiment"]) and row["sentiment"] > 0.15:
            return "Favorable Market Sentiment"
        elif row["ret30"] > 8.0:
            return "High Short-Term Momentum"
        elif row["volatility"] < 0.2:
            return "Stable & Low Volatility"
        return "Momentum / volatility model pick"

    df_stats["reason"] = df_stats.apply(generate_reason, axis=1)

    # เรียงลำดับจากคะแนนมากไปน้อย และดึงตาม limit ที่กำหนด
    top_picks = df_stats.sort_values("ai_score", ascending=False).head(limit)

    # แปลงผลลัพธ์เพื่อส่งกลับไปที่ FastAPI
    results = []
    for _, row in top_picks.iterrows():
        results.append({
            "ticker": row["ticker"],
            "latest_price": row["latest_price"],
            "ret30": row["ret30"],
            "volatility": row["volatility"],
            "sentiment": row["sentiment"],
            "ai_score": round(row["ai_score"], 2),
            "reason": row["reason"],
            "confidence": round(float(row["confidence"]), 2),
            "signal_coverage": round(float(row["signal_coverage"]), 4),
            "price_points": int(row["price_points"]),
            "news_count": int(row["news_count"]),
        })
        
    return results
