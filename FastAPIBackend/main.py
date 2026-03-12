from __future__ import annotations
from datetime import datetime, timedelta
import math, threading, time, requests, pandas as pd, yfinance as yf, feedparser, logging
from typing import List, Dict, Any, Optional
import re
import json
import base64
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Query, Header
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from requests.adapters import HTTPAdapter, Retry
from dotenv import load_dotenv
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from sqlalchemy import text

from init_db import SessionLocal, engine, Base
from models import PortfolioPosition

# ==========================================
# 1. ประกาศ Logger ไว้เป็นอันดับแรกสุด เพื่อให้ทุกส่วนพร้อมใช้งาน
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ==========================================
# 2. นำเข้าโมดูล AI และ Fetcher
# ==========================================
try:
    from fetcher_model import fetch_and_store
except ImportError as e:
    logger.warning(f"⚠️ Failed to load fetcher_model: {e}")

try:
    from transformers import pipeline
except ImportError as e:
    logger.warning(f"⚠️ Failed to load transformers: {e}")

# ==========================================
# 3. ตั้งค่า Path สำหรับแก้ปัญหา Docker หาไฟล์ในเครื่องไม่เจอ
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_PATH = Path(BASE_DIR)

if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

backend_candidates = [
    BASE_PATH / "Backend",
    BASE_PATH.parent / "Backend",
    Path.cwd() / "Backend",
    Path("/Backend"),
]
for candidate in backend_candidates:
    candidate_str = str(candidate)
    if candidate.exists() and candidate_str not in sys.path:
        sys.path.append(candidate_str)

# ==========================================
# 4. นำเข้าโมดูลภายในโปรเจกต์ (risk_model, ai_picker) แบบปลอดภัย
# ==========================================
try:
    from risk_model import recommend_by_level
    HAS_RISK = True
except ImportError as e:
    logger.error(f"❌ Failed to load risk_model: {e}")
    HAS_RISK = False
    def recommend_by_level(level, limit): return []

try:
    from ai_picker import get_ai_picks
    HAS_AI_PICKER = True
except Exception as e:
    logger.error(f"❌ Failed to load AI Picker: {e}")
    HAS_AI_PICKER = False

try:
    from services.market_sentiment import compute_market_sentiment
    HAS_MARKET_SENTIMENT = True
except Exception as e:
    logger.error(f"❌ Failed to load market sentiment service: {e}")
    HAS_MARKET_SENTIMENT = False

# ==========================================
# 5. เริ่มต้นแอป FastAPI
# ==========================================
load_dotenv()

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
NEWSAPI_KEY           = os.getenv("NEWSAPI_KEY")
MARKETAUX_API_KEY     = os.getenv("MARKETAUX_API_KEY")
FINNHUB_API_KEY       = os.getenv("FINNHUB_API_KEY") or os.getenv("FINNHUB_TOKEN")
FMP_API_KEY           = os.getenv("FMP_API_KEY")
GEMINI_API_KEY        = os.getenv("GEMINI_API_KEY")

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"

CACHE_DURATION = timedelta(minutes=10)
TICKERS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META",
    "TSLA", "JPM", "XOM", "JNJ", "PG", "CAT", "UNH"
]
cache_lock = threading.Lock()
cache: Dict[str, Dict[str, Any]] = {}
marketaux_news_cache: Dict[str, Dict[str, Any]] = {}
stock_return_cache: Dict[str, Dict[str, Any]] = {}


# NOTE: logger already configured above; avoid reconfiguring here


if HAS_RISK:
    logger.info("✅ Risk module loaded")

# =========================
# App + CORS
# =========================
app = FastAPI(title="AI Stock Sentiment API", version="3.0")
# Configure CORS: prefer explicit allowed origins (from env FRONTEND_URL) to avoid wildcard+credentials issues
frontend_url = os.getenv("FRONTEND_URL") or "http://localhost:5173"
allowed_origins = [
    frontend_url,
    "http://localhost",
    "http://localhost:80",
    "http://localhost:5173",
    "http://127.0.0.1:80",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure SQL tables exist for runtime features (portfolio, etc.)
Base.metadata.create_all(bind=engine)

PORTFOLIO_QUOTE_CACHE_TTL = 30
PORTFOLIO_META_CACHE_TTL = 3600
PORTFOLIO_AI_CACHE_TTL = 300
AI_SUMMARY_CACHE_TTL = 120
portfolio_quote_cache: Dict[str, Dict[str, Any]] = {}
portfolio_meta_cache: Dict[str, Dict[str, Any]] = {}
portfolio_ai_cache: Dict[str, Dict[str, Any]] = {}
ai_summary_cache: Dict[str, Dict[str, Any]] = {}
stock_stats_cache: Dict[str, Dict[str, Any]] = {}

@app.get("/")
async def root():
    return {"message": "FastAPI ทำงานแล้ว!"}

# =========================
# Sentiment Model (FinBERT)
# =========================
logger.info("Preparing FinBERT model loader (lazy/background)...")
_sentiment_lock = threading.Lock()
sentiment_analyzer = None
_sentiment_ready = False


def _neutral_sentiment_batch(texts):
    return [{"label": "neutral", "score": 0} for _ in texts]


def _load_sentiment_model():
    global sentiment_analyzer, _sentiment_ready
    with _sentiment_lock:
        if _sentiment_ready and sentiment_analyzer is not None:
            return sentiment_analyzer
        logger.info("Loading FinBERT model for sentiment analysis...")
        try:
            sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model="ProsusAI/finbert"
            )
            _sentiment_ready = True
            logger.info("FinBERT loaded successfully")
        except Exception as e:
            logger.error(f"FinBERT load error: {e}")
            sentiment_analyzer = _neutral_sentiment_batch
            _sentiment_ready = True
    return sentiment_analyzer


def get_sentiment_analyzer():
    if sentiment_analyzer is None:
        return _load_sentiment_model()
    return sentiment_analyzer


@app.on_event("startup")
def warmup_sentiment_model():
    # Warm up in background so API can accept requests immediately.
    threading.Thread(target=_load_sentiment_model, daemon=True).start()

# =========================
# Requests session (retry)
# =========================
session = requests.Session()
retries = Retry(total=3, backoff_factor=2, status_forcelist=[429, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

# =========================
# Helpers
# =========================
def safe_float(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return 0.0
        return float(x)
    except Exception:
        return 0.0


def normalize_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip().upper()
    if not raw:
        return ""
    # Normalize common separator variants while preserving class shares (e.g. BRK.A / BRK-B)
    raw = re.sub(r"\s+", "", raw)
    return raw


def normalize_symbol_list(symbols: List[str]) -> List[str]:
    cleaned: List[str] = []
    seen = set()
    for sym in symbols or []:
        normalized = normalize_symbol(sym)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned
    
# =========================
# AI Quant Scoring
# =========================
def ai_trend_score(sma20, sma50):
    if sma20 > sma50:
        return 1
    elif sma20 < sma50:
        return -1
    return 0


def ai_rsi_score(rsi):
    if rsi < 30:
        return 1
    elif rsi > 70:
        return -1
    return 0


def ai_volatility_score(vol):
    if vol > 0.04:
        return -1
    elif vol < 0.02:
        return 1
    return 0


def ai_momentum_score(momentum):
    if momentum > 0.05:
        return 1
    elif momentum < -0.05:
        return -1
    return 0

def ai_bollinger_score(close, upper, lower):

    if close < lower:
        return 1

    elif close > upper:
        return -1

    return 0

def ai_sharpe_score(sharpe):

    if sharpe > 1:
        return 1

    elif sharpe < 0:
        return -1

    return 0

def ai_macd_score(macd, signal):
    if macd > signal:
        return 1
    elif macd < signal:
        return -1
    return 0


def compute_ai_score(history, sentiment):
    # 1. ตรวจสอบข้อมูลก่อนว่ามีไหม ถ้าไม่มีให้คืนค่า 0 ทันที
    if not history:
        return 0, "HOLD"

    # 2. ดึงข้อมูลวันล่าสุดออกมา
    last = history[-1]

    sma20 = last.get("sma20", 0)
    sma50 = last.get("sma50", 0)
    rsi = last.get("rsi", 50)
    vol = last.get("volatility", 0)
    momentum = last.get("momentum", 0)
    bb_upper = last.get("bb_upper", 0)
    bb_lower = last.get("bb_lower", 0)
    close = last.get("close", 0)
    sharpe = last.get("sharpe", 0)
    macd = last.get("macd", 0)
    macd_signal = last.get("macd_signal", 0)

    # 3. คำนวณคะแนนย่อย (Sub-scores) ของแต่ละ Indicator
    bb_s = ai_bollinger_score(close, bb_upper, bb_lower)
    macd_s = ai_macd_score(macd, macd_signal)
    trend = ai_trend_score(sma20, sma50)
    rsi_s = ai_rsi_score(rsi)
    vol_s = ai_volatility_score(vol)
    mom_s = ai_momentum_score(momentum)
    sharpe_s = ai_sharpe_score(sharpe)

    # 4. คำนวณคะแนน Sentiment
    sentiment_s = 0
    if sentiment > 0.2:
        sentiment_s = 1
    elif sentiment < -0.2:
        sentiment_s = -1

    # 5. นำคะแนนทั้งหมดมารวมกันตามน้ำหนัก (Weights) ที่กำหนดไว้
    score = (
        0.20 * mom_s +
        0.20 * trend +
        0.20 * sentiment_s +
        0.10 * rsi_s +
        0.10 * macd_s +
        0.10 * bb_s +
        0.10 * sharpe_s
    )

    # 6. ประมวลผลเป็นคำแนะนำ
    if score > 0.35:
        rec = "BUY"
    elif score < -0.35:
        rec = "SELL"
    else:
        rec = "HOLD"

    return round(score, 4), rec

def _finbert_batch(titles: List[str]) -> List[float]:

    if not titles:
        return []

    try:
        analyzer = get_sentiment_analyzer()
        outs = analyzer(titles)

        scores = []

        for o in outs:
            label = o.get("label","Neutral").lower()
            conf = o.get("score",0)

            if "positive" in label:
                scores.append(conf)

            elif "negative" in label:
                scores.append(-conf)

            else:
                scores.append(0)

        return scores

    except Exception as e:
        print(f"⚠️ FinBERT batch error: {e}")
        return [0]*len(titles)

def score_text(text: str):

    try:
        analyzer = get_sentiment_analyzer()
        out = analyzer([text])[0]

        label = out["label"].lower()
        score = out["score"]

        if "positive" in label:
            return score
        elif "negative" in label:
            return -score
        else:
            return 0

    except:
        return 0

# =========================
# News Providers
# =========================
def get_alpha_news(symbol: str) -> List[Dict[str, Any]]:
    url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
    try:
        res = session.get(url, timeout=8)
        if res.status_code != 200:
            return []
        data = res.json()
        feed = data.get("feed", []) or []
        if not feed:
            return []

        titles = [f.get("title","") + " " + f.get("summary","") for f in feed]

        sentiments = _finbert_batch(titles)
        

        news = []
        for i, item in enumerate(feed[:len(sentiments)]):
            try:
                date_str = item.get("time_published", "")
                date = datetime.strptime(date_str, "%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M")
            except Exception:
                date = "Unknown"
            news.append({
                "title": item.get("title"),
                "link": item.get("url", ""),
                "date": date,
                "sentiment": sentiments[i],
                "provider": item.get("source", "AlphaVantage"),
                "image": item.get("banner_image", "")
            })
        return news
    except Exception as e:
        logger.warning(f"AlphaVantage error: {e}")
        return []

def get_yahoo_news_rss(symbol: str, limit=5):

    try:
        feed = feedparser.parse(
            f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
        )

        titles = [entry.title for entry in feed.entries[:limit]]

        sentiments = _finbert_batch(titles)

        out = []

        for i, entry in enumerate(feed.entries[:limit]):

            out.append({
                "title": entry.title,
                "link": entry.link,
                "date": getattr(entry, "published", datetime.now().strftime("%Y-%m-%d %H:%M")),
                "sentiment": sentiments[i],   # ✅ ใช้ FinBERT
                "provider": "Yahoo Finance RSS",
                "image": ""
            })

        return out

    except Exception as e:
        logger.warning(f"Yahoo RSS error: {e}")
        return []

@app.get("/rss/{symbol}")
def rss_endpoint(symbol: str):
    symbol = symbol.upper()
    try:
        news = get_yahoo_news_rss(symbol)
        return {"symbol": symbol, "news": news}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _sentiment_label_from_score(score: float) -> str:
    if score > 0.2:
        return "Positive"
    if score < -0.2:
        return "Negative"
    return "Neutral"


def _extract_marketaux_symbol_score(article: Dict[str, Any], symbol: str) -> Optional[float]:
    target = (symbol or "").upper()
    entities = article.get("entities") or []
    for ent in entities:
        sym = str(ent.get("symbol") or "").upper()
        if sym == target:
            raw = ent.get("sentiment_score")
            if raw is None:
                return None
            try:
                return float(raw)
            except Exception:
                return None
    return None


def get_marketaux_news(symbol: str, limit=5, days_back=7):
    if not MARKETAUX_API_KEY:
        return []

    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        url = (
            f"https://api.marketaux.com/v1/news/all?symbols={symbol}"
            f"&language=en&limit={limit}&filter_entities=true"
            f"&published_after={start_date:%Y-%m-%dT%H:%M:%S}"
            f"&published_before={end_date:%Y-%m-%dT%H:%M:%S}"
            f"&api_token={MARKETAUX_API_KEY}"
        )
        res = session.get(url, timeout=8)
        data = res.json()
        articles = data.get("data") or []
        if not articles:
            return []

        titles = [
            a.get("title","") + " " + a.get("description","")
            for a in articles
        ]

        sentiments = _finbert_batch(titles)

        out = []
        for i, a in enumerate(articles):
            published = a.get("published_at", "Unknown")
            try:
                published = datetime.strptime(published[:19], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
            score = _extract_marketaux_symbol_score(a, symbol)
            if score is None:
                score = sentiments[i] if i < len(sentiments) else 0.0
            out.append({
                "title": a.get("title", "Untitled"),
                "link": a.get("url", ""),
                "date": published,
                "sentiment": _sentiment_label_from_score(score),
                "sentiment_score": round(float(score), 4),
                "provider": a.get("source", "MarketAux"),
                "image": a.get("image_url", "")
            })
        return out
    except Exception as e:
        logger.warning(f"MarketAux API error: {e}")
        return []


def get_marketaux_news_batch(symbols: List[str], limit_per_symbol=5, days_back=14):
    clean_symbols = [s.upper().strip() for s in symbols if s and s.strip()]
    if not clean_symbols or not MARKETAUX_API_KEY:
        return []

    cache_key = f"{','.join(sorted(clean_symbols))}|{limit_per_symbol}|{days_back}"
    now = datetime.utcnow()
    with cache_lock:
        cached = marketaux_news_cache.get(cache_key)
        if cached and (now - cached["ts"]) < timedelta(minutes=5):
            return cached["data"]

    try:
        end_date = now
        start_date = end_date - timedelta(days=days_back)
        params = {
            "symbols": ",".join(clean_symbols),
            "language": "en",
            "limit": max(limit_per_symbol * len(clean_symbols), 20),
            "filter_entities": "true",
            "published_after": start_date.strftime("%Y-%m-%dT%H:%M:%S"),
            "published_before": end_date.strftime("%Y-%m-%dT%H:%M:%S"),
            "sort": "published_desc",
            "api_token": MARKETAUX_API_KEY,
        }

        res = session.get("https://api.marketaux.com/v1/news/all", params=params, timeout=10)
        if res.status_code != 200:
            logger.warning(f"MarketAux batch status={res.status_code} body={res.text[:200]}")
            return []

        data = res.json()
        articles = data.get("data") or []
        if not articles:
            return []

        by_symbol: Dict[str, List[Dict[str, Any]]] = {sym: [] for sym in clean_symbols}

        for article in articles:
            published = article.get("published_at", "Unknown")
            try:
                published = datetime.strptime(published[:19], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

            entities = article.get("entities") or []
            entity_map = {}
            for ent in entities:
                ent_symbol = str(ent.get("symbol") or "").upper()
                if ent_symbol in by_symbol:
                    try:
                        entity_map[ent_symbol] = float(ent.get("sentiment_score"))
                    except Exception:
                        entity_map[ent_symbol] = None

            if not entity_map:
                continue

            title = article.get("title", "")
            desc = article.get("description", "")
            finbert_score = None
            if any(v is None for v in entity_map.values()):
                finbert_score = score_text(f"{title} {desc}".strip())

            for sym, score in entity_map.items():
                final_score = finbert_score if score is None else score
                by_symbol[sym].append({
                    "title": article.get("title", "Untitled"),
                    "link": article.get("url", ""),
                    "date": published,
                    "sentiment": _sentiment_label_from_score(final_score),
                    "sentiment_score": round(float(final_score), 4),
                    "provider": article.get("source", "MarketAux"),
                    "image": article.get("image_url", ""),
                })

        out = []
        for sym in clean_symbols:
            dedup = []
            seen = set()
            for item in by_symbol.get(sym, []):
                key = item.get("link") or item.get("title")
                if key in seen:
                    continue
                seen.add(key)
                dedup.append(item)
                if len(dedup) >= limit_per_symbol:
                    break
            out.append({"symbol": sym, "news": dedup})

        with cache_lock:
            marketaux_news_cache[cache_key] = {"ts": now, "data": out}
        return out
    except Exception as e:
        logger.warning(f"MarketAux batch error: {e}")
        return []

def get_newsapi_news_batch(symbols: List[str], limit_per_symbol=5, days_back=14):
    if MARKETAUX_API_KEY:
        marketaux_data = get_marketaux_news_batch(symbols, limit_per_symbol=limit_per_symbol, days_back=days_back)
        if marketaux_data and any(row.get("news") for row in marketaux_data):
            return marketaux_data

    out = []
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    for sym in symbols:
        try:
            params = {
                "q": sym,
                "pageSize": limit_per_symbol,
                "sortBy": "publishedAt",
                "language": "en",
                "from": start_date.strftime("%Y-%m-%d"),
                "to": end_date.strftime("%Y-%m-%d"),
                "apiKey": NEWSAPI_KEY
            }
            res = session.get("https://newsapi.org/v2/everything", params=params, timeout=8)
            data = res.json()
            if data.get("status") != "ok" or not data.get("articles"):
                raise ValueError("Empty news")
            articles = data["articles"]
            titles = [a.get("title", "")[:512] for a in articles]
            titles = [
                a.get("title","") + " " + a.get("description","")
                for a in articles
            ]

            sentiments = _finbert_batch(titles)
            
            news = []
            for i, a in enumerate(articles):
                published = a.get("publishedAt", "Unknown")
                try:
                    published = datetime.strptime(published[:19], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
                news.append({
                    "title": a.get("title", "Untitled"),
                    "link": a.get("url", ""),
                    "date": published,
                    "sentiment": sentiments[i],
                    "provider": a.get("source", {}).get("name", "NewsAPI"),
                    "image": a.get("urlToImage", "")
                })
            out.append({"symbol": sym, "news": news})
        except Exception as e:
            logger.warning(f"NewsAPI fallback for {sym}: {e}")
            alt = get_marketaux_news(sym) or get_alpha_news(sym) or get_yahoo_news_rss(sym)
            out.append({"symbol": sym, "news": alt})
    return out

# =========================
# Stock (Finnhub) + Fundamentals (FMP)
# =========================
def _normalize_range(range_value: str) -> str:
    key = (range_value or "3mo").strip().lower()
    mapping = {
        "1d": "1d",
        "5d": "5d",
        "1m": "1mo",
        "1mo": "1mo",
        "3m": "3mo",
        "3mo": "3mo",
        "6m": "6mo",
        "6mo": "6mo",
        "1y": "1y",
        "5y": "5y",
        "ytd": "ytd",
        "all": "max",
        "max": "max",
    }
    return mapping.get(key, "3mo")


def _history_params(range_value: str):
    key = (range_value or "3mo").strip().lower()
    if key == "1d":
        return {"period": "1d", "resolution": "5", "days": 1}
    if key == "5d":
        # Fetch wider calendar window, then keep 5 trading sessions.
        return {"period": "5d", "resolution": "30", "days": 9}
    if key in {"1m", "1mo"}:
        # 1M return baseline should reflect ~30 trading closes.
        return {"period": "1mo", "resolution": "D", "days": 45}
    if key in {"3m", "3mo"}:
        return {"period": "3mo", "resolution": "D", "days": 135}
    if key in {"6m", "6mo"}:
        return {"period": "6mo", "resolution": "D", "days": 270}
    if key == "1y":
        return {"period": "1y", "resolution": "D", "days": 365}
    if key == "5y":
        return {"period": "5y", "resolution": "D", "days": 365 * 5 + 10}
    if key == "ytd":
        now = datetime.utcnow()
        start = datetime(now.year, 1, 1)
        days = max(2, int((now - start).total_seconds() // 86400) + 2)
        return {"period": "ytd", "resolution": "D", "days": days}
    if key in {"all", "max"}:
        return {"period": "max", "resolution": "D", "days": 365 * 30}
    return {"period": "3mo", "resolution": "D", "days": 93}


def _finnhub_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if not FINNHUB_API_KEY:
        raise HTTPException(status_code=503, detail="FINNHUB_API_KEY is missing")
    query = dict(params or {})
    query["token"] = FINNHUB_API_KEY
    res = session.get(f"{FINNHUB_BASE_URL}{path}", params=query, timeout=12)
    if res.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Finnhub upstream error ({res.status_code})")
    payload = res.json()
    if isinstance(payload, dict) and payload.get("error"):
        raise HTTPException(status_code=502, detail=f"Finnhub error: {payload.get('error')}")
    return payload


def _fmp_get(path: str, params: Optional[Dict[str, Any]] = None):
    if not FMP_API_KEY:
        raise HTTPException(status_code=503, detail="FMP_API_KEY is missing")
    query = dict(params or {})
    query["apikey"] = FMP_API_KEY
    res = session.get(f"{FMP_BASE_URL}{path}", params=query, timeout=12)
    if res.status_code != 200:
        raise HTTPException(status_code=502, detail=f"FMP upstream error ({res.status_code})")
    return res.json()


def _fetch_finnhub_candles(symbol: str, range_value: str):
    params = _history_params(range_value)
    now = datetime.utcnow()
    end_ts = int(now.timestamp())
    start_ts = int((now - timedelta(days=params["days"])).timestamp())
    candles = _finnhub_get(
        "/stock/candle",
        {
            "symbol": symbol,
            "resolution": params["resolution"],
            "from": start_ts,
            "to": end_ts,
        },
    )
    if candles.get("s") != "ok":
        # Fallback for provider gaps (especially intraday off-market)
        if params["resolution"] != "D":
            candles = _finnhub_get(
                "/stock/candle",
                {
                    "symbol": symbol,
                    "resolution": "D",
                    "from": start_ts,
                    "to": end_ts,
                },
            )
        if candles.get("s") != "ok":
            return [], params["period"]

    rows = []
    intraday = params["period"] in {"1d", "5d"} and params["resolution"] != "D"
    for t_value, o, h, l, c, v in zip(
        candles.get("t", []),
        candles.get("o", []),
        candles.get("h", []),
        candles.get("l", []),
        candles.get("c", []),
        candles.get("v", []),
    ):
        dt = datetime.utcfromtimestamp(int(t_value))
        date_text = dt.strftime("%Y-%m-%d %H:%M") if intraday else dt.strftime("%Y-%m-%d")
        rows.append({
            "date": date_text,
            "open": safe_float(o),
            "high": safe_float(h),
            "low": safe_float(l),
            "close": safe_float(c),
            "volume": int(v or 0),
        })
    return rows, params["period"]


def _fetch_fmp_quote(symbol: str) -> Dict[str, Any]:
    rows = _fmp_get(f"/quote/{symbol}")
    row = rows[0] if isinstance(rows, list) and rows else {}
    return {
        "price": safe_float(row.get("price")),
        "previous_close": safe_float(row.get("previousClose")),
        "name": row.get("name") or row.get("symbol") or symbol,
    }


def _fetch_fmp_history(symbol: str, range_value: str):
    params = _history_params(range_value)
    period = params["period"]
    rows = []

    # Try intraday chart for short ranges first.
    if period in {"1d", "5d"}:
        interval = "5min" if period == "1d" else "30min"
        try:
            chart_rows = _fmp_get(f"/historical-chart/{interval}/{symbol}")
            if isinstance(chart_rows, list) and chart_rows:
                cutoff = datetime.utcnow() - timedelta(days=(1 if period == "1d" else 5))
                for item in chart_rows:
                    date_raw = str(item.get("date") or "")
                    try:
                        dt = datetime.fromisoformat(date_raw.replace("Z", ""))
                    except Exception:
                        continue
                    if dt < cutoff:
                        continue
                    rows.append({
                        "date": dt.strftime("%Y-%m-%d %H:%M"),
                        "open": safe_float(item.get("open")),
                        "high": safe_float(item.get("high")),
                        "low": safe_float(item.get("low")),
                        "close": safe_float(item.get("close")),
                        "volume": int(item.get("volume") or 0),
                    })
                rows.sort(key=lambda x: x["date"])
                if rows:
                    return rows, period
        except Exception:
            pass

    # Daily fallback.
    timeseries = params["days"] if period != "ytd" else 400
    timeseries = max(2, min(int(timeseries), 10000))
    payload = _fmp_get(f"/historical-price-full/{symbol}", {"timeseries": timeseries, "serietype": "line"})
    historical = payload.get("historical", []) if isinstance(payload, dict) else []
    for item in reversed(historical):
        rows.append({
            "date": str(item.get("date", "")),
            "open": safe_float(item.get("open") or item.get("close")),
            "high": safe_float(item.get("high") or item.get("close")),
            "low": safe_float(item.get("low") or item.get("close")),
            "close": safe_float(item.get("close")),
            "volume": int(item.get("volume") or 0),
        })
    return rows, period


def _symbol_variants(symbol: str) -> List[str]:
    base = str(symbol or "").strip().upper()
    candidates = [base]
    if "." in base:
        candidates.append(base.replace(".", "-"))
    if "-" in base:
        candidates.append(base.replace("-", "."))
    if base.endswith(".A"):
        candidates.append(base[:-2] + "-A")
    if base.endswith(".B"):
        candidates.append(base[:-2] + "-B")
    if base.endswith("-A"):
        candidates.append(base[:-2] + ".A")
    if base.endswith("-B"):
        candidates.append(base[:-2] + ".B")
    dedup = []
    seen = set()
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            dedup.append(item)
    return dedup


def _fetch_yfinance_history(symbol: str, range_value: str):
    key = (range_value or "3mo").strip().lower()
    ticker = yf.Ticker(symbol)
    if key == "1d":
        hist = ticker.history(period="1d", interval="5m", auto_adjust=False, prepost=False, actions=False)
        intraday = True
        period = "1d"
    elif key == "5d":
        hist = ticker.history(period="5d", interval="30m", auto_adjust=False, prepost=False, actions=False)
        intraday = True
        period = "5d"
    else:
        period = _normalize_range(range_value)
        hist = ticker.history(period=period, interval="1d", auto_adjust=False, prepost=False, actions=False)
        intraday = False

    rows = []
    for idx, r in hist.iterrows():
        rows.append({
            "date": idx.strftime("%Y-%m-%d %H:%M") if intraday else idx.strftime("%Y-%m-%d"),
            "open": safe_float(r.get("Open")),
            "high": safe_float(r.get("High")),
            "low": safe_float(r.get("Low")),
            "close": safe_float(r.get("Close")),
            "volume": int(r.get("Volume") or 0),
        })
    return rows, period


def _infer_previous_close_from_history(history_rows: List[Dict[str, Any]]) -> float:
    if not history_rows:
        return 0.0
    closes = [safe_float(row.get("close")) for row in history_rows]
    if len(closes) < 2:
        return 0.0

    last_date = str(history_rows[-1].get("date", ""))
    is_intraday = " " in last_date
    if not is_intraday:
        return safe_float(closes[-2])

    latest_day = last_date.split(" ")[0]
    first_idx_today = None
    for idx, row in enumerate(history_rows):
        row_date = str(row.get("date", ""))
        if row_date.startswith(latest_day):
            first_idx_today = idx
            break
    if first_idx_today is None or first_idx_today <= 0:
        return 0.0
    return safe_float(history_rows[first_idx_today - 1].get("close"))


def _fetch_yfinance_previous_close(symbol: str) -> float:
    try:
        ticker = yf.Ticker(symbol)
        daily = ticker.history(period="7d", interval="1d")
        if daily is None or daily.empty:
            return 0.0
        closes = [safe_float(v) for v in daily.get("Close", []) if safe_float(v) > 0]
        if len(closes) >= 2:
            return safe_float(closes[-2])
        return 0.0
    except Exception:
        return 0.0


def get_stock_data(symbol: str, range_value: str = "3mo"):
    try:
        provider = "Unknown"
        latest_price = 0.0
        previous_close = 0.0
        company_name = symbol
        history = []
        normalized_period = _normalize_range(range_value)
        quote_provider = None
        history_provider = None

        # 1) Prefer Finnhub quote/profile for latest price (if key allows)
        try:
            quote = _finnhub_get("/quote", {"symbol": symbol})
            profile = _finnhub_get("/stock/profile2", {"symbol": symbol})
            latest_price = safe_float(quote.get("c"))
            previous_close = safe_float(quote.get("pc"))
            company_name = str(profile.get("name") or symbol)
            quote_provider = "Finnhub"
        except Exception as finnhub_quote_error:
            logger.warning(f"Finnhub quote/profile unavailable for {symbol}: {finnhub_quote_error}")
            try:
                fmp_quote = _fetch_fmp_quote(symbol)
                latest_price = safe_float(fmp_quote.get("price"))
                previous_close = safe_float(fmp_quote.get("previous_close"))
                company_name = str(fmp_quote.get("name") or symbol)
                quote_provider = "FMP"
            except Exception as fmp_quote_error:
                logger.warning(f"FMP quote/profile unavailable for {symbol}: {fmp_quote_error}")

        # 2) Prefer Finnhub candles for history, then FMP, then Yahoo
        try:
            history, normalized_period = _fetch_finnhub_candles(symbol, range_value)
            history_provider = "Finnhub"
        except Exception as finnhub_candle_error:
            logger.warning(f"Finnhub fallback to FMP for {symbol}: {finnhub_candle_error}")
            try:
                history, normalized_period = _fetch_fmp_history(symbol, range_value)
                history_provider = "FMP"
            except Exception as fmp_error:
                logger.warning(f"FMP fallback to Yahoo for {symbol}: {fmp_error}")
                last_yf_error = None
                for yf_symbol in _symbol_variants(symbol):
                    try:
                        history, normalized_period = _fetch_yfinance_history(yf_symbol, range_value)
                        if history:
                            if not company_name or company_name == symbol:
                                company_name = yf_symbol
                            if previous_close <= 0:
                                previous_close = _fetch_yfinance_previous_close(yf_symbol) or _infer_previous_close_from_history(history)
                            history_provider = "YahooFallback"
                            break
                    except Exception as yf_error:
                        last_yf_error = yf_error
                        continue
                if not history and last_yf_error:
                    raise HTTPException(status_code=500, detail=f"Yahoo fallback error: {last_yf_error}")

        if quote_provider and history_provider:
            provider = quote_provider if quote_provider == history_provider else f"{quote_provider}+{history_provider}"
        elif quote_provider:
            provider = quote_provider
        elif history_provider:
            provider = history_provider
        else:
            provider = "Unavailable"

        if not history:
            raise HTTPException(status_code=404, detail=f"No market candles for {symbol}")

        df = pd.DataFrame(history)
        df = df.sort_values("date").reset_index(drop=True)
        df["return"] = df["close"].pct_change()
        df["sma20"] = df["close"].rolling(20).mean()
        df["sma50"] = df["close"].rolling(50).mean()
        df["volatility"] = df["return"].rolling(20).std()
        df["sharpe"] = df["return"].rolling(20).mean() / df["volatility"].replace(0, 1e-9)
        df["momentum"] = df["close"].pct_change(20)
        df["bb_mid"] = df["close"].rolling(20).mean()
        df["bb_std"] = df["close"].rolling(20).std()
        df["bb_upper"] = df["bb_mid"] + (df["bb_std"] * 2)
        df["bb_lower"] = df["bb_mid"] - (df["bb_std"] * 2)
        exp1 = df["close"].ewm(span=12, adjust=False).mean()
        exp2 = df["close"].ewm(span=26, adjust=False).mean()
        df["macd"] = exp1 - exp2
        df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = gain / loss.replace(0, 1e-9)
        df["rsi"] = 100 - (100 / (1 + rs))
        df = df.fillna(0)

        final_history = []
        for _, row in df.iterrows():
            final_history.append({
                "date": str(row["date"]),
                "open": safe_float(row["open"]),
                "high": safe_float(row["high"]),
                "low": safe_float(row["low"]),
                "close": safe_float(row["close"]),
                "volume": int(row["volume"] or 0),
                "sma20": safe_float(row["sma20"]),
                "sma50": safe_float(row["sma50"]),
                "volatility": safe_float(row["volatility"]),
                "rsi": safe_float(row["rsi"]),
                "momentum": safe_float(row["momentum"]),
                "bb_upper": safe_float(row["bb_upper"]),
                "bb_lower": safe_float(row["bb_lower"]),
                "macd": safe_float(row["macd"]),
                "macd_signal": safe_float(row["macd_signal"]),
                "sharpe": safe_float(row["sharpe"]),
            })

        latest_price = latest_price or safe_float(final_history[-1]["close"])
        inferred_previous_close = _infer_previous_close_from_history(final_history)
        if normalized_period in {"1d", "5d"} and inferred_previous_close > 0:
            previous_close = inferred_previous_close
        elif previous_close <= 0 and inferred_previous_close > 0:
            previous_close = inferred_previous_close

        return {
            "name": company_name,
            "price": latest_price,
            "previous_close": previous_close,
            "history": final_history,
            "range": normalized_period,
            "provider": provider,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"market data error: {e}")

# =========================
# Target Price + Recommendation (Self-contained)
# =========================
# --- REPLACE this function in main.py ---

def compute_recommendation(symbol: str,
                           window_days: int = 7,
                           news_path: str = "../news_clean_pipeline/data/clean/news_clean.csv",
                           prices_path: str = "../yahoo_finance_clean_pipeline/data/clean/clean_long.csv") -> Dict[str, Any]:
    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    def _score_linear(v: float, lo: float, hi: float) -> float:
        if hi <= lo:
            return 50.0
        return _clamp((v - lo) / (hi - lo), 0.0, 1.0) * 100.0

    def _sentiment_to_score(item: Dict[str, Any]) -> float:
        raw = item.get("sentiment_score")
        if raw is not None:
            try:
                return _clamp(float(raw), -1.0, 1.0)
            except Exception:
                pass
        label = str(item.get("sentiment", "Neutral")).strip().lower()
        if label in {"positive", "bullish"}:
            return 0.6
        if label in {"negative", "bearish"}:
            return -0.6
        return 0.0

    sym = symbol.upper()
    stock_data = get_stock_data(sym, "6m")
    history = stock_data.get("history", [])
    if not history:
        return {"error": f"no price data for {sym}"}

    closes = pd.Series([safe_float(h.get("close")) for h in history if safe_float(h.get("close")) > 0])
    if closes.empty:
        return {"error": f"no price data for {sym}"}
    current_price = safe_float(stock_data.get("price")) or safe_float(closes.iloc[-1])

    # Technical indicators
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    ma50 = closes.rolling(50).mean()
    ma200 = closes.rolling(200).mean() if len(closes) >= 200 else closes.rolling(min(100, max(20, len(closes)))).mean()

    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss.replace(0, 1e-9)
    rsi_series = 100 - (100 / (1 + rs))

    trend = float((ma50.iloc[-1] - ma200.iloc[-1]) / max(1e-9, ma200.iloc[-1])) if not pd.isna(ma50.iloc[-1]) and not pd.isna(ma200.iloc[-1]) else 0.0
    momentum_30 = float((closes.iloc[-1] - closes.iloc[max(0, len(closes) - 30)]) / max(1e-9, closes.iloc[max(0, len(closes) - 30)]))
    momentum_60 = float((closes.iloc[-1] - closes.iloc[max(0, len(closes) - 60)]) / max(1e-9, closes.iloc[max(0, len(closes) - 60)]))
    volatility = float(closes.pct_change().dropna().rolling(20).std().iloc[-1]) if len(closes) > 21 else 0.0

    latest_rsi = safe_float(rsi_series.iloc[-1])
    latest_macd = safe_float(macd_line.iloc[-1])
    latest_macd_signal = safe_float(macd_signal.iloc[-1])
    latest_ma50 = safe_float(ma50.iloc[-1])
    latest_ma200 = safe_float(ma200.iloc[-1])

    # News sentiment
    news_rows = get_newsapi_news_batch([sym], limit_per_symbol=20, days_back=window_days)
    news_items = (news_rows[0].get("news", []) if news_rows else [])
    news_scores = [_sentiment_to_score(n) for n in news_items]
    avg_sent = float(sum(news_scores) / len(news_scores)) if news_scores else 0.0
    news_count = len(news_scores)
    bullish_count = len([x for x in news_scores if x > 0.2])
    bearish_count = len([x for x in news_scores if x < -0.2])
    neutral_count = max(0, news_count - bullish_count - bearish_count)
    bullish_pct = round((bullish_count / news_count) * 100, 1) if news_count else 0.0
    neutral_pct = round((neutral_count / news_count) * 100, 1) if news_count else 0.0
    bearish_pct = round((bearish_count / news_count) * 100, 1) if news_count else 0.0

    # Fundamentals (support confidence + context)
    profile_row = {}
    ratios_row = {}
    metrics_row = {}
    growth_row = {}
    try:
        profile = _fmp_get(f"/profile/{sym}")
        ratios = _fmp_get(f"/ratios-ttm/{sym}")
        metrics = _fmp_get(f"/key-metrics-ttm/{sym}")
        growth = _fmp_get(f"/financial-growth/{sym}", {"limit": 1})
        profile_row = profile[0] if isinstance(profile, list) and profile else {}
        ratios_row = ratios[0] if isinstance(ratios, list) and ratios else {}
        metrics_row = metrics[0] if isinstance(metrics, list) and metrics else {}
        growth_row = growth[0] if isinstance(growth, list) and growth else {}
    except Exception as fmp_error:
        logger.warning(f"FMP fundamentals unavailable for {sym}: {fmp_error}")

    pe_ratio = safe_float(ratios_row.get("peRatioTTM") or profile_row.get("pe"))
    roe = safe_float(ratios_row.get("returnOnEquityTTM") or metrics_row.get("roeTTM"))
    debt_to_equity = safe_float(ratios_row.get("debtEquityRatioTTM") or metrics_row.get("debtToEquityTTM"))
    revenue_growth = safe_float(growth_row.get("revenueGrowth"))
    eps_growth = safe_float(growth_row.get("epsgrowth") or growth_row.get("epsGrowth"))
    if abs(revenue_growth) > 1.5:
        revenue_growth /= 100.0
    if abs(eps_growth) > 1.5:
        eps_growth /= 100.0

    # Weighted scoring model
    rsi_score = 100.0 - abs(60.0 - latest_rsi) * 1.6
    macd_score = _score_linear(latest_macd - latest_macd_signal, -1.5, 1.5)
    cross_score = 75.0 if latest_ma50 > latest_ma200 else 35.0
    trend_score = _score_linear(trend, -0.20, 0.20)
    technical_score = _clamp((rsi_score * 0.25) + (macd_score * 0.25) + (cross_score * 0.25) + (trend_score * 0.25), 0.0, 100.0)

    sentiment_score = _score_linear(avg_sent, -1.0, 1.0)
    momentum_score = _score_linear((momentum_30 * 0.6) + (momentum_60 * 0.4), -0.25, 0.35)
    volatility_risk_score = 100.0 - _score_linear(volatility, 0.008, 0.055)

    weighted_score = (
        (technical_score * 0.40) +
        (sentiment_score * 0.30) +
        (momentum_score * 0.20) +
        (volatility_risk_score * 0.10)
    )
    ai_score = float(round(_clamp(weighted_score, 0.0, 100.0), 2))

    # Recommendation bands (requested thresholds)
    if ai_score > 80:
        reco = "Strong Buy"
    elif ai_score >= 60:
        reco = "Buy"
    elif ai_score >= 40:
        reco = "Hold"
    elif ai_score >= 20:
        reco = "Sell"
    else:
        reco = "Strong Sell"

    # Forecast + targets
    expected_30d = _clamp(
        ((ai_score - 50.0) / 50.0) * 0.10 + (momentum_30 * 0.35) + (avg_sent * 0.07) - (volatility * 0.20),
        -0.25,
        0.25,
    )
    target_mean = current_price * (1 + expected_30d)
    target_high = target_mean * 1.10
    target_low = target_mean * 0.90

    if volatility >= 0.04:
        risk_level = "High"
    elif volatility >= 0.022:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    agreement = 100.0 - (max(technical_score, sentiment_score, momentum_score, volatility_risk_score) - min(technical_score, sentiment_score, momentum_score, volatility_risk_score))
    data_points = sum([
        1 if pe_ratio > 0 else 0,
        1 if roe != 0 else 0,
        1 if debt_to_equity != 0 else 0,
        1 if revenue_growth != 0 or eps_growth != 0 else 0,
        1 if news_count > 0 else 0,
    ])
    confidence = round(_clamp(0.45 + (agreement / 100.0) * 0.25 + data_points * 0.05 + min(news_count, 20) * 0.008, 0.35, 0.95), 2)

    forecast_points = []
    for i in range(1, 11):
        step = i / 10.0
        projected = current_price * (1 + expected_30d * step)
        forecast_points.append({"label": f"D+{i*3}", "price": round(projected, 2)})

    upside_pct = ((target_mean - current_price) / current_price * 100) if current_price else 0.0

    return {
        "symbol": sym,
        "current_price": round(current_price, 2),
        "target_price_mean": round(target_mean, 2),
        "target_price_high": round(target_high, 2),
        "target_price_low": round(target_low, 2),
        "upside_pct": round(upside_pct, 2),
        "sentiment_avg": round(avg_sent, 3),
        "trend": round(trend, 3),
        "expected_diff": round(expected_30d, 3),
        "recommendation": reco,
        "confidence": confidence,
        "ai_score": ai_score,
        "ai_recommendation": reco.upper(),
        "risk_level": risk_level,
        "window_days": window_days,
        "news_count": int(news_count),
        "lstm_prediction": None,
        "weights": {
            "technical": 40,
            "news_sentiment": 30,
            "momentum": 20,
            "volatility_risk": 10,
        },
        "signals": {
            "technical_score": round(technical_score, 2),
            "news_sentiment_score": round(sentiment_score, 2),
            "momentum_score": round(momentum_score, 2),
            "volatility_risk_score": round(volatility_risk_score, 2),
            "news_sentiment_label": "Bullish" if avg_sent > 0.2 else ("Bearish" if avg_sent < -0.2 else "Neutral"),
            "forecast_30d_pct": round(expected_30d * 100.0, 2),
        },
        "technical_indicators": {
            "rsi": round(latest_rsi, 2),
            "macd": round(latest_macd, 4),
            "macd_signal": round(latest_macd_signal, 4),
            "ma50": round(latest_ma50, 2),
            "ma200": round(latest_ma200, 2),
            "golden_cross": bool(latest_ma50 > latest_ma200),
            "trend_label": "Bullish" if latest_ma50 > latest_ma200 else "Bearish",
        },
        "news_sentiment_distribution": {
            "bullish": bullish_pct,
            "neutral": neutral_pct,
            "bearish": bearish_pct,
        },
        "forecast": {
            "period_days": 30,
            "predicted_return_pct": round(expected_30d * 100.0, 2),
            "points": forecast_points,
        },
        "fundamentals": {
            "peRatio": pe_ratio,
            "roe": roe,
            "debtToEquity": debt_to_equity,
            "revenueGrowth": revenue_growth,
            "epsGrowth": eps_growth,
        },
        "sources": ["Finnhub", "FinancialModelingPrep", "MarketAux/NewsAPI", "Internal Technical Model"],
    }

# ✅ เพิ่ม API สำหรับ AI Stock Picker ตรงนี้
@app.get("/ai-picker")
def ai_stock_picker(
    strategy: str = Query("BALANCED", description="AGGRESSIVE | BALANCED | DEFENSIVE"),
    limit: int = Query(5, ge=1, le=50)
):
    if not HAS_AI_PICKER:
        raise HTTPException(status_code=503, detail="AI Picker module offline")
    
    try:
        strategy_raw = str(strategy or "").strip().upper()
        strategy_alias = {
            "GROWTH": "AGGRESSIVE",
            "MOMENTUM": "AGGRESSIVE",
            "AI_TREND": "AGGRESSIVE",
            "AI-TREND": "AGGRESSIVE",
            "VALUE": "DEFENSIVE",
            "LOW_RISK": "DEFENSIVE",
            "LOW-RISK": "DEFENSIVE",
        }
        normalized_strategy = strategy_alias.get(strategy_raw, strategy_raw)
        if normalized_strategy not in {"AGGRESSIVE", "BALANCED", "DEFENSIVE"}:
            normalized_strategy = "BALANCED"

        picks = get_ai_picks(normalized_strategy, limit)
        return {
            "strategy": normalized_strategy,
            "items": picks,
            "count": len(picks),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logging.error(f"Error in /ai-picker: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
# =========================
# Background Cache (news)
# =========================
def background_fetch(interval=600):
    while True:
        logger.info("Background: refreshing cache...")

        with cache_lock:
            symbols_to_refresh = list(cache.keys())  # ดึงหุ้นที่เคยค้น

        for sym in symbols_to_refresh:
            try:
                data = get_alpha_news(sym)
                if data:
                    with cache_lock:
                        cache[sym]["time"] = datetime.now()
                        cache[sym]["data"]["news"] = data
            except Exception as e:
                logger.warning(f"Cache update failed for {sym}: {e}")

        time.sleep(interval)

threading.Thread(target=background_fetch, daemon=True).start()

# =========================
# Endpoints
# =========================
@app.get("/health")
def health():
    return {"ok": True, "risk_module": HAS_RISK}


@app.get("/news/providers")
def news_providers():
    return {
        "primary": "MarketAux" if bool(MARKETAUX_API_KEY) else ("NewsAPI" if bool(NEWSAPI_KEY) else "Yahoo/Alpha fallback"),
        "marketaux_enabled": bool(MARKETAUX_API_KEY),
        "newsapi_enabled": bool(NEWSAPI_KEY),
        "alpha_enabled": bool(ALPHA_VANTAGE_API_KEY),
        "finnhub_enabled": bool(FINNHUB_API_KEY),
        "fmp_enabled": bool(FMP_API_KEY),
    }


def _mask_key(key: Optional[str]) -> str:
    raw = str(key or "")
    if len(raw) <= 8:
        return "*" * len(raw)
    return f"{raw[:4]}...{raw[-4:]}"


def _default_active_symbols(limit: int = 5) -> List[str]:
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT ticker, MAX(last_updated) AS last_ts
                    FROM prices
                    WHERE ticker IS NOT NULL AND ticker <> ''
                    GROUP BY ticker
                    ORDER BY last_ts DESC
                    LIMIT :limit
                    """
                ),
                {"limit": int(limit)},
            ).mappings().all()
        symbols = []
        for row in rows:
            ticker = str(row.get("ticker") or "").strip().upper()
            if ticker and ticker not in symbols:
                symbols.append(ticker)
        return symbols
    except Exception as e:
        logger.warning(f"Unable to load active symbols from DB: {e}")
        return []


@app.get("/providers/status")
@app.get("/api/providers/status")
def providers_status():
    sample_symbol = (_default_active_symbols(1) or ["SPY"])[0]
    out: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "sample_symbol": sample_symbol,
        "providers": {
            "finnhub": {
                "configured": bool(FINNHUB_API_KEY),
                "key_masked": _mask_key(FINNHUB_API_KEY),
                "status": "unknown",
            },
            "fmp": {
                "configured": bool(FMP_API_KEY),
                "key_masked": _mask_key(FMP_API_KEY),
                "status": "unknown",
            },
        },
    }

    # Finnhub capability check: quote + candle
    try:
        if not FINNHUB_API_KEY:
            raise HTTPException(status_code=503, detail="missing FINNHUB_API_KEY")
        now_ts = int(datetime.utcnow().timestamp())
        from_ts = int((datetime.utcnow() - timedelta(days=3)).timestamp())
        query = {"symbol": sample_symbol, "resolution": "D", "from": from_ts, "to": now_ts, "token": FINNHUB_API_KEY}
        quote_res = session.get(f"{FINNHUB_BASE_URL}/quote", params={"symbol": sample_symbol, "token": FINNHUB_API_KEY}, timeout=10)
        candle_res = session.get(f"{FINNHUB_BASE_URL}/stock/candle", params=query, timeout=10)
        out["providers"]["finnhub"] = {
            **out["providers"]["finnhub"],
            "status": "ok" if quote_res.status_code == 200 and candle_res.status_code == 200 else "error",
            "quote_http": quote_res.status_code,
            "candle_http": candle_res.status_code,
            "rate_limit": quote_res.headers.get("X-RateLimit-Remaining") or candle_res.headers.get("X-RateLimit-Remaining"),
            "rate_reset": quote_res.headers.get("X-RateLimit-Reset") or candle_res.headers.get("X-RateLimit-Reset"),
            "quote_error": (quote_res.json().get("error") if quote_res.headers.get("content-type", "").startswith("application/json") else None),
            "candle_state": (candle_res.json().get("s") if candle_res.headers.get("content-type", "").startswith("application/json") else None),
        }
    except Exception as e:
        out["providers"]["finnhub"] = {
            **out["providers"]["finnhub"],
            "status": "error",
            "error": str(e),
        }

    # FMP capability check: quote + profile + ratios
    try:
        if not FMP_API_KEY:
            raise HTTPException(status_code=503, detail="missing FMP_API_KEY")
        base_params = {"apikey": FMP_API_KEY}
        quote_res = session.get(f"{FMP_BASE_URL}/quote/{sample_symbol}", params=base_params, timeout=10)
        profile_res = session.get(f"{FMP_BASE_URL}/profile/{sample_symbol}", params=base_params, timeout=10)
        ratios_res = session.get(f"{FMP_BASE_URL}/ratios-ttm/{sample_symbol}", params=base_params, timeout=10)
        out["providers"]["fmp"] = {
            **out["providers"]["fmp"],
            "status": "ok" if quote_res.status_code == 200 and profile_res.status_code == 200 and ratios_res.status_code == 200 else "error",
            "quote_http": quote_res.status_code,
            "profile_http": profile_res.status_code,
            "ratios_http": ratios_res.status_code,
            "rate_limit": quote_res.headers.get("X-RateLimit-Remaining") or profile_res.headers.get("X-RateLimit-Remaining"),
            "rate_reset": quote_res.headers.get("X-RateLimit-Reset") or profile_res.headers.get("X-RateLimit-Reset"),
        }
    except Exception as e:
        out["providers"]["fmp"] = {
            **out["providers"]["fmp"],
            "status": "error",
            "error": str(e),
        }

    return out

# ข่าวหลายตัว
@app.get("/news")
def news_endpoint(symbols: str, days_back: int = 7):
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=400, detail="No valid symbols")
    return get_newsapi_news_batch(syms, 10, days_back)

@app.get("/api/news")
def news_api_compat():
    default_symbols = _default_active_symbols(3)
    if not default_symbols:
        raise HTTPException(status_code=503, detail="No active symbols available for news feed")
    data = get_newsapi_news_batch(default_symbols, 3, 7)
    merged = []
    for row in data:
        merged.extend(row.get("news", []))
    return {"news": merged[:9], "symbols": default_symbols}


@app.get("/market-sentiment")
@app.get("/api/market-sentiment")
def market_sentiment_endpoint(force_refresh: bool = Query(False, description="Bypass cache (10m)")):
    if not HAS_MARKET_SENTIMENT:
        raise HTTPException(status_code=503, detail="Market sentiment service unavailable")
    try:
        return compute_market_sentiment(force_refresh=force_refresh)
    except Exception as e:
        logger.error(f"Error in /market-sentiment: {e}")
        raise HTTPException(status_code=500, detail="Failed to compute market sentiment")


class AIAdvisorContext(BaseModel):
    watchlist: List[str] = Field(default_factory=list)
    portfolio: List[Dict[str, Any]] = Field(default_factory=list)
    sentiment: Optional[float] = None
    recent_searches: List[str] = Field(default_factory=list)
    risk_profile: Optional[str] = None
    selected_stock: Optional[str] = None
    chat_state: Dict[str, Any] = Field(default_factory=dict)


class AIAdvisorRequest(BaseModel):
    question: str
    context: AIAdvisorContext = Field(default_factory=AIAdvisorContext)


class AISummaryRequest(BaseModel):
    context: AIAdvisorContext = Field(default_factory=AIAdvisorContext)


class PortfolioInsightRequest(BaseModel):
    holdings: List[Dict[str, Any]] = Field(default_factory=list)
    watchlist: List[str] = Field(default_factory=list)


class PortfolioPositionCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    shares: float = Field(..., gt=0)
    average_buy_price: float = Field(..., gt=0)
    purchase_date: str = Field(..., min_length=8, max_length=16)


class PortfolioPositionUpdate(BaseModel):
    symbol: Optional[str] = Field(default=None, min_length=1, max_length=16)
    shares: Optional[float] = Field(default=None, gt=0)
    average_buy_price: Optional[float] = Field(default=None, gt=0)
    purchase_date: Optional[str] = Field(default=None, min_length=8, max_length=16)


def _extract_user_id_from_authorization(auth_header: Optional[str]) -> int:
    if not auth_header or not str(auth_header).startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = str(auth_header).split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    try:
        parts = token.split(".")
        if len(parts) < 2:
            raise ValueError("Malformed JWT")
        payload_b64 = parts[1]
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
        user_id = int(payload.get("id") or payload.get("user_id") or 0)
        if user_id <= 0:
            raise ValueError("Missing user id in JWT payload")
        return user_id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token payload: {e}")


def _portfolio_profile_defaults(symbol: str) -> Dict[str, Any]:
    return {
        "company": symbol,
        "sector": "Other",
        "beta": 1.0,
    }


def _get_portfolio_profile(symbol: str) -> Dict[str, Any]:
    sym = str(symbol or "").upper().strip()
    cached = portfolio_meta_cache.get(sym)
    if cached and (time.time() - float(cached.get("ts", 0))) < PORTFOLIO_META_CACHE_TTL:
        return cached.get("data", _portfolio_profile_defaults(sym))

    profile = _portfolio_profile_defaults(sym)
    try:
        fmp_profile = _fmp_get(f"/profile/{sym}")
        row = fmp_profile[0] if isinstance(fmp_profile, list) and fmp_profile else {}
        profile = {
            "company": row.get("companyName") or row.get("name") or sym,
            "sector": row.get("sector") or "Other",
            "beta": safe_float(row.get("beta")) or 1.0,
        }
    except Exception:
        try:
            fh_profile = _finnhub_get("/stock/profile2", {"symbol": sym})
            profile = {
                "company": fh_profile.get("name") or sym,
                "sector": fh_profile.get("finnhubIndustry") or "Other",
                "beta": 1.0,
            }
        except Exception:
            pass

    portfolio_meta_cache[sym] = {"ts": time.time(), "data": profile}
    return profile


def _get_portfolio_quote(symbol: str) -> Dict[str, float]:
    sym = str(symbol or "").upper().strip()
    cached = portfolio_quote_cache.get(sym)
    if cached and (time.time() - float(cached.get("ts", 0))) < PORTFOLIO_QUOTE_CACHE_TTL:
        return cached.get("data", {"price": 0.0, "previous_close": 0.0, "daily_change_pct": 0.0})

    price = 0.0
    previous_close = 0.0
    try:
        q = _finnhub_get("/quote", {"symbol": sym})
        price = safe_float(q.get("c"))
        previous_close = safe_float(q.get("pc"))
    except Exception:
        data = get_stock_data(sym, "1d")
        price = safe_float(data.get("price"))
        previous_close = safe_float(data.get("previous_close"))

    daily_change_pct = ((price - previous_close) / previous_close * 100.0) if previous_close > 0 else 0.0
    payload = {
        "price": round(price, 4),
        "previous_close": round(previous_close, 4),
        "daily_change_pct": round(daily_change_pct, 4),
    }
    portfolio_quote_cache[sym] = {"ts": time.time(), "data": payload}
    return payload


def _get_cached_ai_score(symbol: str) -> float:
    sym = str(symbol or "").upper().strip()
    cached = portfolio_ai_cache.get(sym)
    if cached and (time.time() - float(cached.get("ts", 0))) < PORTFOLIO_AI_CACHE_TTL:
        return float(cached.get("value", 50.0))
    try:
        reco = compute_recommendation(sym, window_days=14)
        score = safe_float(reco.get("ai_score"))
        if score <= 0:
            score = 50.0
    except Exception:
        score = 50.0
    portfolio_ai_cache[sym] = {"ts": time.time(), "value": score}
    return float(score)


def _portfolio_range_to_stock_range(range_value: str) -> str:
    key = str(range_value or "1m").lower()
    if key in {"1m", "1mo"}:
        return "1m"
    if key in {"3m", "3mo"}:
        return "3m"
    if key in {"6m", "6mo"}:
        return "6m"
    return "1y"


def _calculate_portfolio_overview(user_id: int, range_value: str = "1m") -> Dict[str, Any]:
    with SessionLocal() as db:
        positions: List[PortfolioPosition] = (
            db.query(PortfolioPosition)
            .filter(PortfolioPosition.user_id == user_id)
            .order_by(PortfolioPosition.created_at.asc())
            .all()
        )

    if not positions:
        return {
            "summary": {
                "totalValue": 0.0,
                "dailyChange": 0.0,
                "dailyChangePct": 0.0,
                "totalGainLoss": 0.0,
                "totalGainPct": 0.0,
                "holdingsCount": 0,
                "diversificationScore": 0,
            },
            "rows": [],
            "allocation": [],
            "sectorExposure": [],
            "performance": [],
            "risk": {"score": 0, "level": "Low"},
            "insight": {
                "summary": "No positions yet.",
                "dominant_sector": "N/A",
                "diversification": "N/A",
                "suggestions": ["Add your first position to begin portfolio analysis."],
            },
        }

    rows = []
    total_value = 0.0
    total_cost = 0.0
    total_daily_change = 0.0
    sector_value: Dict[str, float] = defaultdict(float)
    weighted_beta_numerator = 0.0
    timeseries_sum: Dict[str, float] = defaultdict(float)
    all_returns: List[float] = []
    dominant_sector = "Other"

    stock_range = _portfolio_range_to_stock_range(range_value)

    for p in positions:
        symbol = str(p.symbol or "").upper().strip()
        shares = float(p.shares or 0)
        avg_price = float(p.average_buy_price or 0)
        if not symbol or shares <= 0:
            continue

        profile = _get_portfolio_profile(symbol)
        quote = _get_portfolio_quote(symbol)
        current_price = safe_float(quote.get("price"))
        previous_close = safe_float(quote.get("previous_close"))

        market_value = shares * current_price
        cost_value = shares * avg_price
        gain_loss = market_value - cost_value
        gain_pct = ((current_price - avg_price) / avg_price * 100.0) if avg_price > 0 else 0.0
        daily_change = (current_price - previous_close) * shares if previous_close > 0 else 0.0
        ai_score = _get_cached_ai_score(symbol)

        total_value += market_value
        total_cost += cost_value
        total_daily_change += daily_change
        sector_name = str(profile.get("sector") or "Other")
        sector_value[sector_name] += market_value
        weighted_beta_numerator += safe_float(profile.get("beta") or 1.0) * market_value

        try:
            history = get_stock_data(symbol, stock_range).get("history", [])
        except Exception:
            history = []
        prev_close = None
        for point in history:
            date_key = str(point.get("date", ""))[:10]
            close = safe_float(point.get("close"))
            if not date_key or close <= 0:
                continue
            timeseries_sum[date_key] += close * shares
            if prev_close and prev_close > 0:
                all_returns.append((close - prev_close) / prev_close)
            prev_close = close

        rows.append({
            "id": p.id,
            "symbol": symbol,
            "company": profile.get("company") or symbol,
            "sector": sector_name,
            "shares": round(shares, 4),
            "avgPrice": round(avg_price, 4),
            "purchaseDate": p.purchase_date,
            "currentPrice": round(current_price, 4),
            "previousClose": round(previous_close, 4),
            "dailyChange": round(daily_change, 4),
            "dailyChangePct": round(safe_float(quote.get("daily_change_pct")), 4),
            "marketValue": round(market_value, 4),
            "gainLoss": round(gain_loss, 4),
            "gainPct": round(gain_pct, 4),
            "aiScore": round(ai_score, 2),
        })

    rows.sort(key=lambda x: x["marketValue"], reverse=True)
    if not rows:
        return {
            "summary": {
                "totalValue": 0.0,
                "dailyChange": 0.0,
                "dailyChangePct": 0.0,
                "totalGainLoss": 0.0,
                "totalGainPct": 0.0,
                "holdingsCount": 0,
                "diversificationScore": 0,
            },
            "rows": [],
            "allocation": [],
            "sectorExposure": [],
            "performance": [],
            "risk": {"score": 0, "level": "Low"},
            "insight": {
                "summary": "No active positions found.",
                "dominant_sector": "N/A",
                "diversification": "N/A",
                "suggestions": ["Add your first position to begin portfolio analysis."],
            },
        }

    total_gain_loss = total_value - total_cost
    total_gain_pct = ((total_value - total_cost) / total_cost * 100.0) if total_cost > 0 else 0.0
    daily_change_pct = (total_daily_change / (total_value - total_daily_change) * 100.0) if (total_value - total_daily_change) > 0 else 0.0

    allocation = []
    for symbol_group in rows:
        pct = (symbol_group["marketValue"] / total_value * 100.0) if total_value > 0 else 0.0
        allocation.append({
            "name": symbol_group["symbol"],
            "value": round(pct, 2),
        })

    sector_exposure = []
    for s_name, s_value in sector_value.items():
        pct = (s_value / total_value * 100.0) if total_value > 0 else 0.0
        sector_exposure.append({"name": s_name, "value": round(pct, 2)})
    sector_exposure.sort(key=lambda x: x["value"], reverse=True)
    if sector_exposure:
        dominant_sector = sector_exposure[0]["name"]

    performance = [{"label": d, "value": round(v, 2)} for d, v in sorted(timeseries_sum.items(), key=lambda x: x[0])]
    if len(performance) > 120:
        step = max(1, len(performance) // 120)
        performance = performance[::step]

    unique_sectors = len(sector_exposure)
    diversification_score = int(max(0, min(100, round((unique_sectors / max(1, min(6, len(rows)))) * 100))))
    concentration = sector_exposure[0]["value"] if sector_exposure else 100.0
    volatility = 0.0
    if all_returns:
        mean_r = sum(all_returns) / len(all_returns)
        variance = sum((r - mean_r) ** 2 for r in all_returns) / len(all_returns)
        volatility = (variance ** 0.5) * 100
    beta_exposure = (weighted_beta_numerator / total_value) if total_value > 0 else 1.0

    vol_score = max(0.0, min(100.0, volatility * 8.0))
    concentration_score = max(0.0, min(100.0, concentration))
    beta_score = max(0.0, min(100.0, abs(beta_exposure - 1.0) * 100.0))
    risk_score = int(round((vol_score * 0.4) + (concentration_score * 0.4) + (beta_score * 0.2)))
    risk_level = "Low" if risk_score < 35 else ("Medium" if risk_score < 70 else "High")
    diversification_label = "High" if diversification_score >= 70 else ("Moderate" if diversification_score >= 40 else "Low")

    suggestions = []
    if concentration > 45:
        suggestions.append(f"Reduce {dominant_sector} exposure; current allocation is {concentration:.1f}%.")
    if beta_exposure > 1.2:
        suggestions.append("Portfolio beta is above market. Add lower-beta ETFs for stability.")
    if diversification_score < 45:
        suggestions.append("Diversification is low. Add holdings from uncorrelated sectors.")
    if not suggestions:
        suggestions = [
            "Portfolio allocation looks balanced. Rebalance monthly to maintain risk profile.",
            "Monitor drawdown and keep a portion in defensive assets.",
        ]

    return {
        "summary": {
            "totalValue": round(total_value, 2),
            "dailyChange": round(total_daily_change, 2),
            "dailyChangePct": round(daily_change_pct, 2),
            "totalGainLoss": round(total_gain_loss, 2),
            "totalGainPct": round(total_gain_pct, 2),
            "holdingsCount": len(rows),
            "diversificationScore": diversification_score,
        },
        "rows": rows,
        "allocation": allocation,
        "sectorExposure": sector_exposure,
        "performance": performance,
        "risk": {"score": risk_score, "level": risk_level, "betaExposure": round(beta_exposure, 2), "volatility": round(volatility, 2)},
        "insight": {
            "summary": (
                f"Portfolio diversification: {diversification_label}. "
                f"Dominant sector: {dominant_sector}. "
                f"Current risk level: {risk_level}."
            ),
            "dominant_sector": dominant_sector,
            "diversification": diversification_label,
            "suggestions": suggestions,
        },
    }


def _parse_symbol_from_question(question: str, context: AIAdvisorContext) -> Optional[str]:
    q = (question or "").upper().replace("$", " ")
    raw_tokens = [w.strip(" ,.?/\\|()[]{}:;!") for w in q.split()]
    stopwords = {
        "IS", "ARE", "WAS", "WERE", "A", "AN", "THE", "THIS", "THAT", "THESE", "THOSE",
        "WHAT", "HOW", "ABOUT", "WITH", "FOR", "SHOW", "COMPARE", "VS", "VERSUS",
        "STOCK", "STOCKS", "MARKET", "SECTOR", "SECTORS", "RISK", "NEWS", "TODAY", "NOW",
    }
    candidates = []
    for token in raw_tokens:
        if not token:
            continue
        compact = "".join(ch for ch in token if ch.isalnum() or ch in {".", "-"})
        if compact in stopwords:
            continue
        if 2 <= len(compact) <= 10:
            candidates.append(compact)
    if candidates:
        return normalize_symbol(candidates[0])
    return normalize_symbol_list(context.watchlist or [])[0] if (context.watchlist or []) else None


def _extract_ticker_candidates(question: str) -> List[str]:
    q = str(question or "").upper()
    candidates = re.findall(r"\b[A-Z]{2,5}(?:[.-][A-Z])?\b", q)
    stopwords = {
        "VS", "AND", "OR", "THE", "THIS", "THAT", "WITH", "FOR", "WHAT", "ABOUT",
        "SHOW", "TOP", "RISK", "NEWS", "MARKET", "SECTOR", "SECTORS", "STOCK",
        "STOCKS", "TODAY", "NOW", "BEST", "IS", "ARE", "WAS", "WERE", "AN",
    }
    out = []
    seen = set()
    for c in candidates:
        if c in stopwords:
            continue
        if c in seen:
            continue
        seen.add(c)
        out.append(c)
    return out


def _extract_comparison_symbols(question: str, context: AIAdvisorContext) -> List[str]:
    explicit = normalize_symbol_list(_extract_ticker_candidates(question))
    if len(explicit) >= 2:
        return explicit[:2]

    state = context.chat_state or {}
    last_symbol = str(state.get("last_symbol") or "").upper().strip()
    if len(explicit) == 1 and last_symbol and explicit[0] != last_symbol:
        return [last_symbol, explicit[0]]

    last_symbols = [str(s).upper().strip() for s in (state.get("last_symbols") or []) if str(s).strip()]
    if len(explicit) == 1 and last_symbols:
        other = next((s for s in last_symbols if s != explicit[0]), None)
        if other:
            return [explicit[0], other]

    return explicit[:2]


def _sentiment_label(score: float) -> str:
    if score >= 75:
        return "Extreme Greed"
    if score >= 56:
        return "Greed"
    if score >= 45:
        return "Neutral"
    if score >= 25:
        return "Fear"
    return "Extreme Fear"


def _build_price_chart(symbol: str) -> Dict[str, Any]:
    try:
        stock = get_stock_data(symbol, "1m")
        history = stock.get("history", [])[-20:]
        points = [{"label": str(i + 1), "value": round(float(h.get("close", 0)), 2)} for i, h in enumerate(history)]
        return {"title": f"{symbol} price (1M)", "points": points}
    except Exception:
        return {"title": f"{symbol} price (1M)", "points": []}


def _build_sentiment_chart(symbol: str) -> Dict[str, Any]:
    try:
        news_rows = get_newsapi_news_batch([symbol], limit_per_symbol=6, days_back=7)
        items = (news_rows[0].get("news", []) if news_rows else [])[:6]
        points = []
        for i, n in enumerate(items):
            score = n.get("sentiment_score")
            if score is None:
                score = 0.0
            points.append({"label": str(i + 1), "value": round(float(score), 3)})
        return {"title": f"{symbol} sentiment (recent news)", "points": points}
    except Exception:
        return {"title": f"{symbol} sentiment (recent news)", "points": []}


def _classify_intent(question: str) -> str:
    q = (question or "").strip().lower()
    if not q:
        return "unclear_query"
    picker_terms = [
        "top stocks", "top names", "stock picks", "leaders", "laggards", "momentum stocks",
        "strongest stocks", "best ideas", "show stocks", "show names", "show top", "those names",
        "หุ้นเด่น", "หุ้นนำ", "หุ้นโมเมนตัม", "รายชื่อหุ้น", "หุ้นตัวไหน", "ตัวไหนเด่น", "ชื่อหุ้น",
    ]
    sector_terms = [
        "sector", "sectors", "industry", "this sector", "that sector", "in this sector",
        "กลุ่ม", "เซกเตอร์", "หมวด", "กลุ่มนี้", "เซกเตอร์นี้",
    ]
    why_terms = ["why", "แข็ง", "อ่อน", "strong", "weak", "ทำไม"]
    attractiveness_terms = ["attractive", "น่าสนใจ", "ควรลงทุน", "overall", "ภาพรวม"]

    if any(t in q for t in picker_terms) and any(s in q for s in sector_terms):
        return "sector_stock_picker"
    if any(t in q for t in why_terms) and any(s in q for s in sector_terms):
        return "sector_explanation"
    if any(t in q for t in attractiveness_terms) and any(s in q for s in sector_terms):
        return "sector_analysis"
    if any(x in q for x in ["compare", "vs", "versus", "better than", "เปรียบเทียบ", "เทียบ", "ดีกว่า"]):
        return "stock_comparison"
    if any(x in q for x in ["what about", "how about", "แล้ว", "ล่ะ", "ตัวนี้", "them", "that one"]):
        return "follow_up_question"
    if any(x in q for x in ["news", "headline", "ข่าว", "พาดหัว"]):
        return "news_summary"
    if any(x in q for x in ["risk", "downside", "drawdown", "ความเสี่ยง", "ขาลง"]):
        return "risk_explanation"
    if any(x in q for x in [
        "portfolio", "allocation", "holdings", "watchlist",
        "พอร์ต", "พอร์ท", "สัดส่วน", "ถืออยู่", "รายการที่ติดตาม",
    ]):
        return "portfolio_advice"
    if any(x in q for x in [
        "sector", "sectors", "semiconductor", "technology", "energy", "finance", "industry",
        "กลุ่ม", "อุตสาหกรรม", "เซกเตอร์", "หมวด", "กลุ่มไหน", "sector ไหน", "โมเมนตัมกลุ่ม",
    ]):
        return "sector_analysis"
    if any(x in q for x in [
        "market", "trend", "fear", "greed", "summary", "sentiment", "macro",
        "ตลาด", "แนวโน้ม", "ภาพรวม", "ความเชื่อมั่น", "กลัว", "โลภ", "สรุปตลาด",
    ]):
        return "market_overview"
    if any(x in q for x in [
        "stock", "ticker", "nvda", "aapl", "msft", "tsla", "amzn", "buy", "sell", "investment",
        "หุ้น", "ตัวไหนดี", "น่าซื้อ", "น่าขาย", "วิเคราะห์", "แนะนำหุ้น",
    ]):
        return "single_stock_analysis"
    return "unclear_query"


def _classify_intent_category(question: str, intent: str) -> str:
    q = (question or "").strip().lower()
    sector_terms = [
        "sector", "sectors", "industry", "energy", "semiconductor", "technology", "finance", "healthcare",
        "กลุ่ม", "เซกเตอร์", "หมวด", "พลังงาน", "อุตสาหกรรม",
    ]
    risk_terms = ["risk", "risks", "downside", "weaken", "drawdown", "ความเสี่ยง", "อ่อนตัว", "อ่อนแอ", "ขาลง"]
    sentiment_terms = ["sentiment", "fear", "greed", "ความเชื่อมั่น", "กลัว", "โลภ"]
    momentum_terms = ["momentum", "strong momentum", "leaders", "laggards", "แรง", "โมเมนตัม", "นำตลาด"]
    portfolio_terms = ["portfolio", "holdings", "allocation", "watchlist", "พอร์ต", "สัดส่วน", "ถืออยู่"]

    if any(t in q for t in risk_terms):
        return "Risk Analysis"
    if any(t in q for t in momentum_terms) and any(t in q for t in sector_terms):
        return "Sector Momentum"
    if any(t in q for t in sentiment_terms):
        return "Market Sentiment"
    if any(t in q for t in portfolio_terms):
        return "Portfolio Analysis"
    if intent in {"single_stock_analysis", "stock_comparison"}:
        return "Stock Analysis"
    if intent in {"sector_stock_picker", "sector_analysis", "sector_explanation"}:
        return "Sector Momentum"
    if intent in {"market_overview", "risk_explanation"}:
        return "Risk Analysis"
    return "Stock Analysis"


def _is_sector_reference(question: str, context: AIAdvisorContext) -> bool:
    q = (question or "").lower()
    if _extract_sector_from_text(q):
        return True
    ref_terms = ["this sector", "that sector", "in this sector", "กลุ่มนี้", "เซกเตอร์นี้", "หมวดนี้"]
    if any(t in q for t in ref_terms):
        last_sector = str((context.chat_state or {}).get("last_sector") or "").strip()
        return bool(last_sector)
    return False


def _select_analysis_engine(
    *,
    question: str,
    intent: str,
    intent_category: str,
    explicit_symbol: Optional[str],
    context: AIAdvisorContext,
) -> str:
    if intent_category == "Risk Analysis":
        if explicit_symbol:
            return "stock_risk_engine"
        if _is_sector_reference(question, context):
            return "sector_risk_engine"
        return "market_risk_engine"
    if intent == "stock_comparison":
        return "stock_comparison_engine"
    if intent == "sector_stock_picker":
        return "sector_stock_picker_engine"
    if intent in {"sector_analysis", "sector_explanation"}:
        return "sector_analysis_engine"
    if intent == "portfolio_advice":
        return "portfolio_analysis_engine"
    if intent == "single_stock_analysis":
        return "stock_analysis_engine"
    return "general_engine"


def _build_stock_risk_response(
    symbol: str,
    stock_result: Dict[str, Any],
    market: Dict[str, Any],
) -> Dict[str, Any]:
    analysis = stock_result.get("analysis", {})
    raw = stock_result.get("raw", {}) or {}
    technical = analysis.get("indicators", {}) or {}
    signals = raw.get("signals", {}) or {}
    sentiment_avg = safe_float(raw.get("sentiment_avg", 0.0))
    sentiment_label = "Bullish" if sentiment_avg > 0.15 else ("Bearish" if sentiment_avg < -0.15 else "Neutral")
    momentum_score = safe_float(signals.get("momentum_score", 50.0))
    momentum_label = "Weakening" if momentum_score < 50 else ("Moderate" if momentum_score < 70 else "Strong")
    technical_trend = str(analysis.get("technical_trend", "Neutral"))
    fear_greed = safe_float(market.get("market_score", 50.0))
    fear_label = str(market.get("market_label", "Neutral"))
    sector = _sector_for_symbol(symbol)

    key_risks = [
        "Valuation Risk: current pricing may be sensitive to earnings-expectation resets.",
        "Demand Cyclicality: end-market spending slowdowns can reduce growth momentum.",
        "Competition Risk: peer pressure can compress margins and pricing power.",
        "Supply Chain / Geopolitical Risk: disruptions can affect production and delivery.",
    ]
    if sector == "Semiconductors":
        key_risks = [
            "Valuation Risk: semiconductor multiples can compress quickly when growth slows.",
            "AI Demand Cyclicality: hyperscaler capex normalization may reduce chip demand.",
            "Competition Risk: AMD/other accelerators can pressure share and margins.",
            "Supply Chain / Geopolitical Risk: foundry concentration and export controls add uncertainty.",
        ]
    elif sector == "Technology":
        key_risks = [
            "Valuation Risk: large-cap tech remains sensitive to rate and multiple compression.",
            "Demand Cyclicality: enterprise/cloud spending softness may reduce topline momentum.",
            "Competition Risk: product-cycle intensity can pressure market share and margins.",
            "Regulatory Risk: antitrust and data-policy pressure can affect growth optionality.",
        ]

    short_term = "High" if momentum_score < 45 or fear_greed < 30 else ("Medium" if momentum_score < 65 or fear_greed < 50 else "Low")
    long_term = "Low" if sector in {"Technology", "Semiconductors"} else "Medium"
    confidence = int(max(55, min(90, analysis.get("confidence", 75))))

    answer = (
        f"Stock Risk Analysis: {symbol}\n\n"
        "Key Risks\n"
        + "\n".join([f"- {x}" for x in key_risks]) + "\n\n"
        "Market Signals\n"
        f"- {symbol} price trend: {technical_trend}\n"
        f"- Momentum: {momentum_label} ({momentum_score:.1f}/100)\n"
        f"- Fear & Greed: {fear_greed:.0f} ({fear_label})\n"
        f"- News sentiment: {sentiment_label} ({sentiment_avg:+.2f})\n"
        f"- RSI: {safe_float(technical.get('rsi')):.2f}\n\n"
        "Impact Assessment\n"
        f"- Short-term downside risk: {short_term}\n"
        f"- Long-term structural risk: {long_term}\n\n"
        f"Confidence\n- {confidence}%"
    )
    followups = [
        f"Which risk is most critical for {symbol} now?",
        f"How does {symbol} downside risk compare vs sector peers?",
        f"What signals would reduce {symbol} risk?",
    ]
    schema = {
        "intent": "risk_analysis",
        "answer_title": f"Stock Risk Analysis: {symbol}",
        "direct_answer": f"Main downside risks for {symbol} are valuation sensitivity, demand cyclicality, competition, and supply-chain/geopolitical exposure.",
        "summary_points": key_risks,
        "market_signals": {
            "price_trend": technical_trend,
            "momentum_score": round(momentum_score, 1),
            "fear_greed_score": round(fear_greed, 1),
            "fear_greed_label": fear_label,
            "news_sentiment": round(sentiment_avg, 3),
            "rsi": round(safe_float(technical.get("rsi")), 2),
        },
        "impact_assessment": {
            "short_term_downside_risk": short_term,
            "long_term_structural_risk": long_term,
        },
        "risks": key_risks,
        "confidence": confidence,
        "sources": stock_result.get("sources", ["Finnhub", "Market News", "Internal Technical Model"]),
        "followups": followups,
    }
    return {"answer": answer, "schema": schema, "followups": followups}


def _build_market_risk_response(market: Dict[str, Any]) -> Dict[str, Any]:
    fg = safe_float(market.get("market_score", 50.0))
    label = str(market.get("market_label", "Neutral"))
    top_sector = str((market.get("sector_momentum") or {}).get("sector", "Technology"))
    top_momentum = str((market.get("sector_momentum") or {}).get("momentum", "Moderate"))
    short_term = "High" if fg < 30 else ("Medium" if fg < 55 else "Low")
    answer = (
        "Market Risk Analysis\n\n"
        "Key Risks\n"
        "- Liquidity and macro policy shocks can increase index-level drawdown risk.\n"
        "- Growth slowdown risk can pressure earnings revisions.\n"
        "- Risk-off regime can widen volatility and correlation.\n\n"
        "Market Signals\n"
        f"- Fear & Greed: {fg:.0f} ({label})\n"
        f"- Leading sector momentum: {top_sector} ({top_momentum})\n\n"
        "Impact Assessment\n"
        f"- Short-term downside risk: {short_term}\n"
        "- Long-term structural risk: policy and growth-cycle uncertainty\n\n"
        "Confidence\n- 70%"
    )
    followups = [
        "What risks could weaken this sector?",
        "Show top momentum stocks in this sector",
        "Which sectors are defensive now?",
    ]
    schema = {
        "intent": "risk_analysis",
        "answer_title": "Market Risk Analysis",
        "direct_answer": "Current downside risk is driven by macro/liquidity pressure and sentiment regime.",
        "summary_points": [
            "Macro and liquidity shocks can increase volatility.",
            "Earnings downgrade risk remains a key downside driver.",
            "Risk-off sentiment can amplify sector rotation.",
        ],
        "impact_assessment": {
            "short_term_downside_risk": short_term,
            "long_term_structural_risk": "Medium",
        },
        "confidence": 70,
        "sources": ["Fear & Greed Model", "Sector ETF Model", "Market News"],
        "followups": followups,
    }
    return {"answer": answer, "schema": schema, "followups": followups}


def _build_sector_risk_response(
    question: str,
    sector: str,
    market: Dict[str, Any],
    top_sector_data: Dict[str, Any],
) -> Dict[str, Any]:
    etf_map = {
        "Energy": "XLE",
        "Semiconductors": "SOXX",
        "Technology": "XLK",
        "Finance": "XLF",
        "Healthcare": "XLV",
    }
    etf = etf_map.get(sector, "XLK")
    etf_ret_3m = safe_float(top_sector_data.get("return_3m_pct", 0.0))
    etf_mom = safe_float(top_sector_data.get("momentum_score", 50.0))
    sentiment = safe_float(top_sector_data.get("news_sentiment", 0.0))
    sentiment_label = "Bullish" if sentiment > 0.15 else ("Bearish" if sentiment < -0.15 else "Neutral")
    fear_greed = safe_float(market.get("market_score", 50.0))
    regime = str(market.get("market_label", "Neutral"))

    if etf_mom < 45 or fear_greed < 35:
        impact = "High"
    elif etf_mom < 60 or fear_greed < 50:
        impact = "Medium"
    else:
        impact = "Low"

    key_risks = [
        "Commodity price downside can pressure sector earnings and margins.",
        "Global demand slowdown can reduce volume growth and pricing power.",
        "Policy/regulatory shifts can change long-term capital allocation trends.",
    ]
    if sector == "Semiconductors":
        key_risks = [
            "Inventory correction and capex slowdown can pressure revenue growth.",
            "Geopolitical/export restrictions can disrupt supply chain demand.",
            "Valuation compression risk remains elevated if growth expectations reset.",
        ]
    elif sector == "Technology":
        key_risks = [
            "Rate-sensitive valuation pressure can reduce upside multiples.",
            "Enterprise spending slowdown can impact software and cloud growth.",
            "Regulatory and antitrust pressure can affect large-cap leadership.",
        ]
    elif sector == "Finance":
        key_risks = [
            "Credit quality deterioration can increase provisioning costs.",
            "Yield curve shifts can pressure net interest margins.",
            "Regulatory tightening can limit capital return flexibility.",
        ]

    answer = (
        f"Sector Risk Analysis: {sector}\n\n"
        "Key Risks\n"
        + "\n".join([f"- {x}" for x in key_risks]) + "\n\n"
        "Macro Factors\n"
        f"- Fear & Greed regime: {regime} ({fear_greed:.0f})\n"
        f"- Sector ETF ({etf}) 3M return: {etf_ret_3m:+.2f}%\n"
        f"- Sector news sentiment: {sentiment_label} ({sentiment:+.2f})\n\n"
        "Market Signals\n"
        f"- {etf} momentum score: {etf_mom:.1f}/100\n"
        f"- Market risk outlook: {market.get('risk_outlook', 'Medium')}\n\n"
        "Impact Assessment\n"
        f"- Short-term risk: {impact}\n"
        "- Long-term risk: structural transition and macro-policy uncertainty\n\n"
        f"Confidence\n- {74 if impact == 'Medium' else (80 if impact == 'High' else 70)}%"
    )

    followups = [
        f"Show top momentum stocks in {sector}",
        f"Which {sector} names are lower-risk now?",
        f"How does {sector} risk compare vs Technology?",
    ]
    schema = {
        "intent": "sector_risk",
        "answer_title": f"Sector Risk Analysis: {sector}",
        "direct_answer": f"Main downside risks for {sector} are demand sensitivity, macro regime pressure, and policy transition risk.",
        "summary_points": key_risks,
        "market_signals": {
            "fear_greed": round(fear_greed, 1),
            "sector_etf": etf,
            "sector_etf_return_3m_pct": round(etf_ret_3m, 2),
            "sector_momentum_score": round(etf_mom, 1),
            "sector_news_sentiment": round(sentiment, 3),
        },
        "impact_assessment": {
            "short_term": impact,
            "long_term": "Structural transition / policy sensitivity",
        },
        "risks": key_risks,
        "confidence": 74 if impact == "Medium" else (80 if impact == "High" else 70),
        "sources": ["Finnhub", "Sector ETF Model", "Market News", "Fear & Greed Model"],
        "followups": followups,
    }
    return {"answer": answer, "schema": schema, "followups": followups}


def _build_followup_prompts(intent: str, symbol: Optional[str], top_sector: Optional[str] = None) -> List[str]:
    sym = str(symbol or "").upper().strip()
    sector = str(top_sector or "Technology")
    if intent == "stock_comparison" and sym:
        return [
            f"What are the downside risks for {sym}?",
            f"Which is better for short-term momentum?",
            "Show valuation and risk difference",
        ]
    if intent == "single_stock_analysis" and sym:
        return [
            f"Compare {sym} vs AMD",
            f"What are the downside risks for {sym}?",
            f"Show related stocks to {sym}",
        ]
    if intent == "sector_stock_picker":
        return [
            f"Compare top names in {sector}",
            f"Show lower-risk stocks in {sector}",
            f"Which {sector} names have bullish sentiment?",
        ]
    if intent == "sector_explanation":
        return [
            f"Show top momentum stocks in {sector}",
            f"What risks could weaken {sector}?",
            f"Is {sector} still attractive overall?",
        ]
    if intent == "sector_risk":
        return [
            f"Show top momentum stocks in {sector}",
            f"Which {sector} names are lower-risk now?",
            f"How does {sector} risk compare vs Technology?",
        ]
    if intent == "sector_analysis":
        return [
            f"Why is {sector} leading right now?",
            "Which sector looks defensive now?",
            "Show top momentum stocks in this sector",
        ]
    if intent in {"market_overview", "risk_explanation"}:
        return [
            "What are the biggest market risks now?",
            "Show bullish large-cap ideas",
            "Summarize today's market sentiment",
        ]
    if intent == "portfolio_advice":
        return [
            "How can I reduce portfolio concentration risk?",
            "Suggest low-volatility additions",
            "Which holdings are weakest by momentum?",
        ]
    return [
        "What stocks are trending today?",
        "What sectors have strong momentum?",
        "Show bullish large-cap ideas",
    ]


def _build_answer_schema(
    *,
    intent: str,
    analysis: Dict[str, Any],
    market: Dict[str, Any],
    sources: List[str],
    signal: Optional[str] = None,
) -> Dict[str, Any]:
    recommendation = signal or str(analysis.get("recommendation") or "Hold")
    stance = str(analysis.get("news_sentiment") or "Neutral")
    ticker = str(analysis.get("ticker") or "N/A")
    company_name = str(analysis.get("company_name") or ticker)
    sector = str(analysis.get("sector") or "N/A")
    industry = str(analysis.get("industry") or "N/A")
    price = safe_float(analysis.get("current_price", 0))
    price_change = safe_float(analysis.get("price_change", 0))
    momentum = str(analysis.get("momentum") or "Moderate")
    technical_trend = str(analysis.get("technical_trend") or "Neutral")
    sentiment = str(analysis.get("news_sentiment") or "Neutral")
    fear_greed = safe_float(market.get("market_score", 50))
    market_label = str(market.get("market_label", "Neutral"))
    analyst_target = analysis.get("analyst_target")
    forecast = analysis.get("forecast_horizon", {"7d": 0, "30d": 0, "90d": 0})
    if recommendation.lower().startswith("strong buy"):
        stance = "Bullish"
    elif recommendation.lower() in {"sell", "strong sell"}:
        stance = "Bearish"

    rationale = []
    if analysis.get("technical_trend"):
        rationale.append(f"Technical trend: {analysis.get('technical_trend')}")
    if analysis.get("momentum"):
        rationale.append(f"Momentum: {analysis.get('momentum')}")
    if market.get("market_label"):
        rationale.append(f"Market regime: {market.get('market_label')} ({market.get('market_score')})")
    if not rationale:
        rationale = ["Limited confirmed signals from current data."]

    risks = list(analysis.get("risks", [])) or [
        "Macro volatility can shift short-term trend quickly.",
        "News flow can change sentiment regime."
    ]

    return {
        "intent": intent,
        "answer_title": f"{company_name} ({ticker})",
        "direct_answer": (
            f"Based on current technical and sentiment data, {company_name} ({ticker}) is {recommendation}."
        ),
        "summary": (
            f"{company_name} ({ticker}) view is {recommendation} with "
            f"{analysis.get('confidence', 70)}% confidence under current signals."
        ),
        "stance": stance,
        "rationale": rationale[:4],
        "risks": risks[:4],
        "actionable_view": recommendation,
        "confidence": int(analysis.get("confidence", 70)),
        "stock_overview": {
            "company_name": company_name,
            "ticker": ticker,
            "sector": sector,
            "industry": industry,
            "price": round(price, 2) if price > 0 else None,
            "price_change": round(price_change, 2),
        },
        "market_signals": {
            "technical_trend": technical_trend,
            "momentum": momentum,
            "news_sentiment": sentiment,
            "fear_greed_index": round(fear_greed, 1),
            "market_regime": market_label,
            "analyst_target": analyst_target if analyst_target not in ("", None) else None,
        },
        "investment_view": {
            "recommendation": recommendation,
            "confidence": int(analysis.get("confidence", 70)),
            "forecast_horizon": {
                "7d": round(safe_float(forecast.get("7d")), 2),
                "30d": round(safe_float(forecast.get("30d")), 2),
                "90d": round(safe_float(forecast.get("90d")), 2),
            },
        },
        "forecast_horizon": {
            "7d": round(safe_float(forecast.get("7d")), 2),
            "30d": round(safe_float(forecast.get("30d")), 2),
            "90d": round(safe_float(forecast.get("90d")), 2),
        },
        "sources": sources,
        "data_coverage": {
            "price_data": bool(analysis.get("current_price", 0) > 0),
            "news_sentiment": bool(str(analysis.get("news_sentiment", "")).strip()),
            "technical_signals": bool(analysis.get("technical_trend")),
        },
    }


def _resolve_intent_with_context(base_intent: str, question: str, context: AIAdvisorContext, symbols: List[str]) -> str:
    if base_intent != "follow_up_question":
        return base_intent
    q = (question or "").strip().lower()
    state = context.chat_state or {}
    last_intent = str(state.get("last_intent") or "").strip()
    last_symbol = str(state.get("last_symbol") or "").upper().strip()
    picker_terms = ["top stocks", "top names", "stock picks", "momentum stocks", "leaders", "those names", "หุ้นเด่น", "รายชื่อหุ้น", "หุ้นโมเมนตัม"]
    sector_ref_terms = ["sector", "this sector", "that sector", "กลุ่มนี้", "เซกเตอร์นี้", "หมวดนี้"]
    why_terms = ["why", "ทำไม", "strong", "weak", "แข็ง", "อ่อน"]
    if any(t in q for t in picker_terms) and (
        any(t in q for t in sector_ref_terms) or last_intent in {"sector_analysis", "sector_explanation", "sector_stock_picker", "market_overview"}
    ):
        return "sector_stock_picker"
    if any(t in q for t in why_terms) and (
        any(t in q for t in sector_ref_terms) or last_intent in {"sector_analysis", "sector_explanation", "sector_stock_picker"}
    ):
        return "sector_explanation"
    if len(symbols) >= 2:
        return "stock_comparison"
    if len(symbols) == 1:
        if last_symbol and last_symbol != symbols[0]:
            return "stock_comparison"
        return "single_stock_analysis"
    if last_intent in {
        "single_stock_analysis",
        "stock_comparison",
        "market_overview",
        "sector_analysis",
        "sector_explanation",
        "sector_stock_picker",
        "news_summary",
        "risk_explanation",
        "portfolio_advice",
    }:
        return last_intent
    return "unclear_query"


def _build_comparison_schema(
    left: Dict[str, Any],
    right: Dict[str, Any],
    sources: List[str],
) -> Dict[str, Any]:
    l = left.get("analysis", {})
    r = right.get("analysis", {})
    ls = str(l.get("ticker", "LEFT"))
    rs = str(r.get("ticker", "RIGHT"))

    l_m = safe_float((left.get("raw", {}) or {}).get("signals", {}).get("momentum_score", 0))
    r_m = safe_float((right.get("raw", {}) or {}).get("signals", {}).get("momentum_score", 0))
    l_s = safe_float((left.get("raw", {}) or {}).get("sentiment_avg", 0))
    r_s = safe_float((right.get("raw", {}) or {}).get("sentiment_avg", 0))
    l_r = str(l.get("risk_level", "Medium"))
    r_r = str(r.get("risk_level", "Medium"))

    def winner(a, b, left_name, right_name):
        if a > b:
            return left_name
        if b > a:
            return right_name
        return "Tie"

    risk_rank = {"Low": 3, "Medium": 2, "High": 1}
    l_rv = risk_rank.get(l_r, 2)
    r_rv = risk_rank.get(r_r, 2)

    verdict_winner = winner(l_m + (l_s * 20), r_m + (r_s * 20), ls, rs)
    style_fit = f"{ls} for stronger momentum; {rs} for comparatively balanced risk/reward." if verdict_winner == ls else f"{rs} for stronger momentum; {ls} for comparatively balanced risk/reward."

    return {
        "intent": "stock_comparison",
        "answer_title": f"{ls} vs {rs}",
        "direct_answer": (
            f"{verdict_winner if verdict_winner != 'Tie' else 'Both'} currently shows stronger combined momentum/sentiment signals."
        ),
        "stance": f"comparison_{verdict_winner.lower()}" if verdict_winner != "Tie" else "balanced",
        "summary_points": [
            f"Momentum score: {ls} {l_m:.1f} vs {rs} {r_m:.1f}",
            f"News sentiment score: {ls} {l_s:+.2f} vs {rs} {r_s:+.2f}",
            f"Risk level: {ls} {l_r} vs {rs} {r_r}",
            style_fit,
        ],
        "comparison": {
            "left_symbol": ls,
            "right_symbol": rs,
            "categories": [
                {
                    "label": "Momentum",
                    "left_value": f"{l_m:.1f}/100",
                    "right_value": f"{r_m:.1f}/100",
                    "winner": winner(l_m, r_m, ls, rs),
                },
                {
                    "label": "News Sentiment",
                    "left_value": f"{l_s:+.2f}",
                    "right_value": f"{r_s:+.2f}",
                    "winner": winner(l_s, r_s, ls, rs),
                },
                {
                    "label": "Risk",
                    "left_value": l_r,
                    "right_value": r_r,
                    "winner": winner(l_rv, r_rv, ls, rs),
                },
            ],
        },
        "risks": [
            "Both names remain sensitive to market volatility and macro shocks.",
            "Signal leadership can rotate quickly after earnings/news surprises.",
        ],
        "confidence": int(min(safe_float(l.get("confidence", 70)), safe_float(r.get("confidence", 70)))),
        "sources": sources,
        "followups": [
            f"What are the downside risks for {ls}?",
            f"Show {rs} technical picture",
            "Which is better for short-term momentum?",
        ],
    }


def _looks_like_thai(text: str) -> bool:
    return bool(re.search(r"[\u0E00-\u0E7F]", str(text or "")))


def _is_generation_off_topic(intent: str, question: str, generated: str, evidence: Dict[str, Any]) -> bool:
    text = str(generated or "").lower()
    q = str(question or "").lower()
    if not text:
        return True

    if intent in {"sector_analysis", "sector_explanation", "market_overview", "risk_explanation", "news_summary"}:
        # ถ้าถาม sector/market แต่โมเดลตอบเป็น stock analysis เจาะรายตัว
        if "stock analysis" in text and "sector" in q:
            return True
        top_sector = str((evidence.get("top_sector") or {}).get("sector", "")).lower()
        if "sector" in q and top_sector and top_sector not in text:
            return True

    if intent == "single_stock_analysis":
        ticker = str((evidence.get("analysis") or {}).get("ticker", "")).lower()
        if ticker and ticker not in text:
            return True
    if intent == "stock_comparison":
        left = str((evidence.get("left") or {}).get("ticker", "")).lower()
        right = str((evidence.get("right") or {}).get("ticker", "")).lower()
        if left and right and (left not in text or right not in text):
            return True

    # บังคับภาษาตามคำถาม: ถ้าผู้ใช้ถามไทยแต่โมเดลตอบอังกฤษล้วน ให้ fallback
    if _looks_like_thai(question) and not _looks_like_thai(generated):
        return True

    return False


def _sector_for_symbol(symbol: str) -> str:
    sym = str(symbol or "").upper()
    sector_map = {
        "NVDA": "Semiconductors", "AMD": "Semiconductors", "AVGO": "Semiconductors", "TSM": "Semiconductors", "INTC": "Semiconductors",
        "MSFT": "Technology", "AAPL": "Technology", "GOOGL": "Technology", "AMZN": "Technology", "META": "Technology", "TSLA": "Technology",
        "JPM": "Finance", "BAC": "Finance", "GS": "Finance", "XOM": "Energy", "CVX": "Energy",
    }
    return sector_map.get(sym, "Technology")


SECTOR_STOCK_UNIVERSE: Dict[str, List[str]] = {
    "Energy": ["XOM", "CVX", "SLB", "EOG", "OXY", "COP"],
    "Semiconductors": ["NVDA", "AMD", "AVGO", "TSM", "INTC", "MU"],
    "Technology": ["MSFT", "AAPL", "AMZN", "GOOGL", "META", "ORCL"],
    "Finance": ["JPM", "BAC", "GS", "MS", "WFC", "C"],
    "Healthcare": ["LLY", "JNJ", "UNH", "PFE", "MRK", "ABT"],
}

SECTOR_ETF_MAP: Dict[str, str] = {
    "Technology": "XLK",
    "Semiconductors": "SOXX",
    "Energy": "XLE",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Finance": "XLF",
}


def _extract_sector_from_text(text: str) -> Optional[str]:
    q = (text or "").lower()
    alias_map = {
        "energy": "Energy", "xle": "Energy", "พลังงาน": "Energy",
        "semiconductor": "Semiconductors", "semiconductors": "Semiconductors", "chip": "Semiconductors", "ชิป": "Semiconductors", "เซมิคอนดักเตอร์": "Semiconductors",
        "technology": "Technology", "tech": "Technology", "เทค": "Technology", "เทคโนโลยี": "Technology",
        "finance": "Finance", "financial": "Finance", "ธนาคาร": "Finance", "การเงิน": "Finance",
        "healthcare": "Healthcare", "health": "Healthcare", "เฮลท์แคร์": "Healthcare", "สุขภาพ": "Healthcare",
    }
    for k, v in alias_map.items():
        if k in q:
            return v
    return None


def _resolve_sector_context(
    question: str,
    context: AIAdvisorContext,
    rankings: List[Dict[str, Any]],
) -> str:
    direct = _extract_sector_from_text(question)
    if direct:
        return direct
    state = context.chat_state or {}
    last_sector = str(state.get("last_sector") or "").strip()
    if last_sector:
        return last_sector
    if context.selected_stock:
        return _sector_for_symbol(context.selected_stock)
    if rankings:
        return str(rankings[0].get("sector", "Technology"))
    return "Technology"


def _rank_sector_stock_momentum(sector: str) -> Dict[str, Any]:
    symbols = SECTOR_STOCK_UNIVERSE.get(sector, [])
    ranked: List[Dict[str, Any]] = []
    missing = 0
    spy_ret_3m = 0.0
    try:
        spy_data = get_stock_data("SPY", "3m")
        spy_hist = spy_data.get("history", [])
        if len(spy_hist) >= 2:
            spy_first = safe_float(spy_hist[0].get("close"))
            spy_last = safe_float(spy_hist[-1].get("close"))
            if spy_first > 0:
                spy_ret_3m = ((spy_last - spy_first) / spy_first) * 100.0
    except Exception:
        spy_ret_3m = 0.0

    def _momentum_label(score: float) -> str:
        if score >= 70:
            return "Strong"
        if score >= 50:
            return "Moderate"
        return "Weak"

    for sym in symbols:
        try:
            data_3m = get_stock_data(sym, "3m")
            hist_3m = data_3m.get("history", [])
            if len(hist_3m) < 20:
                missing += 1
                continue
            first = safe_float(hist_3m[0].get("close"))
            last = safe_float(hist_3m[-1].get("close"))
            if first <= 0 or last <= 0:
                missing += 1
                continue
            ret_3m = ((last - first) / first) * 100.0
            rel_strength = ret_3m - spy_ret_3m

            data_6m = get_stock_data(sym, "6m")
            hist_6m = data_6m.get("history", [])
            closes_6m = [safe_float(h.get("close")) for h in hist_6m if safe_float(h.get("close")) > 0]
            ma50 = None
            ma200 = None
            trend_score = 50.0
            if len(closes_6m) >= 50:
                ma50 = float(sum(closes_6m[-50:]) / 50.0)
            if len(closes_6m) >= 200:
                ma200 = float(sum(closes_6m[-200:]) / 200.0)
            elif len(closes_6m) >= 100:
                ma200 = float(sum(closes_6m[-100:]) / 100.0)
            if ma50 and ma200 and ma200 > 0:
                trend_score = max(0.0, min(100.0, ((ma50 / ma200) - 0.9) / 0.2 * 100.0))

            ret_score = max(0.0, min(100.0, (ret_3m + 20.0) / 40.0 * 100.0))
            rs_score = max(0.0, min(100.0, (rel_strength + 15.0) / 30.0 * 100.0))
            momentum_score = round((ret_score * 0.50) + (rs_score * 0.30) + (trend_score * 0.20), 2)
            momentum_label = _momentum_label(momentum_score)

            price = safe_float(data_3m.get("price") or last)
            profile = stock_profile_endpoint(sym)
            name = str(profile.get("name") or sym)
            industry = str(profile.get("industry") or sector)
            reason = (
                "3M return and relative strength are leading peers, with MA trend supportive."
                if momentum_label == "Strong"
                else "Momentum is positive but mixed versus peers."
                if momentum_label == "Moderate"
                else "Momentum is lagging peers; trend needs confirmation."
            )
            ranked.append({
                "symbol": sym,
                "name": name,
                "price": round(price, 2) if price > 0 else None,
                "change": round(safe_float(data_3m.get("change")), 2),
                "return_3m_pct": round(ret_3m, 2),
                "relative_strength_vs_spy": round(rel_strength, 2),
                "ma_trend": "Bullish" if ma50 and ma200 and ma50 >= ma200 else "Mixed/Weak",
                "momentum_score": momentum_score,
                "momentum": momentum_label,
                "sector": sector,
                "industry": industry,
                "reason": reason,
            })
        except Exception:
            missing += 1

    ranked.sort(key=lambda x: safe_float(x.get("momentum_score")), reverse=True)
    top = ranked[:5]
    complete = len(top) >= 3
    return {
        "sector": sector,
        "stocks": top,
        "complete": complete,
        "missing_count": missing,
    }


def _compute_sector_momentum() -> Dict[str, Any]:
    sectors = {
        "Semiconductors": ["NVDA", "AMD", "AVGO"],
        "Technology": ["MSFT", "AAPL", "AMZN"],
        "Finance": ["JPM", "BAC", "GS"],
        "Energy": ["XOM", "CVX", "COP"],
    }
    best_name: Optional[str] = None
    best_score: Optional[float] = None
    details: Dict[str, float] = {}
    for name, symbols in sectors.items():
        scores = []
        for sym in symbols:
            try:
                s = get_stock_data(sym, "1m")
                hist = s.get("history", [])
                if len(hist) >= 2:
                    first = safe_float(hist[0].get("close"))
                    last = safe_float(hist[-1].get("close"))
                    if first > 0:
                        scores.append((last - first) / first * 100.0)
            except Exception:
                continue
        if scores:
            avg = float(sum(scores) / len(scores))
            details[name] = round(avg, 2)
            if best_score is None or avg > best_score:
                best_score = avg
                best_name = name
    if best_name is None or best_score is None:
        return {"sector": None, "momentum": "Unavailable", "score": None, "all": details}
    momentum_label = "Strong" if best_score > 2.0 else ("Moderate" if best_score > 0.5 else "Weak")
    return {"sector": best_name, "momentum": momentum_label, "score": round(best_score, 2), "all": details}


def _safe_news_sentiment_for_symbol(symbol: str, days_back: int = 14) -> float:
    try:
        rows = get_newsapi_news_batch([symbol], limit_per_symbol=10, days_back=days_back)
        items = (rows[0].get("news", []) if rows else [])
        scores = []
        for item in items:
            raw = item.get("sentiment_score")
            if raw is not None:
                try:
                    scores.append(float(raw))
                    continue
                except Exception:
                    pass
            label = str(item.get("sentiment", "")).lower()
            if "positive" in label or "bullish" in label:
                scores.append(0.6)
            elif "negative" in label or "bearish" in label:
                scores.append(-0.6)
            else:
                scores.append(0.0)
        if not scores:
            return 0.0
        return float(sum(scores) / len(scores))
    except Exception:
        return 0.0


def _rank_sector_etfs() -> Dict[str, Any]:
    # Requested sector momentum based on ETF 3M return + relative strength + news sentiment.
    etfs = {
        "Technology": "XLK",
        "Semiconductors": "SOXX",
        "Energy": "XLE",
        "Healthcare": "XLV",
        "Financials": "XLF",
    }
    market_symbol = "SPY"
    market_ret: Optional[float] = None
    try:
        m = get_stock_data(market_symbol, "3m")
        mh = m.get("history", [])
        if len(mh) >= 2:
            first_m = safe_float(mh[0].get("close"))
            last_m = safe_float(mh[-1].get("close"))
            if first_m > 0:
                market_ret = ((last_m - first_m) / first_m) * 100.0
    except Exception:
        market_ret = None

    ranked = []
    for sector, etf in etfs.items():
        ret_3m: Optional[float] = None
        try:
            s = get_stock_data(etf, "3m")
            hist = s.get("history", [])
            if len(hist) >= 2:
                first = safe_float(hist[0].get("close"))
                last = safe_float(hist[-1].get("close"))
                if first > 0:
                    ret_3m = ((last - first) / first) * 100.0
        except Exception:
            ret_3m = None
        if ret_3m is None:
            continue
        rel_strength = (ret_3m - market_ret) if market_ret is not None else None
        sent = _safe_news_sentiment_for_symbol(etf, days_back=14)
        sent_score = max(0.0, min(100.0, (sent + 1.0) * 50.0))
        ret_score = max(0.0, min(100.0, (ret_3m + 12.0) / 24.0 * 100.0))
        rs_score = (
            max(0.0, min(100.0, ((rel_strength or 0.0) + 10.0) / 20.0 * 100.0))
            if rel_strength is not None
            else 50.0
        )
        momentum_score = round((ret_score * 0.50) + (rs_score * 0.30) + (sent_score * 0.20), 2)
        ranked.append({
            "sector": sector,
            "etf": etf,
            "return_3m_pct": round(ret_3m, 2),
            "relative_strength_pct": round(rel_strength, 2) if rel_strength is not None else None,
            "news_sentiment": round(sent, 3),
            "momentum_score": momentum_score,
        })

    ranked.sort(key=lambda x: x["momentum_score"], reverse=True)
    top = ranked[0] if ranked else {}
    momentum_label = "Unavailable"
    if ranked:
        momentum_label = "Strong" if safe_float(top.get("momentum_score")) >= 70 else ("Moderate" if safe_float(top.get("momentum_score")) >= 50 else "Weak")
    return {
        "top_sector": top.get("sector") if top else None,
        "top_momentum_label": momentum_label,
        "rankings": ranked,
    }


def _build_structured_answer_sections(
    intent: str,
    question: str,
    analysis: Dict[str, Any],
    market: Dict[str, Any],
    sources: List[str],
    context: AIAdvisorContext,
) -> Dict[str, Any]:
    forecast = analysis.get("forecast_horizon", {"7d": 0, "30d": 0, "90d": 0})
    sector_rank = _rank_sector_etfs()
    top_sector = sector_rank.get("top_sector", "Technology")
    top_label = sector_rank.get("top_momentum_label", "Moderate")
    news_sent = analysis.get("news_sentiment", "Neutral")
    risks = list(analysis.get("risks", [])) or [
        "Macro rate uncertainty may increase volatility.",
        "Valuation sensitivity can pressure upside."
    ]

    market_summary = []
    if intent in {"market_overview", "sector_analysis", "sector_explanation"} or "sector" in question.lower() or "trending" in question.lower():
        market_summary.append(f"Fear & Greed: {market.get('market_score', 50)} ({market.get('market_label', 'Neutral')})")
        market_summary.append(f"Strongest Sector: {top_sector} ({top_label})")
        market_summary.append(f"Top AI Pick: {analysis.get('ticker', 'NVDA')}")
        if sector_rank.get("rankings"):
            top3 = sector_rank["rankings"][:3]
            market_summary.append("Sector ranking (3M): " + " | ".join(
                f"{x['sector']} {x['momentum_score']:.1f}" for x in top3
            ))
    else:
        market_summary.append(
            f"{analysis.get('ticker', 'NVDA')} in a {market.get('market_label', 'Neutral')} regime "
            f"with Fear & Greed at {market.get('market_score', 50)}."
        )
        market_summary.append(f"Strongest Sector: {top_sector} ({top_label})")

    tech = analysis.get("indicators", {}) or {}
    technical_signals = [
        f"Price Trend: {analysis.get('technical_trend', 'Neutral')}",
        f"RSI: {safe_float(tech.get('rsi')):.2f}",
        f"MACD vs Signal: {safe_float(tech.get('macd')):.3f} / {safe_float(tech.get('macd_signal')):.3f}",
        f"MA50 vs MA200: {safe_float(tech.get('ma50')):.2f} / {safe_float(tech.get('ma200')):.2f}",
        f"Momentum: {analysis.get('momentum', 'Moderate')}",
    ]

    news_section = [
        f"Recent sentiment: {news_sent}",
        "Sentiment source from latest market news aggregation model.",
    ]

    portfolio_risk = "N/A"
    if context and context.portfolio:
        count = len(context.portfolio)
        portfolio_risk = "High" if count <= 2 else ("Medium" if count <= 6 else "Low")
        risks.append(f"Portfolio concentration risk: {portfolio_risk} ({count} holdings tracked).")

    recommendation = {
        "signal": analysis.get("recommendation", "Hold"),
        "reason": "Recommendation is derived from technical trend, news sentiment, momentum, and risk scoring.",
        "forecast_horizon": {
            "7d": round(safe_float(forecast.get("7d")), 2),
            "30d": round(safe_float(forecast.get("30d")), 2),
            "90d": round(safe_float(forecast.get("90d")), 2),
        },
    }

    return {
        "market_summary": market_summary,
        "technical_signals": technical_signals,
        "news_sentiment": news_section,
        "risk_factors": risks,
        "ai_recommendation": recommendation,
        "confidence_score": int(analysis.get("confidence", 70)),
        "sources": sources,
        "sector_rankings": sector_rank.get("rankings", []),
    }


def _build_market_snapshot(context: AIAdvisorContext) -> Dict[str, Any]:
    market_score: Optional[float] = None
    market_label = "Unknown"
    market_meta: Dict[str, Any] = {"score": None, "sentiment": market_label}
    try:
        if HAS_MARKET_SENTIMENT:
            sent = compute_market_sentiment(force_refresh=False)
            if isinstance(sent, dict):
                market_meta = sent
                raw_score = sent.get("score")
                market_score = float(raw_score) if raw_score is not None else None
                market_label = str(sent.get("sentiment", _sentiment_label(market_score))) if market_score is not None else str(sent.get("sentiment", "Unknown"))
    except Exception:
        if context.sentiment is not None:
            market_score = float(context.sentiment)
            market_label = _sentiment_label(market_score)
            market_meta = {"score": market_score, "sentiment": market_label, "source": "Context"}

    sector_momentum = _compute_sector_momentum()
    if market_score is None:
        risk_outlook = "Unknown"
    else:
        risk_outlook = "High" if market_score < 30 else ("Medium" if market_score < 70 else "Low")
    return {
        "market_score": round(market_score, 1) if market_score is not None else None,
        "market_label": market_label,
        "market_meta": market_meta,
        "sector_momentum": sector_momentum,
        "risk_outlook": risk_outlook,
    }


def _analyze_stock_pipeline(symbol: str, window_days: int = 14) -> Dict[str, Any]:
    sym = str(symbol or "").upper()
    reco = compute_recommendation(sym, window_days=window_days)
    if reco.get("error"):
        raise ValueError(str(reco["error"]))

    current_price = safe_float(reco.get("current_price"))
    technical = reco.get("technical_indicators", {}) or {}
    signals = reco.get("signals", {}) or {}
    data_validation = {
        "price_data": current_price > 0,
        "news_data": int(reco.get("news_count", 0)) > 0,
        "technical_data": safe_float(technical.get("rsi")) > 0 and safe_float(technical.get("ma50")) > 0,
    }
    if not all(data_validation.values()):
        return {
            "ok": False,
            "symbol": sym,
            "message": "I cannot confirm this analysis due to missing market data.",
            "data_validation": data_validation,
            "analysis": {},
            "sources": ["Finnhub", "Market News", "Yahoo Finance"],
            "charts": {
                "price": _build_price_chart(sym),
                "sentiment": _build_sentiment_chart(sym),
            },
        }

    forecast_30 = safe_float(reco.get("forecast", {}).get("predicted_return_pct"))
    forecast_horizons = {
        "7d": round(forecast_30 * 0.35, 2),
        "30d": round(forecast_30, 2),
        "90d": round(forecast_30 * 2.2, 2),
    }
    momentum_score = safe_float(signals.get("momentum_score"))
    momentum_label = "Strong" if momentum_score >= 70 else ("Moderate" if momentum_score >= 50 else "Weak")
    confidence_pct = int(round(safe_float(reco.get("confidence")) * 100))
    profile = {}
    try:
        profile = stock_profile_endpoint(sym)
    except Exception:
        profile = {}
    company_name = str(profile.get("name") or reco.get("company_name") or sym)
    sector = str(profile.get("industry") or _sector_for_symbol(sym))
    industry = str(profile.get("industry") or sector)
    analyst_target = safe_float((reco.get("target_price_mean") or 0))
    price_change = safe_float((reco.get("price_change") or 0))

    analysis = {
        "ticker": sym,
        "company_name": company_name,
        "sector": sector,
        "industry": industry,
        "current_price": round(current_price, 2),
        "price_change": round(price_change, 2),
        "recommendation": str(reco.get("recommendation", "Hold")),
        "confidence": confidence_pct,
        "risk_level": str(reco.get("risk_level", "Medium")),
        "technical_trend": str(technical.get("trend_label", "Neutral")),
        "news_sentiment": str(signals.get("news_sentiment_label", "Neutral")),
        "momentum": momentum_label,
        "forecast_horizon": forecast_horizons,
        "analyst_target": round(analyst_target, 2) if analyst_target > 0 else None,
        "indicators": {
            "rsi": safe_float(technical.get("rsi")),
            "macd": safe_float(technical.get("macd")),
            "macd_signal": safe_float(technical.get("macd_signal")),
            "ma50": safe_float(technical.get("ma50")),
            "ma200": safe_float(technical.get("ma200")),
        },
        "drivers": [
            "Technical trend and moving-average alignment",
            "Recent news sentiment aggregation",
            "Momentum and volatility-weighted scoring model",
        ],
        "risks": [
            "High volatility can reduce forecast confidence",
            "News regime can shift quickly after macro events",
        ],
    }
    return {
        "ok": True,
        "symbol": sym,
        "data_validation": data_validation,
        "analysis": analysis,
        "raw": reco,
        "sources": ["Finnhub", "Market News", "Yahoo Finance", "Internal Technical Model"],
        "charts": {
            "price": _build_price_chart(sym),
            "sentiment": _build_sentiment_chart(sym),
        },
    }


def _gemini_reasoning(prompt: str) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None
    try:
        res = session.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 350},
            },
            timeout=15,
        )
        if res.status_code != 200:
            return None
        data = res.json()
        return (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text")
        )
    except Exception:
        return None


def _generate_grounded_response(
    question: str,
    intent: str,
    evidence: Dict[str, Any],
    fallback_text: str,
) -> str:
    # Grounded generation: Gemini may rephrase but must stay within evidence.
    prompt = (
        "You are a professional investment assistant.\n"
        "Your first duty is to answer exactly what the user asked.\n"
        "Answer only the question asked.\n"
        "Use only relevant context.\n"
        "Do not generalize unless asked.\n"
        "Do not compare unless asked.\n"
        "Do not invent missing facts.\n"
        "Less irrelevant information is better than more irrelevant information.\n"
        "Use ONLY facts and numbers from EVIDENCE JSON below.\n"
        "If data is incomplete, say it clearly.\n"
        "Structure response as: direct answer -> supporting reasons -> risks/caveats -> optional next step.\n\n"
        f"Intent: {intent}\n"
        f"User question: {question}\n"
        f"EVIDENCE JSON: {json.dumps(evidence, ensure_ascii=False)}\n"
    )
    generated = _gemini_reasoning(prompt)
    if (
        generated
        and len(generated.strip()) >= 40
        and not _is_generation_off_topic(intent, question, generated, evidence)
    ):
        return generated.strip()
    return fallback_text


@app.post("/ai-advisor")
@app.post("/api/ai-advisor")
def ai_advisor_endpoint(payload: AIAdvisorRequest):
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    base_intent = _classify_intent(question)
    ticker_candidates = _extract_ticker_candidates(question)
    intent = _resolve_intent_with_context(base_intent, question, payload.context, ticker_candidates)
    intent_category = _classify_intent_category(question, intent)
    symbol = _parse_symbol_from_question(question, payload.context)
    explicit_candidates = ticker_candidates
    explicit_symbol = normalize_symbol(explicit_candidates[0]) if explicit_candidates else None
    market = _build_market_snapshot(payload.context)
    analysis_type = "stock_analysis"

    is_sector_stock_picker = intent == "sector_stock_picker"
    is_sector_explanation = intent == "sector_explanation"
    analysis_engine = _select_analysis_engine(
        question=question,
        intent=intent,
        intent_category=intent_category,
        explicit_symbol=explicit_symbol,
        context=payload.context,
    )
    is_sector_risk = analysis_engine == "sector_risk_engine"
    is_stock_risk = analysis_engine == "stock_risk_engine"
    is_market_risk = analysis_engine == "market_risk_engine"
    is_sector_query = intent == "sector_analysis" or is_sector_explanation or any(k in question.lower() for k in ["sector", "sectors", "industry", "industries"])
    is_market_query = intent in {"market_overview", "risk_explanation", "news_summary"} and explicit_symbol is None
    is_portfolio_query = intent == "portfolio_advice"
    is_comparison_query = intent == "stock_comparison"

    if intent in {"news_summary"} and explicit_symbol:
        intent = "single_stock_analysis"
        is_market_query = False

    if intent == "unclear_query":
        return {
            "intent": "unclear_query",
            "intent_category": intent_category,
            "analysis_type": "clarification",
            "analysis_engine": analysis_engine,
            "answer": "Do you want a quick stock view, a stock comparison, or a market-wide summary?",
            "answer_schema": {
                "intent": "unclear_query",
                "answer_title": "Clarify Request",
                "direct_answer": "I need a bit more context before analyzing.",
                "summary_points": [
                    "Choose: single stock view",
                    "Choose: stock comparison",
                    "Choose: market or sector summary",
                ],
                "risks": [],
                "confidence": 0.55,
                "sources": ["Internal Intent Router"],
            },
            "confidence": 55,
            "sources": ["Internal Intent Router"],
            "followups": [
                "Is NVDA still a good investment?",
                "Compare NVDA vs AMD",
                "Summarize today’s market sentiment",
            ],
            "status": {
                "online": True,
                "message": "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
        }

    if is_comparison_query:
        analysis_type = "stock_comparison"
        comp_symbols = _extract_comparison_symbols(question, payload.context)
        if len(comp_symbols) < 2:
            return {
                "intent": "stock_comparison",
                "intent_category": intent_category,
                "analysis_type": analysis_type,
                "analysis_engine": analysis_engine,
                "answer": "I need two valid symbols to compare. Example: Compare NVDA vs AMD.",
                "confidence": 45,
                "sources": ["Internal Intent Router"],
                "followups": ["Compare NVDA vs AMD", "Compare AAPL vs MSFT"],
                "answer_schema": {
                    "intent": "stock_comparison",
                    "answer_title": "Comparison Needs Two Symbols",
                    "direct_answer": "Please provide both symbols for a side-by-side comparison.",
                    "summary_points": ["Format: Compare <SYMBOL1> vs <SYMBOL2>"],
                    "risks": [],
                    "confidence": 0.45,
                    "sources": ["Internal Intent Router"],
                },
            }

        left_symbol, right_symbol = comp_symbols[0], comp_symbols[1]
        left_result = _analyze_stock_pipeline(left_symbol, window_days=14)
        right_result = _analyze_stock_pipeline(right_symbol, window_days=14)
        if not left_result.get("ok") or not right_result.get("ok"):
            return {
                "intent": "stock_comparison",
                "intent_category": intent_category,
                "analysis_type": analysis_type,
                "analysis_engine": analysis_engine,
                "answer": "I don’t have enough confirmed data for one of these symbols right now.",
                "confidence": 40,
                "sources": ["Finnhub", "Market News", "Yahoo Finance"],
                "followups": [
                    f"Show single-stock view for {left_symbol}",
                    f"Show single-stock view for {right_symbol}",
                ],
                "answer_schema": {
                    "intent": "stock_comparison",
                    "answer_title": f"{left_symbol} vs {right_symbol}",
                    "direct_answer": "Comparison is unavailable because one or both symbols have incomplete data.",
                    "summary_points": [],
                    "risks": ["Data coverage is incomplete for this pair."],
                    "confidence": 0.4,
                    "sources": ["Finnhub", "Market News", "Yahoo Finance"],
                },
            }

        sources = list(dict.fromkeys((left_result.get("sources", []) + right_result.get("sources", []))))
        schema = _build_comparison_schema(left_result, right_result, sources)
        l = left_result.get("analysis", {})
        r = right_result.get("analysis", {})
        fallback_text = (
            f"Here’s a direct {left_symbol} vs {right_symbol} comparison. "
            f"Momentum: {left_symbol} {safe_float((left_result.get('raw', {}) or {}).get('signals', {}).get('momentum_score', 0)):.1f} "
            f"vs {right_symbol} {safe_float((right_result.get('raw', {}) or {}).get('signals', {}).get('momentum_score', 0)):.1f}; "
            f"News sentiment: {left_symbol} {safe_float((left_result.get('raw', {}) or {}).get('sentiment_avg', 0)):+.2f} "
            f"vs {right_symbol} {safe_float((right_result.get('raw', {}) or {}).get('sentiment_avg', 0)):+.2f}; "
            f"Risk: {left_symbol} {l.get('risk_level', 'Medium')} vs {right_symbol} {r.get('risk_level', 'Medium')}."
        )
        answer = _generate_grounded_response(
            question=question,
            intent="stock_comparison",
            evidence={
                "left": l,
                "right": r,
                "left_raw": left_result.get("raw", {}),
                "right_raw": right_result.get("raw", {}),
                "schema": schema,
                "sources": sources,
            },
            fallback_text=fallback_text,
        )
        return {
            "intent": "stock_comparison",
            "intent_category": intent_category,
            "analysis_type": analysis_type,
            "analysis_engine": analysis_engine,
            "answer": answer,
            "answer_schema": schema,
            "confidence": int(schema.get("confidence", 70)),
            "sources": sources,
            "followups": schema.get("followups", _build_followup_prompts("stock_comparison", left_symbol)),
            "charts": {
                "price": _build_price_chart(left_symbol),
                "sentiment": _build_sentiment_chart(left_symbol),
            },
            "status": {
                "online": True,
                "message": "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
            "data_validation": {"price_data": True, "news_data": True, "technical_data": True},
            "analysis": {
                "type": "stock_comparison",
                "left_symbol": left_symbol,
                "right_symbol": right_symbol,
            },
        }

    if is_stock_risk:
        analysis_type = "stock_risk"
        risk_symbol = explicit_symbol or symbol or str(payload.context.selected_stock or "").upper().strip()
        if not risk_symbol:
            if payload.context.watchlist:
                risk_symbol = str(payload.context.watchlist[0]).upper().strip()
            elif payload.context.recent_searches:
                risk_symbol = str(payload.context.recent_searches[0]).upper().strip()
            else:
                return {
                    "intent": "risk_explanation",
                    "intent_category": intent_category,
                    "analysis_type": analysis_type,
                    "analysis_engine": analysis_engine,
                    "answer": "I need a stock symbol for downside risk analysis. Example: What are NVDA downside risks?",
                    "confidence": 45,
                    "sources": ["Internal Intent Router"],
                    "followups": ["What are NVDA downside risks?", "What are AAPL downside risks?"],
                }
        stock_result = _analyze_stock_pipeline(risk_symbol, window_days=14)
        if not stock_result.get("ok"):
            return {
                "intent": "risk_explanation",
                "intent_category": intent_category,
                "analysis_type": analysis_type,
                "analysis_engine": analysis_engine,
                "answer": stock_result.get("message", "I cannot confirm this analysis due to missing market data."),
                "confidence": 40,
                "sources": stock_result.get("sources", []),
                "followups": _build_followup_prompts("sector_risk", risk_symbol, _sector_for_symbol(risk_symbol)),
            }
        risk_result = _build_stock_risk_response(risk_symbol, stock_result, market)
        return {
            "intent": "risk_explanation",
            "intent_category": intent_category,
            "analysis_type": analysis_type,
            "analysis_engine": analysis_engine,
            "answer": risk_result["answer"],
            "answer_schema": risk_result["schema"],
            "confidence": risk_result["schema"].get("confidence", 74),
            "sources": risk_result["schema"].get("sources", []),
            "followups": risk_result["followups"],
            "status": {
                "online": True,
                "message": "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
            "analysis": {
                "type": "stock_risk",
                "ticker": risk_symbol,
            },
            "summary": {
                "market_sentiment": market.get("market_label", "Neutral"),
                "fear_greed_score": market.get("market_score", 50),
                "trending_sector": _sector_for_symbol(risk_symbol),
                "risk_outlook": market.get("risk_outlook", "Medium"),
            },
            "charts": stock_result.get("charts", {}),
        }

    if is_market_risk:
        analysis_type = "market_risk"
        risk_result = _build_market_risk_response(market)
        return {
            "intent": "risk_explanation",
            "intent_category": intent_category,
            "analysis_type": analysis_type,
            "analysis_engine": analysis_engine,
            "answer": risk_result["answer"],
            "answer_schema": risk_result["schema"],
            "confidence": risk_result["schema"].get("confidence", 70),
            "sources": risk_result["schema"].get("sources", []),
            "followups": risk_result["followups"],
            "status": {
                "online": True,
                "message": "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
            "analysis": {
                "type": "market_risk",
            },
            "summary": {
                "market_sentiment": market.get("market_label", "Neutral"),
                "fear_greed_score": market.get("market_score", 50),
                "trending_sector": (market.get("sector_momentum") or {}).get("sector", "Technology"),
                "risk_outlook": market.get("risk_outlook", "Medium"),
            },
        }

    if is_sector_risk:
        analysis_type = "sector_risk"
        sector_rank = _rank_sector_etfs()
        rankings = sector_rank.get("rankings", [])
        resolved_sector = _resolve_sector_context(question, payload.context, rankings)
        top_match = next((x for x in rankings if str(x.get("sector", "")).lower() == resolved_sector.lower()), {}) if rankings else {}
        risk_result = _build_sector_risk_response(question, resolved_sector, market, top_match)
        return {
            "intent": "risk_explanation",
            "intent_category": intent_category,
            "analysis_type": analysis_type,
            "analysis_engine": analysis_engine,
            "answer": risk_result["answer"],
            "answer_schema": risk_result["schema"],
            "confidence": risk_result["schema"].get("confidence", 74),
            "sources": risk_result["schema"].get("sources", []),
            "followups": risk_result["followups"],
            "status": {
                "online": True,
                "message": "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
            "analysis": {
                "type": "sector_risk",
                "sector": resolved_sector,
            },
            "summary": {
                "market_sentiment": market.get("market_label", "Neutral"),
                "fear_greed_score": market.get("market_score", 50),
                "trending_sector": resolved_sector,
                "risk_outlook": market.get("risk_outlook", "Medium"),
            },
        }

    if is_sector_stock_picker:
        analysis_type = "sector_stock_picker"
        sector_rank = _rank_sector_etfs()
        rankings = sector_rank.get("rankings", [])
        resolved_sector = _resolve_sector_context(question, payload.context, rankings)
        etf_symbol = SECTOR_ETF_MAP.get(resolved_sector, "XLK")
        sector_snapshot = next((x for x in rankings if str(x.get("sector", "")).lower() == resolved_sector.lower()), {}) if rankings else {}
        stock_rank = _rank_sector_stock_momentum(resolved_sector)
        top_stocks = stock_rank.get("stocks", [])[:5]
        market_label = str(market.get("market_label", "Unknown"))
        market_score_raw = market.get("market_score")
        market_score = float(market_score_raw) if market_score_raw is not None else None
        weak_regime = market_label in {"Fear", "Extreme Fear"}

        if len(top_stocks) < 3:
            direct = f"I do not have enough confirmed stock-level ranking data for {resolved_sector} right now."
            display_rows = top_stocks
            confidence = 52
        else:
            direct = f"Top momentum stocks in {resolved_sector}: {', '.join([x['symbol'] for x in top_stocks])}."
            display_rows = top_stocks
            confidence = 74

        top_list = [w.get("symbol") for w in display_rows if w.get("symbol")][:5]
        why_lines = [
            f"{i+1}. {row.get('name') or row.get('symbol')} ({row.get('symbol')}) | "
            f"Price " + (f"${safe_float(row.get('price')):.2f}" if row.get("price") is not None else "N/A") + " | "
            f"3M Return " + (f"{safe_float(row.get('return_3m_pct')):+.2f}%" if row.get("return_3m_pct") is not None else "N/A") + " | "
            f"Momentum {row.get('momentum', 'N/A')}"
            for i, row in enumerate(display_rows[:5])
        ]
        risk_note = (
            f"Risk note: market regime is {market_label}, so higher-beta names in {resolved_sector} can stay volatile."
            if weak_regime else
            f"Risk note: watch for sector rotation and earnings-event volatility in {resolved_sector} names."
        )
        momentum_snapshot = sector_snapshot.get("momentum_score")
        momentum_context = (
            "improving" if momentum_snapshot is not None and safe_float(momentum_snapshot) >= 55 else "mixed"
        )
        fg_part = (
            f"Fear & Greed Index: {market_score:.0f} ({market_label})."
            if market_score is not None
            else "Fear & Greed Index: N/A."
        )
        sector_context = (
            f"{resolved_sector} sector momentum is {momentum_context} "
            f"based on available 3M trend and relative-strength signals. {fg_part}"
        )
        followups = _build_followup_prompts("sector_stock_picker", top_list[0] if top_list else "", resolved_sector)
        answer = (
            f"Direct answer: {direct}\n\n"
            f"Sector overview: {resolved_sector} ({etf_symbol})\n"
            f"Top Stocks: {' • '.join(top_list) if top_list else 'N/A'}\n\n"
            f"Top momentum stocks:\n" + ("\n".join(why_lines) if why_lines else "- No confirmed stock-level ranking data available.") + "\n\n"
            f"Sector context: {sector_context}\n\n"
            f"{risk_note}\n\n"
            f"Suggested follow-ups: {' / '.join(followups)}"
        )
        answer_schema = {
            "intent": "sector_stock_picker",
            "answer_title": f"{resolved_sector} Top Momentum Stocks",
            "direct_answer": direct,
            "summary_points": [f"- {line}" for line in why_lines],
            "sector_overview": {
                "sector": resolved_sector,
                "etf": etf_symbol,
                "top_stocks_inline": top_list,
                "fear_greed_index": round(market_score, 1) if market_score is not None else None,
                "market_regime": market_label,
                "sector_momentum_score": round(safe_float(momentum_snapshot), 2) if momentum_snapshot is not None else None,
                "context": sector_context,
            },
            "sector_stock_picker": {
                "sector": resolved_sector,
                "etf": etf_symbol,
                "stocks": display_rows if display_rows else [],
            },
            "risks": [risk_note.replace("Risk note: ", "")],
            "confidence": confidence,
            "sources": ["Finnhub", "Market News", "Internal Technical Model"],
            "followups": followups,
            "data_coverage": {
                "stock_level_ranking": len(top_stocks) >= 3,
                "market_regime": True,
            },
        }
        return {
            "intent": "sector_stock_picker",
            "intent_category": intent_category,
            "analysis_type": analysis_type,
            "analysis_engine": analysis_engine,
            "answer": answer,
            "answer_schema": answer_schema,
            "confidence": confidence,
            "sources": ["Finnhub", "Market News", "Internal Technical Model"],
            "followups": followups,
            "status": {
                "online": True,
                "message": "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
            "analysis": {
                "type": "sector_stock_picker",
                "sector": resolved_sector,
                "top_stocks": top_list,
            },
            "summary": {
                "market_sentiment": market_label,
                "fear_greed_score": market.get("market_score"),
                "trending_sector": resolved_sector,
            },
        }

    if is_sector_query or is_market_query:
        analysis_type = "sector_or_market"
        sector_rank = _rank_sector_etfs()
        rankings = sector_rank.get("rankings", [])
        if not rankings:
            return {
                "intent": "sector_analysis" if is_sector_query else "market_overview",
                "intent_category": intent_category,
                "analysis_type": analysis_type,
                "analysis_engine": analysis_engine,
                "answer": "I cannot confirm sector momentum ranking right now because live sector data is unavailable.",
                "confidence": 35,
                "data_validation": {"price_data": False, "news_data": False, "technical_data": False},
                "sources": ["Finnhub", "Market News", "Internal Technical Model"],
                "followups": [
                    "Try again in a few minutes",
                    "Ask for single-stock analysis instead",
                ],
                "status": {
                    "online": True,
                    "message": "Connected",
                    "live_data_ready": False,
                    "market_context_loaded": True,
                },
            }

        top = rankings[0]
        top_sector = str(top.get("sector", "Unknown"))
        top_etf = str(top.get("etf", "SPY"))
        score_raw = top.get("momentum_score")
        score = safe_float(score_raw) if score_raw is not None else None
        top_news_sentiment = safe_float(top.get("news_sentiment"))
        top_news_label = "Bullish" if top_news_sentiment > 0.15 else ("Bearish" if top_news_sentiment < -0.15 else "Neutral")
        signal = (
            f"Overweight {top_sector}" if score is not None and score >= 70
            else (f"Selective exposure to {top_sector}" if score is not None and score >= 50 else "Defensive sector allocation")
        )
        confidence = int(max(45, min(92, round(50 + (score * 0.35 if score is not None else 12)))))
        fg_score = market.get("market_score")
        fg_line = (
            f"Fear & Greed: {fg_score} ({market['market_label']})"
            if fg_score is not None
            else f"Fear & Greed: N/A ({market['market_label']})"
        )
        sections = {
            "market_summary": [
                fg_line,
                f"Strongest sector now: {top_sector} ({top_etf})",
                "Sector ranking (3M momentum): " + " | ".join(
                    [f"{r['sector']} {safe_float(r['momentum_score']):.1f}" for r in rankings[:3]]
                ),
            ],
            "technical_signals": [
                f"{top_etf} 3M return: {safe_float(top.get('return_3m_pct')):+.2f}%",
                (
                    f"Relative strength vs SPY: {safe_float(top.get('relative_strength_pct')):+.2f}%"
                    if top.get("relative_strength_pct") is not None
                    else "Relative strength vs SPY: N/A"
                ),
                (f"Sector momentum score: {score:.1f}/100" if score is not None else "Sector momentum score: N/A"),
            ],
            "news_sentiment": [
                f"{top_sector} news sentiment score: {safe_float(top.get('news_sentiment')):+.3f}",
                "News sentiment is included in sector momentum ranking.",
            ],
            "risk_factors": [
                "Sector leadership can rotate quickly during macro shocks.",
                "High momentum sectors may mean higher drawdown risk.",
                f"Current market regime: {market['market_label']}",
            ],
            "ai_recommendation": {
                "signal": signal,
                "reason": "Based on 3M return, relative strength, and news sentiment.",
                "forecast_horizon": {},
            },
            "confidence_score": confidence,
            "sources": ["Finnhub", "Market News", "Yahoo Finance", "Internal Technical Model"],
            "sector_rankings": rankings,
        }
        ret3m_txt = (
            f"{safe_float(top.get('return_3m_pct')):+.2f}%"
            if top.get("return_3m_pct") is not None
            else "N/A"
        )
        rs_txt = (
            f"{safe_float(top.get('relative_strength_pct')):+.2f}%"
            if top.get("relative_strength_pct") is not None
            else "N/A"
        )
        score_txt = f"{score:.1f}/100" if score is not None else "N/A"
        fg_txt = f"{fg_score} ({market['market_label']})" if fg_score is not None else f"N/A ({market['market_label']})"
        fallback_text = (
            f"ตอนนี้กลุ่มที่เด่นที่สุดจากข้อมูลที่มีคือ {top_sector} ({top_etf}) "
            f"โดย 3M return = {ret3m_txt}, Relative Strength vs SPY = {rs_txt}, "
            f"และ sector momentum score = {score_txt}. "
            f"ภาพรวมตลาด Fear & Greed = {fg_txt}. "
            f"ดังนั้นมุมมองเชิงกลยุทธ์ตอนนี้คือ {signal} พร้อมติดตามการหมุน sector อย่างใกล้ชิด."
        )
        answer = _generate_grounded_response(
            question=question,
            intent="sector_explanation" if is_sector_explanation else ("sector_analysis" if is_sector_query else "market_overview"),
            evidence={
                "market": market,
                "top_sector": top,
                "rankings": rankings[:5],
                "recommendation": signal,
                "confidence": confidence,
                "sources": sections["sources"],
            },
            fallback_text=fallback_text,
        )
        answer_schema = _build_answer_schema(
            intent="sector_explanation" if is_sector_explanation else ("sector_analysis" if is_sector_query else "market_overview"),
            analysis={
                "ticker": top_etf,
                "recommendation": signal,
                "confidence": confidence,
                "technical_trend": "Momentum-driven",
                "momentum": sector_rank.get("top_momentum_label", "Moderate"),
                "news_sentiment": top_news_label,
                "risks": sections.get("risk_factors", []),
                "forecast_horizon": {},
            },
            market=market,
            sources=sections["sources"],
            signal=signal,
        )
        followups = _build_followup_prompts(
            "sector_explanation" if is_sector_explanation else ("sector_analysis" if is_sector_query else "market_overview"),
            top_etf,
            top_sector,
        )
        return {
            "intent": "sector_explanation" if is_sector_explanation else ("sector_analysis" if is_sector_query else "market_overview"),
            "intent_category": intent_category,
            "analysis_type": analysis_type,
            "analysis_engine": analysis_engine,
            "answer": answer,
            "confidence": confidence,
            "data_validation": {"price_data": True, "news_data": True, "technical_data": True},
            "analysis": {
                "type": "sector_explanation" if is_sector_explanation else ("sector_analysis" if is_sector_query else "market_overview"),
                "ticker": top_etf,
                "current_price": None,
                "recommendation": signal,
                "risk_level": market["risk_outlook"],
                "technical_trend": "Momentum-driven",
                "news_sentiment": top_news_label,
                "momentum": sector_rank.get("top_momentum_label", "Moderate"),
                "forecast_horizon": {},
                "sector_rankings": rankings,
            },
            "sections": {},
            "sources": sections["sources"],
            "summary": {
                "market_sentiment": market["market_label"],
                "fear_greed_score": market["market_score"],
                "top_ai_pick": top_etf,
                "top_ai_pick_confidence": confidence,
                "trending_sector": top_sector,
                "sector_momentum": sector_rank.get("top_momentum_label", "Moderate"),
                "risk_outlook": market["risk_outlook"],
                "signal": signal,
                "forecast_horizon": {},
                "market_momentum": safe_float(top.get("momentum_score")),
                "sector_performance": {r["sector"]: safe_float(r["momentum_score"]) for r in rankings},
                "explanation": "Sector ranking is computed from 3M return, relative strength vs SPY, and aggregated news sentiment.",
            },
            "charts": {
                "price": _build_price_chart(top_etf),
                "sentiment": _build_sentiment_chart(top_etf),
            },
            "answer_schema": answer_schema,
            "followups": followups,
            "status": {
                "online": True,
                "message": "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
            "gemini_used": bool(GEMINI_API_KEY),
        }

    if is_portfolio_query:
        holdings = payload.context.portfolio or []
        symbols = [str(x.get("symbol", "")).upper().strip() for x in holdings if str(x.get("symbol", "")).strip()]
        if not symbols:
            symbols = [str(x).upper() for x in (payload.context.watchlist or [])][:8]
        if not symbols:
            return {
                "intent": "portfolio_advice",
                "answer": "I cannot analyze portfolio risk because no user portfolio positions were provided.",
                "confidence": 30,
                "data_validation": {"price_data": False, "news_data": False, "technical_data": False},
                "sources": ["Finnhub", "Internal Portfolio Model"],
                "followups": [
                    "Add portfolio positions first",
                    "Ask for market overview instead",
                ],
                "status": {
                    "online": True,
                    "message": "Connected",
                    "live_data_ready": False,
                    "market_context_loaded": True,
                },
            }

        sector_counts: Dict[str, int] = {}
        for sym in symbols:
            sec = _sector_for_symbol(sym)
            sector_counts[sec] = sector_counts.get(sec, 0) + 1
        dominant = max(sector_counts.items(), key=lambda kv: kv[1])[0] if sector_counts else "Technology"
        concentration = (max(sector_counts.values()) / max(len(symbols), 1)) if sector_counts else 0.5
        diversification = "Low" if concentration >= 0.55 else ("Moderate" if concentration >= 0.35 else "High")
        risk = "High" if market["risk_outlook"] == "High" and concentration >= 0.5 else ("Medium" if concentration >= 0.35 else "Low")
        confidence = 74
        sections = {
            "market_summary": [
                f"Tracked holdings: {len(symbols)}",
                f"Dominant sector: {dominant}",
                f"Diversification: {diversification}",
            ],
            "technical_signals": [
                f"Market regime: {market['market_label']} ({market['market_score']})",
                f"Concentration ratio: {concentration*100:.1f}%",
            ],
            "news_sentiment": [
                "Portfolio-level sentiment inferred from market and dominant sector.",
                f"Current risk regime: {market['risk_outlook']}",
            ],
            "risk_factors": [
                "Concentrated portfolios can underperform during sector rotation.",
                "Macro rate shifts can raise portfolio volatility.",
            ],
            "ai_recommendation": {
                "signal": "Reduce concentration risk" if diversification == "Low" else "Maintain balanced allocation",
                "reason": "Based on sector concentration and market regime.",
                "forecast_horizon": {"7d": 0, "30d": 0, "90d": 0},
            },
            "confidence_score": confidence,
            "sources": ["Finnhub", "Market News", "Internal Portfolio Model"],
        }
        fallback_text = (
            f"พอร์ตตอนนี้ถือ {len(symbols)} ตัว โดยกระจุกใน {dominant} ค่อนข้างมาก "
            f"(concentration {concentration*100:.1f}%, diversification {diversification}). "
            f"ภาวะตลาดเป็น {market['market_label']} และ risk outlook คือ {market['risk_outlook']} "
            f"จึงแนะนำว่า {sections['ai_recommendation']['signal']} เพื่อกดความเสี่ยงรวมของพอร์ต."
        )
        answer = _generate_grounded_response(
            question=question,
            intent="portfolio_advice",
            evidence={
                "market": market,
                "portfolio_symbols": symbols,
                "dominant_sector": dominant,
                "concentration_pct": round(concentration * 100, 2),
                "diversification": diversification,
                "risk_level": risk,
                "suggested_action": sections["ai_recommendation"]["signal"],
                "confidence": confidence,
                "sources": sections["sources"],
            },
            fallback_text=fallback_text,
        )
        answer_schema = _build_answer_schema(
            intent="portfolio_advice",
            analysis={
                "ticker": symbols[0],
                "recommendation": sections["ai_recommendation"]["signal"],
                "confidence": confidence,
                "technical_trend": market["market_label"],
                "momentum": market["sector_momentum"].get("momentum", "Moderate"),
                "news_sentiment": "Market-driven",
                "risks": sections.get("risk_factors", []),
                "forecast_horizon": {},
            },
            market=market,
            sources=sections["sources"],
            signal=sections["ai_recommendation"]["signal"],
        )
        followups = _build_followup_prompts("portfolio_advice", symbols[0], dominant)
        return {
            "intent": "portfolio_advice",
            "answer": answer,
            "confidence": confidence,
            "data_validation": {"price_data": True, "news_data": True, "technical_data": True},
            "analysis": {
                "type": "portfolio_advice",
                "ticker": symbols[0],
                "current_price": None,
                "recommendation": sections["ai_recommendation"]["signal"],
                "risk_level": risk,
                "technical_trend": market["market_label"],
                "news_sentiment": "Market-driven",
                "momentum": market["sector_momentum"].get("momentum", "Moderate"),
                "forecast_horizon": {},
            },
            "sections": {},
            "sources": sections["sources"],
            "summary": {
                "market_sentiment": market["market_label"],
                "fear_greed_score": market["market_score"],
                "top_ai_pick": symbols[0],
                "top_ai_pick_confidence": confidence,
                "trending_sector": dominant,
                "sector_momentum": market["sector_momentum"].get("momentum", "Moderate"),
                "risk_outlook": risk,
                "signal": sections["ai_recommendation"]["signal"],
                "forecast_horizon": {},
                "market_momentum": market["sector_momentum"].get("score", 0.0),
                "sector_performance": market["sector_momentum"].get("all", {}),
                "explanation": "Portfolio risk is assessed from concentration and current market regime.",
            },
            "charts": {
                "price": _build_price_chart(symbols[0]),
                "sentiment": _build_sentiment_chart(symbols[0]),
            },
            "answer_schema": answer_schema,
            "followups": followups,
            "status": {
                "online": True,
                "message": "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
            "gemini_used": bool(GEMINI_API_KEY),
        }

    if intent in {"market_overview", "news_summary", "risk_explanation", "sector_explanation"}:
        sector_rank = _rank_sector_etfs()
        rankings = sector_rank.get("rankings", [])
        top = rankings[0] if rankings else {}
        confidence = 68
        fallback_text = (
            f"ตอนนี้ภาพรวมตลาดอยู่ที่ Fear & Greed {market['market_score']} ({market['market_label']}) "
            f"และกลุ่มนำตลาดคือ {top.get('sector', 'N/A')} ({top.get('etf', 'N/A')}) "
            f"ด้วยคะแนนโมเมนตัม {safe_float(top.get('momentum_score')):.1f}/100. "
            "หากต้องการคำแนะนำที่แม่นขึ้น กรุณาระบุชื่อหุ้นหรือพอร์ตที่ต้องการวิเคราะห์."
        )
        answer = _generate_grounded_response(
            question=question,
            intent=intent,
            evidence={
                "market": market,
                "top_sector": top,
                "rankings": rankings[:5],
                "sources": ["Finnhub", "Market News", "Yahoo Finance", "Internal Technical Model"],
            },
            fallback_text=fallback_text,
        )
        answer_schema = _build_answer_schema(
            intent=intent,
            analysis={
                "ticker": str(top.get("etf", "N/A")),
                "recommendation": "Market overview",
                "confidence": confidence,
                "technical_trend": "Mixed",
                "momentum": sector_rank.get("top_momentum_label", "Moderate"),
                "news_sentiment": market["market_label"],
                "forecast_horizon": {},
            },
            market=market,
            sources=["Finnhub", "Market News", "Yahoo Finance", "Internal Technical Model"],
            signal="Market overview",
        )
        followups = _build_followup_prompts(intent, str(top.get("etf", "N/A")), str(top.get("sector", "N/A")))
        return {
            "intent": intent,
            "answer": answer,
            "confidence": confidence,
            "data_validation": {"price_data": True, "news_data": True, "technical_data": True},
            "analysis": {
                "type": intent,
                "ticker": str(top.get("etf", "N/A")),
                "recommendation": "Market overview",
                "risk_level": market["risk_outlook"],
            },
            "sections": {},
            "sources": ["Finnhub", "Market News", "Yahoo Finance", "Internal Technical Model"],
            "summary": {
                "market_sentiment": market["market_label"],
                "fear_greed_score": market["market_score"],
                "top_ai_pick": str(top.get("etf", "N/A")),
                "top_ai_pick_confidence": confidence,
                "trending_sector": str(top.get("sector", "N/A")),
                "sector_momentum": sector_rank.get("top_momentum_label", "Moderate"),
                "risk_outlook": market["risk_outlook"],
                "signal": "Market overview",
                "forecast_horizon": {},
            },
            "charts": {
                "price": _build_price_chart(str(top.get("etf", "N/A"))),
                "sentiment": _build_sentiment_chart(str(top.get("etf", "N/A"))),
            },
            "answer_schema": answer_schema,
            "followups": followups,
            "status": {
                "online": True,
                "message": "Connected",
                "live_data_ready": True,
                "market_context_loaded": True,
            },
            "gemini_used": bool(GEMINI_API_KEY),
        }

    if explicit_symbol:
        symbol = explicit_symbol
    if not symbol:
        if payload.context.watchlist:
            symbol = str(payload.context.watchlist[0]).upper()
        elif payload.context.recent_searches:
            symbol = str(payload.context.recent_searches[0]).upper()
        else:
            return {
                "intent": intent,
                "answer": "I cannot determine which symbol to analyze. Please provide a stock ticker.",
                "confidence": 30,
                "warning": "Missing symbol context.",
                "data_validation": {"price_data": False, "news_data": False, "technical_data": False},
                "analysis": {},
                "sources": [],
                "summary": {
                    "market_sentiment": market["market_label"],
                    "fear_greed_score": market["market_score"],
                    "top_ai_pick": "N/A",
                    "top_ai_pick_confidence": 30,
                    "trending_sector": market["sector_momentum"].get("sector", "N/A"),
                    "sector_momentum": market["sector_momentum"].get("momentum", "N/A"),
                    "risk_outlook": market["risk_outlook"],
                    "forecast_horizon": {},
                },
                "answer_schema": {
                    "summary": "No ticker symbol available in question or context.",
                    "stance": "Unknown",
                    "rationale": ["Provide a ticker, e.g. NVDA, AAPL, TSLA."],
                    "risks": ["No symbol means no stock-level analysis can be validated."],
                    "actionable_view": "Resubmit your question with a symbol.",
                    "confidence": 30,
                    "sources": [],
                    "data_coverage": {"price_data": False, "news_data": False, "technical_data": False},
                },
                "followups": ["Analyze NVDA", "Compare NVDA vs AMD", "Show market overview"],
                "status": {
                    "online": True,
                    "message": "Connected",
                    "live_data_ready": False,
                    "market_context_loaded": True,
                },
            }

    stock_result = _analyze_stock_pipeline(symbol, window_days=14)
    if not stock_result.get("ok"):
        followups = _build_followup_prompts(intent, symbol, market["sector_momentum"].get("sector", "Technology"))
        return {
            "intent": intent,
            "answer": stock_result.get("message"),
            "confidence": 35,
            "warning": "Insufficient reliable market data for a validated response.",
            "data_validation": stock_result.get("data_validation", {}),
            "analysis": {},
            "sources": stock_result.get("sources", []),
            "summary": {
                "market_sentiment": market["market_label"],
                "fear_greed_score": market["market_score"],
                "top_ai_pick": symbol,
                "top_ai_pick_confidence": 35,
                "trending_sector": market["sector_momentum"].get("sector", "Technology"),
                "sector_momentum": market["sector_momentum"].get("momentum", "Moderate"),
                "risk_outlook": market["risk_outlook"],
                "forecast_horizon": {"7d": 0, "30d": 0, "90d": 0},
            },
            "charts": stock_result.get("charts", {}),
            "answer_schema": {
                "summary": stock_result.get("message"),
                "stance": "Neutral",
                "rationale": ["Current market dataset is incomplete for this symbol."],
                "risks": ["Signal quality is reduced due to missing data."],
                "actionable_view": "Request another symbol or broader market view.",
                "confidence": 35,
                "sources": stock_result.get("sources", []),
                "data_coverage": stock_result.get("data_validation", {}),
            },
            "followups": followups,
            "status": {
                "online": True,
                "message": "Fallback mode",
                "live_data_ready": False,
                "market_context_loaded": True,
            },
        }

    analysis = stock_result["analysis"]
    confidence = int(analysis.get("confidence", 70))
    forecast_horizons = analysis.get("forecast_horizon", {"7d": 0, "30d": 0, "90d": 0})
    top_sector = market["sector_momentum"].get("sector", _sector_for_symbol(symbol))
    sources = stock_result.get("sources", ["Finnhub", "Market News", "Yahoo Finance"])
    sections = _build_structured_answer_sections(
        intent=intent,
        question=question,
        analysis=analysis,
        market=market,
        sources=sources,
        context=payload.context,
    )

    fallback_text = (
        f"{analysis.get('company_name')} ({analysis.get('ticker')})\n\n"
        "Stock Overview\n"
        f"- Price: ${safe_float(analysis.get('current_price')):.2f}\n"
        f"- Sector: {analysis.get('sector')}\n"
        f"- Industry: {analysis.get('industry')}\n\n"
        "Technical Signals\n"
        f"- Technical trend: {analysis.get('technical_trend')}\n"
        f"- Momentum: {analysis.get('momentum')}\n\n"
        "Market Sentiment\n"
        f"- News sentiment: {analysis.get('news_sentiment')}\n"
        f"- Fear & Greed Index: {market['market_score']} ({market['market_label']})\n\n"
        "Key Risks\n"
        + "\n".join([f"- {r}" for r in (analysis.get("risks") or [])[:3]])
        + "\n\nInvestment View\n"
        f"- Recommendation: {analysis.get('recommendation')}\n"
        f"- Forecast horizon: 7D {safe_float(forecast_horizons.get('7d')):+.2f}% | "
        f"30D {safe_float(forecast_horizons.get('30d')):+.2f}% | "
        f"90D {safe_float(forecast_horizons.get('90d')):+.2f}%"
    )
    if intent == "single_stock_analysis":
        answer = fallback_text
    else:
        answer = _generate_grounded_response(
            question=question,
            intent=intent,
            evidence={
                "analysis": analysis,
                "market": market,
                "forecast": forecast_horizons,
                "sources": sources,
                "summary_sections": sections,
            },
            fallback_text=fallback_text,
        )
    answer = answer.replace("I'm not fully confident", "Based on current technical and sentiment data")

    followups = _build_followup_prompts(intent, analysis.get("ticker", symbol), top_sector)
    answer_schema = _build_answer_schema(
        intent=intent,
        analysis=analysis,
        market=market,
        sources=sources,
        signal=analysis.get("recommendation", "Hold"),
    )

    return {
        "intent": intent,
        "answer": answer,
        "confidence": confidence,
        "data_validation": stock_result.get("data_validation", {}),
        "analysis": {
            "type": intent,
            **analysis,
        },
        "sections": {},
        "sources": sources,
        "summary": {
            "market_sentiment": market["market_label"],
            "fear_greed_score": market["market_score"],
            "top_ai_pick": analysis.get("ticker", symbol),
            "top_ai_pick_confidence": confidence,
            "trending_sector": top_sector,
            "sector_momentum": market["sector_momentum"].get("momentum", "Moderate"),
            "risk_outlook": market["risk_outlook"],
            "signal": analysis.get("recommendation", "Hold"),
            "forecast_horizon": forecast_horizons,
            "market_momentum": market["sector_momentum"].get("score", 0.0),
            "sector_performance": market["sector_momentum"].get("all", {}),
            "explanation": "AI analysis indicates that sectors with stronger relative momentum and positive sentiment are receiving higher allocation signals.",
        },
        "charts": stock_result.get("charts", {}),
        "answer_schema": answer_schema,
        "followups": followups,
        "status": {
            "online": True,
            "message": "Connected",
            "live_data_ready": True,
            "market_context_loaded": True,
        },
        "gemini_used": bool(GEMINI_API_KEY),
    }


@app.post("/ai-summary")
@app.post("/api/ai-summary")
def ai_summary_endpoint(payload: AISummaryRequest):
    watchlist = normalize_symbol_list(payload.context.watchlist[:8] if payload.context.watchlist else [])
    recent = normalize_symbol_list(payload.context.recent_searches[:8] if payload.context.recent_searches else [])
    cache_key = json.dumps({"watchlist": watchlist, "recent": recent}, sort_keys=True)
    now_ts = time.time()

    cached_summary = ai_summary_cache.get(cache_key)
    if cached_summary and (now_ts - float(cached_summary.get("ts", 0))) < AI_SUMMARY_CACHE_TTL:
        return cached_summary.get("data")

    market = _build_market_snapshot(payload.context)
    context_symbols = watchlist[:5]
    candidates = context_symbols or _default_active_symbols(5)
    if not candidates:
        raise HTTPException(status_code=503, detail="No live symbols available for AI summary")
    best = {"symbol": candidates[0], "confidence": 0, "score": -1, "analysis": None}

    # Fast path: use AI picker ranking first (DB-backed and much faster than per-symbol live pipeline loop).
    if HAS_AI_PICKER:
        try:
            picker_rows = get_ai_picks("BALANCED", 20) or []
            if context_symbols:
                picker_rows = [row for row in picker_rows if normalize_symbol(row.get("ticker")) in set(context_symbols)]
            if picker_rows:
                top_row = max(picker_rows, key=lambda row: safe_float(row.get("ai_score")))
                pick_conf = int(round(safe_float(top_row.get("confidence"))))
                best = {
                    "symbol": normalize_symbol(top_row.get("ticker")) or candidates[0],
                    "confidence": max(35, min(95, pick_conf or 70)),
                    "score": safe_float(top_row.get("ai_score")),
                    "analysis": None,
                }
        except Exception as e:
            logger.warning(f"ai-summary fast path failed, fallback to stock pipeline: {e}")

    # Fallback path: live pipeline (limited candidates for speed).
    if best["score"] < 0:
        for sym in candidates[:3]:
            try:
                analyzed = _analyze_stock_pipeline(sym, window_days=14)
                if not analyzed.get("ok"):
                    continue
                a = analyzed.get("analysis", {})
                score = safe_float(analyzed.get("raw", {}).get("ai_score"))
                conf = int(a.get("confidence", 0))
                if score > best["score"]:
                    best = {"symbol": sym, "confidence": conf, "score": score, "analysis": analyzed}
            except Exception:
                continue

    top_symbol = best["symbol"] or candidates[0]
    top_conf = best["confidence"] or 70
    explanation = (
        f"AI analysis indicates that {market['sector_momentum'].get('sector', 'Technology')} stocks "
        f"show {market['sector_momentum'].get('momentum', 'moderate').lower()} relative momentum "
        "supported by recent sentiment and trend signals."
    )
    response_payload = {
        "summary": {
            "market_sentiment": market["market_label"],
            "fear_greed_score": market["market_score"],
            "fear_greed_source": market.get("market_meta", {}).get("source", "InternalModel"),
            "top_ai_pick": top_symbol,
            "top_ai_pick_confidence": top_conf,
            "trending_sector": market["sector_momentum"].get("sector", "Technology"),
            "sector_momentum": market["sector_momentum"].get("momentum", "Moderate"),
            "risk_outlook": market["risk_outlook"],
            "forecast_horizon": (best.get("analysis", {}) or {}).get("analysis", {}).get("forecast_horizon", {"7d": 0, "30d": 0, "90d": 0}),
            "market_momentum": market["sector_momentum"].get("score", 0.0),
            "sector_performance": market["sector_momentum"].get("all", {}),
            "explanation": explanation,
        },
        "sources": ["Finnhub", "Market News", "Yahoo Finance", "Internal Technical Model"],
    }
    ai_summary_cache[cache_key] = {"ts": now_ts, "data": response_payload}
    return response_payload


@app.get("/ai-analyze-stock")
@app.get("/api/ai-analyze-stock")
def ai_analyze_stock_endpoint(
    ticker: str = Query(..., min_length=1, max_length=12),
    window_days: int = Query(14, ge=1, le=60),
):
    sym = str(ticker or "").strip().upper()
    result = _analyze_stock_pipeline(sym, window_days=window_days)
    if not result.get("ok"):
        return {
            "ticker": sym,
            "ok": False,
            "message": result.get("message"),
            "data_validation": result.get("data_validation", {}),
            "sources": result.get("sources", []),
            "charts": result.get("charts", {}),
        }
    return {
        "ticker": sym,
        "ok": True,
        "analysis": result.get("analysis", {}),
        "sources": result.get("sources", []),
        "charts": result.get("charts", {}),
    }


@app.post("/portfolio-insights")
@app.post("/api/portfolio-insights")
def portfolio_insights_endpoint(payload: PortfolioInsightRequest):
    symbols = []
    for item in payload.holdings:
        sym = str(item.get("symbol") or item.get("ticker") or "").upper().strip()
        if sym:
            symbols.append(sym)
    symbols.extend([str(s).upper().strip() for s in payload.watchlist if str(s).strip()])
    symbols = [s for i, s in enumerate(symbols) if s and s not in symbols[:i]][:12]
    if not symbols:
        return {
            "ok": False,
            "message": "I cannot confirm this analysis due to missing market data.",
            "risk_level": "Medium",
            "diversification": "Low",
            "suggestions": [],
            "sources": ["Finnhub", "Market News", "Yahoo Finance"],
        }

    sector_counts: Dict[str, int] = {}
    scores = []
    for sym in symbols:
        sector = _sector_for_symbol(sym)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        try:
            analyzed = _analyze_stock_pipeline(sym, window_days=14)
            if analyzed.get("ok"):
                scores.append(safe_float(analyzed.get("raw", {}).get("ai_score")))
        except Exception:
            continue

    dominant_sector = max(sector_counts.items(), key=lambda kv: kv[1])[0] if sector_counts else "Technology"
    concentration = max(sector_counts.values()) / max(1, len(symbols))
    diversification = "High" if concentration <= 0.35 else ("Moderate" if concentration <= 0.55 else "Low")
    avg_score = sum(scores) / len(scores) if scores else 50.0
    risk_level = "High" if avg_score < 45 else ("Medium" if avg_score < 70 else "Low")
    suggestions = [
        f"Reduce concentration in {dominant_sector} if allocation exceeds 45%.",
        "Add broad-market ETF exposure for downside stability.",
        "Review holdings with weak momentum and bearish sentiment weekly.",
    ]

    return {
        "ok": True,
        "symbols": symbols,
        "risk_level": risk_level,
        "diversification": diversification,
        "dominant_sector": dominant_sector,
        "avg_ai_score": round(avg_score, 2),
        "suggestions": suggestions,
        "sources": ["Finnhub", "Market News", "Yahoo Finance", "Internal Technical Model"],
    }


@app.get("/portfolio/positions")
@app.get("/api/portfolio/positions")
def get_portfolio_positions(authorization: Optional[str] = Header(default=None)):
    user_id = _extract_user_id_from_authorization(authorization)
    with SessionLocal() as db:
        rows: List[PortfolioPosition] = (
            db.query(PortfolioPosition)
            .filter(PortfolioPosition.user_id == user_id)
            .order_by(PortfolioPosition.created_at.desc())
            .all()
        )
    return {
        "ok": True,
        "items": [
            {
                "id": r.id,
                "symbol": r.symbol,
                "shares": float(r.shares or 0),
                "average_buy_price": float(r.average_buy_price or 0),
                "purchase_date": r.purchase_date,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in rows
        ],
    }


@app.post("/portfolio/positions")
@app.post("/api/portfolio/positions")
def create_portfolio_position(
    payload: PortfolioPositionCreate,
    authorization: Optional[str] = Header(default=None),
):
    user_id = _extract_user_id_from_authorization(authorization)
    symbol = str(payload.symbol or "").upper().strip()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    try:
        # Validate symbol quickly with provider quote.
        q = _get_portfolio_quote(symbol)
        if safe_float(q.get("price")) <= 0:
            raise ValueError("invalid price")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid symbol or quote unavailable: {e}")

    with SessionLocal() as db:
        row = PortfolioPosition(
            user_id=user_id,
            symbol=symbol,
            shares=float(payload.shares),
            average_buy_price=float(payload.average_buy_price),
            purchase_date=str(payload.purchase_date),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return {
        "ok": True,
        "item": {
            "id": row.id,
            "symbol": row.symbol,
            "shares": float(row.shares),
            "average_buy_price": float(row.average_buy_price),
            "purchase_date": row.purchase_date,
        },
    }


@app.put("/portfolio/positions/{position_id}")
@app.put("/api/portfolio/positions/{position_id}")
def update_portfolio_position(
    position_id: int,
    payload: PortfolioPositionUpdate,
    authorization: Optional[str] = Header(default=None),
):
    user_id = _extract_user_id_from_authorization(authorization)
    with SessionLocal() as db:
        row: Optional[PortfolioPosition] = (
            db.query(PortfolioPosition)
            .filter(PortfolioPosition.id == position_id, PortfolioPosition.user_id == user_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Position not found")

        if payload.symbol is not None:
            next_symbol = str(payload.symbol).upper().strip()
            if not next_symbol:
                raise HTTPException(status_code=400, detail="symbol cannot be empty")
            row.symbol = next_symbol
        if payload.shares is not None:
            row.shares = float(payload.shares)
        if payload.average_buy_price is not None:
            row.average_buy_price = float(payload.average_buy_price)
        if payload.purchase_date is not None:
            row.purchase_date = str(payload.purchase_date)
        row.updated_at = datetime.utcnow()

        db.add(row)
        db.commit()
        db.refresh(row)

    return {
        "ok": True,
        "item": {
            "id": row.id,
            "symbol": row.symbol,
            "shares": float(row.shares),
            "average_buy_price": float(row.average_buy_price),
            "purchase_date": row.purchase_date,
        },
    }


@app.delete("/portfolio/positions/{position_id}")
@app.delete("/api/portfolio/positions/{position_id}")
def delete_portfolio_position(position_id: int, authorization: Optional[str] = Header(default=None)):
    user_id = _extract_user_id_from_authorization(authorization)
    with SessionLocal() as db:
        row: Optional[PortfolioPosition] = (
            db.query(PortfolioPosition)
            .filter(PortfolioPosition.id == position_id, PortfolioPosition.user_id == user_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Position not found")
        db.delete(row)
        db.commit()
    return {"ok": True}


@app.get("/portfolio/overview")
@app.get("/api/portfolio/overview")
def portfolio_overview(
    range: str = Query("1m", description="1m | 3m | 6m | 1y"),
    authorization: Optional[str] = Header(default=None),
):
    user_id = _extract_user_id_from_authorization(authorization)
    normalized = str(range or "1m").lower()
    if normalized not in {"1m", "3m", "6m", "1y"}:
        normalized = "1m"
    payload = _calculate_portfolio_overview(user_id=user_id, range_value=normalized)
    payload["range"] = normalized
    payload["updated_at"] = datetime.utcnow().isoformat()
    payload["sources"] = ["Finnhub", "FMP", "Internal Portfolio Model"]
    return payload

@app.get("/stock/{symbol}")
def stock_endpoint(
    symbol: str,
    range: str = Query("3mo", description="1d | 5d | 1m | 3m | 6m | ytd | 1y | 5y | all")
):
    def _latest_day_range(history_rows: List[Dict[str, Any]]) -> Dict[str, float]:
        if not history_rows:
            return {"low": 0.0, "high": 0.0}
        last_date = str(history_rows[-1].get("date", ""))
        latest_day = last_date.split(" ")[0]
        same_day = [r for r in history_rows if str(r.get("date", "")).startswith(latest_day)]
        target_rows = same_day if same_day else [history_rows[-1]]
        lows = [safe_float(r.get("low")) for r in target_rows if safe_float(r.get("low")) > 0]
        highs = [safe_float(r.get("high")) for r in target_rows if safe_float(r.get("high")) > 0]
        if not lows or not highs:
            close_value = safe_float(history_rows[-1].get("close"))
            return {"low": close_value, "high": close_value}
        return {"low": min(lows), "high": max(highs)}

    def _get_52w_range(sym: str) -> Dict[str, float]:
        now_ts = time.time()
        cached = stock_stats_cache.get(sym)
        if cached and (now_ts - float(cached.get("ts", 0))) < 300:
            data = cached.get("data", {})
            return {"low": safe_float(data.get("low")), "high": safe_float(data.get("high"))}
        try:
            one_year = get_stock_data(sym, "1y")
            rows = one_year.get("history", []) or []
            highs = [safe_float(r.get("high")) for r in rows if safe_float(r.get("high")) > 0]
            lows = [safe_float(r.get("low")) for r in rows if safe_float(r.get("low")) > 0]
            if highs and lows:
                result = {"low": min(lows), "high": max(highs)}
                stock_stats_cache[sym] = {"ts": now_ts, "data": result}
                return result
        except Exception as e:
            logger.warning(f"52W range fallback failed for {sym}: {e}")
        return {"low": 0.0, "high": 0.0}

    def _yahoo_aligned_return(sym: str, range_value: str) -> Dict[str, Any]:
        key = str(range_value or "").strip().lower()
        cache_key = f"{sym.upper()}:{key}"
        now_ts = time.time()
        cached = stock_return_cache.get(cache_key)
        if cached and (now_ts - float(cached.get("ts", 0))) < 300:
            return dict(cached.get("data") or {})
        range_map = {
            "1d": ("1d", "5m"),
            "5d": ("5d", "30m"),
            "1m": ("1mo", "1d"),
            "1mo": ("1mo", "1d"),
            "3m": ("3mo", "1d"),
            "3mo": ("3mo", "1d"),
            "6m": ("6mo", "1d"),
            "6mo": ("6mo", "1d"),
            "ytd": ("ytd", "1d"),
            "1y": ("1y", "1d"),
            "5y": ("5y", "1d"),
            "all": ("max", "1d"),
            "max": ("max", "1d"),
        }
        yf_range, yf_interval = range_map.get(key, ("1mo", "1d"))
        for yf_symbol in _symbol_variants(sym):
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yf_symbol}"
                resp = requests.get(
                    url,
                    params={
                        "range": yf_range,
                        "interval": yf_interval,
                        "includePrePost": "false",
                        "events": "div,splits",
                    },
                    timeout=12,
                )
                if resp.status_code != 200:
                    continue
                payload = resp.json() if resp.content else {}
                result = ((payload.get("chart") or {}).get("result") or [])
                if not result:
                    continue
                quote = (((result[0].get("indicators") or {}).get("quote") or [{}])[0] or {})
                closes = quote.get("close") or []
                series = [safe_float(x) for x in closes if safe_float(x) > 0]
                if len(series) < 2:
                    continue
                first = safe_float(series[0])
                last = safe_float(series[-1])
                if first <= 0 or last <= 0:
                    continue
                result = {
                    "first_close": first,
                    "last_close": last,
                    "return_pct": ((last - first) / first) * 100.0,
                    "source": "YahooChartClose",
                }
                stock_return_cache[cache_key] = {"ts": now_ts, "data": result}
                return result
            except Exception:
                continue
        return {"first_close": 0.0, "last_close": 0.0, "return_pct": 0.0, "source": None}

    symbol = symbol.upper()
    stock_data = get_stock_data(symbol, range)
    history = stock_data.get("history", [])
    latest_price = stock_data.get("price", 0.0)
    previous_close = safe_float(stock_data.get("previous_close", 0.0))
    range_key = str(stock_data.get("range", _normalize_range(range))).lower()

    if history:
        # Keep return calculations close-only so they match finance platforms.
        latest_close = safe_float(history[-1].get("close")) or safe_float(latest_price)
        first_close = safe_float(history[0].get("close"))
        last_close = latest_close
        reference_close = previous_close if previous_close > 0 else (safe_float(history[-2].get("close")) if len(history) > 1 else 0.0)
    else:
        latest_close = safe_float(latest_price)
        first_close = 0.0
        last_close = latest_close
        reference_close = previous_close if previous_close > 0 else 0.0

    change_abs = (latest_close - reference_close) if reference_close > 0 else 0.0
    change_pct = ((change_abs / reference_close) * 100.0) if reference_close > 0 else 0.0
    range_return_source = "PrimaryCloseSeries"
    if range_key == "1d":
        range_return_pct = change_pct
    else:
        range_return_pct = ((latest_close - first_close) / first_close * 100.0) if first_close > 0 else 0.0

    # Force Yahoo as single baseline source for first/last close in all ranges for near 1:1 parity.
    yahoo_ret = _yahoo_aligned_return(symbol, range)
    if yahoo_ret["first_close"] > 0 and yahoo_ret["last_close"] > 0:
        first_close = safe_float(yahoo_ret["first_close"])
        last_close = safe_float(yahoo_ret["last_close"])
        latest_close = last_close
        range_return_pct = safe_float(yahoo_ret["return_pct"])
        range_return_source = str(yahoo_ret.get("source") or "YahooClose")

    day_range = _latest_day_range(history)
    range_52w = _get_52w_range(symbol)
    latest_volume = int(history[-1].get("volume") or 0) if history else 0

    return {
        "symbol": symbol,
        "name": stock_data.get("name", symbol),
        "latest_price": round(float(latest_close), 2),
        "previous_close": round(float(previous_close), 2) if previous_close else None,
        "change": round(float(change_abs), 2),
        "change_pct": round(float(change_pct), 4),
        "change_text": f"{change_abs:+.2f} ({change_pct:+.2f}%)",
        "range_return_pct": round(float(range_return_pct), 4),
        "range_return_source": range_return_source,
        "history": history,
        "range": stock_data.get("range", _normalize_range(range)),
        "first_close": round(float(first_close), 4) if first_close > 0 else None,
        "last_close": round(float(last_close), 4) if last_close > 0 else None,
        "volume": latest_volume,
        "day_range_low": round(float(day_range["low"]), 4) if day_range["low"] > 0 else None,
        "day_range_high": round(float(day_range["high"]), 4) if day_range["high"] > 0 else None,
        "range_52w_low": round(float(range_52w["low"]), 4) if range_52w["low"] > 0 else None,
        "range_52w_high": round(float(range_52w["high"]), 4) if range_52w["high"] > 0 else None,
        "source_provider": stock_data.get("provider"),
    }


@app.get("/stock/profile/{symbol}")
@app.get("/api/stock/profile/{symbol}")
def stock_profile_endpoint(symbol: str):
    sym = normalize_symbol(symbol)
    if not sym:
        raise HTTPException(status_code=400, detail="symbol is required")

    def _domain_from_url(url_value: Any) -> Optional[str]:
        raw = str(url_value or "").strip()
        if not raw:
            return None
        if not raw.startswith("http://") and not raw.startswith("https://"):
            raw = f"https://{raw}"
        try:
            parsed = urlparse(raw)
            host = str(parsed.netloc or "").lower().strip()
            if host.startswith("www."):
                host = host[4:]
            return host or None
        except Exception:
            return None

    profile = {
        "name": sym,
        "ticker": sym,
        "exchange": None,
        "industry": None,
        "logo": None,
        "weburl": None,
        "domain": None,
        "source": "Unknown",
    }

    try:
        fh = _finnhub_get("/stock/profile2", {"symbol": sym}) or {}
        profile.update({
            "name": fh.get("name") or sym,
            "ticker": fh.get("ticker") or sym,
            "exchange": fh.get("exchange"),
            "industry": fh.get("finnhubIndustry"),
            "logo": fh.get("logo"),
            "weburl": fh.get("weburl"),
            "source": "Finnhub",
        })
    except Exception as e:
        logger.warning(f"Finnhub profile unavailable for {sym}: {e}")
        try:
            fmp_rows = _fmp_get(f"/profile/{sym}")
            row = fmp_rows[0] if isinstance(fmp_rows, list) and fmp_rows else {}
            profile.update({
                "name": row.get("companyName") or row.get("name") or sym,
                "ticker": row.get("symbol") or sym,
                "exchange": row.get("exchangeShortName") or row.get("exchange"),
                "industry": row.get("industry") or row.get("sector"),
                "logo": row.get("image"),
                "weburl": row.get("website"),
                "source": "FMP",
            })
        except Exception as fmp_error:
            logger.warning(f"FMP profile unavailable for {sym}: {fmp_error}")
            try:
                t = yf.Ticker(sym)
                info = t.info or {}
                profile.update({
                    "name": info.get("longName") or info.get("shortName") or sym,
                    "ticker": info.get("symbol") or sym,
                    "exchange": info.get("exchange") or info.get("fullExchangeName"),
                    "industry": info.get("industry"),
                    "logo": info.get("logo_url") or info.get("logoUrl"),
                    "weburl": info.get("website"),
                    "source": "YahooFallback",
                })
            except Exception:
                pass

    domain = _domain_from_url(profile.get("weburl"))
    profile["domain"] = domain
    if not profile.get("logo") and domain:
        profile["logo"] = f"https://logo.clearbit.com/{domain}"

    return profile


@app.get("/stock/details/{symbol}")
@app.get("/api/stock/details/{symbol}")
def stock_details_endpoint(symbol: str):
    sym = normalize_symbol(symbol)
    if not sym:
        raise HTTPException(status_code=400, detail="symbol is required")

    quote = {}
    profile = {}
    metric = {}
    basic_metric = {}
    earnings_date = None
    source = "Finnhub"
    market_data_timestamp = None

    try:
        quote = _finnhub_get("/quote", {"symbol": sym}) or {}
        quote_ts = int(quote.get("t") or 0)
        if quote_ts > 0:
            market_data_timestamp = datetime.utcfromtimestamp(quote_ts).isoformat() + "Z"
        profile = _finnhub_get("/stock/profile2", {"symbol": sym}) or {}
        metric_payload = _finnhub_get("/stock/metric", {"symbol": sym, "metric": "all"}) or {}
        metric = (metric_payload.get("metric") if isinstance(metric_payload, dict) else {}) or {}
        basic_payload = _finnhub_get("/stock/basic-financials", {"symbol": sym, "metric": "all"}) or {}
        basic_metric = (basic_payload.get("metric") if isinstance(basic_payload, dict) else {}) or {}
        try:
            earnings_payload = _finnhub_get("/calendar/earnings", {"symbol": sym}) or {}
            earnings_rows = earnings_payload.get("earningsCalendar") if isinstance(earnings_payload, dict) else []
            if isinstance(earnings_rows, list) and earnings_rows:
                earnings_date = earnings_rows[0].get("date")
        except Exception:
            earnings_date = None
    except Exception as e:
        logger.warning(f"Finnhub stock details unavailable for {sym}: {e}")
        source = "FMP"
        try:
            fmp_quote_rows = _fmp_get(f"/quote/{sym}")
            fmp_quote = fmp_quote_rows[0] if isinstance(fmp_quote_rows, list) and fmp_quote_rows else {}
            fmp_profile_rows = _fmp_get(f"/profile/{sym}")
            fmp_profile = fmp_profile_rows[0] if isinstance(fmp_profile_rows, list) and fmp_profile_rows else {}
            fmp_key_metrics = _fmp_get(f"/key-metrics-ttm/{sym}")
            fmp_metrics = fmp_key_metrics[0] if isinstance(fmp_key_metrics, list) and fmp_key_metrics else {}
            fmp_ratios = {}
            try:
                ratio_rows = _fmp_get(f"/ratios-ttm/{sym}")
                fmp_ratios = ratio_rows[0] if isinstance(ratio_rows, list) and ratio_rows else {}
            except Exception:
                fmp_ratios = {}
            quote = {
                "o": fmp_quote.get("open"),
                "h": fmp_quote.get("dayHigh"),
                "l": fmp_quote.get("dayLow"),
                "pc": fmp_quote.get("previousClose"),
                "v": fmp_quote.get("volume"),
                "c": fmp_quote.get("price"),
            }
            profile = {"marketCapitalization": fmp_profile.get("mktCap"), "name": fmp_profile.get("companyName")}
            metric = {
                "52WeekHigh": fmp_quote.get("yearHigh"),
                "52WeekLow": fmp_quote.get("yearLow"),
                "beta": fmp_profile.get("beta"),
                "peTTM": fmp_quote.get("pe"),
                "epsTTM": fmp_quote.get("eps"),
                "3MonthAverageTradingVolume": fmp_quote.get("avgVolume"),
                "dividendYieldIndicatedAnnual": fmp_quote.get("dividendYield") or fmp_ratios.get("dividendYielTTM"),
                "dividendPerShareAnnual": fmp_quote.get("lastDiv"),
                "exDividendDate": fmp_profile.get("lastDiv"),
                "targetMeanPrice": fmp_quote.get("priceTarget"),
                "revenueTTM": fmp_metrics.get("revenuePerShareTTM"),
                "freeCashFlowTTM": fmp_metrics.get("freeCashFlowPerShareTTM"),
                "grossMarginTTM": fmp_ratios.get("grossProfitMarginTTM"),
            }
            basic_metric = {
                "52WeekHigh": fmp_quote.get("yearHigh"),
                "52WeekLow": fmp_quote.get("yearLow"),
                "peTTM": fmp_quote.get("pe"),
                "epsTTM": fmp_quote.get("eps"),
                "revenueTTM": fmp_metrics.get("revenuePerShareTTM"),
                "freeCashFlowTTM": fmp_metrics.get("freeCashFlowPerShareTTM"),
                "grossMarginTTM": fmp_ratios.get("grossProfitMarginTTM"),
            }
            earnings_date = fmp_profile.get("ipoDate")
        except Exception as fmp_error:
            logger.warning(f"FMP stock details unavailable for {sym}: {fmp_error}")
            source = "YahooFallback"
            try:
                stock_1m = get_stock_data(sym, "1m")
                stock_1y = get_stock_data(sym, "1y")
                history_1m = stock_1m.get("history", []) or []
                history_1y = stock_1y.get("history", []) or []
                latest = safe_float(stock_1m.get("price"))
                previous = safe_float(stock_1m.get("previous_close")) or _fetch_yfinance_previous_close(sym)
                latest_row = history_1m[-1] if history_1m else {}
                day_low = safe_float(latest_row.get("low"))
                day_high = safe_float(latest_row.get("high"))
                week_52_low = min([safe_float(r.get("low")) for r in history_1y if safe_float(r.get("low")) > 0], default=0.0)
                week_52_high = max([safe_float(r.get("high")) for r in history_1y if safe_float(r.get("high")) > 0], default=0.0)
                latest_volume = int(history_1m[-1].get("volume") or 0) if history_1m else 0
                avg_volume = int(
                    sum(int(r.get("volume") or 0) for r in history_1m[-20:]) / max(1, len(history_1m[-20:]))
                ) if history_1m else 0

                info = {}
                fast_info = {}
                calendar = {}
                for yf_symbol in _symbol_variants(sym):
                    try:
                        ticker = yf.Ticker(yf_symbol)
                        try:
                            info = ticker.info or {}
                        except Exception:
                            info = {}
                        try:
                            fast_info = ticker.fast_info or {}
                        except Exception:
                            fast_info = {}
                        try:
                            cal = ticker.calendar
                            calendar = cal if isinstance(cal, dict) else {}
                        except Exception:
                            calendar = {}
                        if info or fast_info:
                            break
                    except Exception:
                        continue
                open_price = safe_float(info.get("open") or fast_info.get("open"))
                if open_price <= 0 and history_1m:
                    open_price = safe_float(history_1m[0].get("open"))

                quote = {
                    "o": open_price,
                    "h": day_high,
                    "l": day_low,
                    "pc": previous,
                    "v": latest_volume,
                    "c": latest,
                    "b": info.get("bid"),
                    "a": info.get("ask"),
                }
                profile = {
                    "marketCapitalization": info.get("marketCap") or fast_info.get("marketCap") or fast_info.get("market_cap"),
                    "name": stock_1m.get("name") or sym,
                }
                dividend_yield_raw = info.get("dividendYield")
                if dividend_yield_raw is not None:
                    try:
                        dividend_yield_raw = float(dividend_yield_raw)
                        if abs(dividend_yield_raw) <= 1:
                            dividend_yield_raw = dividend_yield_raw * 100.0
                    except Exception:
                        dividend_yield_raw = None
                metric = {
                    "52WeekHigh": week_52_high,
                    "52WeekLow": week_52_low,
                    "beta": info.get("beta"),
                    "peTTM": info.get("trailingPE"),
                    "epsTTM": info.get("trailingEps"),
                    "3MonthAverageTradingVolume": info.get("averageVolume") or fast_info.get("threeMonthAverageVolume") or avg_volume,
                    "dividendYieldIndicatedAnnual": dividend_yield_raw,
                    "dividendPerShareAnnual": info.get("dividendRate"),
                    "targetMeanPrice": info.get("targetMeanPrice"),
                    "exDividendDate": info.get("exDividendDate") or calendar.get("Ex-Dividend Date"),
                    "revenueTTM": info.get("totalRevenue"),
                    "freeCashFlowTTM": info.get("freeCashflow"),
                    "grossMarginTTM": info.get("grossMargins"),
                }
                basic_metric = metric
                calendar_earnings = calendar.get("Earnings Date")
                if isinstance(calendar_earnings, list) and calendar_earnings:
                    earnings_date = calendar_earnings[0]
                else:
                    earnings_date = info.get("earningsTimestamp")
            except Exception as yf_error:
                raise HTTPException(status_code=500, detail=f"Unable to load stock details for {sym}: {yf_error}")

    def _to_float_or_none(value):
        if value is None or value == "":
            return None
        try:
            f = float(value)
            if math.isnan(f) or math.isinf(f):
                return None
            return f
        except Exception:
            return None

    def _pick_optional(*values):
        for v in values:
            f = _to_float_or_none(v)
            if f is not None:
                return f
        return None

    def _to_percent(value):
        f = _to_float_or_none(value)
        if f is None:
            return None
        return (f * 100.0) if abs(f) <= 1 else f

    previous_close = _pick_optional(quote.get("pc"))
    open_price = _pick_optional(quote.get("o"))
    bid_price = _pick_optional(quote.get("b"), metric.get("bid"), basic_metric.get("bid"))
    ask_price = _pick_optional(quote.get("a"), metric.get("ask"), basic_metric.get("ask"))
    day_low = _pick_optional(quote.get("l"))
    day_high = _pick_optional(quote.get("h"))
    week_52_low = _pick_optional(metric.get("52WeekLow"), basic_metric.get("52WeekLow"))
    week_52_high = _pick_optional(metric.get("52WeekHigh"), basic_metric.get("52WeekHigh"))
    volume_raw = _pick_optional(quote.get("v"), metric.get("10DayAverageTradingVolume"))
    avg_volume_raw = _pick_optional(metric.get("3MonthAverageTradingVolume"), basic_metric.get("3MonthAverageTradingVolume"), metric.get("10DayAverageTradingVolume"))
    market_cap_raw = _pick_optional(profile.get("marketCapitalization"), metric.get("marketCapitalization"), basic_metric.get("marketCapitalization"))
    beta = _pick_optional(metric.get("beta"), basic_metric.get("beta"))
    pe_ratio = _pick_optional(metric.get("peTTM"), basic_metric.get("peTTM"), metric.get("peNormalizedAnnual"), basic_metric.get("peNormalizedAnnual"))
    eps_ttm = _pick_optional(metric.get("epsTTM"), basic_metric.get("epsTTM"), metric.get("epsInclExtraItemsTTM"), basic_metric.get("epsInclExtraItemsTTM"))
    dividend_yield_pct = _to_percent(_pick_optional(metric.get("dividendYieldIndicatedAnnual"), basic_metric.get("dividendYieldIndicatedAnnual"), metric.get("currentDividendYieldTTM"), basic_metric.get("currentDividendYieldTTM")))
    forward_dividend = _pick_optional(metric.get("dividendPerShareAnnual"), basic_metric.get("dividendPerShareAnnual"))
    ex_dividend_date = metric.get("exDividendDate") or basic_metric.get("exDividendDate")
    target_price = _pick_optional(metric.get("targetMeanPrice"), basic_metric.get("targetMeanPrice"))
    revenue_ttm = _pick_optional(metric.get("revenueTTM"), basic_metric.get("revenueTTM"), metric.get("totalRevenueTTM"), basic_metric.get("totalRevenueTTM"))
    free_cash_flow = _pick_optional(metric.get("freeCashFlowTTM"), basic_metric.get("freeCashFlowTTM"), metric.get("fcfTTM"), basic_metric.get("fcfTTM"))
    gross_margin = _to_percent(_pick_optional(metric.get("grossMarginTTM"), basic_metric.get("grossMarginTTM"), metric.get("grossMarginAnnual"), basic_metric.get("grossMarginAnnual")))
    price_for_yield = _pick_optional(quote.get("c"), quote.get("pc"))
    # Normalize yield scale and recover from noisy upstream values.
    if dividend_yield_pct is not None:
        if dividend_yield_pct > 25 and forward_dividend is not None and price_for_yield is not None and price_for_yield > 0:
            dividend_yield_pct = (forward_dividend / price_for_yield) * 100.0
        elif dividend_yield_pct > 25:
            dividend_yield_pct = dividend_yield_pct / 100.0
    if (
        dividend_yield_pct is not None
        and forward_dividend is not None
        and price_for_yield is not None
        and price_for_yield > 0
    ):
        implied_yield = (forward_dividend / price_for_yield) * 100.0
        if abs(dividend_yield_pct - implied_yield) > 1.0:
            dividend_yield_pct = implied_yield
    if (dividend_yield_pct is None or dividend_yield_pct <= 0) and forward_dividend is not None and price_for_yield is not None and price_for_yield > 0:
        dividend_yield_pct = (forward_dividend / price_for_yield) * 100.0

    if earnings_date and isinstance(earnings_date, (int, float)):
        try:
            earnings_date = datetime.utcfromtimestamp(int(earnings_date)).date().isoformat()
        except Exception:
            earnings_date = None

    volume = int(volume_raw) if volume_raw is not None else None
    avg_volume = int(avg_volume_raw) if avg_volume_raw is not None else None

    return {
        "symbol": sym,
        "source": source,
        "marketDataTimestamp": market_data_timestamp,
        "updatedAt": datetime.utcnow().isoformat() + "Z",
        "previousClose": previous_close,
        "open": open_price,
        "bid": bid_price,
        "ask": ask_price,
        "dayHigh": day_high,
        "dayLow": day_low,
        "dayRange": f"{day_low:.2f} - {day_high:.2f}" if day_low is not None and day_high is not None else None,
        "week52High": week_52_high,
        "week52Low": week_52_low,
        "week52Range": f"{week_52_low:.2f} - {week_52_high:.2f}" if week_52_low is not None and week_52_high is not None else None,
        "volume": volume,
        "avgVolume": avg_volume,
        "marketCap": market_cap_raw,
        "marketCapRaw": market_cap_raw,
        "beta": beta,
        "peRatio": pe_ratio,
        "eps": eps_ttm,
        "earningsDate": earnings_date,
        "forwardDividend": forward_dividend,
        "dividendYield": dividend_yield_pct,
        "exDividendDate": ex_dividend_date,
        "targetPrice": target_price,
        "revenueTTM": revenue_ttm,
        "freeCashFlow": free_cash_flow,
        "grossMargin": gross_margin,
        "companyName": profile.get("name") or sym,
    }


@app.get("/stock/financials/{symbol}")
@app.get("/api/stock/financials/{symbol}")
def stock_financials_endpoint(symbol: str):
    return stock_details_endpoint(symbol)


@app.get("/stock-history")
@app.get("/api/stock-history")
def stock_history_endpoint(
    ticker: str = Query(..., min_length=1, max_length=12, description="Ticker symbol, e.g. NVDA"),
    period: str = Query("3m", description="1d | 5d | 1m | 3m | 6m | ytd | 1y | 5y | all"),
):
    safe_ticker = str(ticker or "").strip().upper()
    if not safe_ticker:
        raise HTTPException(status_code=400, detail="ticker is required")

    stock_data = get_stock_data(safe_ticker, period)
    history = stock_data.get("history", []) or []

    rows = []
    for item in history:
        date = str(item.get("date", ""))
        price = safe_float(item.get("close"))
        volume = int(item.get("volume", 0) or 0)
        if not date or not price:
            continue
        rows.append({
            "date": date,
            "price": round(price, 4),
            "volume": volume,
        })

    rows.sort(key=lambda x: x["date"])
    return rows

# ข้อมูลหุ้นเดี่ยว + ข่าว
@app.get("/risk/recommend")
def risk_recommend(
    level: str = Query("LOW", description="LOW | MEDIUM | HIGH"),
    limit: int = Query(15, ge=1, le=50)
):
    try:
        items = recommend_by_level(level, limit)
        return {
            "level": level.upper(),
            "items": items,
            "count": len(items),
            "risk_module": True 
        }
    except Exception as e:
        logger.error(f"Error in /risk/recommend: {e}")
        return {
            "level": level.upper(),
            "items": [],
            "count": 0,
            "risk_module": False,
            "error": "ไม่สามารถดึงข้อมูลความเสี่ยงได้ในขณะนี้"
        }

# 5. Route: ให้คำแนะนำการลงทุน (ทายราคาเป้าหมาย)
@app.post("/recommend")
@app.get("/recommend")
def recommend_endpoint(
    symbol: str = Query(..., description="Stock symbol, e.g. MU"),
    window_days: int = Query(7, ge=1, le=60)
):
    symbol = symbol.upper()
    try:
        payload = compute_recommendation(symbol, window_days=window_days)
        if payload.get("error"):
            raise ValueError(payload["error"])

        rec = str(payload.get("recommendation", "Hold"))
        rec_lower = rec.lower()
        if "strong buy" in rec_lower or rec_lower == "buy" or rec_lower == "hold":
            simple_action = "ถือลงทุน"
        else:
            simple_action = "เลี่ยงหุ้น"

        return {
            "symbol": payload["symbol"],
            "current_price": payload["current_price"],
            "target_price": payload.get("target_price_mean"),
            "target_price_high": payload.get("target_price_high"),
            "target_price_low": payload.get("target_price_low"),
            "upside_pct": payload.get("upside_pct"),
            "recommendation": rec,
            "simple_action": simple_action,
            "confidence": payload.get("confidence", 0.0),
            "risk_level": payload.get("risk_level", "Medium"),
            "ai_score": payload.get("ai_score", 50.0),
            "sentiment_avg": payload.get("sentiment_avg", 0.0),
            "signals": payload.get("signals", {}),
            "weights": payload.get("weights", {}),
            "technical_indicators": payload.get("technical_indicators", {}),
            "news_sentiment_distribution": payload.get("news_sentiment_distribution", {}),
            "forecast": payload.get("forecast", {}),
            "sources": payload.get("sources", []),
            "window_days": window_days
        }
    except ValueError as ve:
        # ถ้ารู้ว่าเป็น Error เชิงตรรกะ ส่งเป็น 400 Bad Request
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # ถ้า Error ไม่คาดคิด ให้ส่งเป็น 500 แต่บอกผู้ใช้แบบปลอดภัย
        logger.error(f"System error in /recommend for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการคำนวณคำแนะนำ")


# Note: `recommend_endpoint` already accepts GET and POST, no additional wrapper needed

# Run local (optional)
if __name__ == "__main__":
    fetch_and_store(TICKERS)
    print("Data fetched, cleaned, and stored successfully.")
