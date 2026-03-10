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
    news_query = text("SELECT ticker, sentiment FROM news WHERE published_at >= :cutoff")

    try:
        with engine.connect() as conn:
            df_prices = pd.read_sql(price_query, conn, params={"cutoff": cutoff_date})
            df_news = pd.read_sql(news_query, conn, params={"cutoff": cutoff_date})
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
        
        # คำนวณ Sentiment เฉลี่ย
        sentiment = 0.5  # ค่าเริ่มต้น
        if not df_news.empty:
            ticker_news = df_news[df_news['ticker'] == ticker]
            if not ticker_news.empty:
                sentiment = ticker_news['sentiment'].mean()
                
        stats.append({
            "ticker": ticker,
            "latest_price": float(last_price),
            "ret30": round(float(ret30) * 100, 2),  # แปลงเป็น % สำหรับ React UI
            "volatility": float(volatility),
            "sentiment": float(sentiment)
        })
        
    if not stats:
        return []

    df_stats = pd.DataFrame(stats)
    
    # คิดคะแนนตาม Strategy
    if strategy == "DEFENSIVE":
        df_stats["raw_score"] = (df_stats["sentiment"] * 30) - (df_stats["volatility"] * 70) + (df_stats["ret30"] * 10)
    elif strategy == "AGGRESSIVE":
        df_stats["raw_score"] = (df_stats["ret30"] * 60) + (df_stats["sentiment"] * 30) - (df_stats["volatility"] * 10)
    else: # BALANCED
        df_stats["raw_score"] = (df_stats["ret30"] * 40) + (df_stats["sentiment"] * 40) - (df_stats["volatility"] * 20)

    # ปรับสเกลคะแนนเป็น 0-100 (Min-Max Scaling)
    min_s, max_s = df_stats["raw_score"].min(), df_stats["raw_score"].max()
    if max_s > min_s:
        df_stats["ai_score"] = ((df_stats["raw_score"] - min_s) / (max_s - min_s)) * 100
    else:
        df_stats["ai_score"] = 50.0

    # สร้างเหตุผลประกอบ (Reason)
    def generate_reason(row):
        if row["sentiment"] > 0.6 and row["ret30"] > 5.0:
            return "Positive News & Strong Uptrend"
        elif row["sentiment"] > 0.4:
            return "Favorable Market Sentiment"
        elif row["ret30"] > 8.0:
            return "High Short-Term Momentum"
        elif row["volatility"] < 0.2:
            return "Stable & Low Volatility"
        return "Algorithm Selected Pick"

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
            "reason": row["reason"]
        })
        
    return results