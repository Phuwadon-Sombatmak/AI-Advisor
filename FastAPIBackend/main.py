from __future__ import annotations
from datetime import datetime, timedelta
import math, threading, time, requests, pandas as pd, yfinance as yf, logging, hashlib
from typing import List, Dict, Any, Optional
import re
import json
import base64
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException, Query, Header, Body
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from requests.adapters import HTTPAdapter, Retry
from dotenv import load_dotenv
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from sqlalchemy import text

from init_db import SessionLocal, engine, Base
from models import PortfolioPosition, AIRecommendationTrade

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
fetch_and_store = None
try:
    from fetcher_model import fetch_and_store
except Exception as e:
    logger.warning(f"⚠️ Failed to load fetcher_model safely: {e}")

try:
    from transformers import pipeline
except ImportError as e:
    logger.warning(f"⚠️ Failed to load transformers: {e}")

try:
    import feedparser
except ImportError as e:
    logger.warning(f"⚠️ Failed to load feedparser: {e}")
    feedparser = None

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
except Exception as e:
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

try:
    from data.market_data import MarketDataGateway
    from data.news_data import NewsDataGateway
    from data.macro_data import MacroDataGateway
    from data_sources.market_prices import UltimateMarketDataEngine
    from ai.advisor_reasoning import InvestmentReasoningEngine
    from api.advisor_endpoint import AdvisorEndpointService, create_advisor_router
    HAS_MODULAR_ADVISOR = True
except Exception as e:
    logger.error(f"❌ Failed to load modular advisor architecture: {e}")
    HAS_MODULAR_ADVISOR = False

# ==========================================
# 5. เริ่มต้นแอป FastAPI
# ==========================================
load_dotenv()

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
NEWSAPI_KEY           = os.getenv("NEWSAPI_KEY") or os.getenv("NEWS_API_KEY")
MARKETAUX_API_KEY     = os.getenv("MARKETAUX_API_KEY")
FINNHUB_API_KEY       = os.getenv("FINNHUB_API_KEY") or os.getenv("FINNHUB_TOKEN")
FMP_API_KEY           = os.getenv("FMP_API_KEY")
GEMINI_API_KEY        = os.getenv("GEMINI_API_KEY")
POLYGON_API_KEY       = os.getenv("POLYGON_API_KEY")
TWELVEDATA_API_KEY    = os.getenv("TWELVEDATA_API_KEY")

AI_TUNING_DIR = BASE_PATH / "runtime"
AI_TUNING_FILE = AI_TUNING_DIR / "ai_autotune.json"
DEFAULT_AI_TUNING_CONFIG = {
    "strong_buy_momentum_min": 60.0,
    "strong_buy_technical_min": 65.0,
    "strong_sell_forecast_max": -20.0,
    "strong_sell_technical_max": 30.0,
    "long_position_scale": 1.0,
    "sell_weight_scale": 1.0,
    "position_size_scale": 1.0,
    "updated_at": None,
    "adjustments": [],
}


def _load_ai_tuning_config() -> Dict[str, Any]:
    config = dict(DEFAULT_AI_TUNING_CONFIG)
    try:
        if AI_TUNING_FILE.exists():
            raw = json.loads(AI_TUNING_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                config.update(raw)
    except Exception as exc:
        logger.warning(f"⚠️ Failed to load AI tuning config: {exc}")
    return config


def _save_ai_tuning_config(config: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(DEFAULT_AI_TUNING_CONFIG)
    payload.update(config or {})
    AI_TUNING_DIR.mkdir(parents=True, exist_ok=True)
    AI_TUNING_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload

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
generic_ttl_cache: Dict[str, Dict[str, Any]] = {}
modular_advisor_service: Optional[Any] = None
APP_STARTED_AT = datetime.utcnow()


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
app.add_middleware(GZipMiddleware, minimum_size=1024)

def _safe_init_db_tables() -> bool:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized")
        return True
    except Exception as e:
        logger.warning(f"Database table init skipped: {e}")
        return False


# Ensure SQL tables exist for runtime features (portfolio, etc.) without crashing app startup.
DB_TABLES_READY = _safe_init_db_tables()

PORTFOLIO_QUOTE_CACHE_TTL = 30
PORTFOLIO_META_CACHE_TTL = 3600
PORTFOLIO_AI_CACHE_TTL = 300
AI_SUMMARY_CACHE_TTL = 300
portfolio_quote_cache: Dict[str, Dict[str, Any]] = {}
portfolio_meta_cache: Dict[str, Dict[str, Any]] = {}
portfolio_ai_cache: Dict[str, Dict[str, Any]] = {}
ai_summary_cache: Dict[str, Dict[str, Any]] = {}
stock_stats_cache: Dict[str, Dict[str, Any]] = {}
AI_ADVISOR_CACHE_TTL = 300
AI_MARKET_CONTEXT_CACHE_TTL = 180
STOCK_DETAILS_CACHE_TTL = 300
STOCK_DATA_CACHE_TTL = 600
AI_PICKER_CACHE_TTL = 120
STOCK_ENDPOINT_CACHE_TTL = 180
STOCK_RETURN_CACHE_TTL = 900


def _cache_get(cache_store: Dict[str, Dict[str, Any]], key: str, ttl_seconds: int) -> Optional[Any]:
    cached = cache_store.get(key)
    if not cached:
        return None
    if (time.time() - float(cached.get("ts", 0))) >= ttl_seconds:
        return None
    return cached.get("data")


def _cache_set(cache_store: Dict[str, Dict[str, Any]], key: str, data: Any) -> Any:
    cache_store[key] = {"ts": time.time(), "data": data}
    return data


def _cache_entry(cache_store: Dict[str, Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
    return cache_store.get(key)


def _with_cache_metadata(payload: Optional[Dict[str, Any]], *, cache_entry: Optional[Dict[str, Any]], mode: str, stale_cache_used: bool = False) -> Optional[Dict[str, Any]]:
    if payload is None:
        return None
    enriched = dict(payload)
    age_minutes = None
    if cache_entry and cache_entry.get("ts"):
        age_minutes = round(max(0.0, (time.time() - float(cache_entry["ts"])) / 60.0), 1)
    enriched["data_source_mode"] = mode
    enriched["stale_cache_used"] = stale_cache_used
    enriched["cached_age_minutes"] = age_minutes
    return enriched


def _stable_cache_key(prefix: str, payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def _parallel_map(func, items: List[Any], max_workers: int = 4) -> List[Any]:
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(func, items))


def _downsample_rows(rows: List[Dict[str, Any]], max_points: int = 140) -> List[Dict[str, Any]]:
    if len(rows) <= max_points:
        return rows
    if max_points <= 2:
        return rows[:max_points]
    step = (len(rows) - 1) / float(max_points - 1)
    sampled = []
    used = set()
    for idx in range(max_points):
        source_index = int(round(idx * step))
        source_index = max(0, min(len(rows) - 1, source_index))
        if source_index in used:
            continue
        used.add(source_index)
        sampled.append(rows[source_index])
    if sampled[-1] is not rows[-1]:
        sampled[-1] = rows[-1]
    return sampled

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


def calculate_total_return(first_price: Any, last_price: Any) -> float:
    first = safe_float(first_price)
    last = safe_float(last_price)
    if first <= 0 or last <= 0:
        return 0.0
    return ((last / first) - 1.0) * 100.0


def _is_unrealistic_total_return(return_pct: Any) -> bool:
    value = safe_float(return_pct)
    return (not math.isfinite(value)) or abs(value) > 1_000_000.0


def _first_valid_traded_close(
    closes: List[Any],
    volumes: Optional[List[Any]] = None,
) -> float:
    if not closes:
        return 0.0

    parsed_closes = [safe_float(value) for value in closes]
    parsed_volumes = [safe_float(value) for value in (volumes or [])]

    if parsed_volumes:
        for close, volume in zip(parsed_closes, parsed_volumes):
            if close > 0 and volume > 0:
                return close

    for close in parsed_closes:
        if close > 0:
            return close
    return 0.0


SYMBOL_ALIASES = {
    "MICROSOFT": "MSFT",
    "MICROSOFTCORPORATION": "MSFT",
    "MICRSOFT": "MSFT",
    "MICORSOFT": "MSFT",
    "APPLE": "AAPL",
    "APPLEINC": "AAPL",
    "APPL": "AAPL",
    "AAPL": "AAPL",
    "NVIDIA": "NVDA",
    "NVDIA": "NVDA",
    "NVIDIACORPORATION": "NVDA",
    "NVDA": "NVDA",
    "AMAZON": "AMZN",
    "AMAZONCOM": "AMZN",
    "AMAZONCOMINC": "AMZN",
    "AMAZN": "AMZN",
    "ALPHABET": "GOOGL",
    "ALPHABETINC": "GOOGL",
    "GOOGLE": "GOOGL",
    "GOOGLEINC": "GOOGL",
    "META": "META",
    "METAPLATFORMS": "META",
    "METAPLATFORMSINC": "META",
    "TESLA": "TSLA",
    "TESLAINC": "TSLA",
    "TESAL": "TSLA",
    "TSAL": "TSLA",
    "BERKSHIREHATHAWAY": "BRK.A",
    "BERKSHIREHATHAWAYINC": "BRK.A",
    "UNITEDHEALTH": "UNH",
    "UNITEDHEALTHGROUP": "UNH",
    "UNITEDHEALTHGROUPINC": "UNH",
}

COMMON_SYMBOLS = {
    "AAPL", "AMD", "AMZN", "AVGO", "BRK.A", "BRK.B", "COIN", "DIA", "GLD",
    "GOOG", "GOOGL", "INTC", "IWM", "META", "MSFT", "MSTR", "MARA", "NFLX",
    "NVDA", "PLTR", "QQQ", "RIOT", "SPY", "TSLA", "TSM", "UNH", "XLB", "XLE",
    "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
}


def _bounded_levenshtein(a: str, b: str, max_distance: int = 1) -> int:
    if a == b:
        return 0
    if abs(len(a) - len(b)) > max_distance:
        return max_distance + 1

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        row_min = curr[0]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            ))
            row_min = min(row_min, curr[-1])
        if row_min > max_distance:
            return max_distance + 1
        prev = curr
    return prev[-1]


def _is_single_transposition(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    diffs = [idx for idx, (ca, cb) in enumerate(zip(a, b)) if ca != cb]
    if len(diffs) != 2:
        return False
    i, j = diffs
    return j == i + 1 and a[i] == b[j] and a[j] == b[i]


def _fuzzy_symbol_match(raw: str) -> str:
    if not raw or not raw.isalpha() or not (3 <= len(raw) <= 8):
        return raw
    if raw in COMMON_SYMBOLS:
        return raw

    candidates = []
    for symbol in COMMON_SYMBOLS:
        token = symbol.replace(".", "").replace("-", "")
        if abs(len(raw) - len(token)) > 1:
            continue
        if _is_single_transposition(raw, token) or _bounded_levenshtein(raw, token, max_distance=1) <= 1:
            candidates.append(symbol)

    if len(candidates) == 1:
        logger.info(f"Fuzzy-corrected symbol '{raw}' -> '{candidates[0]}'")
        return candidates[0]
    return raw


def normalize_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip().upper()
    if not raw:
        return ""
    # Normalize common separator variants while preserving class shares (e.g. BRK.A / BRK-B)
    raw = re.sub(r"\s+", "", raw)
    raw = SYMBOL_ALIASES.get(raw, raw)
    raw = _fuzzy_symbol_match(raw)
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
        if feedparser is None:
            logger.warning("Yahoo RSS skipped because feedparser is not installed")
            return []
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
    symbol = normalize_symbol(symbol)
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


def _fetch_finnhub_quote(symbol: str) -> Dict[str, Any]:
    quote = _finnhub_get("/quote", {"symbol": symbol}) or {}
    return {
        "price": safe_float(quote.get("c")),
        "previous_close": safe_float(quote.get("pc")),
        "name": symbol,
        "c": safe_float(quote.get("c")),
        "pc": safe_float(quote.get("pc")),
    }


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


def _fetch_alpha_vantage_quote(symbol: str) -> Dict[str, Any]:
    if not ALPHA_VANTAGE_API_KEY:
        raise RuntimeError("Alpha Vantage API key not configured")
    payload = session.get(
        "https://www.alphavantage.co/query",
        params={
            "function": "GLOBAL_QUOTE",
            "symbol": symbol,
            "apikey": ALPHA_VANTAGE_API_KEY,
        },
        timeout=15,
    ).json()
    row = payload.get("Global Quote") or {}
    return {
        "price": safe_float(row.get("05. price")),
        "previous_close": safe_float(row.get("08. previous close")),
        "name": symbol,
    }


def _fetch_alpha_vantage_history(symbol: str, range_value: str):
    if not ALPHA_VANTAGE_API_KEY:
        raise RuntimeError("Alpha Vantage API key not configured")
    params = _history_params(range_value)
    payload = session.get(
        "https://www.alphavantage.co/query",
        params={
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": ALPHA_VANTAGE_API_KEY,
        },
        timeout=20,
    ).json()
    series = payload.get("Time Series (Daily)") or {}
    rows = []
    for date_text in sorted(series.keys()):
        item = series[date_text] or {}
        rows.append({
            "date": date_text,
            "open": safe_float(item.get("1. open")),
            "high": safe_float(item.get("2. high")),
            "low": safe_float(item.get("3. low")),
            "close": safe_float(item.get("4. close")),
            "volume": int(float(item.get("5. volume") or 0)),
        })
    if not rows:
        raise RuntimeError("Alpha Vantage returned no history rows")
    days = params["days"] if params["period"] != "ytd" else 400
    return rows[-days:], params["period"]


def _fetch_polygon_quote(symbol: str) -> Dict[str, Any]:
    if not POLYGON_API_KEY:
        raise RuntimeError("Polygon API key not configured")
    payload = session.get(
        f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev",
        params={"adjusted": "true", "apiKey": POLYGON_API_KEY},
        timeout=15,
    ).json()
    results = payload.get("results") or []
    row = results[0] if results else {}
    return {
        "price": safe_float(row.get("c")),
        "previous_close": safe_float(row.get("o")),
        "name": symbol,
    }


def _fetch_polygon_history(symbol: str, range_value: str):
    if not POLYGON_API_KEY:
        raise RuntimeError("Polygon API key not configured")
    params = _history_params(range_value)
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=max(params["days"] * 2, 30))
    payload = session.get(
        f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start_date.isoformat()}/{end_date.isoformat()}",
        params={"adjusted": "true", "sort": "asc", "limit": 5000, "apiKey": POLYGON_API_KEY},
        timeout=20,
    ).json()
    rows = []
    for item in payload.get("results") or []:
        dt = datetime.utcfromtimestamp(int(item.get("t", 0)) / 1000.0)
        rows.append({
            "date": dt.strftime("%Y-%m-%d"),
            "open": safe_float(item.get("o")),
            "high": safe_float(item.get("h")),
            "low": safe_float(item.get("l")),
            "close": safe_float(item.get("c")),
            "volume": int(item.get("v") or 0),
        })
    if not rows:
        raise RuntimeError("Polygon returned no history rows")
    days = params["days"] if params["period"] != "ytd" else 400
    return rows[-days:], params["period"]


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

    close_field = "Close"
    if not intraday and "Adj Close" in hist.columns:
        close_field = "Adj Close"

    rows = []
    for idx, r in hist.iterrows():
        rows.append({
            "date": idx.strftime("%Y-%m-%d %H:%M") if intraday else idx.strftime("%Y-%m-%d"),
            "open": safe_float(r.get("Open")),
            "high": safe_float(r.get("High")),
            "low": safe_float(r.get("Low")),
            "close": safe_float(r.get(close_field)),
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
    normalized_symbol = normalize_symbol(symbol)
    normalized_range = str(range_value or "3mo").strip().lower()
    cache_key = f"stock-data:{normalized_symbol}:{normalized_range}"
    cache_entry = _cache_entry(generic_ttl_cache, cache_key)
    cached_payload = _cache_get(generic_ttl_cache, cache_key, STOCK_DATA_CACHE_TTL)
    if cached_payload is not None:
        return _with_cache_metadata(cached_payload, cache_entry=cache_entry, mode="live")

    try:
        latest_price = 0.0
        previous_close = 0.0
        company_name = normalized_symbol or symbol
        history = []
        normalized_period = _normalize_range(range_value)
        provider_chain: List[str] = []

        last_error = None
        logger.info(f"Trying yfinance for {normalized_symbol} [{normalized_range}]...")
        for yf_symbol in _symbol_variants(normalized_symbol):
            try:
                history, normalized_period = _fetch_yfinance_history(yf_symbol, range_value)
                if not history:
                    raise RuntimeError("Yahoo Finance returned no history rows")
                latest_price = safe_float(history[-1].get("close"))
                previous_close = _fetch_yfinance_previous_close(yf_symbol) or _infer_previous_close_from_history(history)
                company_name = yf_symbol if not company_name or company_name == normalized_symbol else company_name
                provider_chain.append("Yahoo Finance")
                break
            except Exception as yf_error:
                last_error = yf_error
        if not history:
            logger.info(f"Trying Alpha Vantage for {normalized_symbol} [{normalized_range}]...")
            try:
                av_quote = _fetch_alpha_vantage_quote(normalized_symbol)
                history, normalized_period = _fetch_alpha_vantage_history(normalized_symbol, range_value)
                latest_price = safe_float(av_quote.get("price")) or safe_float(history[-1].get("close"))
                previous_close = safe_float(av_quote.get("previous_close")) or _infer_previous_close_from_history(history)
                company_name = str(av_quote.get("name") or normalized_symbol)
                provider_chain.append("Alpha Vantage")
            except Exception as alpha_error:
                last_error = alpha_error
        if not history:
            logger.info(f"Trying Finnhub for {normalized_symbol} [{normalized_range}]...")
            try:
                quote = _finnhub_get("/quote", {"symbol": normalized_symbol})
                profile = _finnhub_get("/stock/profile2", {"symbol": normalized_symbol})
                history, normalized_period = _fetch_finnhub_candles(normalized_symbol, range_value)
                latest_price = safe_float(quote.get("c")) or safe_float(history[-1].get("close"))
                previous_close = safe_float(quote.get("pc")) or _infer_previous_close_from_history(history)
                company_name = str(profile.get("name") or normalized_symbol)
                provider_chain.append("Finnhub")
            except Exception as finnhub_error:
                last_error = finnhub_error
        if not history:
            logger.info(f"Trying Polygon for {normalized_symbol} [{normalized_range}]...")
            try:
                polygon_quote = _fetch_polygon_quote(normalized_symbol)
                history, normalized_period = _fetch_polygon_history(normalized_symbol, range_value)
                latest_price = safe_float(polygon_quote.get("price")) or safe_float(history[-1].get("close"))
                previous_close = safe_float(polygon_quote.get("previous_close")) or _infer_previous_close_from_history(history)
                company_name = str(polygon_quote.get("name") or normalized_symbol)
                provider_chain.append("Polygon")
            except Exception as polygon_error:
                last_error = polygon_error

        if not history:
            logger.info(f"Trying cached market data for {normalized_symbol} [{normalized_range}]...")
            stale_payload = _with_cache_metadata(
                cache_entry.get("data") if cache_entry else None,
                cache_entry=cache_entry,
                mode="cached",
                stale_cache_used=True,
            )
            if stale_payload is not None:
                stale_provider = stale_payload.get("provider") or "Cached Market Data"
                stale_payload["provider"] = f"Cached Market Data ({stale_provider})"
                stale_payload["provider_chain"] = [stale_provider, "Cached Market Data"]
                return stale_payload
            raise HTTPException(status_code=503, detail="Market data temporarily unavailable")

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
        final_history = []
        for _, row in df.iterrows():
            def _series_value(value):
                return None if pd.isna(value) else safe_float(value)
            final_history.append({
                "date": str(row["date"]),
                "open": safe_float(row["open"]),
                "high": safe_float(row["high"]),
                "low": safe_float(row["low"]),
                "close": safe_float(row["close"]),
                "volume": int(row["volume"] or 0),
                "sma20": _series_value(row["sma20"]),
                "sma50": _series_value(row["sma50"]),
                "volatility": _series_value(row["volatility"]),
                "rsi": _series_value(row["rsi"]),
                "momentum": _series_value(row["momentum"]),
                "bb_upper": _series_value(row["bb_upper"]),
                "bb_lower": _series_value(row["bb_lower"]),
                "macd": _series_value(row["macd"]),
                "macd_signal": _series_value(row["macd_signal"]),
                "sharpe": _series_value(row["sharpe"]),
            })

        latest_price = latest_price or safe_float(final_history[-1]["close"])
        inferred_previous_close = _infer_previous_close_from_history(final_history)
        if normalized_period in {"1d", "5d"} and inferred_previous_close > 0:
            previous_close = inferred_previous_close
        elif previous_close <= 0 and inferred_previous_close > 0:
            previous_close = inferred_previous_close

        provider = " → ".join(provider_chain) if provider_chain else "Unavailable"
        result = {
            "name": company_name,
            "price": latest_price,
            "previous_close": previous_close,
            "history": final_history,
            "range": normalized_period,
            "provider": provider,
            "provider_chain": provider_chain,
            "data_source_mode": "live",
            "stale_cache_used": False,
            "cached_age_minutes": 0.0,
        }
        return _with_cache_metadata(
            _cache_set(generic_ttl_cache, cache_key, result),
            cache_entry=_cache_entry(generic_ttl_cache, cache_key),
            mode="live",
        )

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

    def _optional_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            candidate = float(value)
            if math.isnan(candidate) or math.isinf(candidate):
                return None
            return candidate
        except Exception:
            return None

    def _validated_number(value: Any, label: str, recompute=None) -> Optional[float]:
        candidate = value
        try:
            assert candidate is not None
            candidate = float(candidate)
            assert not math.isnan(candidate)
            assert not math.isinf(candidate)
            return candidate
        except Exception:
            if recompute is not None:
                try:
                    candidate = recompute()
                    assert candidate is not None
                    candidate = float(candidate)
                    assert not math.isnan(candidate)
                    assert not math.isinf(candidate)
                    return candidate
                except Exception:
                    logger.warning(f"Unable to recompute validated numeric output for {symbol}::{label}")
                    return None
            logger.warning(f"Invalid numeric output for {symbol}::{label}")
            return None

    def _score_linear(v: float, lo: float, hi: float) -> float:
        if hi <= lo:
            return 50.0
        return _clamp((v - lo) / (hi - lo), 0.0, 1.0) * 100.0

    def _is_bullish_technical(ts: Optional[float], macd: Optional[float], macd_sig: Optional[float], ma50v: Optional[float], ma200v: Optional[float]) -> bool:
        return (
            ts is not None
            and ts >= 60
            and macd is not None
            and macd_sig is not None
            and macd > macd_sig
            and ma50v is not None
            and ma200v is not None
            and ma50v > ma200v
        )

    def _is_bearish_technical(ts: Optional[float], macd: Optional[float], macd_sig: Optional[float], ma50v: Optional[float], ma200v: Optional[float]) -> bool:
        return (
            ts is not None
            and ts <= 40
            and macd is not None
            and macd_sig is not None
            and macd < macd_sig
            and ma50v is not None
            and ma200v is not None
            and ma50v < ma200v
        )

    def _recommendation_level(
        *,
        upside: Optional[float],
        technical_score_value: Optional[float],
        technical_bullish: bool,
        technical_bearish: bool,
        momentum: Optional[float],
        sentiment: Optional[float],
        forecast: Optional[float],
    ) -> str:
        tuning = _load_ai_tuning_config()
        strong_buy_momentum_min = safe_float(tuning.get("strong_buy_momentum_min")) or 60.0
        strong_buy_technical_min = safe_float(tuning.get("strong_buy_technical_min")) or 65.0
        strong_sell_forecast_max = safe_float(tuning.get("strong_sell_forecast_max")) or -20.0
        strong_sell_technical_max = safe_float(tuning.get("strong_sell_technical_max")) or 30.0

        technical_strong = technical_score_value is not None and technical_score_value > strong_buy_technical_min
        technical_weak = technical_score_value is not None and technical_score_value < 40
        technical_very_bearish = technical_score_value is not None and technical_score_value < strong_sell_technical_max
        momentum_positive = momentum is not None and momentum > strong_buy_momentum_min
        momentum_very_negative = momentum is not None and momentum < 30
        forecast_positive = forecast is not None and forecast > 0
        forecast_negative = forecast is not None and forecast < 0
        forecast_very_negative = forecast is not None and forecast < strong_sell_forecast_max
        sentiment_bearish = sentiment is not None and sentiment <= 40

        bullish_count = sum(
            1 for flag in [
                upside is not None and upside > 15,
                technical_score_value is not None and technical_score_value >= 55,
                momentum is not None and momentum >= 50,
                forecast is not None and forecast > 0,
                sentiment is not None and sentiment >= 55,
            ] if flag
        )
        bearish_count = sum(
            1 for flag in [
                upside is not None and upside < 15,
                technical_score_value is not None and technical_score_value < 45,
                momentum is not None and momentum < 45,
                forecast is not None and forecast < 0,
                sentiment is not None and sentiment <= 45,
            ] if flag
        )
        hold_label = "Hold"
        if bearish_count > bullish_count:
            hold_label = "Hold (Bearish Bias)"
        elif bullish_count > bearish_count:
            hold_label = "Hold (Bullish Bias)"

        if upside is not None and upside > 30 and technical_strong and technical_bullish and momentum_positive and forecast_positive:
            return "Strong Buy"
        if forecast_very_negative and technical_very_bearish and momentum_very_negative and sentiment_bearish and not (upside is not None and upside > 25):
            return "Strong Sell"
        if upside is not None and upside > 25 and technical_bearish and forecast_negative:
            return hold_label
        if upside is not None and 15 <= upside <= 30 and not technical_bearish and not forecast_very_negative:
            return "Buy"
        if upside is not None and upside < 15 and technical_weak and forecast_negative and not (upside is not None and upside > 25):
            return "Sell"
        if technical_bearish and technical_very_bearish and momentum_very_negative and forecast_negative:
            return "Strong Sell"
        if bullish_count > 0 and bearish_count > 0:
            return hold_label
        if technical_bearish and forecast_negative:
            return "Sell"
        if bullish_count >= 4 and not forecast_very_negative:
            return "Buy"
        if bearish_count >= 4:
            return "Strong Sell"
        return hold_label

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

    sym = normalize_symbol(symbol)
    logger.info(f"[recommend] start symbol={sym} window_days={window_days}")

    stock_data: Dict[str, Any] = {}
    history: List[Dict[str, Any]] = []
    closes = pd.Series(dtype="float64")
    selected_range = None
    last_history_error = None

    # Prefer 1Y so MA200 and long-horizon technicals remain available for validation and UI.
    for candidate_range in ("1y", "6m", "3m", "1m"):
        try:
            candidate_stock_data = get_stock_data(sym, candidate_range)
            candidate_history = candidate_stock_data.get("history", [])
            candidate_closes = pd.Series(
                [safe_float(h.get("close")) for h in candidate_history if safe_float(h.get("close")) > 0],
                dtype="float64",
            )
            if candidate_history and not candidate_closes.empty:
                stock_data = candidate_stock_data
                history = candidate_history
                closes = candidate_closes
                selected_range = candidate_range
                break
        except Exception as history_error:
            last_history_error = history_error
            logger.warning(f"[recommend] history load failed symbol={sym} range={candidate_range}: {history_error}")

    if not history:
        logger.warning(f"[recommend] no history symbol={sym} last_error={last_history_error}")
        return {"error": f"no price data for {sym}"}

    if closes.empty:
        logger.warning(f"[recommend] closes empty symbol={sym} range={selected_range}")
        return {"error": f"no price data for {sym}"}

    current_price = _optional_float(stock_data.get("price")) or _optional_float(closes.iloc[-1])
    logger.info(
        f"[recommend] price data loaded symbol={sym} history_points={len(closes)} range={selected_range}"
    )

    # Technical indicators
    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    ma50 = closes.rolling(50).mean()
    ma200 = closes.rolling(200).mean() if len(closes) >= 200 else pd.Series([float("nan")] * len(closes), index=closes.index, dtype="float64")

    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rs = gain / loss.replace(0, 1e-9)
    rsi_series = 100 - (100 / (1 + rs))

    trend = float((ma50.iloc[-1] - ma200.iloc[-1]) / max(1e-9, ma200.iloc[-1])) if not pd.isna(ma50.iloc[-1]) and not pd.isna(ma200.iloc[-1]) else None
    momentum_30 = float((closes.iloc[-1] - closes.iloc[max(0, len(closes) - 30)]) / max(1e-9, closes.iloc[max(0, len(closes) - 30)]))
    momentum_60 = float((closes.iloc[-1] - closes.iloc[max(0, len(closes) - 60)]) / max(1e-9, closes.iloc[max(0, len(closes) - 60)]))
    volatility = float(closes.pct_change().dropna().rolling(20).std().iloc[-1]) if len(closes) > 21 else None

    latest_rsi = _optional_float(rsi_series.iloc[-1])
    latest_macd = _optional_float(macd_line.iloc[-1])
    latest_macd_signal = _optional_float(macd_signal.iloc[-1])
    latest_ma50 = _optional_float(ma50.iloc[-1])
    latest_ma200 = _optional_float(ma200.iloc[-1])
    logger.info(f"[recommend] technical indicators calculated symbol={sym} rsi={'ok' if latest_rsi is not None else 'missing'} macd={'ok' if latest_macd is not None and latest_macd_signal is not None else 'missing'}")

    # News sentiment
    try:
        news_rows = get_newsapi_news_batch([sym], limit_per_symbol=20, days_back=window_days)
        news_items = (news_rows[0].get("news", []) if news_rows else [])
    except Exception as news_error:
        logger.warning(f"[recommend] news fetch failed symbol={sym}: {news_error}")
        news_items = []
    news_scores = [_sentiment_to_score(n) for n in news_items]
    avg_sent = float(sum(news_scores) / len(news_scores)) if news_scores else None
    news_count = len(news_scores)
    bullish_count = len([x for x in news_scores if x > 0.2])
    bearish_count = len([x for x in news_scores if x < -0.2])
    neutral_count = max(0, news_count - bullish_count - bearish_count)
    bullish_pct = round((bullish_count / news_count) * 100, 1) if news_count else None
    neutral_pct = round((neutral_count / news_count) * 100, 1) if news_count else None
    bearish_pct = round((bearish_count / news_count) * 100, 1) if news_count else None
    logger.info(f"[recommend] news sentiment calculated symbol={sym} news_count={news_count}")

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

    pe_ratio = _optional_float(ratios_row.get("peRatioTTM") or profile_row.get("pe"))
    roe = _optional_float(ratios_row.get("returnOnEquityTTM") or metrics_row.get("roeTTM"))
    debt_to_equity = _optional_float(ratios_row.get("debtEquityRatioTTM") or metrics_row.get("debtToEquityTTM"))
    revenue_growth = _optional_float(growth_row.get("revenueGrowth"))
    eps_growth = _optional_float(growth_row.get("epsgrowth") or growth_row.get("epsGrowth"))
    if revenue_growth is not None and abs(revenue_growth) > 1.5:
        revenue_growth /= 100.0
    if eps_growth is not None and abs(eps_growth) > 1.5:
        eps_growth /= 100.0

    # Weighted scoring model
    technical_components = []
    if latest_rsi is not None:
        technical_components.append((100.0 - abs(60.0 - latest_rsi) * 1.6, 0.25))
    if latest_macd is not None and latest_macd_signal is not None:
        technical_components.append((_score_linear(latest_macd - latest_macd_signal, -1.5, 1.5), 0.25))
    if latest_ma50 is not None and latest_ma200 is not None:
        technical_components.append(((75.0 if latest_ma50 > latest_ma200 else 35.0), 0.25))
    if trend is not None:
        technical_components.append((_score_linear(trend, -0.20, 0.20), 0.25))

    technical_score = None
    if technical_components:
        total_technical_weight = sum(weight for _, weight in technical_components)
        technical_score = _clamp(
            sum(score * weight for score, weight in technical_components) / max(total_technical_weight, 1e-9),
            0.0,
            100.0,
        )

    sentiment_score = _score_linear(avg_sent, -1.0, 1.0) if avg_sent is not None else None
    momentum_score = _score_linear((momentum_30 * 0.6) + (momentum_60 * 0.4), -0.25, 0.35)
    volatility_risk_score = 100.0 - _score_linear(volatility, 0.008, 0.055) if volatility is not None else None
    normalized_forecast_components = [
        momentum_30 if math.isfinite(momentum_30) else None,
        (momentum_60 * 0.7) if math.isfinite(momentum_60) else None,
        (((technical_score - 50.0) / 100.0) * 0.12) if technical_score is not None else None,
        ((avg_sent or 0.0) * 0.08) if avg_sent is not None else None,
        (-(min(volatility, 0.12)) * 0.35) if volatility is not None else None,
    ]
    normalized_forecast_values = [value for value in normalized_forecast_components if value is not None and math.isfinite(value)]
    forecast_30d_pct = _validated_number(
        _clamp((sum(normalized_forecast_values) / len(normalized_forecast_values)) * 100.0, -25.0, 25.0),
        "forecast_30d_pct",
    ) if normalized_forecast_values else None

    weighted_components = [
        ("technical_score", technical_score, 0.40),
        ("sentiment_score", sentiment_score, 0.30),
        ("momentum_score", momentum_score, 0.20),
        ("volatility_risk_score", volatility_risk_score, 0.10),
    ]
    used_components = [(name, score, weight) for name, score, weight in weighted_components if score is not None]
    if not used_components:
        return {"error": f"relevant data is not available for {sym}"}
    total_weight = sum(weight for _, _, weight in used_components)
    weighted_score = sum(score * weight for _, score, weight in used_components) / max(total_weight, 1e-9)
    base_ai_score = _validated_number(round(_clamp(weighted_score, 0.0, 100.0), 2), "ai_score")
    if base_ai_score is None:
        return {"error": f"relevant data is not available for {sym}"}
    logger.info(f"[recommend] ai signals generated symbol={sym} ai_score={base_ai_score}")

    # Price targets must come from real analyst/fundamental data only.
    analyst_target = _validated_number(
        metrics_row.get("targetMeanPrice") or profile_row.get("priceTarget"),
        "analyst_target",
    )

    if volatility is None:
        risk_level = "Relevant data is not available."
    elif volatility >= 0.04:
        risk_level = "High"
    elif volatility >= 0.022:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    agreement_inputs = [score for score in [technical_score, sentiment_score, momentum_score, volatility_risk_score] if score is not None]
    agreement = 100.0 - (max(agreement_inputs) - min(agreement_inputs)) if agreement_inputs else 50.0
    data_points = sum([
        1 if pe_ratio is not None and pe_ratio > 0 else 0,
        1 if roe is not None else 0,
        1 if debt_to_equity is not None else 0,
        1 if revenue_growth is not None or eps_growth is not None else 0,
        1 if news_count > 0 else 0,
    ])
    confidence = _validated_number(
        round(_clamp(0.45 + (agreement / 100.0) * 0.25 + data_points * 0.05 + min(news_count, 20) * 0.008, 0.35, 0.95), 2),
        "confidence",
    )
    if confidence is None:
        return {"error": f"relevant data is not available for {sym}"}

    upside_pct = None
    if analyst_target is not None and current_price:
        upside_pct = _validated_number(((analyst_target - current_price) / current_price) * 100, "upside_pct")

    technical_bullish = _is_bullish_technical(technical_score, latest_macd, latest_macd_signal, latest_ma50, latest_ma200)
    technical_bearish = _is_bearish_technical(technical_score, latest_macd, latest_macd_signal, latest_ma50, latest_ma200)

    reco = _recommendation_level(
        upside=upside_pct,
        technical_score_value=technical_score,
        technical_bullish=technical_bullish,
        technical_bearish=technical_bearish,
        momentum=momentum_score,
        sentiment=sentiment_score,
        forecast=forecast_30d_pct,
    )

    recommendation_driver = base_ai_score
    if reco == "Strong Buy":
        recommendation_driver = max(base_ai_score, 82.0)
    elif reco == "Buy":
        recommendation_driver = max(min(base_ai_score, 79.0), 62.0)
    elif reco.startswith("Hold"):
        recommendation_driver = min(max(base_ai_score, 40.0), 69.0)
    elif reco == "Sell":
        recommendation_driver = min(base_ai_score, 39.0)
    elif reco == "Strong Sell":
        recommendation_driver = min(base_ai_score, 19.0)
    recommendation_driver = _clamp(recommendation_driver, 0.0, 100.0)

    latest_rsi = _validated_number(latest_rsi, "rsi")
    latest_macd = _validated_number(latest_macd, "macd")
    latest_macd_signal = _validated_number(latest_macd_signal, "macd_signal")
    latest_ma50 = _validated_number(latest_ma50, "ma50")
    latest_ma200 = _validated_number(latest_ma200, "ma200")
    technical_score = _validated_number(round(technical_score, 2), "technical_score") if technical_score is not None else None
    sentiment_score = _validated_number(round(sentiment_score, 2), "sentiment_score") if sentiment_score is not None else None
    momentum_score = _validated_number(round(momentum_score, 2), "momentum_score")
    volatility_risk_score = _validated_number(round(volatility_risk_score, 2), "volatility_risk_score") if volatility_risk_score is not None else None
    current_price = _validated_number(round(current_price, 2), "current_price", recompute=lambda: safe_float(closes.iloc[-1]))
    if current_price is None:
        return {"error": f"relevant data is not available for {sym}"}

    return {
        "symbol": sym,
        "current_price": current_price,
        "target_price_mean": round(analyst_target, 2) if analyst_target is not None else None,
        "target_price_high": None,
        "target_price_low": None,
        "upside_pct": round(upside_pct, 2) if upside_pct is not None else None,
        "sentiment_avg": round(avg_sent, 3) if avg_sent is not None else None,
        "trend": round(trend, 3) if _validated_number(trend, "trend") is not None else None,
        "expected_diff": None,
        "recommendation": reco,
        "confidence": confidence,
        "ai_score": round(recommendation_driver, 2),
        "base_ai_score": base_ai_score,
        "ai_recommendation": reco.upper(),
        "risk_level": risk_level,
        "window_days": window_days,
        "history_range": selected_range,
        "news_count": int(news_count),
        "lstm_prediction": None,
        "weights": {
            "technical": 40,
            "news_sentiment": 30,
            "momentum": 20,
            "volatility_risk": 10,
        },
        "signals": {
            "technical_score": technical_score,
            "news_sentiment_score": sentiment_score,
            "momentum_score": momentum_score,
            "volatility_risk_score": volatility_risk_score,
            "news_sentiment_label": (
                "Bullish" if avg_sent is not None and avg_sent > 0.2
                else ("Bearish" if avg_sent is not None and avg_sent < -0.2 else ("Neutral" if avg_sent is not None else "Relevant data is not available"))
            ),
            "forecast_30d_pct": round(forecast_30d_pct, 2) if forecast_30d_pct is not None else None,
        },
        "technical_indicators": {
            "rsi": round(latest_rsi, 2) if latest_rsi is not None else None,
            "macd": round(latest_macd, 4) if latest_macd is not None else None,
            "macd_signal": round(latest_macd_signal, 4) if latest_macd_signal is not None else None,
            "ma50": round(latest_ma50, 2) if latest_ma50 is not None else None,
            "ma200": round(latest_ma200, 2) if latest_ma200 is not None else None,
            "golden_cross": bool(latest_ma50 is not None and latest_ma200 is not None and latest_ma50 > latest_ma200),
            "trend_label": (
                "Bullish" if latest_ma50 is not None and latest_ma200 is not None and latest_ma50 > latest_ma200
                else ("Bearish" if latest_ma50 is not None and latest_ma200 is not None else "Relevant data is not available")
            ),
        },
        "news_sentiment_distribution": {
            "bullish": bullish_pct,
            "neutral": neutral_pct,
            "bearish": bearish_pct,
        },
        "forecast": (
            {"predicted_return_pct": round(forecast_30d_pct, 2)} if forecast_30d_pct is not None
            else {"status": "Forecast unavailable"}
        ),
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

        cache_key = f"ai-picker:{normalized_strategy}:{int(limit)}"
        cached = _cache_get(generic_ttl_cache, cache_key, AI_PICKER_CACHE_TTL)
        if cached is not None:
            return cached

        picks = get_ai_picks(normalized_strategy, limit)
        payload = {
            "strategy": normalized_strategy,
            "items": picks,
            "count": len(picks),
            "timestamp": datetime.now().isoformat()
        }
        return _cache_set(generic_ttl_cache, cache_key, payload)
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


def _qa_results_dir() -> Path:
    return BASE_PATH.parent / "qa" / "results"


def _qa_latest_file() -> Path:
    return _qa_results_dir() / "latest.json"


def _qa_metrics_file() -> Path:
    return _qa_results_dir() / "metrics.jsonl"


def _qa_alerts_file() -> Path:
    return _qa_results_dir() / "alerts.json"


def _qa_regime_history_file() -> Path:
    return _qa_results_dir() / "regime_history.jsonl"


def _safe_json_read(path: Path) -> Any:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Unable to read JSON file {path}: {exc}")
        return None


def _safe_jsonl_read(path: Path, limit: int = 30) -> List[Dict[str, Any]]:
    try:
        if not path.exists():
            return []
        rows: List[Dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = str(line or "").strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        return rows[-limit:]
    except Exception as exc:
        logger.warning(f"Unable to read JSONL file {path}: {exc}")
        return []


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _qa_read_alerts() -> Dict[str, Any]:
    payload = _safe_json_read(_qa_alerts_file())
    if isinstance(payload, dict):
        return payload
    return {"active": {}, "history": [], "updated_at": None}


def _qa_save_alerts(payload: Dict[str, Any]) -> None:
    path = _qa_alerts_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _qa_now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _qa_find_alert(alert_id: str, state: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], str]:
    payload = state or _qa_read_alerts()
    active = dict(payload.get("active") or {})
    alert = active.get(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return payload, alert_id


def _qa_test_group(test_id: str) -> str:
    text = str(test_id or "").upper()
    if text.startswith("DATA_"):
        return "data"
    if text.startswith("DECISION_"):
        return "decision"
    if text.startswith("AI_"):
        return "ai"
    if text.startswith("INTENT_"):
        return "intent"
    if text.startswith("RESILIENCE_"):
        return "resilience"
    if text.startswith("FLOW_"):
        return "flow"
    return "other"


def _qa_parse_deviation(value: Any) -> Optional[float]:
    raw = str(value or "").strip().lower()
    if not raw or raw == "n/a":
        return None
    try:
        normalized = (
            raw.replace("%", "")
            .replace("pts", "")
            .replace("point", "")
            .replace("points", "")
            .strip()
        )
        return float(normalized)
    except Exception:
        return None


def _qa_compute_data_accuracy(results: List[Dict[str, Any]]) -> Optional[float]:
    data_results = [row for row in results if _qa_test_group(row.get("test_id")) == "data"]
    if not data_results:
        return None
    score = 100.0
    failures = sum(1 for row in data_results if str(row.get("status")).upper() != "PASS")
    score -= failures * 12.5
    deviations = [_qa_parse_deviation(row.get("deviation")) for row in data_results]
    numeric_deviations = [value for value in deviations if value is not None]
    if numeric_deviations:
        score -= min(sum(numeric_deviations) / len(numeric_deviations), 20.0)
    return round(max(0.0, min(100.0, score)), 1)


def _qa_compute_ai_reliability(results: List[Dict[str, Any]]) -> Optional[float]:
    ai_results = [
        row for row in results
        if _qa_test_group(row.get("test_id")) in {"decision", "ai", "intent"}
    ]
    if not ai_results:
        return None
    passed = sum(1 for row in ai_results if str(row.get("status")).upper() == "PASS")
    return round((passed / len(ai_results)) * 100.0, 1)


def _qa_metric_delta(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None:
        return None
    try:
        return round(float(current) - float(previous), 1)
    except Exception:
        return None


def _qa_parse_metric_rows(metrics_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    series: List[Dict[str, Any]] = []
    for row in metrics_rows:
        total = _to_float(row.get("total"))
        passed = _to_float(row.get("passed"))
        pass_rate = None
        if total and total > 0 and passed is not None:
            pass_rate = round((passed / total) * 100.0, 1)
        data_accuracy = _to_float(row.get("data_accuracy"))
        ai_reliability = _to_float(row.get("ai_reliability"))
        series.append({
            "timestamp": row.get("generated_at"),
            "pass_rate": pass_rate,
            "data_accuracy": round(data_accuracy, 1) if data_accuracy is not None else None,
            "ai_reliability": round(ai_reliability, 1) if ai_reliability is not None else None,
            "passed": row.get("passed"),
            "failed": row.get("failed"),
            "total": row.get("total"),
        })
    return series


def _qa_api_health_snapshot() -> Dict[str, Any]:
    provider_snapshot = providers_status()
    providers = provider_snapshot.get("providers") or {}
    states = []
    for name, payload in providers.items():
        status = str((payload or {}).get("status") or "unknown").lower()
        configured = bool((payload or {}).get("configured"))
        if configured and status in {"ok", "healthy", "up"}:
            state = "healthy"
        elif configured and status in {"unknown", "degraded"}:
            state = "degraded"
        elif configured:
            state = "degraded"
        else:
            state = "missing"
        states.append({"provider": name, "state": state, "details": payload})

    if states and all(item["state"] == "healthy" for item in states):
        overall = "healthy"
    elif any(item["state"] == "healthy" for item in states):
        overall = "degraded"
    else:
        overall = "critical"

    return {
        "overall": overall,
        "providers": states,
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }


def _qa_build_dashboard_payload() -> Dict[str, Any]:
    latest = _safe_json_read(_qa_latest_file()) or {}
    metrics_rows = _safe_jsonl_read(_qa_metrics_file(), limit=500)
    results = list((latest.get("results") or []))
    summary = dict(latest.get("summary") or {})
    total = int(summary.get("total") or len(results) or 0)
    passed = int(summary.get("passed") or 0)
    failed = int(summary.get("failed") or max(0, total - passed))
    pass_rate = round((passed / total) * 100.0, 1) if total > 0 else None
    data_accuracy = _qa_compute_data_accuracy(results)
    ai_reliability = _qa_compute_ai_reliability(results)
    uptime_seconds = max(0.0, (datetime.utcnow() - APP_STARTED_AT).total_seconds())
    uptime_hours = round(uptime_seconds / 3600.0, 2)
    failed_tests = [
        {
            "test_id": row.get("test_id"),
            "expected": row.get("expected"),
            "actual": row.get("actual"),
            "deviation": row.get("deviation"),
            "notes": row.get("notes"),
            "group": _qa_test_group(row.get("test_id")),
        }
        for row in results
        if str(row.get("status") or "").upper() != "PASS"
    ]
    metric_trends = _qa_parse_metric_rows(metrics_rows)
    deviation_trends = [
        {
            "timestamp": row.get("timestamp"),
            "pass_rate": row.get("pass_rate"),
            "passed": row.get("passed"),
            "failed": row.get("failed"),
            "total": row.get("total"),
        }
        for row in metric_trends
    ]
    latest_metric_point = metric_trends[-1] if metric_trends else None
    previous_metric_point = metric_trends[-2] if len(metric_trends) > 1 else None
    thresholds = {
        "pass_rate_alert_below": 90.0,
        "data_accuracy_alert_below": 95.0,
        "ai_reliability_alert_below": 80.0,
    }
    alert_state = _qa_read_alerts()
    active_alerts = list((alert_state.get("active") or {}).values())
    recent_history = list(alert_state.get("history") or [])[-20:]

    group_summary: Dict[str, Dict[str, Any]] = {}
    for group in ["data", "decision", "ai", "intent", "resilience", "flow", "other"]:
        group_rows = [row for row in results if _qa_test_group(row.get("test_id")) == group]
        if not group_rows:
            continue
        group_total = len(group_rows)
        group_passed = sum(1 for row in group_rows if str(row.get("status")).upper() == "PASS")
        group_summary[group] = {
            "total": group_total,
            "passed": group_passed,
            "failed": group_total - group_passed,
            "pass_rate": round((group_passed / group_total) * 100.0, 1),
        }

    return {
        "generated_at": latest.get("generated_at"),
        "summary": {
            "total_tests": total,
            "passed_tests": passed,
            "failed_tests": failed,
            "pass_rate": pass_rate,
            "data_accuracy_score": data_accuracy,
            "ai_reliability_score": ai_reliability,
            "system_uptime_seconds": round(uptime_seconds, 1),
            "system_uptime_hours": uptime_hours,
        },
        "api_health": _qa_api_health_snapshot(),
        "thresholds": thresholds,
        "alerts": active_alerts,
        "alert_history": recent_history,
        "alert_state_updated_at": alert_state.get("updated_at"),
        "failed_tests": failed_tests[:20],
        "deviation_trends": deviation_trends,
        "metric_trends": metric_trends,
        "metric_latest": {
            "pass_rate": latest_metric_point.get("pass_rate") if latest_metric_point else pass_rate,
            "data_accuracy": latest_metric_point.get("data_accuracy") if latest_metric_point else data_accuracy,
            "ai_reliability": latest_metric_point.get("ai_reliability") if latest_metric_point else ai_reliability,
        },
        "metric_deltas": {
            "pass_rate": _qa_metric_delta(
                latest_metric_point.get("pass_rate") if latest_metric_point else pass_rate,
                previous_metric_point.get("pass_rate") if previous_metric_point else None,
            ),
            "data_accuracy": _qa_metric_delta(
                latest_metric_point.get("data_accuracy") if latest_metric_point else data_accuracy,
                previous_metric_point.get("data_accuracy") if previous_metric_point else None,
            ),
            "ai_reliability": _qa_metric_delta(
                latest_metric_point.get("ai_reliability") if latest_metric_point else ai_reliability,
                previous_metric_point.get("ai_reliability") if previous_metric_point else None,
            ),
        },
        "group_summary": group_summary,
        "results_available": bool(results),
    }


@app.get("/qa/dashboard")
@app.get("/api/qa/dashboard")
def qa_dashboard_endpoint():
    return _qa_build_dashboard_payload()


@app.post("/qa/alerts/{alert_id}/acknowledge")
@app.post("/api/qa/alerts/{alert_id}/acknowledge")
def qa_alert_acknowledge_endpoint(alert_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    alert_state, resolved_id = _qa_find_alert(alert_id)
    active = dict(alert_state.get("active") or {})
    alert = dict(active.get(resolved_id) or {})
    body = payload or {}
    alert["acknowledged"] = True
    alert["acknowledged_by"] = str(body.get("acknowledged_by") or body.get("operator") or "operator").strip() or "operator"
    alert["acknowledged_at"] = _qa_now_iso()
    active[resolved_id] = alert
    history = list(alert_state.get("history") or [])
    history.append({**alert, "event_type": "ACKNOWLEDGED", "notes": f"Acknowledged by {alert['acknowledged_by']}"})
    updated_state = {
        **alert_state,
        "active": active,
        "history": history[-100:],
        "updated_at": _qa_now_iso(),
    }
    _qa_save_alerts(updated_state)
    return {"ok": True, "alert": alert}


@app.post("/qa/alerts/{alert_id}/mute")
@app.post("/api/qa/alerts/{alert_id}/mute")
def qa_alert_mute_endpoint(alert_id: str, minutes: int = Query(60, ge=1, le=10080), payload: Optional[Dict[str, Any]] = Body(None)):
    alert_state, resolved_id = _qa_find_alert(alert_id)
    active = dict(alert_state.get("active") or {})
    alert = dict(active.get(resolved_id) or {})
    muted_until = datetime.utcnow() + timedelta(minutes=minutes)
    alert["muted_until"] = muted_until.isoformat() + "Z"
    active[resolved_id] = alert
    body = payload or {}
    operator = str(body.get("muted_by") or body.get("operator") or "operator").strip() or "operator"
    history = list(alert_state.get("history") or [])
    history.append({**alert, "event_type": "MUTED", "notes": f"Muted by {operator} for {minutes} minutes"})
    updated_state = {
        **alert_state,
        "active": active,
        "history": history[-100:],
        "updated_at": _qa_now_iso(),
    }
    _qa_save_alerts(updated_state)
    return {"ok": True, "alert": alert}

# ข่าวหลายตัว
@app.get("/news")
def news_endpoint(symbols: str, days_back: int = 7):
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not syms:
        raise HTTPException(status_code=400, detail="No valid symbols")
    try:
        return get_newsapi_news_batch(syms, 10, days_back)
    except Exception as e:
        logger.error(f"Error in /news: {e}")
        return [{"symbol": sym, "news": []} for sym in syms]

@app.get("/api/news")
def news_api_compat():
    try:
        default_symbols = _default_active_symbols(3)
        if not default_symbols:
            return {
                "news": [],
                "symbols": [],
                "status": "degraded",
                "message": "No active symbols available for news feed",
            }
        data = get_newsapi_news_batch(default_symbols, 3, 7)
        merged = []
        for row in data:
            merged.extend(row.get("news", []))
        return {
            "news": merged[:9],
            "symbols": default_symbols,
            "status": "ok",
        }
    except Exception as e:
        logger.error(f"Error in /api/news: {e}")
        return {
            "news": [],
            "symbols": [],
            "status": "degraded",
            "message": "News feed temporarily unavailable",
        }


@app.get("/prices")
@app.get("/api/prices")
def prices_batch_endpoint(symbols: str = Query(..., description="Comma-separated symbols")):
    normalized_symbols = normalize_symbol_list(symbols.split(","))
    if not normalized_symbols:
        raise HTTPException(status_code=400, detail="No valid symbols")

    def _load_quote(sym: str) -> Dict[str, Any]:
        try:
            data = get_stock_data(sym, "1d")
            price = safe_float(data.get("price"))
            previous_close = safe_float(data.get("previous_close"))
            change_pct = ((price - previous_close) / previous_close * 100.0) if previous_close > 0 else 0.0
            return {
                "symbol": sym,
                "price": round(price, 4),
                "previous_close": round(previous_close, 4) if previous_close > 0 else None,
                "change_pct": round(change_pct, 4),
                "provider": data.get("provider"),
                "ok": True,
            }
        except HTTPException as e:
            logger.warning(f"/api/prices partial failure for {sym}: {e.detail}")
            return {
                "symbol": sym,
                "price": None,
                "previous_close": None,
                "change_pct": None,
                "provider": None,
                "ok": False,
                "error": str(e.detail),
            }
        except Exception as e:
            logger.warning(f"/api/prices unexpected partial failure for {sym}: {e}")
            return {
                "symbol": sym,
                "price": None,
                "previous_close": None,
                "change_pct": None,
                "provider": None,
                "ok": False,
                "error": "quote unavailable",
            }

    rows = _parallel_map(_load_quote, normalized_symbols[:25], max_workers=min(8, len(normalized_symbols[:25])))
    success_count = len([row for row in rows if row.get("ok")])
    return {
        "items": rows,
        "count": len(rows),
        "success_count": success_count,
        "updatedAt": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/market-sentiment")
@app.get("/api/market-sentiment")
def market_sentiment_endpoint(force_refresh: bool = Query(False, description="Bypass cache (10m)")):
    if not HAS_MARKET_SENTIMENT:
        return {
            "sentiment_score": None,
            "sentiment_label": None,
            "score": None,
            "sentiment": None,
            "cnn_reference": {
                "score": None,
                "divergence": None,
                "label": None,
                "fetched_at": None,
                "endpoint": None,
            },
            "cnn_reference_score": None,
            "cnn_divergence": None,
            "regime": None,
            "confidence": None,
            "regime_interpretation": "Volatility calming does not imply bullish recovery when momentum and breadth remain weak.",
            "positioning": {
                "overweight": ["Balanced allocation"],
                "neutral": ["Healthcare", "Industrials"],
                "underweight": ["High-beta Growth"],
            },
            "suggested_etfs": ["SPY", "XLI"],
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "source": "Unavailable",
            "status": "degraded",
            "message": "Market sentiment service unavailable",
            "indicators": {
                "momentum": None,
                "strength": None,
                "volatility": None,
                "safeHaven": None,
            },
        }
    try:
        return compute_market_sentiment(force_refresh=force_refresh)
    except Exception as e:
        logger.error(f"Error in /market-sentiment: {e}")
        return {
            "sentiment_score": None,
            "sentiment_label": None,
            "score": None,
            "sentiment": None,
            "cnn_reference": {
                "score": None,
                "divergence": None,
                "label": None,
                "fetched_at": None,
                "endpoint": None,
            },
            "cnn_reference_score": None,
            "cnn_divergence": None,
            "regime": None,
            "confidence": None,
            "regime_interpretation": "Volatility calming does not imply bullish recovery when momentum and breadth remain weak.",
            "positioning": {
                "overweight": ["Balanced allocation"],
                "neutral": ["Healthcare", "Industrials"],
                "underweight": ["High-beta Growth"],
            },
            "suggested_etfs": ["SPY", "XLI"],
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "source": "Unavailable",
            "status": "degraded",
            "message": "Failed to compute market sentiment",
            "indicators": {
                "momentum": None,
                "strength": None,
                "volatility": None,
                "safeHaven": None,
            },
        }


@app.get("/api/market-sentiment/history")
@app.get("/market-sentiment/history")
def market_sentiment_history_endpoint(limit: int = Query(100, ge=1, le=1000)):
    rows = _safe_jsonl_read(_qa_regime_history_file(), limit=limit)
    distribution: Dict[str, int] = {}
    confidence_distribution: Dict[str, int] = {}
    for row in rows:
        regime = str(row.get("regime") or "unknown")
        distribution[regime] = int(distribution.get(regime, 0)) + 1
        confidence = str(row.get("confidence") or "unknown")
        confidence_distribution[confidence] = int(confidence_distribution.get(confidence, 0)) + 1

    total = len(rows)
    regime_distribution = [
        {
            "regime": regime,
            "count": count,
            "share_pct": round((count / total) * 100.0, 2) if total else 0.0,
        }
        for regime, count in sorted(distribution.items(), key=lambda item: item[1], reverse=True)
    ]
    confidence_breakdown = [
        {
            "confidence": confidence,
            "count": count,
            "share_pct": round((count / total) * 100.0, 2) if total else 0.0,
        }
        for confidence, count in sorted(confidence_distribution.items(), key=lambda item: item[1], reverse=True)
    ]

    return {
        "count": total,
        "items": rows,
        "regime_distribution": regime_distribution,
        "confidence_distribution": confidence_breakdown,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


class AIAdvisorContext(BaseModel):
    watchlist: List[str] = Field(default_factory=list)
    portfolio: List[Dict[str, Any]] = Field(default_factory=list)
    sentiment: Optional[float] = None
    recent_searches: List[str] = Field(default_factory=list)
    risk_profile: Optional[str] = None
    selected_stock: Optional[str] = None
    chat_state: Dict[str, Any] = Field(default_factory=dict)
    history: List[str] = Field(default_factory=list)


class AIAdvisorRequest(BaseModel):
    question: str
    history: List[str] = Field(default_factory=list)
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


class AITradeSignalRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    recommendation: str = Field(..., min_length=3, max_length=32)
    size: float = Field(default=1.0, gt=0, le=1.0)


class AITradeExitRequest(BaseModel):
    reason: Optional[str] = Field(default="manual_exit", min_length=3, max_length=32)


class AIAutoTuneRequest(BaseModel):
    operator: Optional[str] = Field(default="system", min_length=2, max_length=64)


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


AI_TRADE_SIGNAL_MAP = {
    "STRONG BUY": ("long", 1.0),
    "BUY": ("long", 0.5),
    "HOLD": (None, 0.0),
    "HOLD (BULLISH BIAS)": (None, 0.0),
    "HOLD (BEARISH BIAS)": (None, 0.0),
    "SELL": ("short", 0.5),
    "STRONG SELL": ("short", 1.0),
}


def _normalize_recommendation_signal(label: Any) -> str:
    return str(label or "HOLD").strip().upper()


def _signal_trade_profile(label: Any) -> Dict[str, Any]:
    normalized = _normalize_recommendation_signal(label)
    position, default_size = AI_TRADE_SIGNAL_MAP.get(normalized, (None, 0.0))
    tuning = _load_ai_tuning_config()
    position_size_scale = _clamp(safe_float(tuning.get("position_size_scale")) or 1.0, 0.1, 1.0)
    long_position_scale = _clamp(safe_float(tuning.get("long_position_scale")) or 1.0, 0.1, 1.0)
    sell_weight_scale = _clamp(safe_float(tuning.get("sell_weight_scale")) or 1.0, 0.1, 1.5)

    scaled_size = float(default_size or 0.0) * position_size_scale
    if position == "long":
        scaled_size *= long_position_scale
    elif position == "short":
        scaled_size *= sell_weight_scale

    return {
        "recommendation": normalized,
        "position": position,
        "default_size": round(_clamp(scaled_size, 0.0, 1.0), 4),
    }


def _trade_direction_multiplier(position: Any) -> float:
    return 1.0 if str(position or "").lower() == "long" else -1.0


def _trade_unrealized_pnl(entry_price: Any, current_price: Any, position: Any, size: Any) -> float:
    entry = safe_float(entry_price)
    current = safe_float(current_price)
    trade_size = safe_float(size)
    if entry <= 0 or current <= 0 or trade_size <= 0:
        return 0.0
    return (current - entry) * _trade_direction_multiplier(position) * trade_size


def _trade_return_pct(entry_price: Any, exit_price: Any, position: Any) -> float:
    entry = safe_float(entry_price)
    exit_value = safe_float(exit_price)
    if entry <= 0 or exit_value <= 0:
        return 0.0
    return ((exit_value - entry) / entry) * _trade_direction_multiplier(position) * 100.0


def _close_trade(row: AIRecommendationTrade, exit_price: float, reason: str) -> None:
    row.exit_price = float(exit_price)
    row.exit_time = datetime.utcnow()
    row.exit_reason = str(reason or "manual_exit")
    row.realized_pnl = round(
        _trade_unrealized_pnl(row.entry_price, exit_price, row.position, row.size),
        4,
    )
    row.status = "closed"
    row.updated_at = datetime.utcnow()


def _close_expired_ai_trades(db, user_id: int) -> int:
    expiry_cutoff = datetime.utcnow() - timedelta(days=30)
    rows: List[AIRecommendationTrade] = (
        db.query(AIRecommendationTrade)
        .filter(
            AIRecommendationTrade.user_id == user_id,
            AIRecommendationTrade.status == "open",
            AIRecommendationTrade.entry_time <= expiry_cutoff,
        )
        .all()
    )
    closed = 0
    for row in rows:
        quote = _get_portfolio_quote(row.symbol)
        current_price = safe_float(quote.get("price"))
        if current_price <= 0:
            continue
        _close_trade(row, current_price, "max_holding_period")
        db.add(row)
        closed += 1
    if closed:
        db.commit()
    return closed


def _serialize_ai_trade(row: AIRecommendationTrade) -> Dict[str, Any]:
    quote = _get_portfolio_quote(row.symbol)
    current_price = safe_float(quote.get("price"))
    previous_close = safe_float(quote.get("previous_close"))
    direction = _trade_direction_multiplier(row.position)
    unrealized_pnl = (
        _trade_unrealized_pnl(row.entry_price, current_price, row.position, row.size)
        if row.status == "open"
        else 0.0
    )
    realized_pnl = safe_float(row.realized_pnl)
    daily_pnl = 0.0
    if row.status == "open" and current_price > 0 and previous_close > 0:
        daily_pnl = (current_price - previous_close) * direction * safe_float(row.size)
    exposure = abs(current_price * safe_float(row.size)) if row.status == "open" and current_price > 0 else 0.0
    days_open = None
    if row.entry_time:
        end_point = row.exit_time or datetime.utcnow()
        days_open = max(0, (end_point - row.entry_time).days)

    return {
        "id": row.id,
        "symbol": row.symbol,
        "recommendation": row.recommendation,
        "position": row.position,
        "size": round(safe_float(row.size), 4),
        "entry_price": round(safe_float(row.entry_price), 4),
        "entry_time": row.entry_time.isoformat() if row.entry_time else None,
        "status": row.status,
        "current_price": round(current_price, 4) if current_price > 0 else None,
        "previous_close": round(previous_close, 4) if previous_close > 0 else None,
        "unrealized_pnl": round(unrealized_pnl, 4),
        "realized_pnl": round(realized_pnl, 4),
        "daily_pnl": round(daily_pnl, 4),
        "exposure": round(exposure, 4),
        "trade_return_pct": round(
            _trade_return_pct(
                row.entry_price,
                current_price if row.status == "open" else row.exit_price,
                row.position,
            ),
            4,
        ),
        "days_open": days_open,
        "exit_price": round(safe_float(row.exit_price), 4) if safe_float(row.exit_price) > 0 else None,
        "exit_time": row.exit_time.isoformat() if row.exit_time else None,
        "exit_reason": row.exit_reason,
    }


def _summarize_ai_trades(rows: List[AIRecommendationTrade]) -> Dict[str, Any]:
    serialized = [_serialize_ai_trade(row) for row in rows]
    open_rows = [row for row in serialized if row["status"] == "open"]
    closed_rows = [row for row in serialized if row["status"] == "closed"]

    unrealized = sum(float(row["unrealized_pnl"] or 0.0) for row in open_rows)
    realized = sum(float(row["realized_pnl"] or 0.0) for row in closed_rows)
    daily_pnl = sum(float(row["daily_pnl"] or 0.0) for row in open_rows)
    exposure = sum(abs(float(row["exposure"] or 0.0)) for row in open_rows)
    total_pnl = unrealized + realized
    daily_return = (daily_pnl / exposure * 100.0) if exposure > 0 else 0.0
    closed_returns = [float(row["trade_return_pct"] or 0.0) for row in closed_rows]
    winning_closed = [ret for ret in closed_returns if ret > 0]
    win_rate = (len(winning_closed) / len(closed_returns) * 100.0) if closed_returns else 0.0
    average_trade_return = (sum(closed_returns) / len(closed_returns)) if closed_returns else 0.0

    return {
        "total_pnl": round(total_pnl, 4),
        "daily_return": round(daily_return, 4),
        "unrealized_pnl": round(unrealized, 4),
        "realized_pnl": round(realized, 4),
        "exposure": round(exposure, 4),
        "open_positions": len(open_rows),
        "closed_positions": len(closed_rows),
        "win_rate": round(win_rate, 2),
        "average_trade_return": round(average_trade_return, 4),
        "trades": serialized,
    }


def _build_spy_regime_map() -> Dict[str, str]:
    try:
        history = get_stock_data("SPY", "all").get("history", [])
    except Exception:
        history = []
    if not history:
        return {}

    frame = pd.DataFrame(history)
    if frame.empty or "date" not in frame.columns or "close" not in frame.columns:
        return {}
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["date", "close"]).sort_values("date")
    if frame.empty:
        return {}

    frame["sma200"] = frame["close"].rolling(200, min_periods=50).mean()
    frame["ret63"] = frame["close"].pct_change(63)

    regime_map: Dict[str, str] = {}
    for _, row in frame.iterrows():
        date_key = row["date"].strftime("%Y-%m-%d")
        close = safe_float(row["close"])
        sma200 = safe_float(row.get("sma200"))
        ret63 = safe_float(row.get("ret63"))
        bullish = close > 0 and sma200 > 0 and close >= sma200 and ret63 >= 0
        bearish = close > 0 and sma200 > 0 and close < sma200 and ret63 < 0
        regime_map[date_key] = "bull" if bullish else ("bear" if bearish else "neutral")
    return regime_map


def _resolve_regime_for_trade(entry_time: Optional[datetime], regime_map: Dict[str, str]) -> str:
    if not entry_time or not regime_map:
        return "unknown"
    date_key = entry_time.strftime("%Y-%m-%d")
    if date_key in regime_map:
        return regime_map[date_key]
    eligible = [key for key in regime_map.keys() if key <= date_key]
    if not eligible:
        return "unknown"
    return regime_map[max(eligible)]


def _compute_return_risk_metrics(returns: List[float]) -> Dict[str, Any]:
    clean_returns = [float(value) for value in returns]
    if not clean_returns:
        return {
            "trades": 0,
            "confidence": "low",
            "low_confidence": True,
            "avg_return": 0.0,
            "win_rate": 0.0,
            "std_return": 0.0,
            "sharpe": None,
            "sortino": None,
            "max_drawdown": 0.0,
            "calmar": None,
            "profit_factor": None,
            "profit_factor_status": "insufficient_data",
            "best_trade": 0.0,
            "worst_trade": 0.0,
        }

    trade_count = len(clean_returns)
    low_confidence = trade_count < 10
    confidence = "high" if trade_count >= 30 else ("medium" if trade_count >= 10 else "low")

    wins = [value for value in clean_returns if value > 0]
    losses = [value for value in clean_returns if value < 0]
    avg_return = sum(clean_returns) / trade_count
    win_rate = (len(wins) / trade_count) * 100.0

    series = pd.Series(clean_returns, dtype=float)
    std = float(series.std(ddof=0) or 0.0)
    sharpe = None if std <= 1e-12 else float(series.mean() / std)

    downside = series[series < 0]
    downside_std = float(downside.std(ddof=0) or 0.0) if not downside.empty else 0.0
    sortino = None if downside_std <= 1e-12 else float(series.mean() / downside_std)

    equity = (1.0 + (series / 100.0)).cumprod()
    running_peak = equity.cummax()
    drawdowns = ((equity / running_peak) - 1.0) * 100.0
    max_drawdown = float(drawdowns.min() or 0.0)
    total_return = float((equity.iloc[-1] - 1.0) * 100.0) if not equity.empty else 0.0
    calmar = None if abs(max_drawdown) <= 1e-12 else float(total_return / abs(max_drawdown))

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss <= 1e-12:
        profit_factor = None
        profit_factor_status = "infinite" if gross_profit > 0 else "flat"
    else:
        profit_factor = gross_profit / gross_loss
        profit_factor_status = "finite"

    return {
        "trades": trade_count,
        "confidence": confidence,
        "low_confidence": low_confidence,
        "avg_return": round(avg_return, 4),
        "win_rate": round(win_rate, 2),
        "std_return": round(std, 4),
        "sharpe": round(sharpe, 4) if sharpe is not None else None,
        "sortino": round(sortino, 4) if sortino is not None else None,
        "max_drawdown": round(max_drawdown, 4),
        "calmar": round(calmar, 4) if calmar is not None else None,
        "profit_factor": round(profit_factor, 4) if profit_factor is not None else None,
        "profit_factor_status": profit_factor_status,
        "best_trade": round(max(clean_returns), 4),
        "worst_trade": round(min(clean_returns), 4),
    }


def _aggregate_trade_groups(rows: List[Dict[str, Any]], key_name: str) -> List[Dict[str, Any]]:
    grouped: Dict[str, List[float]] = defaultdict(list)
    for row in rows:
        key = str(row.get(key_name) or "unknown")
        grouped[key].append(float(row.get("trade_return_pct") or 0.0))

    summary = []
    for key, values in grouped.items():
        if not values:
            continue
        metrics = _compute_return_risk_metrics(values)
        summary.append({
            "label": key,
            "trades": metrics["trades"],
            "confidence": metrics["confidence"],
            "low_confidence": metrics["low_confidence"],
            "average_return": metrics["avg_return"],
            "win_rate": metrics["win_rate"],
            "std_return": metrics["std_return"],
            "best_trade": metrics["best_trade"],
            "worst_trade": metrics["worst_trade"],
            "sharpe": metrics["sharpe"],
            "sortino": metrics["sortino"],
            "max_drawdown": metrics["max_drawdown"],
            "calmar": metrics["calmar"],
            "profit_factor": metrics["profit_factor"],
            "profit_factor_status": metrics["profit_factor_status"],
        })
    summary.sort(key=lambda item: (item["average_return"], item["win_rate"]), reverse=True)
    return summary


def _load_regime_history(limit: int = 5000) -> List[Dict[str, Any]]:
    rows = _safe_jsonl_read(_qa_regime_history_file(), limit=limit)
    enriched: List[Dict[str, Any]] = []
    for row in rows:
        timestamp = _parse_iso_datetime(row.get("timestamp"))
        if not timestamp:
            continue
        enriched.append({**row, "_dt": timestamp})
    enriched.sort(key=lambda row: row["_dt"])
    return enriched


def _resolve_regime_snapshot_for_trade(entry_time: Optional[datetime], regime_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    fallback = {
        "regime": "unknown",
        "confidence": "low",
        "timestamp": None,
        "momentum": None,
        "strength": None,
        "volatility": None,
        "safe_haven": None,
    }
    if not entry_time or not regime_rows:
        return fallback

    target_ts = entry_time.timestamp()
    nearest = None
    nearest_delta = None
    for row in regime_rows:
        dt = row.get("_dt")
        if not dt:
            continue
        delta = abs(dt.timestamp() - target_ts)
        if nearest_delta is None or delta < nearest_delta:
            nearest = row
            nearest_delta = delta

    if not nearest:
        return fallback

    return {
        "regime": str(nearest.get("regime") or "unknown"),
        "confidence": str(nearest.get("confidence") or "low"),
        "timestamp": nearest.get("timestamp"),
        "momentum": nearest.get("momentum"),
        "strength": nearest.get("strength"),
        "volatility": nearest.get("volatility"),
        "safe_haven": nearest.get("safe_haven"),
    }


def _aggregate_regime_signal_performance(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[tuple, List[float]] = defaultdict(list)
    for row in rows:
        regime = str(row.get("market_regime") or "unknown")
        signal = str(row.get("recommendation_group") or "unknown")
        grouped[(regime, signal)].append(float(row.get("trade_return_pct") or 0.0))

    output: List[Dict[str, Any]] = []
    for (regime, signal), returns in grouped.items():
        metrics = _compute_return_risk_metrics(returns)
        output.append({
            "regime": regime,
            "signal": signal,
            "trades": metrics["trades"],
            "confidence": metrics["confidence"],
            "avg_return": metrics["avg_return"],
            "win_rate": metrics["win_rate"],
            "std_return": metrics["std_return"],
            "sharpe": metrics["sharpe"],
            "sortino": metrics["sortino"],
            "max_drawdown": metrics["max_drawdown"],
            "profit_factor": metrics["profit_factor"],
        })
    output.sort(key=lambda row: (row["regime"], -safe_float(row.get("avg_return")), -safe_float(row.get("win_rate"))))
    return output


def _build_regime_signal_insights(regime_signal_performance: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_regime: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in regime_signal_performance:
        by_regime[str(row.get("regime") or "unknown")].append(row)

    best_signal_per_regime: List[Dict[str, Any]] = []
    worst_signal_per_regime: List[Dict[str, Any]] = []
    insights: List[str] = []
    suggested_adaptations: List[str] = []

    for regime, rows in by_regime.items():
        ordered = sorted(rows, key=lambda item: (safe_float(item.get("avg_return")), safe_float(item.get("win_rate"))), reverse=True)
        if not ordered:
            continue
        best = ordered[0]
        worst = ordered[-1]
        best_signal_per_regime.append({
            "regime": regime,
            "signal": best.get("signal"),
            "avg_return": best.get("avg_return"),
            "win_rate": best.get("win_rate"),
            "trades": best.get("trades"),
        })
        worst_signal_per_regime.append({
            "regime": regime,
            "signal": worst.get("signal"),
            "avg_return": worst.get("avg_return"),
            "win_rate": worst.get("win_rate"),
            "trades": worst.get("trades"),
        })

        if regime == "Risk-Off":
            if str(worst.get("signal")) in {"BUY", "STRONG BUY"}:
                insights.append(f"{worst.get('signal')} signals underperform in {regime} regimes.")
                suggested_adaptations.append("Disable Strong Buy signals during Risk-Off regimes.")
            if str(best.get("signal")) in {"SELL", "STRONG SELL"}:
                insights.append(f"{best.get('signal')} signals perform best during {regime} regimes.")
                suggested_adaptations.append("Increase weight of defensive sectors during Risk-Off.")
        elif regime == "Risk-On":
            if str(best.get("signal")) in {"BUY", "STRONG BUY"}:
                insights.append(f"{best.get('signal')} signals perform best in {regime} environments.")
                suggested_adaptations.append("Increase allocation to momentum signals during Risk-On.")
            if str(worst.get("signal")) in {"SELL", "STRONG SELL"}:
                insights.append(f"{worst.get('signal')} signals lose edge in {regime} environments.")
        elif regime == "Neutral":
            insights.append(f"{best.get('signal')} is the most resilient signal in Neutral regimes.")

    return {
        "best_signal_per_regime": best_signal_per_regime,
        "worst_signal_per_regime": worst_signal_per_regime,
        "insights": list(dict.fromkeys(insights)),
        "suggested_adaptations": list(dict.fromkeys(suggested_adaptations)),
    }


def _compute_trade_window_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    returns = [float(row.get("trade_return_pct") or 0.0) for row in rows]
    metrics = _compute_return_risk_metrics(returns)
    return {
        "trades": metrics["trades"],
        "confidence": metrics["confidence"],
        "low_confidence": metrics["low_confidence"],
        "avg_return": metrics["avg_return"],
        "win_rate": metrics["win_rate"],
        "std_return": metrics["std_return"],
        "sharpe": metrics["sharpe"],
        "sortino": metrics["sortino"],
        "max_drawdown": metrics["max_drawdown"],
        "calmar": metrics["calmar"],
        "profit_factor": metrics["profit_factor"],
        "profit_factor_status": metrics["profit_factor_status"],
    }


def _build_rolling_trade_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ordered_rows = sorted(
        rows,
        key=lambda row: str(row.get("entry_time") or ""),
        reverse=True,
    )
    last_30 = _compute_trade_window_metrics(ordered_rows[:30])
    last_60 = _compute_trade_window_metrics(ordered_rows[:60])
    all_time = _compute_trade_window_metrics(ordered_rows)

    baseline = float(all_time.get("avg_return") or 0.0)
    recent = float(last_30.get("avg_return") or 0.0)
    if abs(baseline) > 1e-9:
        delta_ratio = (recent - baseline) / abs(baseline)
    else:
        delta_ratio = 0.0 if abs(recent) < 1e-9 else (1.0 if recent > 0 else -1.0)

    if delta_ratio > 0.2:
        trend = "improving"
    elif delta_ratio < -0.2:
        trend = "degrading"
    else:
        trend = "stable"

    return {
        "rolling": {
            "last_30": last_30,
            "last_60": last_60,
            "all_time": all_time,
        },
        "trend": trend,
    }


def _build_auto_tuning_payload(
    signal_performance: List[Dict[str, Any]],
    regime_performance: List[Dict[str, Any]],
    rolling_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    current = _load_ai_tuning_config()
    proposed = dict(current)
    adjustments: List[str] = []

    signal_map = {str(row.get("label") or "").upper(): row for row in signal_performance}
    strong_buy = signal_map.get("STRONG BUY")
    buy = signal_map.get("BUY")
    strong_sell = signal_map.get("STRONG SELL")
    sell = signal_map.get("SELL")
    bear_regime = next((row for row in regime_performance if str(row.get("label")) == "bear"), None)
    overall = ((rolling_metrics or {}).get("rolling") or {}).get("all_time") or {}
    overall_win_rate = safe_float(overall.get("win_rate"))

    if strong_buy and buy and safe_float(strong_buy.get("average_return")) < safe_float(buy.get("average_return")):
        proposed["strong_buy_momentum_min"] = max(70.0, safe_float(current.get("strong_buy_momentum_min")) or 60.0)
        proposed["strong_buy_technical_min"] = max(65.0, safe_float(current.get("strong_buy_technical_min")) or 65.0)
        adjustments.append("increase Strong Buy threshold")

    strong_sell_poor = False
    if strong_sell and sell and safe_float(strong_sell.get("average_return")) > safe_float(sell.get("average_return")):
        strong_sell_poor = True
    if strong_sell and safe_float(strong_sell.get("win_rate")) < 50.0:
        strong_sell_poor = True
    if strong_sell_poor:
        proposed["strong_sell_forecast_max"] = min(-30.0, safe_float(current.get("strong_sell_forecast_max")) or -20.0)
        proposed["strong_sell_technical_max"] = min(25.0, safe_float(current.get("strong_sell_technical_max")) or 30.0)
        adjustments.append("tighten Strong Sell criteria")

    if bear_regime and safe_float(bear_regime.get("average_return")) < 0:
        proposed["long_position_scale"] = round(min(safe_float(current.get("long_position_scale")) or 1.0, 0.75), 4)
        proposed["sell_weight_scale"] = round(max(safe_float(current.get("sell_weight_scale")) or 1.0, 1.2), 4)
        adjustments.append("reduce long exposure in bear regime")
        adjustments.append("increase sell weight in bear regime")

    if overall_win_rate < 50.0:
        proposed["position_size_scale"] = round(min(safe_float(current.get("position_size_scale")) or 1.0, 0.75), 4)
        adjustments.append("reduce position size")

    deduped_adjustments = list(dict.fromkeys(adjustments))
    proposed["adjustments"] = deduped_adjustments
    proposed["updated_at"] = datetime.utcnow().isoformat()
    changed = False
    for key in [
        "strong_buy_momentum_min",
        "strong_buy_technical_min",
        "strong_sell_forecast_max",
        "strong_sell_technical_max",
        "long_position_scale",
        "sell_weight_scale",
        "position_size_scale",
    ]:
        if abs(safe_float(proposed.get(key)) - safe_float(current.get(key))) > 1e-9:
            changed = True
            break

    return {
        "current": current,
        "proposed": proposed,
        "adjustments": deduped_adjustments,
        "changed": changed,
    }


def _build_evaluation_rankings(
    signal_performance: List[Dict[str, Any]],
    regime_performance: List[Dict[str, Any]],
) -> Dict[str, Any]:
    confidence_multiplier = {
        "high": 1.0,
        "medium": 0.8,
        "low": 0.5,
    }

    def _risk_adjusted_score(row: Dict[str, Any]) -> float:
        return (
            0.5 * safe_float(row.get("sharpe"))
            + 0.3 * safe_float(row.get("calmar"))
            + 0.2 * safe_float(row.get("profit_factor"))
        )

    def _consistency_score(row: Dict[str, Any]) -> float:
        std_return = abs(safe_float(row.get("std_return")))
        volatility_penalty = min(std_return, 100.0)
        return safe_float(row.get("win_rate")) - volatility_penalty

    def _enrich_signal(row: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(row)
        confidence = str(row.get("confidence") or "low").lower()
        multiplier = confidence_multiplier.get(confidence, 0.5)
        eligible = int(safe_float(row.get("trades"))) >= 10
        exploratory = not eligible
        base_score = _risk_adjusted_score(row)
        final_score = base_score * multiplier
        enriched["confidence"] = confidence
        enriched["confidence_multiplier"] = multiplier
        enriched["base_score"] = round(base_score, 4)
        enriched["score"] = round(final_score, 4)
        enriched["risk_adjusted_score"] = round(final_score, 4)
        enriched["consistency_score"] = round(_consistency_score(row) * multiplier, 4)
        enriched["eligible"] = eligible
        enriched["exploratory"] = exploratory
        return enriched

    def _enrich_regime(row: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(row)
        confidence = str(row.get("confidence") or "low").lower()
        eligible = int(safe_float(row.get("trades"))) >= 10
        enriched["confidence"] = confidence
        enriched["eligible"] = eligible
        enriched["exploratory"] = not eligible
        return enriched

    ranked_signals = [_enrich_signal(row) for row in (signal_performance or [])]
    eligible_signals = [row for row in ranked_signals if row.get("eligible")]
    exploratory_signals = [row for row in ranked_signals if row.get("exploratory")]
    enriched_regimes = [_enrich_regime(row) for row in (regime_performance or [])]
    eligible_regimes = [row for row in enriched_regimes if row.get("eligible")]

    best_signal = max(
        eligible_signals,
        key=lambda row: (safe_float(row.get("score")), safe_float(row.get("average_return")), safe_float(row.get("win_rate"))),
        default=None,
    )
    if best_signal is None and exploratory_signals:
        best_signal = max(
            exploratory_signals,
            key=lambda row: (safe_float(row.get("score")), safe_float(row.get("average_return")), safe_float(row.get("win_rate"))),
            default=None,
        )
    most_consistent_signal = max(
        eligible_signals,
        key=lambda row: (safe_float(row.get("consistency_score")), safe_float(row.get("win_rate")), -abs(safe_float(row.get("std_return")))),
        default=None,
    )
    if most_consistent_signal is None and exploratory_signals:
        most_consistent_signal = max(
            exploratory_signals,
            key=lambda row: (safe_float(row.get("consistency_score")), safe_float(row.get("win_rate")), -abs(safe_float(row.get("std_return")))),
            default=None,
        )
    worst_regime = min(
        eligible_regimes or enriched_regimes,
        key=lambda row: safe_float(row.get("max_drawdown")),
        default=None,
    )

    return {
        "best_signal": best_signal,
        "worst_regime": worst_regime,
        "most_consistent_signal": most_consistent_signal,
    }


def _build_ai_trade_evaluation(rows: List[AIRecommendationTrade]) -> Dict[str, Any]:
    serialized = [_serialize_ai_trade(row) for row in rows]
    if not serialized:
        return {
            "signal_performance": [],
            "best_performing_signals": [],
            "worst_signals": [],
            "sector_performance": [],
            "market_regime_performance": [],
            "regime_signal_performance": [],
            "regime_insights": {
                "best_signal_per_regime": [],
                "worst_signal_per_regime": [],
                "insights": [],
            },
            "strategy_adaptation": [],
            "rankings": {
                "best_signal": None,
                "worst_regime": None,
                "most_consistent_signal": None,
            },
            "overall_performance": {
                "trades": 0,
                "confidence": "low",
                "low_confidence": True,
                "avg_return": 0.0,
                "win_rate": 0.0,
                "std_return": 0.0,
                "sharpe": None,
                "sortino": None,
                "max_drawdown": 0.0,
                "calmar": None,
                "profit_factor": None,
                "profit_factor_status": "insufficient_data",
            },
            "rolling": {
                "last_30": {"trades": 0, "confidence": "low", "low_confidence": True, "avg_return": 0.0, "win_rate": 0.0, "std_return": 0.0, "sharpe": None, "sortino": None, "max_drawdown": 0.0, "calmar": None, "profit_factor": None, "profit_factor_status": "insufficient_data"},
                "last_60": {"trades": 0, "confidence": "low", "low_confidence": True, "avg_return": 0.0, "win_rate": 0.0, "std_return": 0.0, "sharpe": None, "sortino": None, "max_drawdown": 0.0, "calmar": None, "profit_factor": None, "profit_factor_status": "insufficient_data"},
                "all_time": {"trades": 0, "confidence": "low", "low_confidence": True, "avg_return": 0.0, "win_rate": 0.0, "std_return": 0.0, "sharpe": None, "sortino": None, "max_drawdown": 0.0, "calmar": None, "profit_factor": None, "profit_factor_status": "insufficient_data"},
            },
            "trend": "stable",
            "suggested_improvements": [
                "No AI trades have been recorded yet. Start logging signals to evaluate live strategy quality."
            ],
            "auto_tuning_preview": {
                "current": _load_ai_tuning_config(),
                "proposed": _load_ai_tuning_config(),
                "adjustments": [],
                "changed": False,
            },
        }

    regime_history = _load_regime_history()
    enriched_rows: List[Dict[str, Any]] = []
    for raw, serialized_row in zip(rows, serialized):
        enriched = dict(serialized_row)
        enriched["recommendation_group"] = _normalize_recommendation_signal(raw.recommendation)
        enriched["sector"] = _get_portfolio_profile(raw.symbol).get("sector") or _sector_for_symbol(raw.symbol)
        regime_snapshot = _resolve_regime_snapshot_for_trade(raw.entry_time, regime_history)
        enriched["market_regime"] = regime_snapshot.get("regime")
        enriched["market_regime_confidence"] = regime_snapshot.get("confidence")
        enriched["market_regime_timestamp"] = regime_snapshot.get("timestamp")
        enriched["market_regime_momentum"] = regime_snapshot.get("momentum")
        enriched["market_regime_strength"] = regime_snapshot.get("strength")
        enriched["market_regime_volatility"] = regime_snapshot.get("volatility")
        enriched["market_regime_safe_haven"] = regime_snapshot.get("safe_haven")
        enriched_rows.append(enriched)

    signal_performance = _aggregate_trade_groups(enriched_rows, "recommendation_group")
    sector_performance = _aggregate_trade_groups(enriched_rows, "sector")
    regime_performance = _aggregate_trade_groups(enriched_rows, "market_regime")
    regime_signal_performance = _aggregate_regime_signal_performance(enriched_rows)
    regime_signal_insights = _build_regime_signal_insights(regime_signal_performance)
    overall_performance = _compute_trade_window_metrics(enriched_rows)
    rankings = _build_evaluation_rankings(signal_performance, regime_performance)

    best_performing_signals = signal_performance[:3]
    worst_signals = list(reversed(sorted(signal_performance, key=lambda item: (item["average_return"], item["win_rate"]))))[:3]

    suggestions: List[str] = []
    signal_map = {row["label"]: row for row in signal_performance}
    strong_buy = signal_map.get("STRONG BUY")
    buy = signal_map.get("BUY")
    strong_sell = signal_map.get("STRONG SELL")
    sell = signal_map.get("SELL")
    bear_regime = next((row for row in regime_performance if row["label"] == "bear"), None)
    bull_regime = next((row for row in regime_performance if row["label"] == "bull"), None)

    if strong_buy and buy and strong_buy["average_return"] < buy["average_return"]:
        suggestions.append("Strong Buy signals are underperforming Buy signals. Tighten Strong Buy thresholds or require stronger momentum confirmation.")
    if strong_sell and sell and strong_sell["average_return"] > sell["average_return"]:
        suggestions.append("Strong Sell signals are not outperforming regular Sell calls. Recalibrate bearish escalation logic before labeling a signal Strong Sell.")
    risk_off_regime = next((row for row in regime_performance if row["label"] == "Risk-Off"), None)
    risk_on_regime = next((row for row in regime_performance if row["label"] == "Risk-On"), None)
    if risk_off_regime and risk_off_regime["average_return"] < 0:
        suggestions.append("AI trades struggle in Risk-Off regimes. Consider reducing position size or requiring stronger confirmation during defensive markets.")
    if risk_on_regime and risk_off_regime and (risk_on_regime["average_return"] - risk_off_regime["average_return"]) > 5:
        suggestions.append("Performance is regime-sensitive. Add market regime as a sizing overlay so risk stays lower in weak markets.")
    if bear_regime and bear_regime["average_return"] < 0:
        suggestions.append("Legacy SPY bear-regime analysis still shows weaker performance. Compare it against the new market regime history for sizing decisions.")
    if bull_regime and bear_regime and (bull_regime["average_return"] - bear_regime["average_return"]) > 5:
        suggestions.append("Legacy bull/bear regime spread remains wide. Use the newer regime timeline to refine adaptive signal weighting.")
    if sector_performance:
        weakest_sector = min(sector_performance, key=lambda item: item["average_return"])
        suggestions.append(f"Weakest sector so far is {weakest_sector['label']}. Review sector-specific signal quality and consider stricter filters there.")
    suggestions.extend(regime_signal_insights.get("suggested_adaptations") or [])
    if not suggestions:
        suggestions = [
            "Signal performance is balanced. Continue collecting trades and review thresholds after a larger sample size.",
            "Monitor regime-specific hit rate to decide whether position sizing should adapt to bull vs bear conditions.",
        ]

    rolling_metrics = _build_rolling_trade_metrics(enriched_rows)
    auto_tuning_preview = _build_auto_tuning_payload(
        signal_performance=signal_performance,
        regime_performance=regime_performance,
        rolling_metrics=rolling_metrics,
    )

    return {
        "signal_performance": signal_performance,
        "best_performing_signals": best_performing_signals,
        "worst_signals": worst_signals,
        "sector_performance": sector_performance,
        "market_regime_performance": regime_performance,
        "regime_signal_performance": regime_signal_performance,
        "regime_insights": {
            "best_signal_per_regime": regime_signal_insights.get("best_signal_per_regime") or [],
            "worst_signal_per_regime": regime_signal_insights.get("worst_signal_per_regime") or [],
            "insights": regime_signal_insights.get("insights") or [],
        },
        "strategy_adaptation": regime_signal_insights.get("suggested_adaptations") or [],
        "rankings": rankings,
        "overall_performance": overall_performance,
        "rolling": rolling_metrics["rolling"],
        "trend": rolling_metrics["trend"],
        "suggested_improvements": list(dict.fromkeys(suggestions)),
        "auto_tuning_preview": auto_tuning_preview,
    }


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
            if p.purchase_date:
                try:
                    point_date = datetime.fromisoformat(date_key).date()
                    if point_date < p.purchase_date:
                        continue
                except Exception:
                    pass
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
        "SHOW", "TOP", "RISK", "RISKS", "NEWS", "MARKET", "MACRO", "SECTOR", "SECTORS", "STOCK",
        "STOCKS", "TODAY", "NOW", "BEST", "IS", "ARE", "WAS", "WERE", "AN",
        "HOW", "DO", "DOES", "DID", "CAN", "COULD", "WOULD", "SHOULD", "WILL",
        "COMPARE", "VERSUS", "BETTER", "THAN", "OVERALL", "TECHNOLOGY", "ENERGY",
        "FINANCIALS", "HEALTHCARE", "INDUSTRIALS", "STAPLES", "DISCRETIONARY",
        "XLK", "XLE", "XLF", "XLV", "XLI", "XLP", "XLY",
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
    last_symbols = [str(s).upper().strip() for s in (state.get("last_symbols") or []) if str(s).strip()]
    q = str(question or "").lower()
    if len(explicit) == 1 and last_symbol and explicit[0] != last_symbol:
        return [last_symbol, explicit[0]]

    if len(explicit) == 1 and last_symbols:
        other = next((s for s in last_symbols if s != explicit[0]), None)
        if other:
            return [explicit[0], other]

    if not explicit and len(last_symbols) >= 2 and any(term in q for term in ["compare them", "compare both", "them", "both", "สองตัว", "คู่นี้", "เปรียบเทียบคู่นี้"]):
        return last_symbols[:2]

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
    stock_recommendation_terms = [
        "low risk stock", "low-risk stock", "defensive stock", "defensive stocks",
        "stable stock", "stable stocks", "safe stock", "safe stocks", "dividend stock",
        "quality stock", "blue chip", "blue-chip", "recommend a low risk stock",
        "recommend low risk", "lower risk stock", "defensive names",
        "หุ้นเสี่ยงต่ำ", "หุ้นความเสี่ยงต่ำ", "หุ้นปลอดภัย", "หุ้น defensive",
        "หุ้นปันผล", "หุ้นอะไรเสี่ยงต่ำ", "หุ้นใหญ่เสี่ยงต่ำ",
    ]
    open_recommendation_terms = [
        "recommend a stock", "recommend stock", "recommend some stocks", "recommend stocks",
        "stock ideas", "give me stock ideas", "what stock should i buy", "what stocks should i buy",
        "best stocks now", "best stock now", "top stock ideas", "suggest a stock", "suggest stocks",
        "แนะนำหุ้น", "ช่วยแนะนำหุ้น", "มีหุ้นอะไรแนะนำ", "หุ้นน่าสนใจ", "หุ้นไหนดี", "หุ้นตัวไหนดี",
    ]
    trending_terms = [
        "trending today", "trending stocks", "what stocks are trending", "high volume stocks",
        "unusual movers", "top movers", "stocks moving today", "หุ้นเด่นวันนี้", "หุ้นที่กำลังมา",
        "หุ้นตัวไหนกำลังแรง", "หุ้นกำลังวิ่ง", "หุ้นเด่นวันนี้",
    ]
    market_scanner_terms = [
        "what stocks are trending today", "show trending stocks", "show top movers",
        "most active stocks", "high momentum stocks", "market scanner", "scan the market",
        "top gainers", "top volume stocks", "stocks moving now", "discover stocks",
        "หุ้นอะไรเด่นวันนี้", "สแกนตลาด", "หุ้นที่น่าสนใจวันนี้", "หุ้นที่กำลังเป็นกระแส",
        "หุ้นตัวไหนกำลังมาแรง", "หุ้นตัวไหนกำลังแรง", "หุ้นที่กำลังมาแรง", "หุ้นที่กำลังมา",
    ]
    global_sector_terms = [
        "sector momentum", "sector ranking", "sector rankings", "show sector momentum ranking",
        "show all sector rankings", "which sectors are strongest", "which sectors have strong momentum",
        "which sectors have the strongest momentum", "leading sectors", "top sectors", "sector leaderboard",
        "กลุ่มไหนแข็งแรง", "จัดอันดับ sector", "จัดอันดับกลุ่ม", "กลุ่มไหน momentum ดี",
        "sector ไหนแรง", "sector ไหนเด่น", "กลุ่มไหนแรง", "กลุ่มไหนเด่น", "จัดอันดับโมเมนตัมกลุ่ม",
    ]
    macro_terms = [
        "macro", "war", "iran", "middle east", "oil", "crude", "geopolitic", "geopolitical",
        "sanction", "conflict", "strait of hormuz", "tariff", "inflation", "rates", "fed",
        "yield", "treasury", "recession", "gdp", "jobs report", "สงคราม", "อิหร่าน",
        "น้ำมัน", "ภูมิรัฐศาสตร์", "เงินเฟ้อ", "ดอกเบี้ย",
    ]
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

    if any(t in q for t in stock_recommendation_terms):
        return "stock_recommendation"
    if any(t in q for t in open_recommendation_terms):
        return "open_recommendation"
    if any(t in q for t in market_scanner_terms):
        return "market_scanner"
    if any(t in q for t in trending_terms):
        return "trending_stock_discovery"
    if any(t in q for t in global_sector_terms):
        return "global_market_query"
    if any(t in q for t in macro_terms):
        return "macro_analysis"
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
    ref_terms = ["this sector", "that sector", "in this sector", "same sector", "same industry", "กลุ่มนี้", "เซกเตอร์นี้", "หมวดนี้", "กลุ่มเดียวกัน", "sector เดียวกัน"]
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
    if intent == "trending_stock_discovery":
        return "trending_stock_engine"
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
    sentiment_avg_raw = raw.get("sentiment_avg")
    sentiment_avg = safe_float(sentiment_avg_raw) if sentiment_avg_raw is not None else None
    sentiment_label = (
        "Bullish" if sentiment_avg is not None and sentiment_avg > 0.15
        else ("Bearish" if sentiment_avg is not None and sentiment_avg < -0.15 else ("Neutral" if sentiment_avg is not None else "Relevant data is not available"))
    )
    momentum_score_raw = signals.get("momentum_score")
    momentum_score = safe_float(momentum_score_raw) if momentum_score_raw is not None else None
    momentum_label = (
        "Weakening" if momentum_score is not None and momentum_score < 50
        else ("Moderate" if momentum_score is not None and momentum_score < 70 else ("Strong" if momentum_score is not None else "Relevant data is not available"))
    )
    technical_trend = str(analysis.get("technical_trend", "Neutral"))
    fear_greed_raw = market.get("market_score")
    fear_greed = safe_float(fear_greed_raw) if fear_greed_raw is not None else None
    fear_label = str(market.get("market_label") or "Relevant data is not available")
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

    short_term = (
        "High" if (momentum_score is not None and momentum_score < 45) or (fear_greed is not None and fear_greed < 30)
        else ("Medium" if (momentum_score is not None and momentum_score < 65) or (fear_greed is not None and fear_greed < 50) else "Low")
    )
    long_term = "Low" if sector in {"Technology", "Semiconductors"} else "Medium"
    confidence = int(max(55, min(90, analysis.get("confidence", 75))))

    answer = (
        f"Stock Risk Analysis: {symbol}\n\n"
        "Key Risks\n"
        + "\n".join([f"- {x}" for x in key_risks]) + "\n\n"
        "Market Signals\n"
        f"- {symbol} price trend: {technical_trend}\n"
        + (f"- Momentum: {momentum_label} ({momentum_score:.1f}/100)\n" if momentum_score is not None else "- Momentum: Relevant data is not available.\n")
        + (f"- Fear & Greed: {fear_greed:.0f} ({fear_label})\n" if fear_greed is not None else "- Fear & Greed: Relevant data is not available.\n")
        + (f"- News sentiment: {sentiment_label} ({sentiment_avg:+.2f})\n" if sentiment_avg is not None else "- News sentiment: Relevant data is not available.\n")
        + (f"- RSI: {safe_float(technical.get('rsi')):.2f}\n\n" if technical.get("rsi") is not None else "- RSI: Relevant data is not available.\n\n")
        + "Impact Assessment\n"
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
            "momentum_score": round(momentum_score, 1) if momentum_score is not None else None,
            "fear_greed_score": round(fear_greed, 1) if fear_greed is not None else None,
            "fear_greed_label": fear_label,
            "news_sentiment": round(sentiment_avg, 3) if sentiment_avg is not None else None,
            "rsi": round(safe_float(technical.get("rsi")), 2) if technical.get("rsi") is not None else None,
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
    fg_raw = market.get("market_score")
    fg = safe_float(fg_raw) if fg_raw is not None else None
    label = str(market.get("market_label") or "Relevant data is not available")
    top_sector = str((market.get("sector_momentum") or {}).get("sector") or "Relevant data is not available")
    top_momentum = str((market.get("sector_momentum") or {}).get("momentum") or "Relevant data is not available")
    short_term = "High" if fg is not None and fg < 30 else ("Medium" if fg is not None and fg < 55 else "Relevant data is not available")
    answer = (
        "Market Risk Analysis\n\n"
        "Key Risks\n"
        "- Liquidity and macro policy shocks can increase index-level drawdown risk.\n"
        "- Growth slowdown risk can pressure earnings revisions.\n"
        "- Risk-off regime can widen volatility and correlation.\n\n"
        "Market Signals\n"
        + (f"- Fear & Greed: {fg:.0f} ({label})\n" if fg is not None else "- Fear & Greed: Relevant data is not available.\n")
        + f"- Leading sector momentum: {top_sector} ({top_momentum})\n\n"
        + "Impact Assessment\n"
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
    etf_ret_raw = top_sector_data.get("return_3m_pct")
    etf_ret_3m = safe_float(etf_ret_raw) if etf_ret_raw is not None else None
    etf_mom_raw = top_sector_data.get("momentum_score")
    etf_mom = safe_float(etf_mom_raw) if etf_mom_raw is not None else None
    sentiment_raw = top_sector_data.get("news_sentiment")
    sentiment = safe_float(sentiment_raw) if sentiment_raw is not None else None
    sentiment_label = (
        "Bullish" if sentiment is not None and sentiment > 0.15
        else ("Bearish" if sentiment is not None and sentiment < -0.15 else ("Neutral" if sentiment is not None else "Relevant data is not available"))
    )
    fear_greed_raw = market.get("market_score")
    fear_greed = safe_float(fear_greed_raw) if fear_greed_raw is not None else None
    regime = str(market.get("market_label") or "Relevant data is not available")

    if (etf_mom is not None and etf_mom < 45) or (fear_greed is not None and fear_greed < 35):
        impact = "High"
    elif (etf_mom is not None and etf_mom < 60) or (fear_greed is not None and fear_greed < 50):
        impact = "Medium"
    else:
        impact = "Relevant data is not available" if etf_mom is None and fear_greed is None else "Low"

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
        + (f"- Fear & Greed regime: {regime} ({fear_greed:.0f})\n" if fear_greed is not None else "- Fear & Greed regime: Relevant data is not available.\n")
        + (f"- Sector ETF ({etf}) 3M return: {etf_ret_3m:+.2f}%\n" if etf_ret_3m is not None else f"- Sector ETF ({etf}) 3M return: Relevant data is not available.\n")
        + (f"- Sector news sentiment: {sentiment_label} ({sentiment:+.2f})\n\n" if sentiment is not None else "- Sector news sentiment: Relevant data is not available.\n\n")
        + "Market Signals\n"
        + (f"- {etf} momentum score: {etf_mom:.1f}/100\n" if etf_mom is not None else f"- {etf} momentum score: Relevant data is not available.\n")
        + f"- Market risk outlook: {market.get('risk_outlook', 'Medium')}\n\n"
        + "Impact Assessment\n"
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
            "fear_greed": round(fear_greed, 1) if fear_greed is not None else None,
            "sector_etf": etf,
            "sector_etf_return_3m_pct": round(etf_ret_3m, 2) if etf_ret_3m is not None else None,
            "sector_momentum_score": round(etf_mom, 1) if etf_mom is not None else None,
            "sector_news_sentiment": round(sentiment, 3) if sentiment is not None else None,
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
    raw_price = analysis.get("current_price")
    price = safe_float(raw_price) if raw_price is not None else None
    raw_price_change = analysis.get("price_change")
    price_change = safe_float(raw_price_change) if raw_price_change is not None else None
    momentum = str(analysis.get("momentum") or "Relevant data is not available")
    technical_trend = str(analysis.get("technical_trend") or "Relevant data is not available")
    sentiment = str(analysis.get("news_sentiment") or "Relevant data is not available")
    raw_fear_greed = market.get("market_score")
    fear_greed = safe_float(raw_fear_greed) if raw_fear_greed is not None else None
    market_label = str(market.get("market_label") or "Relevant data is not available")
    analyst_target = analysis.get("analyst_target")
    forecast = analysis.get("forecast_horizon", {})
    price_change_pct_raw = analysis.get("price_change_pct")
    price_change_pct = safe_float(price_change_pct_raw) if price_change_pct_raw is not None else None
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

    market_context_points = []
    if fear_greed is not None and market_label and market_label != "Relevant data is not available":
        market_context_points.append(
            f"The current market regime is {market_label.lower()} with Fear & Greed at {round(fear_greed, 1)}."
        )
    else:
        market_context_points.append("Relevant data is not available.")
    strongest_sector = str((market.get("sector_momentum") or {}).get("sector") or "").strip()
    strongest_sector_momentum = str((market.get("sector_momentum") or {}).get("momentum") or "").strip()
    if strongest_sector:
        market_context_points.append(
            f"Sector leadership currently points to {strongest_sector}"
            + (f" with {strongest_sector_momentum.lower()} momentum." if strongest_sector_momentum else ".")
        )

    technical_points = []
    technical_points.append(f"Technical trend: {technical_trend}")
    if analysis.get("indicators", {}).get("ma50") is not None and analysis.get("indicators", {}).get("ma200") is not None:
        ma50 = safe_float(analysis["indicators"]["ma50"])
        ma200 = safe_float(analysis["indicators"]["ma200"])
        ma_signal = "Above MA200" if ma50 > ma200 else "Below MA200"
        technical_points.append(f"Moving average signal: {ma_signal}")
    else:
        technical_points.append("Moving average signal: Relevant data is not available.")
    technical_points.append(f"Momentum: {momentum}")
    if analysis.get("indicators", {}).get("rsi") is not None:
        technical_points.append(f"RSI: {round(safe_float(analysis['indicators']['rsi']), 2)}")

    driver_points = list(analysis.get("drivers", [])) or []
    if not driver_points:
        if sector == "Semiconductors":
            driver_points = [
                "AI infrastructure demand remains an important industry tailwind.",
                "Semiconductor leadership is sensitive to capex and product-cycle momentum.",
            ]
        elif sector == "Technology":
            driver_points = [
                "Large-cap technology leadership is still influenced by earnings visibility and software/cloud demand.",
                "Product and platform scale continue to shape competitive positioning.",
            ]
        else:
            driver_points = [
                f"{sector} performance is being shaped by current sector-specific demand and sentiment conditions.",
            ]

    investment_interpretation = (
        f"Based on current technical and sentiment data, {company_name} ({ticker}) shows a {recommendation} setup."
        if recommendation and recommendation != "Relevant data is not available"
        else "Relevant data is not available."
    )

    return {
        "intent": intent,
        "answer_title": f"{company_name} ({ticker})",
        "overview": (
            f"{company_name} ({ticker}) is currently in a {recommendation} setup under a {market_label.lower()} market regime."
            if market_label and market_label != "Relevant data is not available"
            else f"{company_name} ({ticker}) is currently in a {recommendation} setup."
        ),
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
            "price": round(price, 2) if price is not None and price > 0 else None,
            "price_change": round(price_change, 2) if price_change is not None else None,
            "price_change_pct": round(price_change_pct, 2) if price_change_pct is not None else None,
        },
        "market_context": {
            "market_regime": market_label,
            "fear_greed_index": round(fear_greed, 1) if fear_greed is not None else None,
            "points": market_context_points[:3],
        },
        "technical_signals_section": {
            "trend": technical_trend,
            "momentum": momentum,
            "points": technical_points[:5],
        },
        "fundamental_drivers": {
            "sector": sector,
            "industry": industry,
            "points": driver_points[:4],
        },
        "risk_factors": {
            "points": risks[:4],
        },
        "investment_interpretation": {
            "recommendation": recommendation,
            "text": investment_interpretation,
            "confidence": int(analysis.get("confidence", 70)),
            "forecast_horizon": {
                "7d": round(safe_float(forecast.get("7d")), 2) if forecast.get("7d") is not None else None,
                "30d": round(safe_float(forecast.get("30d")), 2) if forecast.get("30d") is not None else None,
                "90d": round(safe_float(forecast.get("90d")), 2) if forecast.get("90d") is not None else None,
            },
        },
        "market_signals": {
            "technical_trend": technical_trend,
            "momentum": momentum,
            "news_sentiment": sentiment,
            "fear_greed_index": round(fear_greed, 1) if fear_greed is not None else None,
            "market_regime": market_label,
            "analyst_target": analyst_target if analyst_target not in ("", None) else None,
        },
        "investment_view": {
            "recommendation": recommendation,
            "confidence": int(analysis.get("confidence", 70)),
            "forecast_horizon": {
                "7d": round(safe_float(forecast.get("7d")), 2) if forecast.get("7d") is not None else None,
                "30d": round(safe_float(forecast.get("30d")), 2) if forecast.get("30d") is not None else None,
                "90d": round(safe_float(forecast.get("90d")), 2) if forecast.get("90d") is not None else None,
            },
        },
        "forecast_horizon": {
            "7d": round(safe_float(forecast.get("7d")), 2) if forecast.get("7d") is not None else None,
            "30d": round(safe_float(forecast.get("30d")), 2) if forecast.get("30d") is not None else None,
            "90d": round(safe_float(forecast.get("90d")), 2) if forecast.get("90d") is not None else None,
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
    history_text = " ".join([str(item or "").strip().lower() for item in (context.history or []) if str(item or "").strip()])
    last_intent = str(state.get("last_intent") or "").strip()
    last_symbol = str(state.get("last_symbol") or "").upper().strip()
    last_symbols = [str(s).upper().strip() for s in (state.get("last_symbols") or []) if str(s).strip()]
    picker_terms = ["top stocks", "top names", "stock picks", "momentum stocks", "leaders", "those names", "หุ้นเด่น", "รายชื่อหุ้น", "หุ้นโมเมนตัม"]
    sector_ref_terms = ["sector", "this sector", "that sector", "same sector", "same industry", "กลุ่มนี้", "เซกเตอร์นี้", "หมวดนี้", "กลุ่มเดียวกัน", "sector เดียวกัน"]
    why_terms = ["why", "ทำไม", "strong", "weak", "แข็ง", "อ่อน"]
    comparison_ref_terms = ["compare them", "compare both", "them", "both", "คู่นี้", "สองตัว", "เปรียบเทียบคู่นี้"]
    single_ref_terms = ["what about this one", "what about it", "that stock", "this stock", "ตัวนี้", "ตัวนั้น", "หุ้นตัวนี้", "หุ้นตัวนั้น"]
    macro_history_terms = ["war", "iran", "oil", "inflation", "yield", "rates", "fed", "สงคราม", "อิหร่าน", "น้ำมัน", "เงินเฟ้อ", "ดอกเบี้ย"]
    sector_target_terms = ["tech", "technology", "energy", "financial", "healthcare", "sector", "หุ้นเทค", "หุ้นเทคโนโลยี", "พลังงาน", "ธนาคาร", "สุขภาพ", "กลุ่ม"]
    if any(t in history_text for t in macro_history_terms) and any(t in q for t in sector_target_terms):
        return "macro_analysis"
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
    if not symbols and len(last_symbols) >= 2 and any(term in q for term in comparison_ref_terms):
        return "stock_comparison"
    if len(symbols) == 1:
        if last_symbol and last_symbol != symbols[0]:
            return "stock_comparison"
        return "single_stock_analysis"
    if not symbols and last_symbol and any(term in q for term in single_ref_terms):
        return "single_stock_analysis"
    if last_intent in {
        "single_stock_analysis",
        "stock_comparison",
        "macro_analysis",
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

    l_m_raw = (left.get("raw", {}) or {}).get("signals", {}).get("momentum_score")
    r_m_raw = (right.get("raw", {}) or {}).get("signals", {}).get("momentum_score")
    l_s_raw = (left.get("raw", {}) or {}).get("sentiment_avg")
    r_s_raw = (right.get("raw", {}) or {}).get("sentiment_avg")
    l_m = safe_float(l_m_raw) if l_m_raw is not None else None
    r_m = safe_float(r_m_raw) if r_m_raw is not None else None
    l_s = safe_float(l_s_raw) if l_s_raw is not None else None
    r_s = safe_float(r_s_raw) if r_s_raw is not None else None
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

    verdict_winner = winner(
        (l_m if l_m is not None else 0.0) + ((l_s if l_s is not None else 0.0) * 20),
        (r_m if r_m is not None else 0.0) + ((r_s if r_s is not None else 0.0) * 20),
        ls,
        rs,
    )
    style_fit = f"{ls} for stronger momentum; {rs} for comparatively balanced risk/reward." if verdict_winner == ls else f"{rs} for stronger momentum; {ls} for comparatively balanced risk/reward."
    quick_verdict = (
        f"{verdict_winner} currently has the stronger combined technical and sentiment setup."
        if verdict_winner != "Tie" else
        "Both names look broadly balanced on currently available signals."
    )

    return {
        "intent": "stock_comparison",
        "answer_title": f"{ls} vs {rs}",
        "direct_answer": quick_verdict,
        "stance": f"comparison_{verdict_winner.lower()}" if verdict_winner != "Tie" else "balanced",
        "summary_points": [
            f"Momentum: {ls} {(f'{l_m:.1f}/100' if l_m is not None else 'Relevant data is not available')} vs {rs} {(f'{r_m:.1f}/100' if r_m is not None else 'Relevant data is not available')}",
            f"News sentiment: {ls} {(f'{l_s:+.2f}' if l_s is not None else 'Relevant data is not available')} vs {rs} {(f'{r_s:+.2f}' if r_s is not None else 'Relevant data is not available')}",
            f"Risk level: {ls} {l_r} vs {rs} {r_r}",
            style_fit,
        ],
        "quick_verdict": quick_verdict,
        "comparison": {
            "left_symbol": ls,
            "right_symbol": rs,
            "categories": [
                {
                    "label": "Momentum",
                    "left_value": f"{l_m:.1f}/100" if l_m is not None else "Relevant data is not available",
                    "right_value": f"{r_m:.1f}/100" if r_m is not None else "Relevant data is not available",
                    "winner": winner(l_m or 0.0, r_m or 0.0, ls, rs),
                },
                {
                    "label": "News Sentiment",
                    "left_value": f"{l_s:+.2f}" if l_s is not None else "Relevant data is not available",
                    "right_value": f"{r_s:+.2f}" if r_s is not None else "Relevant data is not available",
                    "winner": winner(l_s or 0.0, r_s or 0.0, ls, rs),
                },
                {
                    "label": "Risk",
                    "left_value": l_r,
                    "right_value": r_r,
                    "winner": winner(l_rv, r_rv, ls, rs),
                },
            ],
        },
        "best_fit": {
            "stronger_now": verdict_winner,
            "style_fit": style_fit,
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
    q = (question or "").lower()
    state = context.chat_state or {}
    last_sector = str(state.get("last_sector") or "").strip()
    if last_sector and any(term in q for term in ["same sector", "same industry", "sector เดียวกัน", "กลุ่มเดียวกัน"]):
        return last_sector
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
    etfs = {
        "Technology": "XLK",
        "Energy": "XLE",
        "Healthcare": "XLV",
        "Financials": "XLF",
        "Industrials": "XLI",
        "Consumer Staples": "XLP",
        "Consumer Discretionary": "XLY",
    }

    def _return_from_history(history: List[Dict[str, Any]]) -> Optional[float]:
        if len(history) < 2:
            return None
        first = safe_float(history[0].get("close"))
        last = safe_float(history[-1].get("close"))
        if first <= 0 or last <= 0:
            return None
        return ((last - first) / first) * 100.0

    ranked = []
    for sector, etf in etfs.items():
        try:
            data_1m = get_stock_data(etf, "1m")
            data_3m = get_stock_data(etf, "3m")
            data_6m = get_stock_data(etf, "6m")
            ret_1m = _return_from_history(data_1m.get("history", []))
            ret_3m = _return_from_history(data_3m.get("history", []))
            ret_6m = _return_from_history(data_6m.get("history", []))
        except Exception:
            ret_1m = None
            ret_3m = None
            ret_6m = None
        if ret_1m is None or ret_3m is None:
            continue
        momentum_score = round((ret_1m * 0.40) + (ret_3m * 0.60), 2)
        ranked.append({
            "sector": sector,
            "etf": etf,
            "return_1m_pct": round(ret_1m, 2),
            "return_3m_pct": round(ret_3m, 2),
            "return_6m_pct": round(ret_6m, 2) if ret_6m is not None else None,
            "momentum_score": momentum_score,
        })

    ranked.sort(key=lambda x: x["momentum_score"], reverse=True)
    top = ranked[0] if ranked else {}
    momentum_label = "Unavailable"
    if ranked:
        momentum_label = "Strong" if safe_float(top.get("momentum_score")) >= 8 else ("Moderate" if safe_float(top.get("momentum_score")) >= 2 else "Weak")
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
    forecast = analysis.get("forecast_horizon") or {}
    sector_rank = _rank_sector_etfs()
    top_sector = sector_rank.get("top_sector")
    top_label = sector_rank.get("top_momentum_label") or "Relevant data is not available"
    news_sent = analysis.get("news_sentiment") or "Relevant data is not available"
    risks = list(analysis.get("risks", [])) or [
        "Macro rate uncertainty may increase volatility.",
        "Valuation sensitivity can pressure upside."
    ]

    market_summary = []
    if intent in {"market_overview", "sector_analysis", "sector_explanation"} or "sector" in question.lower() or "trending" in question.lower():
        if market.get("market_score") is not None and market.get("market_label"):
            market_summary.append(f"Fear & Greed: {market.get('market_score')} ({market.get('market_label')})")
        else:
            market_summary.append("Fear & Greed: Relevant data is not available.")
        if top_sector:
            market_summary.append(f"Strongest Sector: {top_sector} ({top_label})")
        else:
            market_summary.append("Strongest Sector: Relevant data is not available.")
        if analysis.get("ticker"):
            market_summary.append(f"Top AI Pick: {analysis.get('ticker')}")
        else:
            market_summary.append("Top AI Pick: Relevant data is not available.")
        if sector_rank.get("rankings"):
            top3 = sector_rank["rankings"][:3]
            market_summary.append("Sector ranking (3M): " + " | ".join(
                f"{x['sector']} {x['momentum_score']:.1f}" for x in top3
            ))
    else:
        ticker = analysis.get("ticker") or "This stock"
        if market.get("market_label") and market.get("market_score") is not None:
            market_summary.append(
                f"{ticker} in a {market.get('market_label')} regime with Fear & Greed at {market.get('market_score')}."
            )
        else:
            market_summary.append(f"{ticker}: broader market regime data is not available.")
        if top_sector:
            market_summary.append(f"Strongest Sector: {top_sector} ({top_label})")
        else:
            market_summary.append("Strongest Sector: Relevant data is not available.")

    tech = analysis.get("indicators", {}) or {}
    technical_signals = [
        f"Price Trend: {analysis.get('technical_trend') or 'Relevant data is not available'}",
        (
            f"RSI: {safe_float(tech.get('rsi')):.2f}"
            if tech.get("rsi") is not None else
            "RSI: Relevant data is not available"
        ),
        (
            f"MACD vs Signal: {safe_float(tech.get('macd')):.3f} / {safe_float(tech.get('macd_signal')):.3f}"
            if tech.get("macd") is not None and tech.get("macd_signal") is not None else
            "MACD vs Signal: Relevant data is not available"
        ),
        (
            f"MA50 vs MA200: {safe_float(tech.get('ma50')):.2f} / {safe_float(tech.get('ma200')):.2f}"
            if tech.get("ma50") is not None and tech.get("ma200") is not None else
            "MA50 vs MA200: Relevant data is not available"
        ),
        f"Momentum: {analysis.get('momentum') or 'Relevant data is not available'}",
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
        "signal": analysis.get("recommendation") or "Relevant data is not available",
        "reason": "Recommendation is derived from technical trend, news sentiment, momentum, and risk scoring.",
        "forecast_horizon": {
            "7d": round(safe_float(forecast.get("7d")), 2) if forecast.get("7d") is not None else None,
            "30d": round(safe_float(forecast.get("30d")), 2) if forecast.get("30d") is not None else None,
            "90d": round(safe_float(forecast.get("90d")), 2) if forecast.get("90d") is not None else None,
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
    cache_key = _stable_cache_key(
        "ai_market_context",
        {
            "sentiment": context.sentiment,
            "watchlist": normalize_symbol_list(context.watchlist or [])[:8],
            "recent": normalize_symbol_list(context.recent_searches or [])[:8],
        },
    )
    cached = _cache_get(generic_ttl_cache, cache_key, AI_MARKET_CONTEXT_CACHE_TTL)
    if cached:
        return cached

    market_score: Optional[float] = None
    market_label = "Unknown"
    market_meta: Dict[str, Any] = {"score": None, "sentiment": market_label}
    market_regime: Optional[str] = None
    regime_confidence: Optional[str] = None
    positioning: Dict[str, List[str]] = {
        "overweight": [],
        "neutral": [],
        "underweight": [],
    }
    suggested_etfs: List[str] = []
    try:
        if HAS_MARKET_SENTIMENT:
            sent = compute_market_sentiment(force_refresh=False)
            if isinstance(sent, dict):
                market_meta = sent
                raw_score = sent.get("sentiment_score")
                if raw_score is None:
                    raw_score = sent.get("score")
                market_score = float(raw_score) if raw_score is not None else None
                raw_label = sent.get("sentiment_label")
                if raw_label is None:
                    raw_label = sent.get("sentiment")
                market_label = str(raw_label or _sentiment_label(market_score) or "Unknown")
                market_regime = str(sent.get("regime") or "").strip() or None
                regime_confidence = str(sent.get("confidence") or "").strip().lower() or None
                positioning_payload = sent.get("positioning")
                if isinstance(positioning_payload, dict):
                    positioning = {
                        "overweight": list(positioning_payload.get("overweight") or []),
                        "neutral": list(positioning_payload.get("neutral") or []),
                        "underweight": list(positioning_payload.get("underweight") or []),
                    }
                suggested_etfs = list(sent.get("suggested_etfs") or [])
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
    payload = {
        "market_score": round(market_score, 1) if market_score is not None else None,
        "market_label": market_label,
        "market_meta": market_meta,
        "regime": market_regime,
        "confidence": regime_confidence,
        "positioning": positioning,
        "suggested_etfs": suggested_etfs,
        "sector_momentum": sector_momentum,
        "risk_outlook": risk_outlook,
    }
    return _cache_set(generic_ttl_cache, cache_key, payload)


def _build_trending_stock_response(context: AIAdvisorContext, market: Dict[str, Any]) -> Dict[str, Any]:
    cache_key = "market-scanner:top-movers"

    sector_trending_fallbacks: Dict[str, List[Dict[str, str]]] = {
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
    etf_decomposition: Dict[str, List[Dict[str, str]]] = {
        "XLE": sector_trending_fallbacks["Energy"],
        "XLU": sector_trending_fallbacks["Utilities"],
        "XLP": sector_trending_fallbacks["Consumer Staples"],
        "XLV": sector_trending_fallbacks["Healthcare"],
        "QQQ": sector_trending_fallbacks["Technology"],
        "SPY": [
            {"symbol": "MSFT", "name": "Microsoft", "role": "mega-cap leader"},
            {"symbol": "AAPL", "name": "Apple", "role": "quality large-cap"},
            {"symbol": "NVDA", "name": "NVIDIA", "role": "AI leader"},
        ],
    }

    def _avg_defined(values: List[Optional[float]]) -> Optional[float]:
        filtered = [safe_float(value) for value in values if value is not None]
        filtered = [value for value in filtered if value is not None]
        if not filtered:
            return None
        return sum(filtered) / len(filtered)

    def _score_linear(value: Optional[float], min_value: float, max_value: float) -> Optional[float]:
        if value is None or max_value <= min_value:
            return None
        normalized = ((safe_float(value) - min_value) / (max_value - min_value)) * 100.0
        return _clamp(normalized, 0.0, 100.0)

    def _normalize_trending_item(item: Dict[str, Any], provider: str) -> Optional[Dict[str, Any]]:
        symbol_value = str(item.get("symbol") or "").strip().upper()
        name_value = str(item.get("name") or "").strip()
        if not symbol_value:
            logger.warning(f"[trending] dropped item missing symbol provider={provider} raw={item}")
            return None
        if not name_value:
            logger.warning(f"[trending] dropped item missing name provider={provider} symbol={symbol_value} raw={item}")
            return None

        price_value = safe_float(item.get("price"))
        if price_value is None:
            logger.warning(f"[trending] dropped item missing price provider={provider} symbol={symbol_value}")
            return None

        daily_change = safe_float(item.get("daily_change"))
        if daily_change is None:
            daily_change = safe_float(item.get("change_pct"))
        return_1m = safe_float(item.get("return_1m"))
        if return_1m is None:
            return_1m = safe_float(item.get("month_return"))

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
        if item.get("volume") is not None:
            volume_value = safe_float(item.get("volume"))
            normalized["volume"] = int(volume_value) if volume_value is not None else None
        if item.get("trend_strength") is not None:
            normalized["trend_strength"] = round(safe_float(item.get("trend_strength")), 1)
        return normalized

    def _infer_trending_stocks(sector: str, regime: str, suggested_etfs: List[str]) -> List[Dict[str, Any]]:
        def _score_stock(symbol: str, sector_name: str, regime_name: str) -> Dict[str, Any]:
            sector_strength_map = {
                "Energy": 86, "Technology": 78, "Healthcare": 74, "Finance": 70,
                "Utilities": 72, "Consumer Staples": 71,
            }
            momentum_map = {
                "XOM": 78, "CVX": 72, "SLB": 76, "NVDA": 82, "MSFT": 68, "AMD": 74,
                "LLY": 70, "JNJ": 58, "UNH": 57, "JPM": 65, "GS": 62, "MS": 61,
                "NEE": 56, "DUK": 50, "SO": 49, "PG": 52, "KO": 48, "PEP": 47,
                "AAPL": 64,
            }
            risk_map = {
                "XOM": 70, "CVX": 76, "SLB": 54, "NVDA": 45, "MSFT": 68, "AMD": 50,
                "LLY": 66, "JNJ": 82, "UNH": 70, "JPM": 63, "GS": 57, "MS": 55,
                "NEE": 80, "DUK": 84, "SO": 84, "PG": 83, "KO": 86, "PEP": 84,
                "AAPL": 66,
            }
            regime_alignment_map = {
                "Risk-Off": {"Energy": 82, "Utilities": 84, "Consumer Staples": 84, "Healthcare": 76, "Finance": 55, "Technology": 34},
                "Late Risk-Off": {"Energy": 78, "Utilities": 80, "Consumer Staples": 79, "Healthcare": 74, "Finance": 58, "Technology": 42},
                "Risk-On": {"Energy": 64, "Utilities": 45, "Consumer Staples": 44, "Healthcare": 58, "Finance": 66, "Technology": 84},
                "Neutral": {"Energy": 72, "Utilities": 62, "Consumer Staples": 60, "Healthcare": 66, "Finance": 64, "Technology": 68},
            }
            sector_strength = sector_strength_map.get(sector_name, 68)
            momentum_proxy = momentum_map.get(symbol, 62)
            risk_score = risk_map.get(symbol, 60)
            regime_alignment = regime_alignment_map.get(regime_name, regime_alignment_map["Neutral"]).get(sector_name, 60)
            score = int(round(max(0.0, min(100.0, 0.40 * sector_strength + 0.20 * momentum_proxy + 0.20 * risk_score + 0.20 * regime_alignment))))
            tags: List[str] = []
            if regime_alignment >= 78 and risk_score >= 70:
                tags.append("High Conviction")
            if momentum_proxy >= 74:
                tags.append("Momentum Leader")
            if risk_score >= 80 and sector_name in {"Utilities", "Consumer Staples", "Healthcare"}:
                tags.append("Defensive Play")
            if not tags and regime_alignment >= 72:
                tags.append("Regime Aligned")
            return {"score": score, "tags": tags}

        picks = list(sector_trending_fallbacks.get(sector, []))
        if not picks:
            for etf in suggested_etfs:
                picks.extend(etf_decomposition.get(str(etf).upper(), []))
        if not picks:
            picks = list(sector_trending_fallbacks.get("Consumer Staples" if "risk-off" in regime.lower() else "Technology", []))

        inferred: List[Dict[str, Any]] = []
        seen = set()
        for item in picks:
            symbol = str(item.get("symbol") or "").upper()
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            score_payload = _score_stock(symbol, sector, regime)
            inferred.append({
                "symbol": symbol,
                "name": str(item.get("name") or symbol),
                "price": None,
                "daily_change": None,
                "return_1m": None,
                "reason": f"Estimated leader based on {sector} strength and {item.get('role') or 'sector leadership'}.",
                "inferred": True,
                "confidence_label": "Estimated leaders based on sector strength",
                "change_pct": None,
                "month_return": None,
                **score_payload,
            })
        inferred.sort(key=lambda row: row.get("score") or 0, reverse=True)
        return inferred[:5]

    def _fallback_response() -> Dict[str, Any]:
        top_sector = str((market.get("sector_momentum") or {}).get("sector") or "Energy")
        second_sector = "Utilities" if str(top_sector).lower() != "utilities" else "Consumer Staples"
        market_sentiment = str(market.get("market_label") or "Neutral")
        risk_outlook = str(market.get("risk_outlook") or "High")
        fear_greed = market.get("market_score")
        aligned_signal_count = sum(
            1
            for value in (market_sentiment, top_sector, risk_outlook)
            if value not in (None, "", "Unknown")
        )
        confidence_split = {
            "data_confidence": "low",
            "reasoning_confidence": "high" if aligned_signal_count >= 3 else ("medium" if aligned_signal_count >= 2 else "low"),
        }
        suggested_etfs = ["XLE", "XLU"] if "fear" in market_sentiment.lower() or risk_outlook.lower() == "high" else ["SPY", "QQQ"]
        inferred_items = _infer_trending_stocks(top_sector, market_sentiment, suggested_etfs)
        answer_lines = [
            "Trending Stocks Today (Estimated)",
            "- Estimated leaders based on sector strength",
            *[f"{idx}. {item['symbol']} (Score: {item.get('score', 'N/A')}) - {', '.join(item.get('tags') or ['Estimated'])}" for idx, item in enumerate(inferred_items, start=1)],
            "",
            "Alternative Insight",
            f"- Top sectors right now: {top_sector}",
            f"- Secondary strength: {second_sector}",
            "",
            "Interpretation",
            f"- Market is in {market_sentiment} conditions",
            "- Capital appears to be rotating into defensive leadership rather than broad risk-taking" if risk_outlook.lower() == "high" else "- Leadership is selective, so sector rotation matters more than single-stock momentum",
            "- Elevated volatility and weak breadth reduce confidence in chasing individual names",
            "",
            "Actionable View",
            f"- Focus on sector ETFs ({', '.join(suggested_etfs)})",
            "- Avoid chasing individual names without confirmation",
        ]
        schema = {
            "intent": "market_scanner",
            "answer_title": "Trending Stocks Today",
            "direct_answer": "Live scanner data is unavailable, so this fallback focuses on sector rotation and macro context instead.",
            "status": "degraded",
            "message": "Trending data inferred from sector strength",
            "items": inferred_items,
            "trending_stocks": inferred_items,
            "summary_points": [
                f"Top sector: {top_sector}",
                f"Secondary sector: {second_sector}",
                f"Risk outlook: {risk_outlook}",
            ],
            "market_context": {
                "market_sentiment": market_sentiment,
                "fear_greed_index": round(safe_float(fear_greed), 1) if fear_greed is not None else None,
                "top_sector": top_sector,
            },
            "alternative_insight": {
                "top_sectors": [top_sector, second_sector],
                "suggested_etfs": suggested_etfs,
            },
            "risks": [
                "Risk-off positioning is still present.",
                "Elevated volatility argues against aggressive stock chasing.",
                "Weak breadth favors sector-level confirmation.",
            ],
            "rationale": [
                f"{top_sector} is leading current sector rotation.",
                f"{market_sentiment} conditions and {risk_outlook.lower()} risk outlook support a defensive stance.",
                "Sector ETFs provide cleaner exposure when scanner confidence is low.",
            ],
            "actionable_view": f"Focus on sector ETFs such as {', '.join(suggested_etfs)} and avoid chasing individual names without confirmation.",
            "confidence": 0.55,
            **confidence_split,
            "confidence_split": confidence_split,
            "sources": ["Sector momentum", "Market sentiment", "Internal technical model"],
            "confidence_label": "Estimated leaders based on sector strength",
            "ranking_model": {
                "weights": {
                    "sector_strength": 0.40,
                    "momentum_proxy": 0.20,
                    "volatility_risk": 0.20,
                    "regime_alignment": 0.20,
                }
            },
        }
        return {
            "intent": "market_scanner",
            "answer": "\n".join(answer_lines),
            "confidence": 55,
            **confidence_split,
            "sources": ["Sector momentum", "Market sentiment", "Internal technical model"],
            "followups": [
                f"Show top stocks in {top_sector}",
                "Show sector momentum ranking",
                "What sectors are strongest now?",
            ],
            "answer_schema": schema,
            "summary": {
                "market_sentiment": market_sentiment,
                "fear_greed_score": round(safe_float(fear_greed), 1) if fear_greed is not None else None,
                "trending_sector": top_sector,
                "risk_outlook": risk_outlook,
                "signal": "Sector rotation fallback",
                "suggested_etfs": suggested_etfs,
                "estimated_leaders": [item["symbol"] for item in inferred_items],
                "estimated_scores": {item["symbol"]: item.get("score") for item in inferred_items},
            },
            "status": {
                "online": True,
                "message": "Scanner unavailable, using sector fallback",
                "live_data_ready": False,
                "market_context_loaded": True,
                "degraded": True,
            },
        }

    symbols = normalize_symbol_list((context.watchlist or []) + (context.recent_searches or []))
    if not symbols:
        symbols = _default_active_symbols(8)
    candidates: List[Dict[str, Any]] = []
    for symbol in symbols[:10]:
        try:
            stock = get_stock_data(symbol, "1m")
            history = stock.get("history", []) or []
            price = safe_float(stock.get("latest_price"))
            price_change = safe_float(stock.get("change"))
            volume = safe_float(stock.get("volume"))
            if price is None or price <= 0:
                continue
            closes = [safe_float(row.get("close")) for row in history if safe_float(row.get("close")) > 0]
            first_close = closes[0] if closes else None
            month_return = ((price - first_close) / first_close) * 100.0 if first_close and first_close > 0 else None
            move_score = abs(safe_float(price_change)) * 10.0 if price_change is not None else None
            ret_score = _score_linear(month_return, -12.0, 20.0) if month_return is not None else None
            volume_score = _score_linear(volume, 1_000_000, 120_000_000) if volume is not None else None
            trend_strength = _avg_defined([move_score, ret_score, volume_score])
            if trend_strength is None:
                continue
            candidates.append({
                "symbol": symbol,
                "name": str(stock.get("company_name") or symbol),
                "price": round(price, 2),
                "daily_change": round(price_change, 2) if price_change is not None else None,
                "volume": int(volume) if volume is not None else None,
                "return_1m": round(month_return, 2) if month_return is not None else None,
                "trend_strength": round(trend_strength, 1),
                "reason": (
                    "High trading volume and strong recent price action."
                    if (volume is not None and volume >= 20_000_000) and (price_change is not None and abs(price_change) >= 1.0)
                    else "Recent price action is standing out versus other actively tracked names."
                ),
            })
        except Exception:
            continue

    candidates.sort(key=lambda item: (item.get("trend_strength") or 0), reverse=True)
    top_names = [
        normalized for normalized in (
            _normalize_trending_item(item, "get_stock_data") for item in candidates[:5]
        ) if normalized is not None
    ]
    if top_names:
        _cache_set(generic_ttl_cache, cache_key, top_names)
    if not top_names:
        cached_top_names = _cache_get(generic_ttl_cache, cache_key, 24 * 60 * 60)
        if cached_top_names:
            top_names = [
                normalized for normalized in (
                    _normalize_trending_item(item, "cache") for item in cached_top_names
                ) if normalized is not None
            ]
        if top_names:
            top_sector = str((market.get("sector_momentum") or {}).get("sector") or "Relevant data is not available")
            market_sentiment = str(market.get("market_label") or "Relevant data is not available")
            fear_greed = market.get("market_score")
            answer_lines = [
                "Market Context",
                (
                    f"Current market sentiment is {market_sentiment} with Fear & Greed at {round(safe_float(fear_greed), 1)}."
                    if fear_greed is not None else
                    f"Current market sentiment is {market_sentiment}."
                ),
                "",
                "Trending Stocks Today (Cached)",
            ]
            for idx, item in enumerate(top_names, start=1):
                signal_bits = [f"Price ${item['price']:.2f}"]
                if item.get("change_pct") is not None:
                    signal_bits.append(f"Day change {item['change_pct']:+.2f}%")
                if item.get("month_return") is not None:
                    signal_bits.append(f"1M return {item['month_return']:+.2f}%")
                answer_lines.append(f"{idx}. {item['name']} ({item['symbol']})")
                answer_lines.append(f"   - {' | '.join(signal_bits)}")
                answer_lines.append(f"   - {item['reason']}")
            answer_lines.extend([
                "",
                "AI Interpretation",
                "Live scanner data is temporarily unavailable, so this list is based on the latest cached market scanner results.",
                "",
                "Investment Insight",
                "Use this cached list as a watchlist for follow-up analysis rather than as an execution signal.",
                "",
                "Sources",
                "Cached Market Scanner · Internal Technical Analysis Engine",
            ])
            schema = {
                "intent": "market_scanner",
                "answer_title": "Trending Stocks Today",
                "direct_answer": "Live scanner data is temporarily unavailable. Using cached top movers from the latest session.",
                "summary_points": [
                    f"{item['symbol']}: {item['reason']}" for item in top_names[:3]
                ],
                "market_context": {
                    "market_sentiment": market_sentiment,
                    "fear_greed_index": round(safe_float(fear_greed), 1) if fear_greed is not None else None,
                    "top_sector": top_sector,
                },
                "trending_stocks": top_names,
                "items": top_names,
                "risks": [
                    "Cached movers may no longer reflect current intraday leadership.",
                    "Trending names can reverse quickly if volume fades.",
                ],
                "confidence": 0.8,
                "sources": ["Cached Market Scanner", "Internal Technical Analysis Engine"],
            }
            return {
                "intent": "market_scanner",
                "answer": "\n".join(answer_lines),
                "confidence": 80,
                "sources": ["Cached Market Scanner", "Internal Technical Analysis Engine"],
                "followups": [
                    f"Compare {top_names[0]['symbol']} vs {top_names[1]['symbol']}" if len(top_names) >= 2 else "Compare NVDA vs AMD",
                    f"What are the downside risks for {top_names[0]['symbol']}?" if top_names else "What are the biggest market risks now?",
                    "Show sector momentum ranking",
                ],
                "answer_schema": schema,
                "summary": {
                    "market_sentiment": market_sentiment,
                    "fear_greed_score": round(safe_float(fear_greed), 1) if fear_greed is not None else None,
                    "top_ai_pick": top_names[0]["symbol"],
                    "top_ai_pick_confidence": 80,
                    "trending_sector": top_sector,
                    "sector_momentum": (market.get("sector_momentum") or {}).get("momentum") or "Relevant data is not available",
                    "risk_outlook": market.get("risk_outlook") or "Relevant data is not available",
                    "signal": "Cached trending stocks",
                    "forecast_horizon": {},
                },
                "status": {
                    "online": True,
                    "message": "Using cached market scanner",
                    "live_data_ready": False,
                    "market_context_loaded": True,
                    "degraded": True,
                },
            }
        return {
            "intent": "market_scanner",
            **_fallback_response(),
        }

    top_sector = str((market.get("sector_momentum") or {}).get("sector") or "Relevant data is not available")
    market_sentiment = str(market.get("market_label") or "Relevant data is not available")
    fear_greed = market.get("market_score")
    answer_lines = [
        "Market Context",
        (
            f"Current market sentiment is {market_sentiment} with Fear & Greed at {round(safe_float(fear_greed), 1)}."
            if fear_greed is not None else
            f"Current market sentiment is {market_sentiment}."
        ),
        "",
        "Key Signals",
    ]
    for idx, item in enumerate(top_names, start=1):
        signal_bits = [f"Price ${item['price']:.2f}"]
        if item.get("change_pct") is not None:
            signal_bits.append(f"Day change {item['change_pct']:+.2f}%")
        if item.get("month_return") is not None:
            signal_bits.append(f"1M return {item['month_return']:+.2f}%")
        answer_lines.append(f"{idx}. {item['name']} ({item['symbol']})")
        answer_lines.append(f"   - {' | '.join(signal_bits)}")
        answer_lines.append(f"   - {item['reason']}")
    answer_lines.extend([
        "",
        "AI Interpretation",
        f"These names are leading the current tracked universe based on unusual price action, recent return strength, and trading activity. Sector leadership currently points to {top_sector}.",
        "",
        "Investment Insight",
        "Use this list as a watchlist for follow-up analysis rather than as a direct buy list. Trending names can remain volatile in a risk-off market.",
        "",
        "Sources",
        "Finnhub · Internal Technical Analysis Engine",
    ])

    schema = {
        "intent": "market_scanner",
        "answer_title": "Trending Stocks Today",
        "direct_answer": "Here are the currently leading tracked stocks based on price action, activity, and short-term trend strength.",
        "summary_points": [
            f"{item['symbol']}: {item['reason']}" for item in top_names[:3]
        ],
        "market_context": {
            "market_sentiment": market_sentiment,
            "fear_greed_index": round(safe_float(fear_greed), 1) if fear_greed is not None else None,
            "top_sector": top_sector,
        },
        "trending_stocks": top_names,
        "items": top_names,
        "risks": [
            "Trending names can reverse quickly if volume fades.",
            "Risk-off markets can increase volatility in high-momentum stocks.",
        ],
        "confidence": 0.68,
        "sources": ["Finnhub", "Internal Technical Analysis Engine"],
    }
    return {
        "intent": "market_scanner",
        "answer": "\n".join(answer_lines),
        "confidence": 68,
        "sources": ["Finnhub", "Internal Technical Analysis Engine"],
        "followups": [
            f"Compare {top_names[0]['symbol']} vs {top_names[1]['symbol']}" if len(top_names) >= 2 else "Compare NVDA vs AMD",
            f"What are the downside risks for {top_names[0]['symbol']}?" if top_names else "What are the biggest market risks now?",
            f"Show top stocks in {top_sector}" if top_sector and top_sector != "Relevant data is not available" else "What sectors have strong momentum?",
        ],
        "answer_schema": schema,
        "summary": {
            "market_sentiment": market_sentiment,
            "fear_greed_score": round(safe_float(fear_greed), 1) if fear_greed is not None else None,
            "top_ai_pick": top_names[0]["symbol"],
            "top_ai_pick_confidence": 68,
            "trending_sector": top_sector,
            "sector_momentum": (market.get("sector_momentum") or {}).get("momentum") or "Relevant data is not available",
            "risk_outlook": market.get("risk_outlook") or "Relevant data is not available",
            "signal": "Trending stocks",
            "forecast_horizon": {},
        },
        "data_validation": {
            "price_data": True,
            "news_data": False,
            "technical_data": True,
        },
        "status": {
            "online": True,
            "message": "Connected",
            "live_data_ready": True,
            "market_context_loaded": True,
        },
        "charts": {
            "price": _build_price_chart(top_names[0]["symbol"]),
            "sentiment": _build_sentiment_chart(top_names[0]["symbol"]),
        },
    }


def _build_legacy_stock_recommendation_response(
    market: Dict[str, Any],
    intent_category: str,
    analysis_engine: str,
) -> Dict[str, Any]:
    fear_greed = safe_float(market.get("market_score")) if market.get("market_score") is not None else None
    market_label = str(market.get("market_label") or "Unknown")
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
            "risk_note": "Can underperform when investors rotate aggressively into higher-beta growth names.",
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
            "risk_note": "Healthcare regulation and litigation can still create company-specific event risk.",
        },
    ]
    direct_answer = "Here are 3 lower-risk stock ideas: Coca-Cola (KO), Procter & Gamble (PG), and Johnson & Johnson (JNJ)."
    answer = (
        "Market Context\n"
        + (
            f"Fear & Greed Index: {fear_greed:.1f} ({market_label}).\n\n"
            if fear_greed is not None else
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
        + "Low-risk does not mean no risk. These stocks may underperform in strong bull markets or during aggressive rotation into cyclical growth leaders.\n\n"
        + "Conclusion\n"
        + "For a lower-risk starting list, focus on large-cap defensive names in Consumer Staples and Healthcare, then verify valuation and trend before acting."
    )
    return {
        "intent": "stock_recommendation",
        "intent_category": intent_category,
        "analysis_type": "stock_recommendation",
        "analysis_engine": analysis_engine,
        "answer": answer,
        "confidence": 76,
        "sources": ["Historical Market Behavior", "Sector Characteristics", "Risk Profile Model"],
        "followups": [
            "Which of these has the strongest dividend profile?",
            "Compare KO vs PG",
            "Show lower-risk healthcare stocks",
        ],
        "answer_schema": {
            "intent": "stock_recommendation",
            "answer_title": "Low-Risk Stock Ideas",
            "direct_answer": direct_answer,
            "recommended_stocks": ideas,
            "risk_factors": {
                "points": [
                    "Low-risk does not mean no risk.",
                    "Defensive names can lag in strong risk-on rallies.",
                    "Rates, regulation, and margin pressure can still affect defensive sectors.",
                ],
            },
            "source_tags": ["Historical Market Behavior", "Sector Characteristics", "Risk Profile Model"],
        },
        "status": {
            "online": True,
            "message": "Connected",
            "live_data_ready": False,
            "market_context_loaded": True,
        },
    }


def _build_legacy_open_recommendation_response(
    market: Dict[str, Any],
    intent_category: str,
    analysis_engine: str,
) -> Dict[str, Any]:
    fear_greed = safe_float(market.get("market_score")) if market.get("market_score") is not None else None
    market_label = str(market.get("market_label") or "Unknown")
    leading_sector = str(market.get("leading_sector") or "Data unavailable for this signal.")
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
    direct_answer = "Here are 3 strong default stock ideas: Apple (AAPL), Microsoft (MSFT), and NVIDIA (NVDA)."
    answer = (
        "Market Context\n"
        + (
            f"Fear & Greed Index: {fear_greed:.1f} ({market_label}).\n"
            if fear_greed is not None else
            "Fear & Greed Index: Data unavailable for this signal.\n"
        )
        + f"Current leading sector: {leading_sector}\n\n"
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
        + "Conclusion\n"
        + "For a broad default recommendation, AAPL and MSFT fit high-quality core holdings, while NVDA adds stronger growth exposure with higher volatility."
    )
    return {
        "intent": "open_recommendation",
        "intent_category": intent_category,
        "analysis_type": "open_recommendation",
        "analysis_engine": analysis_engine,
        "answer": answer,
        "confidence": 74,
        "sources": ["Historical Market Behavior", "Quality Factor Heuristics", "Sector Leadership Context"],
        "followups": [
            "Do you prefer low-risk, growth, or dividend stocks?",
            "Compare AAPL vs MSFT",
            "Show lower-risk stock ideas instead",
        ],
        "answer_schema": {
            "intent": "open_recommendation",
            "answer_title": "Default Stock Ideas",
            "direct_answer": direct_answer,
            "recommended_stocks": ideas,
            "risk_factors": {
                "points": [
                    "Open-ended recommendations are a starting point, not a personalized allocation.",
                    "NVDA carries materially higher volatility than AAPL or MSFT.",
                    "Even large-cap leaders can underperform during valuation resets or macro shocks.",
                ],
            },
            "source_tags": ["Historical Market Behavior", "Quality Factor Heuristics", "Sector Leadership Context"],
        },
        "status": {
            "online": True,
            "message": "Connected",
            "live_data_ready": False,
            "market_context_loaded": True,
        },
    }


def _build_legacy_global_market_query_response(
    market: Dict[str, Any],
    intent_category: str,
    analysis_engine: str,
) -> Dict[str, Any]:
    sector_rank = _rank_sector_etfs()
    rankings = sector_rank.get("rankings", [])
    fear_greed = safe_float(market.get("market_score")) if market.get("market_score") is not None else None
    market_label = str(market.get("market_label") or "Unknown")
    if not rankings:
        return {
            "intent": "global_market_query",
            "intent_category": intent_category,
            "analysis_type": "sector_ranking",
            "analysis_engine": analysis_engine,
            "answer": "Sector momentum ranking is temporarily unavailable because the ETF history set is incomplete.",
            "confidence": 0,
            "sources": ["Sector ETF Model"],
            "answer_schema": {
                "intent": "global_market_query",
                "answer_title": "Sector Momentum Ranking",
                "direct_answer": "Sector momentum ranking is temporarily unavailable because the ETF history set is incomplete.",
                "source_tags": ["Sector ETF Model"],
            },
            "status": {
                "online": True,
                "message": "Connected",
                "live_data_ready": False,
                "market_context_loaded": True,
            },
        }
    ranking_lines = [
        f"{idx + 1}. {row.get('sector')} ({row.get('etf')}): "
        f"1M {safe_float(row.get('return_1m_pct')):+.2f}% | "
        f"3M {safe_float(row.get('return_3m_pct')):+.2f}% | "
        + (
            f"6M {safe_float(row.get('return_6m_pct')):+.2f}% | "
            if row.get("return_6m_pct") is not None else
            "6M Data unavailable | "
        )
        + f"Momentum {safe_float(row.get('momentum_score')):+.2f}%"
        for idx, row in enumerate(rankings)
    ]
    top = rankings[0]
    second = rankings[1] if len(rankings) > 1 else None
    third = rankings[2] if len(rankings) > 2 else None
    decision = _sector_strength_label(
        rank=1,
        momentum=_safe_float(top.get("momentum_score")),
        fear_greed=fear_greed,
    )
    answer = (
        "Sector Ranking (Momentum)\n"
        + "\n".join(ranking_lines)
        + "\n\nInterpretation\n"
        + f"{top.get('sector')} currently leads the sector ranking with a momentum score of {safe_float(top.get('momentum_score')):+.2f}%."
        + (
            f" It is outperforming {second.get('sector')} ({safe_float(second.get('momentum_score')):+.2f}%)"
            if second else ""
        )
        + (
            f" and {third.get('sector')} ({safe_float(third.get('momentum_score')):+.2f}%)."
            if third else "."
        )
        + "\n\nRisk Overlay\n"
        + (
            f"Market sentiment is {market_label} with Fear & Greed at {fear_greed:.1f}, so positioning should respect macro volatility."
            if fear_greed is not None else
            f"Market sentiment is {market_label}, so ranking should be read with normal risk controls."
        )
        + f"\n\nFinal Decision\n{top.get('sector')} is the current leader, with a decision label of {decision}."
    )
    return {
        "intent": "global_market_query",
        "intent_category": intent_category,
        "analysis_type": "sector_ranking",
        "analysis_engine": analysis_engine,
        "answer": answer,
        "confidence": 74,
        "sources": ["Sector ETF Model", "Market Sentiment Model"],
        "followups": [
            f"Compare {top.get('sector')} vs {second.get('sector')}" if second else "Compare Technology vs Energy",
            f"Show top momentum stocks in {top.get('sector')}",
            "What risks could weaken this sector leader?",
        ],
        "answer_schema": {
            "intent": "global_market_query",
            "answer_title": "Sector Momentum Ranking",
            "overview": f"{top.get('sector')} currently leads the sector ranking with a momentum score of {safe_float(top.get('momentum_score')):+.2f}%.",
            "rationale": [
                f"{top.get('sector')} ranks first because its blended 1M and 3M return profile is strongest in the tracked sector ETF universe.",
                (
                    f"It is ahead of {second.get('sector')} and {third.get('sector')} on the same momentum formula."
                    if second and third else
                    "The ranking reflects the strongest confirmed sector momentum in the available ETF universe."
                ),
                (
                    f"Market sentiment is {market_label} with Fear & Greed at {fear_greed:.1f}."
                    if fear_greed is not None else
                    f"Market sentiment is {market_label}, so ranking should still be sized with standard risk controls."
                ),
            ],
            "summary_points": [
                f"{top.get('sector')} ranks first because its blended 1M and 3M return profile is strongest in the tracked sector ETF universe.",
                (
                    f"It is ahead of {second.get('sector')} and {third.get('sector')} on the same momentum formula."
                    if second and third else
                    "The ranking reflects the strongest confirmed sector momentum in the available ETF universe."
                ),
                (
                    f"Market sentiment is {market_label} with Fear & Greed at {fear_greed:.1f}."
                    if fear_greed is not None else
                    f"Market sentiment is {market_label}, so ranking should still be sized with standard risk controls."
                ),
            ],
            "risks": [
                "Sector leadership can reverse quickly when macro expectations shift.",
                "High-ranking sectors often see sharper pullbacks when momentum fades.",
                "Broader market risk can still dominate sector-specific strength.",
            ],
            "direct_answer": f"{top.get('sector')} currently leads the sector ranking with a momentum score of {safe_float(top.get('momentum_score')):+.2f}%.",
            "actionable_view": f"Overweight {top.get('sector')} selectively, stay Neutral defensives, and Underweight weaker laggards until leadership changes.",
            "sector_rankings": rankings,
            "market_context": {
                "market_regime": market_label,
                "fear_greed_index": fear_greed,
            },
            "risk_factors": {
                "points": [
                    f"Macro regime is {market_label}.",
                    "Sector leadership can reverse quickly if market breadth changes.",
                ],
            },
            "source_tags": ["Sector ETF Model", "Market Sentiment Model"],
        },
        "status": {
            "online": True,
            "message": "Connected",
            "live_data_ready": True,
            "market_context_loaded": True,
        },
    }


def _build_legacy_macro_response(
    question: str,
    market: Dict[str, Any],
    intent_category: str,
    analysis_engine: str,
) -> Dict[str, Any]:
    q = (question or "").lower()
    is_thai = any("\u0E00" <= char <= "\u0E7F" for char in str(question or ""))
    fear_greed = safe_float(market.get("market_score")) if market.get("market_score") is not None else None
    market_label = str(market.get("market_label") or "Unknown")
    sector_rank = _rank_sector_etfs()
    top_sector = sector_rank.get("top_sector") or "Energy"
    rankings = sector_rank.get("rankings") or []
    top_three = rankings[:3]
    is_energy_shock = any(
        term in q for term in [
            "iran", "war", "middle east", "oil", "crude", "geopolitic",
            "geopolitical", "sanction", "conflict", "strait of hormuz",
        ]
    )
    if is_energy_shock:
        direct_effects = [
            "Oil prices usually rise first because markets price in supply disruption risk.",
            "US equity volatility often increases as investors shift toward safe-haven assets and reduce cyclical exposure.",
        ]
        indirect_effects = [
            "Higher energy prices can push inflation expectations upward and pressure rate-sensitive growth stocks.",
            "Transport, airlines, industrials, and discretionary names can face margin pressure if fuel costs rise.",
        ]
        sector_effects = [
            "Energy usually benefits first because higher crude prices can improve revenue expectations.",
            "Defense and some commodity-linked industries may also hold up better than the broad market.",
            "Fuel-sensitive sectors usually face more pressure.",
        ]
        risk_scenarios = [
            "Contained conflict: short-lived volatility spike with Energy outperforming.",
            "Oil shock scenario: broader inflation pressure and weaker consumer sectors.",
            "Escalation scenario: wider risk-off behavior across global equities.",
        ]
        direct_answer = "A potential Iran-related conflict would usually affect the US stock market first through oil, inflation expectations, and a broader risk-off reaction."
        conclusion = "Positioning should lean overweight Energy and selective defense exposure, while remaining underweight airlines, fuel-sensitive consumer names, and duration-sensitive growth until the oil and volatility path stabilizes."
        if is_thai:
            direct_effects = [
                "แรงกระแทกแรกมักเริ่มที่ราคาน้ำมัน เพราะตลาดจะรีบสะท้อนความเสี่ยงด้านอุปทานและการขนส่ง",
                "ความผันผวนของหุ้นสหรัฐมักสูงขึ้น เพราะเงินทุนจะไหลเข้าสินทรัพย์ปลอดภัยและลดน้ำหนักหุ้นวัฏจักร",
            ]
            indirect_effects = [
                "ราคาน้ำมันที่สูงขึ้นมักดันคาดการณ์เงินเฟ้อขึ้น และทำให้หุ้น Growth ที่ไวต่อดอกเบี้ยถูกกดดันมากขึ้น",
                "ต้นทุนเชื้อเพลิงที่สูงขึ้นมักบีบ margin ของสายการบิน ขนส่ง อุตสาหกรรม และค้าปลีกบางส่วน",
            ]
            sector_effects = [
                "กลุ่ม Energy มักได้ประโยชน์ก่อน เพราะรายได้มีแนวโน้มดีขึ้นตามราคาน้ำมัน",
                "กลุ่ม Defense และ commodity-linked บางส่วนมักยืนได้ดีกว่าตลาด",
                "กลุ่มที่ใช้พลังงานสูงหรืออิงการบริโภคมักถูกกดดันมากกว่า",
            ]
            risk_scenarios = [
                "กรณีจำกัดวง: ความผันผวนพุ่งช่วงสั้น และ Energy มีโอกาส outperform",
                "กรณีน้ำมันช็อก: เงินเฟ้อสูงขึ้น กดดันผู้บริโภคและเงื่อนไขการเงิน",
                "กรณียกระดับ: ตลาดเสี่ยงทั่วโลกอาจเข้าสู่โหมด risk-off ชัดเจน",
            ]
            direct_answer = "ความขัดแย้งอิหร่านมักส่งผลต่อตลาดหุ้นสหรัฐผ่านราคาน้ำมัน เงินเฟ้อคาดการณ์ และแรงขายสินทรัพย์เสี่ยงก่อน"
            conclusion = "เชิงกลยุทธ์ควรให้น้ำหนักมากกว่าตลาดใน Energy แบบเลือกตัว และคงมุมมองระวังต่อ Airlines, Consumer Discretionary และหุ้น Growth ที่ไวต่อดอกเบี้ย"
    else:
        direct_effects = [
            "Macro shocks usually affect asset prices first through growth expectations, inflation expectations, and policy-rate expectations.",
            "The initial reaction is often strongest in rate-sensitive sectors and high-beta equities.",
        ]
        indirect_effects = [
            "Changes in yields, credit conditions, and sector rotation can reshape equity leadership even when headline index moves are moderate.",
            "Macro uncertainty can compress valuation multiples before it clearly changes earnings expectations.",
        ]
        sector_effects = [
            f"Current sector leadership still matters: {top_sector} is leading in the latest sector ranking set.",
            "Defensive sectors usually hold up better when macro uncertainty rises.",
        ]
        risk_scenarios = [
            "Soft-landing scenario: leadership broadens and risk appetite recovers.",
            "Sticky inflation scenario: rate-sensitive growth remains under pressure.",
            "Growth scare scenario: defensives outperform while cyclical leadership fades.",
        ]
        direct_answer = "Macro developments affect US equities mainly through growth, inflation, rates, and sector rotation rather than through a single one-step market response."
        conclusion = f"Positioning should stay aligned with current sector leadership, with a neutral-to-overweight stance on {top_sector} and tighter risk controls on rate-sensitive or high-beta laggards."
        if is_thai:
            direct_effects = [
                "แรงกระแทกทางมหภาคมักส่งผลต่อราคาสินทรัพย์ผ่านคาดการณ์การเติบโต เงินเฟ้อ และดอกเบี้ยก่อน",
                "แรงตอบสนองระยะแรกมักเห็นชัดในหุ้นที่ไวต่อดอกเบี้ยและหุ้น beta สูง",
            ]
            indirect_effects = [
                "การเปลี่ยนแปลงของ bond yield และ credit conditions สามารถเปลี่ยนผู้นำตลาดได้ แม้ดัชนีหลักจะยังไม่ขยับมาก",
                "ความไม่แน่นอนทางมหภาคสามารถกด valuation ได้ก่อนที่ประมาณการกำไรจะถูกปรับลง",
            ]
            sector_effects = [
                f"ต้องดู sector leadership ปัจจุบันควบคู่กันไป โดยตอนนี้ {top_sector} ยังเป็นกลุ่มนำ",
                "กลุ่ม Defensive มักยืนได้ดีกว่าเมื่อความไม่แน่นอนทางมหภาคเพิ่มขึ้น",
            ]
            risk_scenarios = [
                "Soft landing: ความเชื่อมั่นฟื้นและผู้นำตลาดกระจายกว้างขึ้น",
                "Sticky inflation: หุ้น Growth ที่ไวต่อดอกเบี้ยยังถูกกดดันต่อ",
                "Growth scare: กลุ่ม Defensive มักชนะกลุ่มวัฏจักร",
            ]
            direct_answer = "ปัจจัยมหภาคมักกระทบตลาดหุ้นผ่านการเติบโต เงินเฟ้อ ดอกเบี้ย และการหมุนของ sector มากกว่าผ่าน headline เพียงอย่างเดียว"
            conclusion = f"เชิงกลยุทธ์ควรรักษามุมมองตาม sector leadership ปัจจุบัน โดยให้น้ำหนัก Neutral ถึง Overweight ใน {top_sector} และคุมความเสี่ยงในกลุ่มที่ไวต่อดอกเบี้ย"

    overview_line = (
        (
            f"ตลาดอยู่ในโหมด {market_label} • กลุ่มเด่น {top_sector} • ความเสี่ยงสูงจากแรงส่งด้านน้ำมันและเงินเฟ้อ"
            if is_energy_shock else
            f"ภาวะตลาด {market_label} • กลุ่มนำ {top_sector} • ความเสี่ยงขึ้นกับทิศทางดอกเบี้ยและการหมุนของ sector"
        )
        if is_thai else
        (
            f"Market sentiment is {market_label}; Energy is the key sector, and risk is elevated because oil, inflation, and rates are moving in the same direction."
            if is_energy_shock else
            f"Market sentiment is {market_label}; {top_sector} remains the leading sector, while rate direction still drives overall risk."
        )
    )
    key_drivers = (
        [
            "ราคาน้ำมันมักขยับก่อน เพราะตลาดกังวลความเสี่ยงด้านอุปทาน",
            "น้ำมันที่สูงขึ้นมักยกคาดการณ์เงินเฟ้อขึ้นตาม",
            "เงินเฟ้อที่สูงขึ้นเพิ่มโอกาสที่ดอกเบี้ยจะอยู่สูงนานขึ้น",
            "ดอกเบี้ยสูงและภาวะ risk-off ทำให้เงินทุนหมุนจาก Growth ไปยัง Energy และ Defensive",
        ]
        if is_thai and is_energy_shock else
        [
            "ปัจจัยมหภาคเปลี่ยนคาดการณ์การเติบโตและเงินเฟ้อพร้อมกัน",
            "เส้นทางดอกเบี้ยเป็นตัวกำหนด valuation ของหุ้น Growth เทียบกับ Defensive",
            "การหมุนของ sector เป็นสัญญาณสำคัญกว่าการมอง headline index เพียงอย่างเดียว",
            f"{top_sector} ยังนำอยู่ใน ranking ล่าสุด จึงยังเป็นแกนหลักของการจัดพอร์ต",
        ]
        if is_thai else
        [
            "Oil tends to move first as markets price supply disruption risk.",
            "Higher oil feeds into inflation expectations.",
            "Higher inflation expectations keep rate expectations tighter for longer.",
            "That rate and risk-off mix drives sector rotation away from growth and toward Energy and defensives.",
        ]
        if is_energy_shock else
        [
            "Macro shocks first reset growth and inflation expectations.",
            "Rate expectations then reprice equity valuations, especially in growth.",
            "Sector rotation becomes the clearest market expression of the macro regime.",
            f"{top_sector} still leads the latest ranking, so it remains the main relative-strength reference point.",
        ]
    )
    ui_risks = (
        [
            "margin ของกลุ่มที่ใช้พลังงานสูงอาจถูกกดดัน",
            "หุ้น Growth ที่ไวต่อดอกเบี้ยมีโอกาส underperform",
            "ความผันผวนของตลาดโลกอาจเร่งขึ้นหากเหตุการณ์ยืดเยื้อ",
            "sector leadership อาจกลับทิศเร็วถ้าราคาน้ำมันย่อตัวแรง",
        ]
        if is_thai and is_energy_shock else
        [
            "valuation ของหุ้น Growth ยังเสี่ยงต่อแรงกดดันจาก bond yield",
            "ตลาดอาจแกว่งแรงหากข้อมูลเงินเฟ้อหรือเศรษฐกิจออกมาผิดคาด",
            "การหมุนของ sector อาจเปลี่ยนเร็วในช่วงที่ macro regime ไม่ชัดเจน",
            "หุ้นวัฏจักรยังเสี่ยงหากการเติบโตอ่อนกว่าที่ตลาดคาด",
        ]
        if is_thai else
        [
            "Margin compression can hit fuel-sensitive sectors quickly.",
            "Growth stocks remain vulnerable to higher-for-longer rates.",
            "Global equity volatility can spike if the conflict broadens.",
            "Sector leadership can reverse quickly if oil retraces sharply.",
        ]
        if is_energy_shock else
        [
            "Growth valuations remain sensitive to bond-yield moves.",
            "Equity volatility can rise if inflation or macro data surprise to the upside.",
            "Sector leadership can rotate quickly when the macro regime shifts.",
            "Cyclicals remain exposed if growth expectations deteriorate.",
        ]
    )
    actionable_view = (
        "Overweight: Energy | Neutral: Defensive | Underweight: Growth / Consumer Discretionary"
        if is_energy_shock else
        f"Overweight: {top_sector} | Neutral: Defensive | Underweight: Rate-sensitive Growth"
    )

    ranking_lines = [
        f"{idx + 1}. {row.get('sector')} ({row.get('etf')}): "
        f"1M {safe_float(row.get('return_1m_pct')):+.2f}% | "
        f"3M {safe_float(row.get('return_3m_pct')):+.2f}% | "
        + (
            f"6M {safe_float(row.get('return_6m_pct')):+.2f}% | "
            if row.get("return_6m_pct") is not None else "6M not fully confirmed | "
        )
        + f"Momentum {safe_float(row.get('momentum_score')):+.2f}%"
        for idx, row in enumerate(top_three)
    ]
    if not ranking_lines:
        ranking_lines = (
            [
                "1. Energy (XLE): market usually prices geopolitical supply risk through oil first.",
                "2. Defense-linked cyclicals: relative resilience often improves in risk-off macro regimes.",
                "3. Airlines / consumer discretionary: typically more exposed to fuel-cost and demand pressure.",
            ]
            if not is_thai else
            [
                "1. Energy (XLE): ตลาดมักสะท้อนความเสี่ยงด้านอุปทานผ่านราคาน้ำมันก่อน",
                "2. กลุ่มที่เชื่อมกับ defense: มักยืนได้ดีกว่าในภาวะ risk-off",
                "3. Airlines / Consumer Discretionary: มักถูกกดดันจากต้นทุนพลังงานและอุปสงค์",
            ]
        )

    answer = (
        (
            "ภาพรวมตลาด\n"
            + (
                f"- Fear & Greed Index: {fear_greed:.1f} ({market_label})\n"
                if fear_greed is not None else
                f"- ภาวะตลาดปัจจุบัน: {market_label}\n"
            )
            + "- สายส่งหลักของเหตุการณ์นี้คือ น้ำมัน → เงินเฟ้อ → ดอกเบี้ย → การหมุนของ sector → ตลาดหุ้น\n\n"
            + "กลไกการส่งผ่าน (Macro Transmission)\n"
            + (
                "- น้ำมันสูงขึ้น → ตลาดยกคาดการณ์เงินเฟ้อขึ้น\n- เงินเฟ้อสูงขึ้น → ตลาดเริ่มประเมินว่าดอกเบี้ยอาจอยู่สูงนานขึ้น\n- ดอกเบี้ยสูงนานขึ้น → valuation ของหุ้น Growth และสินทรัพย์เสี่ยงถูกกดดัน"
                if is_energy_shock else
                "- ปัจจัยมหภาคเปลี่ยนมุมมองต่อเงินเฟ้อและการเติบโต\n- เมื่อคาดการณ์ดอกเบี้ยเปลี่ยน ตลาดจะหมุนระหว่าง Growth, Defensive และ Cyclical\n- ผลสุดท้ายคือ sector leadership เปลี่ยนเร็วกว่าที่ดัชนีหลักสะท้อน"
            )
            + "\n\nข้อมูลที่ใช้\n"
            + "\n".join([f"- {line}" for line in ranking_lines])
            + "\n\nผลกระทบต่อกลุ่มอุตสาหกรรม\n"
            + "\n".join([f"- {point}" for point in sector_effects])
            + "\n\nพฤติกรรมตลาด\n"
            + (
                "- ระยะสั้น: ตลาดมักเข้าสู่โหมด risk-off, น้ำมันขึ้น, ความผันผวนเพิ่ม\n- ระยะกลาง: ถ้าเหตุการณ์จำกัดวง ตลาดอาจเริ่มนิ่งขึ้น แต่ถ้าน้ำมันยืนสูงนาน การหมุน sector จะชัดขึ้น"
                if is_energy_shock else
                "- ระยะสั้น: headline จะกระทบ sentiment ก่อน\n- ระยะกลาง: ตลาดจะปรับผ่าน valuation, earnings expectation และการหมุนของ sector"
            )
            + "\n\nกรณีความเสี่ยง\n"
            + "\n".join([f"- {point}" for point in risk_scenarios])
            + "\n\nข้อสรุปเชิงกลยุทธ์\n"
            + conclusion
        )
        if is_thai else
        (
            "Market Context\n"
            + (
                f"- Fear & Greed Index: {fear_greed:.1f} ({market_label})\n"
                if fear_greed is not None else
                f"- Market sentiment: {market_label}\n"
            )
            + "- This macro read-through focuses on oil, inflation expectations, rates, and cross-sector positioning.\n\n"
            + "Data Used\n"
            + "\n".join([f"- {line}" for line in ranking_lines])
            + "\n\n"
            + "Direct Impact\n"
            + "\n".join([f"- {point}" for point in direct_effects])
            + "\n\nIndirect Impact\n"
            + "\n".join([f"- {point}" for point in indirect_effects])
            + "\n\nSector-Level Effects\n"
            + "\n".join([f"- {point}" for point in sector_effects])
            + "\n\nMarket Behavior\n"
            + (
                "- The first reaction is usually a volatility spike and a risk-off move into defensives.\n"
                "- If the shock stays contained, sector leadership can stabilize quickly.\n"
                "- If oil remains elevated, equity dispersion usually widens across cyclicals and defensives."
                if is_energy_shock else
                "- Macro shocks usually hit headline sentiment first, then valuations, then earnings expectations.\n"
                "- Sector rotation often matters more than the index headline in medium-term positioning.\n"
                "- The persistence of the move depends on whether rates and inflation expectations reset materially."
            )
            + "\n\nRisk Scenarios\n"
            + "\n".join([f"- {point}" for point in risk_scenarios])
            + "\n\nConclusion (Actionable)\n"
            + conclusion
        )
    )
    return {
        "intent": "macro_analysis",
        "intent_category": intent_category,
        "analysis_type": "macro_analysis",
        "analysis_engine": analysis_engine,
        "answer": answer,
        "confidence": 72 if is_energy_shock else 68,
        "sources": ["Macro Knowledge Base", "Market Sentiment Model", "Sector ETF Model"],
        "followups": [
            "Which sectors usually benefit from an oil shock?",
            "How would higher oil prices affect inflation?",
            "What could this mean for technology stocks?",
        ],
        "answer_schema": {
            "intent": "macro_analysis",
            "answer_title": "การวิเคราะห์มหภาคและภูมิรัฐศาสตร์" if is_thai else "Macro and Geopolitical Analysis",
            "direct_answer": direct_answer,
            "market_context": {
                "market_regime": market_label,
                "fear_greed_index": fear_greed,
                "points": [
                    f"Fear & Greed: {fear_greed:.1f} ({market_label})" if fear_greed is not None else f"Market sentiment: {market_label}",
                    f"Leading sector now: {top_sector}",
                ] + ranking_lines,
            },
            "sector_analysis": {
                "sector_rankings": top_three,
                "points": ranking_lines,
            },
            "fundamental_drivers": {"points": direct_effects + indirect_effects},
            "risk_factors": {"points": risk_scenarios},
            "investment_interpretation": {
                "recommendation": (
                    "ให้น้ำหนักเชิงเลือกใน Energy / Defensive"
                    if is_thai and is_energy_shock else
                    "Selective Overweight Energy / Defensive"
                    if is_energy_shock else
                    (f"Neutral ถึง Overweight ใน {top_sector}" if is_thai else f"Neutral to Overweight {top_sector}")
                ),
                "text": conclusion,
                "confidence": 72 if is_energy_shock else 68,
                "forecast_horizon": {},
            },
            "source_tags": ["Macro Knowledge Base", "Market Sentiment Model", "Sector ETF Model"],
            "overview": overview_line,
            "rationale": key_drivers,
            "summary_points": key_drivers,
            "risks": ui_risks,
            "actionable_view": actionable_view,
        },
        "status": {
            "online": True,
            "message": "พร้อมใช้งาน" if is_thai else "Connected",
            "live_data_ready": False,
            "market_context_loaded": True,
        },
    }


def _analyze_stock_pipeline(symbol: str, window_days: int = 14) -> Dict[str, Any]:
    sym = str(symbol or "").upper()
    try:
        reco = compute_recommendation(sym, window_days=window_days)
    except HTTPException as e:
        logger.warning(f"Stock analysis pipeline degraded for {sym}: {e.detail}")
        return {
            "ok": False,
            "symbol": sym,
            "message": "Relevant data is not available.",
            "data_validation": {
                "price_data": False,
                "news_data": False,
                "technical_data": False,
            },
            "analysis": {},
            "sources": ["Finnhub", "Market News", "Yahoo Finance"],
            "charts": {
                "price": _build_price_chart(sym),
                "sentiment": _build_sentiment_chart(sym),
            },
        }
    if reco.get("error"):
        return {
            "ok": False,
            "symbol": sym,
            "message": "Relevant data is not available.",
            "data_validation": {
                "price_data": False,
                "news_data": False,
                "technical_data": False,
            },
            "analysis": {},
            "sources": ["Finnhub", "Market News", "Yahoo Finance"],
            "charts": {
                "price": _build_price_chart(sym),
                "sentiment": _build_sentiment_chart(sym),
            },
        }

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

    forecast_30_raw = (reco.get("forecast", {}) or {}).get("predicted_return_pct")
    forecast_30 = safe_float(forecast_30_raw) if forecast_30_raw is not None else None
    forecast_horizons = (
        {
            "7d": round(forecast_30 * 0.35, 2),
            "30d": round(forecast_30, 2),
            "90d": round(forecast_30 * 2.2, 2),
        }
        if forecast_30 is not None else
        {}
    )
    momentum_score = safe_float(signals.get("momentum_score"))
    momentum_label = (
        "Strong" if momentum_score >= 70 else
        ("Moderate" if momentum_score >= 50 else "Weak")
    ) if signals.get("momentum_score") is not None else "Relevant data is not available"
    confidence_raw = reco.get("confidence")
    confidence_pct = int(round(safe_float(confidence_raw) * 100)) if confidence_raw is not None else None
    profile = {}
    try:
        profile = stock_profile_endpoint(sym)
    except Exception:
        profile = {}
    company_name = str(profile.get("name") or reco.get("company_name") or sym)
    sector = str(profile.get("industry") or _sector_for_symbol(sym))
    industry = str(profile.get("industry") or sector)
    analyst_target_raw = reco.get("target_price_mean")
    analyst_target = safe_float(analyst_target_raw) if analyst_target_raw is not None else None
    price_change_raw = reco.get("price_change")
    price_change = safe_float(price_change_raw) if price_change_raw is not None else None
    price_change_pct_raw = reco.get("price_change_pct")
    price_change_pct = safe_float(price_change_pct_raw) if price_change_pct_raw is not None else None

    analysis = {
        "ticker": sym,
        "company_name": company_name,
        "sector": sector,
        "industry": industry,
        "current_price": round(current_price, 2),
        "price_change": round(price_change, 2) if price_change is not None else None,
        "price_change_pct": round(price_change_pct, 2) if price_change_pct is not None else None,
        "recommendation": str(reco.get("recommendation") or "Relevant data is not available"),
        "confidence": confidence_pct,
        "risk_level": str(reco.get("risk_level") or "Relevant data is not available"),
        "technical_trend": str(technical.get("trend_label") or "Relevant data is not available"),
        "news_sentiment": str(signals.get("news_sentiment_label") or "Relevant data is not available"),
        "momentum": momentum_label,
        "forecast_horizon": forecast_horizons,
        "analyst_target": round(analyst_target, 2) if analyst_target is not None and analyst_target > 0 else None,
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


def _has_minimum_ai_evidence(intent: str, evidence: Dict[str, Any]) -> bool:
    if intent == "stock_comparison":
        left = evidence.get("left") or {}
        right = evidence.get("right") or {}
        return bool(left.get("ticker") and right.get("ticker") and left.get("current_price") and right.get("current_price"))
    if intent in {"single_stock_analysis", "risk_explanation", "stock_risk"}:
        analysis = evidence.get("analysis") or {}
        return bool(analysis.get("ticker") and analysis.get("current_price"))
    if intent in {"sector_analysis", "sector_explanation", "sector_stock_picker", "market_overview", "market_risk", "sector_risk"}:
        market = evidence.get("market") or {}
        top_sector = evidence.get("top_sector") or {}
        return market.get("market_score") is not None or bool(top_sector.get("sector"))
    if intent == "portfolio_advice":
        return bool(evidence.get("portfolio_symbols"))
    return True


def _generate_grounded_response(
    question: str,
    intent: str,
    evidence: Dict[str, Any],
    fallback_text: str,
) -> str:
    if not _has_minimum_ai_evidence(intent, evidence):
        return fallback_text

    prompt = (
        "You are a professional hedge fund analyst.\n"
        "Always answer directly.\n"
        "Always explain WHY, not just WHAT.\n"
        "Never ask generic clarification first.\n"
        "Your job is to interpret real market data and generate structured investment insights.\n"
        "Answer exactly what the user asked and never fabricate market statistics.\n"
        "Use only the provided EVIDENCE JSON.\n"
        "If data is missing, say exactly: Relevant data is not available.\n"
        "Never invent prices, targets, percentages, rankings, momentum scores, or sentiment values.\n"
        "Do not guess.\n"
        "Less irrelevant information is better than more irrelevant information.\n"
        "Always write in a professional investment research tone.\n"
        "For macro questions: explain cause, effect, and sector impact.\n"
        "For sector questions: explain rotation, relative strength, and positioning.\n"
        "For stock questions: explain fundamentals, timing, and risk.\n"
        "Preferred answer structure is:\n"
        "Market Context\n"
        "Causal Explanation\n"
        "Sector Impact\n"
        "Risk\n"
        "Actionable View\n"
        "For trending stocks, list the stocks, explain why they are trending, and keep it grounded in price action / activity / news if available.\n"
        "For risk questions, focus on downside risks and do not switch to recommendations unless the user asked.\n"
        "Do not use weak phrases like 'I'm not fully confident'.\n\n"
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


def _context_to_payload(context: AIAdvisorContext) -> Dict[str, Any]:
    if hasattr(context, "model_dump"):
        return context.model_dump()
    if hasattr(context, "dict"):
        return context.dict()
    return dict(context or {})


def _get_modular_advisor_service() -> Optional[Any]:
    global modular_advisor_service

    if not HAS_MODULAR_ADVISOR:
        return None
    if modular_advisor_service is not None:
        return modular_advisor_service

    try:
        market_engine = UltimateMarketDataEngine(
            session=session,
            alpha_vantage_api_key=ALPHA_VANTAGE_API_KEY,
            finnhub_api_key=FINNHUB_API_KEY,
            polygon_api_key=POLYGON_API_KEY,
            fmp_api_key=FMP_API_KEY,
            twelvedata_api_key=TWELVEDATA_API_KEY,
            cache_ttl_seconds=600,
            timeout_seconds=2.0,
            finnhub_quote_fetcher=_fetch_finnhub_quote,
            finnhub_history_fetcher=_fetch_finnhub_candles,
            alpha_quote_fetcher=_fetch_alpha_vantage_quote,
            alpha_history_fetcher=_fetch_alpha_vantage_history,
            polygon_quote_fetcher=_fetch_polygon_quote,
            polygon_history_fetcher=_fetch_polygon_history,
            fmp_quote_fetcher=_fetch_fmp_quote,
            fmp_history_fetcher=_fetch_fmp_history,
            yfinance_history_fetcher=_fetch_yfinance_history,
            yfinance_previous_close_fetcher=_fetch_yfinance_previous_close,
            symbol_variants_fetcher=_symbol_variants,
            log_func=logger.info,
        )
        market_gateway = MarketDataGateway(
            get_stock_data=get_stock_data,
            get_stock_profile=stock_profile_endpoint,
            get_stock_details=stock_details_endpoint,
            build_market_snapshot=_build_market_snapshot,
            rank_sector_etfs=_rank_sector_etfs,
            market_engine=market_engine,
        )
        news_gateway = NewsDataGateway(get_news_batch=get_newsapi_news_batch)
        macro_gateway = MacroDataGateway()
        modular_advisor_service = AdvisorEndpointService(
            reasoning_engine=InvestmentReasoningEngine(
                market_data=market_gateway,
                news_data=news_gateway,
                macro_data=macro_gateway,
            )
        )
        return modular_advisor_service
    except Exception as exc:
        logger.error(f"❌ Failed to initialize modular advisor service: {exc}")
        return None


def _advisor_health_snapshot() -> Dict[str, Any]:
    service = _get_modular_advisor_service()
    return {
        "ok": service is not None,
        "service": "ai_advisor",
        "architecture": "modular_router",
        "live_routes": ["/ai-advisor", "/api/ai-advisor"],
        "providers": {
            "yfinance_available": True,
            "alpha_vantage_configured": bool(ALPHA_VANTAGE_API_KEY),
            "polygon_configured": bool(POLYGON_API_KEY),
            "finnhub_configured": bool(FINNHUB_API_KEY),
            "twelvedata_configured": bool(TWELVEDATA_API_KEY),
            "newsapi_configured": bool(NEWSAPI_KEY),
            "marketaux_configured": bool(MARKETAUX_API_KEY),
            "gemini_configured": bool(GEMINI_API_KEY),
        },
        "modules": {
            "modular_advisor": HAS_MODULAR_ADVISOR,
            "market_sentiment": HAS_MARKET_SENTIMENT,
            "ai_picker": HAS_AI_PICKER,
            "risk_model": HAS_RISK,
        },
        "timestamp": datetime.now().isoformat(),
    }

@app.post("/ai-advisor")
@app.post("/api/ai-advisor")
def ai_advisor_endpoint(payload: AIAdvisorRequest | Dict[str, Any]):
    if isinstance(payload, dict):
        payload = AIAdvisorRequest(**payload)
    if payload.history:
        merged_history = list(payload.context.history or [])
        for item in payload.history:
            text = str(item or "").strip()
            if text and text not in merged_history:
                merged_history.append(text)
        payload.context.history = merged_history[-4:]
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

    modular_service = _get_modular_advisor_service()
    if modular_service:
        try:
            context_payload = _context_to_payload(payload.context)
            if symbol:
                context_payload["selected_stock"] = symbol
            modular_response = modular_service.handle(question, context_payload)
            if modular_response:
                modular_response.setdefault("intent_category", intent_category)
                modular_response.setdefault("gemini_used", False)
                return modular_response
        except Exception as exc:
            logger.error(f"❌ Modular advisor pipeline failed, falling back to legacy flow: {exc}")

    if intent == "stock_recommendation":
        return _build_legacy_stock_recommendation_response(market, intent_category, analysis_engine)

    if intent == "open_recommendation":
        return _build_legacy_open_recommendation_response(market, intent_category, analysis_engine)

    if intent == "global_market_query":
        return _build_legacy_global_market_query_response(market, intent_category, analysis_engine)

    if intent == "macro_analysis":
        return _build_legacy_macro_response(question, market, intent_category, analysis_engine)

    if intent in {"trending_stock_discovery", "market_scanner"}:
        trending_response = _build_trending_stock_response(payload.context, market)
        trending_response.update({
            "intent_category": intent_category,
            "analysis_type": "market_scanner" if intent == "market_scanner" else "trending_stock_discovery",
            "analysis_engine": analysis_engine,
            "gemini_used": False,
        })
        return trending_response

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
                "market_sentiment": market.get("market_label") or "Relevant data is not available",
                "fear_greed_score": market.get("market_score"),
                "trending_sector": _sector_for_symbol(risk_symbol),
                "risk_outlook": market.get("risk_outlook") or "Relevant data is not available",
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
                "market_sentiment": market.get("market_label") or "Relevant data is not available",
                "fear_greed_score": market.get("market_score"),
                "trending_sector": (market.get("sector_momentum") or {}).get("sector") or "Relevant data is not available",
                "risk_outlook": market.get("risk_outlook") or "Relevant data is not available",
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
                "market_sentiment": market.get("market_label") or "Relevant data is not available",
                "fear_greed_score": market.get("market_score"),
                "trending_sector": resolved_sector,
                "risk_outlook": market.get("risk_outlook") or "Relevant data is not available",
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
            "why_these_names": {
                "points": [
                    (
                        f"{row.get('symbol')}: "
                        + (
                            f"stronger 3M trend at {safe_float(row.get('return_3m_pct')):+.2f}%"
                            if row.get("return_3m_pct") is not None
                            else "price trend data is limited"
                        )
                    )
                    for row in display_rows[:5]
                ],
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
        if is_sector_query or is_sector_explanation:
            short_direct_answer = (
                f"{top_sector} still looks attractive on a relative basis, but the current {market['market_label']} regime supports selective exposure rather than aggressive positioning."
                if score is not None and score >= 70
                else (
                    f"{top_sector} remains one of the stronger sectors, although the current {market['market_label']} backdrop still argues for discipline on entry and sizing."
                    if score is not None and score >= 50
                    else f"{top_sector} does not have strong enough confirmation for an aggressive sector call under the current {market['market_label']} backdrop."
                )
            )
        else:
            short_direct_answer = (
                f"Market conditions remain cautious, with {top_sector} currently leading on a relative basis."
                f" The current {market['market_label']} regime still favors selective positioning over broad risk-taking."
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
        answer_schema.update({
            "direct_answer": short_direct_answer,
            "market_context": {
                "market_regime": market["market_label"],
                "fear_greed_index": market["market_score"],
                "points": sections["market_summary"][:3],
            },
            "sector_analysis": {
                "sector": top_sector,
                "etf": top_etf,
                "momentum_label": sector_rank.get("top_momentum_label", "Relevant data is not available"),
                "sector_rankings": rankings[:5],
                "points": [
                    f"{top_etf} 3M return: {ret3m_txt}",
                    f"Relative strength vs SPY: {rs_txt}",
                    f"Sector momentum score: {score_txt}",
                ],
            },
            "fundamental_drivers": {
                "points": [
                    f"{top_sector} is leading because return, relative strength, and sentiment remain supportive."
                    if score is not None else
                    f"Relevant performance drivers are partially available for {top_sector}.",
                    "Sector rotation is influenced by macro regime, earnings visibility, and sentiment flow.",
                ],
            },
            "risk_factors": {
                "points": sections["risk_factors"][:4],
            },
            "investment_interpretation": {
                "recommendation": signal,
                "text": f"Current sector view favors {top_sector} leadership, but position sizing should still reflect the broader {market['market_label']} market regime.",
                "confidence": confidence,
                "forecast_horizon": {},
            },
        })
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
            "answer": short_direct_answer,
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
                "forecast_horizon": {},
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
                "momentum": market["sector_momentum"].get("momentum") or "Relevant data is not available",
                "news_sentiment": "Market-driven",
                "risks": sections.get("risk_factors", []),
                "forecast_horizon": {},
            },
            market=market,
            sources=sections["sources"],
            signal=sections["ai_recommendation"]["signal"],
        )
        answer_schema.update({
            "portfolio_overview": {
                "holdings_count": len(symbols),
                "dominant_sector": dominant,
                "diversification": diversification,
                "risk_level": risk,
                "concentration_pct": round(concentration * 100, 2),
                "symbols": symbols[:8],
            },
            "market_context": {
                "market_regime": market["market_label"],
                "fear_greed_index": market["market_score"],
                "points": sections["market_summary"][:3],
            },
            "portfolio_analysis": {
                "points": [
                    f"Dominant sector: {dominant}",
                    f"Diversification: {diversification}",
                    f"Concentration ratio: {concentration * 100:.1f}%",
                ],
            },
            "risk_factors": {
                "points": sections["risk_factors"][:4],
            },
            "investment_interpretation": {
                "recommendation": sections["ai_recommendation"]["signal"],
                "text": (
                    f"Portfolio positioning suggests a {risk.lower()} risk profile with {diversification.lower()} diversification. "
                    f"Current priority is to {'reduce concentration' if diversification == 'Low' else 'maintain balance while monitoring regime shifts'}."
                ),
                "confidence": confidence,
                "forecast_horizon": {},
            },
        })
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
                "sector_momentum": market["sector_momentum"].get("momentum") or "Relevant data is not available",
                "risk_outlook": risk,
                "signal": sections["ai_recommendation"]["signal"],
                "forecast_horizon": {},
                "market_momentum": market["sector_momentum"].get("score"),
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
                "momentum": sector_rank.get("top_momentum_label") or "Relevant data is not available",
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
                "sector_momentum": sector_rank.get("top_momentum_label") or "Relevant data is not available",
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
        followups = _build_followup_prompts(intent, symbol, market["sector_momentum"].get("sector") or _sector_for_symbol(symbol))
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
                "trending_sector": market["sector_momentum"].get("sector") or _sector_for_symbol(symbol),
                "sector_momentum": market["sector_momentum"].get("momentum") or "Relevant data is not available",
                "risk_outlook": market["risk_outlook"],
                "forecast_horizon": {},
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
    confidence = int(analysis.get("confidence") or 0)
    forecast_horizons = analysis.get("forecast_horizon") or {}
    top_sector = market["sector_momentum"].get("sector") or _sector_for_symbol(symbol)
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
        "Market Context\n"
        + (
            f"- Fear & Greed Index: {market['market_score']} ({market['market_label']})\n"
            if market.get("market_score") is not None else
            "- Fear & Greed Index: Relevant data is not available.\n"
        )
        + (
            f"- Strongest Sector: {market['sector_momentum'].get('sector')} ({market['sector_momentum'].get('momentum')})\n\n"
            if market.get("sector_momentum", {}).get("sector") else
            "- Strongest Sector: Relevant data is not available.\n\n"
        )
        + "Stock Overview\n"
        f"- Price: ${safe_float(analysis.get('current_price')):.2f}\n"
        f"- Sector: {analysis.get('sector')}\n"
        f"- Industry: {analysis.get('industry')}\n\n"
        "Technical Signals\n"
        f"- Technical trend: {analysis.get('technical_trend') or 'Relevant data is not available'}\n"
        f"- Momentum: {analysis.get('momentum') or 'Relevant data is not available'}\n\n"
        "Fundamental Drivers\n"
        + "\n".join([f"- {d}" for d in (analysis.get("drivers") or [])[:3]])
        + "\n\n"
        "Market Sentiment\n"
        f"- News sentiment: {analysis.get('news_sentiment') or 'Relevant data is not available'}\n"
        + "\nKey Risks\n"
        + "\n".join([f"- {r}" for r in (analysis.get("risks") or [])[:3]])
        + "\n\nInvestment View\n"
        f"- Recommendation: {analysis.get('recommendation') or 'Relevant data is not available'}\n"
        + (
            (
                f"- Forecast horizon: 7D {safe_float(forecast_horizons.get('7d')):+.2f}% | "
                f"30D {safe_float(forecast_horizons.get('30d')):+.2f}% | "
                f"90D {safe_float(forecast_horizons.get('90d')):+.2f}%"
            )
            if forecast_horizons else
            "- Forecast horizon: Relevant data is not available"
        )
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
            "sector_momentum": market["sector_momentum"].get("momentum") or "Relevant data is not available",
            "risk_outlook": market["risk_outlook"],
            "signal": analysis.get("recommendation") or "Relevant data is not available",
            "forecast_horizon": forecast_horizons,
            "market_momentum": market["sector_momentum"].get("score"),
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

@app.get("/ai-advisor/health")
@app.get("/api/ai-advisor/health")
def ai_advisor_health():
    return _advisor_health_snapshot()


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
        try:
            analyzed_rows = _parallel_map(
                lambda sym: (sym, _analyze_stock_pipeline(sym, window_days=14)),
                candidates[:3],
                max_workers=3,
            )
        except Exception:
            analyzed_rows = []
        for sym, analyzed in analyzed_rows:
            try:
                if not analyzed.get("ok"):
                    continue
                a = analyzed.get("analysis", {})
                score = safe_float(analyzed.get("raw", {}).get("ai_score"))
                conf = int(a.get("confidence", 0))
                if score > best["score"]:
                    best = {"symbol": sym, "confidence": conf, "score": score, "analysis": analyzed}
            except Exception:
                continue

    top_symbol = best["symbol"] or None
    top_conf = best["confidence"] or None
    top_sector = market["sector_momentum"].get("sector")
    top_sector_momentum = market["sector_momentum"].get("momentum")
    if top_sector and top_sector_momentum:
        explanation = (
            f"AI analysis indicates that {top_sector} stocks "
            f"show {str(top_sector_momentum).lower()} relative momentum "
            "supported by recent sentiment and trend signals."
        )
    else:
        explanation = "Relevant data is not available."
    response_payload = {
        "summary": {
            "market_sentiment": market["market_label"],
            "fear_greed_score": market["market_score"],
            "fear_greed_source": market.get("market_meta", {}).get("source", "InternalModel"),
            "top_ai_pick": top_symbol,
            "top_ai_pick_confidence": top_conf,
            "trending_sector": top_sector,
            "sector_momentum": top_sector_momentum,
            "risk_outlook": market["risk_outlook"],
            "forecast_horizon": (best.get("analysis", {}) or {}).get("analysis", {}).get("forecast_horizon", {}),
            "market_momentum": market["sector_momentum"].get("score"),
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


@app.post("/ai-trades/signal")
@app.post("/api/ai-trades/signal")
def create_ai_trade_signal(
    payload: AITradeSignalRequest,
    authorization: Optional[str] = Header(default=None),
):
    user_id = _extract_user_id_from_authorization(authorization)
    symbol = normalize_symbol(payload.symbol)
    signal_profile = _signal_trade_profile(payload.recommendation)
    recommendation = signal_profile["recommendation"]
    position = signal_profile["position"]
    size = min(float(payload.size or signal_profile["default_size"] or 0.0), 1.0)

    with SessionLocal() as db:
        _close_expired_ai_trades(db, user_id)

        open_rows: List[AIRecommendationTrade] = (
            db.query(AIRecommendationTrade)
            .filter(
                AIRecommendationTrade.user_id == user_id,
                AIRecommendationTrade.symbol == symbol,
                AIRecommendationTrade.status == "open",
            )
            .order_by(AIRecommendationTrade.entry_time.asc())
            .all()
        )

        if position is None:
            return {
                "ok": True,
                "action": "ignored",
                "message": "Hold signal received. No trade opened.",
                "recommendation": recommendation,
                "symbol": symbol,
                "open_trades": [_serialize_ai_trade(row) for row in open_rows],
            }

        quote = _get_portfolio_quote(symbol)
        current_price = safe_float(quote.get("price"))
        if current_price <= 0:
            raise HTTPException(status_code=503, detail=f"Live quote unavailable for {symbol}")

        closed_trade_ids: List[int] = []
        for row in open_rows:
            if row.position != position:
                _close_trade(row, current_price, "opposite_signal")
                db.add(row)
                closed_trade_ids.append(row.id)

        same_direction = next((row for row in open_rows if row.position == position and row.status == "open"), None)
        if same_direction:
            db.commit()
            db.refresh(same_direction)
            return {
                "ok": True,
                "action": "already_open",
                "symbol": symbol,
                "recommendation": recommendation,
                "trade": _serialize_ai_trade(same_direction),
                "closed_trade_ids": closed_trade_ids,
            }

        trade = AIRecommendationTrade(
            user_id=user_id,
            symbol=symbol,
            recommendation=recommendation,
            position=position,
            size=size if size > 0 else float(signal_profile["default_size"] or 1.0),
            entry_price=float(current_price),
            entry_time=datetime.utcnow(),
            status="open",
        )
        db.add(trade)
        db.commit()
        db.refresh(trade)

        return {
            "ok": True,
            "action": "opened",
            "symbol": symbol,
            "recommendation": recommendation,
            "trade": _serialize_ai_trade(trade),
            "closed_trade_ids": closed_trade_ids,
        }


@app.post("/ai-trades/{trade_id}/close")
@app.post("/api/ai-trades/{trade_id}/close")
def close_ai_trade(
    trade_id: int,
    payload: AITradeExitRequest = Body(default=AITradeExitRequest()),
    authorization: Optional[str] = Header(default=None),
):
    user_id = _extract_user_id_from_authorization(authorization)
    with SessionLocal() as db:
        row: Optional[AIRecommendationTrade] = (
            db.query(AIRecommendationTrade)
            .filter(
                AIRecommendationTrade.id == trade_id,
                AIRecommendationTrade.user_id == user_id,
            )
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="AI trade not found")
        if row.status != "open":
            return {"ok": True, "action": "noop", "trade": _serialize_ai_trade(row)}

        quote = _get_portfolio_quote(row.symbol)
        current_price = safe_float(quote.get("price"))
        if current_price <= 0:
            raise HTTPException(status_code=503, detail=f"Live quote unavailable for {row.symbol}")
        _close_trade(row, current_price, payload.reason or "manual_exit")
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"ok": True, "action": "closed", "trade": _serialize_ai_trade(row)}


@app.get("/ai-trades")
@app.get("/api/ai-trades")
def list_ai_trades(
    status: str = Query("all", description="all | open | closed"),
    authorization: Optional[str] = Header(default=None),
):
    user_id = _extract_user_id_from_authorization(authorization)
    normalized_status = str(status or "all").lower()
    with SessionLocal() as db:
        _close_expired_ai_trades(db, user_id)
        query = (
            db.query(AIRecommendationTrade)
            .filter(AIRecommendationTrade.user_id == user_id)
            .order_by(AIRecommendationTrade.entry_time.desc())
        )
        if normalized_status in {"open", "closed"}:
            query = query.filter(AIRecommendationTrade.status == normalized_status)
        rows: List[AIRecommendationTrade] = query.all()
    return {
        "ok": True,
        "status_filter": normalized_status,
        "items": [_serialize_ai_trade(row) for row in rows],
    }


@app.get("/ai-trades/summary")
@app.get("/api/ai-trades/summary")
def ai_trade_summary(authorization: Optional[str] = Header(default=None)):
    user_id = _extract_user_id_from_authorization(authorization)
    with SessionLocal() as db:
        _close_expired_ai_trades(db, user_id)
        rows: List[AIRecommendationTrade] = (
            db.query(AIRecommendationTrade)
            .filter(AIRecommendationTrade.user_id == user_id)
            .order_by(AIRecommendationTrade.entry_time.desc())
            .all()
        )
    summary = _summarize_ai_trades(rows)
    summary["ok"] = True
    return summary


@app.get("/ai-trades/evaluation")
@app.get("/api/ai-trades/evaluation")
def ai_trade_evaluation(
    window: str = Query("all", description="30 | 90 | all"),
    authorization: Optional[str] = Header(default=None),
):
    user_id = _extract_user_id_from_authorization(authorization)
    with SessionLocal() as db:
        _close_expired_ai_trades(db, user_id)
        query = (
            db.query(AIRecommendationTrade)
            .filter(AIRecommendationTrade.user_id == user_id)
            .order_by(AIRecommendationTrade.entry_time.desc())
        )
        normalized_window = str(window or "all").lower()
        if normalized_window in {"30", "90"}:
            query = query.limit(int(normalized_window))
        rows: List[AIRecommendationTrade] = query.all()
    payload = _build_ai_trade_evaluation(rows)
    payload["ok"] = True
    payload["evaluated_trades"] = len(rows)
    payload["window"] = normalized_window
    return payload


@app.get("/api/ai-trades/autotune")
@app.get("/ai-trades/autotune")
def ai_trade_autotune_preview(
    authorization: Optional[str] = Header(default=None),
):
    user_id = _extract_user_id_from_authorization(authorization)
    with SessionLocal() as db:
        _close_expired_ai_trades(db, user_id)
        rows: List[AIRecommendationTrade] = (
            db.query(AIRecommendationTrade)
            .filter(AIRecommendationTrade.user_id == user_id)
            .order_by(AIRecommendationTrade.entry_time.desc())
            .all()
        )
    evaluation = _build_ai_trade_evaluation(rows)
    preview = evaluation.get("auto_tuning_preview") or _build_auto_tuning_payload([], [], {"rolling": {}})
    return {
        "ok": True,
        "evaluated_trades": len(rows),
        **preview,
    }


@app.post("/api/ai-trades/autotune")
@app.post("/ai-trades/autotune")
def ai_trade_autotune_apply(
    payload: AIAutoTuneRequest,
    authorization: Optional[str] = Header(default=None),
):
    user_id = _extract_user_id_from_authorization(authorization)
    with SessionLocal() as db:
        _close_expired_ai_trades(db, user_id)
        rows: List[AIRecommendationTrade] = (
            db.query(AIRecommendationTrade)
            .filter(AIRecommendationTrade.user_id == user_id)
            .order_by(AIRecommendationTrade.entry_time.desc())
            .all()
        )
    evaluation = _build_ai_trade_evaluation(rows)
    preview = evaluation.get("auto_tuning_preview") or _build_auto_tuning_payload([], [], {"rolling": {}})
    proposed = dict(preview.get("proposed") or {})
    proposed["applied_by"] = payload.operator or "system"
    proposed["applied_at"] = datetime.utcnow().isoformat()
    saved = _save_ai_tuning_config(proposed)
    return {
        "ok": True,
        "evaluated_trades": len(rows),
        "adjustments": list(preview.get("adjustments") or []),
        "config": saved,
    }


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
    endpoint_cache_key = f"stock-endpoint:{normalize_symbol(symbol)}:{str(range or '3mo').lower()}"
    cached_payload = _cache_get(generic_ttl_cache, endpoint_cache_key, STOCK_ENDPOINT_CACHE_TTL)
    if cached_payload is not None:
        return cached_payload

    def _yahoo_aligned_return(sym: str, range_value: str) -> Dict[str, Any]:
        key = str(range_value or "").strip().lower()
        cache_key = f"{sym.upper()}:{key}"
        now_ts = time.time()
        cached = stock_return_cache.get(cache_key)
        if cached and (now_ts - float(cached.get("ts", 0))) < STOCK_RETURN_CACHE_TTL:
            return dict(cached.get("data") or {})
        normalized_period = _normalize_range(range_value)
        if key not in {"1d", "5d"}:
            for yf_symbol in _symbol_variants(sym):
                try:
                    hist = yf.Ticker(yf_symbol).history(
                        period=normalized_period,
                        interval="1d",
                        auto_adjust=False,
                        prepost=False,
                        actions=False,
                    )
                    close_field = "Adj Close" if "Adj Close" in hist.columns else "Close"
                    if close_field not in hist.columns:
                        continue
                    series = hist[close_field].dropna()
                    series = series[series > 0]
                    if len(series) < 2:
                        continue
                    result = {
                        "first_close": float(series.iloc[0]),
                        "last_close": float(series.iloc[-1]),
                        "return_pct": calculate_total_return(float(series.iloc[0]), float(series.iloc[-1])),
                        "source": f"yfinance.{close_field}",
                    }
                    stock_return_cache[cache_key] = {"ts": now_ts, "data": result}
                    return result
                except Exception:
                    continue
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
                resp = session.get(
                    url,
                    params={
                        "range": yf_range,
                        "interval": yf_interval,
                        "includePrePost": "false",
                        "events": "div,splits",
                    },
                    timeout=4,
                )
                if resp.status_code != 200:
                    continue
                payload = resp.json() if resp.content else {}
                result = ((payload.get("chart") or {}).get("result") or [])
                if not result:
                    continue
                indicators = result[0].get("indicators") or {}
                quote = ((indicators.get("quote") or [{}])[0] or {})
                if yf_range in {"1d", "5d"}:
                    closes = quote.get("close") or []
                    volumes = quote.get("volume") or []
                    source = "YahooChartClose"
                else:
                    adjclose = ((indicators.get("adjclose") or [{}])[0] or {}).get("adjclose") or []
                    closes = adjclose or quote.get("close") or []
                    volumes = quote.get("volume") or []
                    source = "YahooChartAdjClose" if adjclose else "YahooChartClose"
                series = [safe_float(x) for x in closes if safe_float(x) > 0]
                if len(series) < 2:
                    continue
                first = _first_valid_traded_close(closes, volumes)
                last = safe_float(series[-1])
                if first <= 0 or last <= 0:
                    continue
                result = {
                    "first_close": first,
                    "last_close": last,
                    "return_pct": calculate_total_return(first, last),
                    "source": source,
                }
                stock_return_cache[cache_key] = {"ts": now_ts, "data": result}
                return result
            except Exception:
                continue
        return {"first_close": 0.0, "last_close": 0.0, "return_pct": 0.0, "source": None}

    symbol = normalize_symbol(symbol)
    try:
        stock_data = get_stock_data(symbol, range)
    except HTTPException as exc:
        logger.warning(f"Stock endpoint degraded for {symbol} ({range}): {exc.detail}")
        stock_data = {
            "symbol": symbol,
            "name": symbol,
            "price": 0.0,
            "previous_close": 0.0,
            "history": [],
            "provider": "Unavailable",
            "range": _normalize_range(range),
        }
    except Exception as exc:
        logger.exception(f"Unexpected stock endpoint failure for {symbol} ({range}): {exc}")
        stock_data = {
            "symbol": symbol,
            "name": symbol,
            "price": 0.0,
            "previous_close": 0.0,
            "history": [],
            "provider": "Unavailable",
            "range": _normalize_range(range),
        }
    history = stock_data.get("history", [])
    latest_price = stock_data.get("price", 0.0)
    previous_close = safe_float(stock_data.get("previous_close", 0.0))
    range_key = str(stock_data.get("range", _normalize_range(range))).lower()

    if history:
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
        range_return_pct = calculate_total_return(first_close, latest_close)

    # Force Yahoo as single baseline source for first/last close in all ranges for near 1:1 parity.
    yahoo_ret = _yahoo_aligned_return(symbol, range)
    if yahoo_ret["first_close"] > 0 and yahoo_ret["last_close"] > 0:
        first_close = safe_float(yahoo_ret["first_close"])
        last_close = safe_float(yahoo_ret["last_close"])
        latest_close = last_close
        range_return_pct = safe_float(yahoo_ret["return_pct"])
        range_return_source = str(yahoo_ret.get("source") or "YahooClose")

    if range_key != "1d" and _is_unrealistic_total_return(range_return_pct):
        recalculated_return = calculate_total_return(first_close, last_close or latest_close)
        if not _is_unrealistic_total_return(recalculated_return):
            range_return_pct = recalculated_return
            range_return_source = f"{range_return_source}:validated"

    latest_volume = int(history[-1].get("volume") or 0) if history else 0

    payload = {
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
        "day_range_low": None,
        "day_range_high": None,
        "range_52w_low": None,
        "range_52w_high": None,
        "source_provider": stock_data.get("provider"),
    }
    return _cache_set(generic_ttl_cache, endpoint_cache_key, payload)


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
    cache_key = f"stock-details:{sym}"
    cached = _cache_get(generic_ttl_cache, cache_key, STOCK_DETAILS_CACHE_TTL)
    if cached is not None:
        return cached

    quote = {}
    profile = {}
    metric = {}
    basic_metric = {}
    earnings_date = None
    fmp_quote = {}
    fmp_profile = {}
    fmp_metrics = {}
    fmp_ratios = {}
    source = "Finnhub"
    market_data_timestamp = None

    try:
        with ThreadPoolExecutor(max_workers=5) as executor:
            quote_future = executor.submit(_finnhub_get, "/quote", {"symbol": sym})
            profile_future = executor.submit(_finnhub_get, "/stock/profile2", {"symbol": sym})
            metric_future = executor.submit(_finnhub_get, "/stock/metric", {"symbol": sym, "metric": "all"})
            basic_future = executor.submit(_finnhub_get, "/stock/basic-financials", {"symbol": sym, "metric": "all"})
            earnings_future = executor.submit(_finnhub_get, "/calendar/earnings", {"symbol": sym})

            quote = quote_future.result() or {}
            profile = profile_future.result() or {}
            metric_payload = metric_future.result() or {}
            basic_payload = basic_future.result() or {}
            earnings_payload = earnings_future.result() or {}

        quote_ts = int(quote.get("t") or 0)
        if quote_ts > 0:
            market_data_timestamp = datetime.utcfromtimestamp(quote_ts).isoformat() + "Z"
        metric = (metric_payload.get("metric") if isinstance(metric_payload, dict) else {}) or {}
        basic_metric = (basic_payload.get("metric") if isinstance(basic_payload, dict) else {}) or {}
        earnings_rows = earnings_payload.get("earningsCalendar") if isinstance(earnings_payload, dict) else []
        if isinstance(earnings_rows, list) and earnings_rows:
            earnings_date = earnings_rows[0].get("date")
    except Exception as e:
        logger.warning(f"Finnhub stock details unavailable for {sym}: {e}")
        source = "FMP"
        try:
            with ThreadPoolExecutor(max_workers=4) as executor:
                quote_future = executor.submit(_fmp_get, f"/quote/{sym}")
                profile_future = executor.submit(_fmp_get, f"/profile/{sym}")
                metrics_future = executor.submit(_fmp_get, f"/key-metrics-ttm/{sym}")
                ratios_future = executor.submit(_fmp_get, f"/ratios-ttm/{sym}")

                fmp_quote_rows = quote_future.result()
                fmp_profile_rows = profile_future.result()
                fmp_key_metrics = metrics_future.result()
                ratio_rows = ratios_future.result()

            fmp_quote = fmp_quote_rows[0] if isinstance(fmp_quote_rows, list) and fmp_quote_rows else {}
            fmp_profile = fmp_profile_rows[0] if isinstance(fmp_profile_rows, list) and fmp_profile_rows else {}
            fmp_metrics = fmp_key_metrics[0] if isinstance(fmp_key_metrics, list) and fmp_key_metrics else {}
            fmp_ratios = ratio_rows[0] if isinstance(ratio_rows, list) and ratio_rows else {}
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

    # Fill missing fundamentals using FMP even when Finnhub is available but incomplete.
    # This avoids returning N/A for common metrics such as PE/EPS for symbols where Finnhub omits fields.
    if FMP_API_KEY:
        try:
            fetch_plan = []
            if not fmp_quote:
                fetch_plan.append(("quote", f"/quote/{sym}"))
            if not fmp_profile:
                fetch_plan.append(("profile", f"/profile/{sym}"))
            if not fmp_metrics:
                fetch_plan.append(("metrics", f"/key-metrics-ttm/{sym}"))
            if not fmp_ratios:
                fetch_plan.append(("ratios", f"/ratios-ttm/{sym}"))
            if fetch_plan:
                with ThreadPoolExecutor(max_workers=min(4, len(fetch_plan))) as executor:
                    future_map = {name: executor.submit(_fmp_get, path) for name, path in fetch_plan}
                    for name, future in future_map.items():
                        rows = future.result()
                        row = rows[0] if isinstance(rows, list) and rows else {}
                        if name == "quote":
                            fmp_quote = row
                        elif name == "profile":
                            fmp_profile = row
                        elif name == "metrics":
                            fmp_metrics = row
                        elif name == "ratios":
                            fmp_ratios = row
            if not earnings_date:
                earnings_date = fmp_quote.get("earningsAnnouncement") or fmp_profile.get("ipoDate")
        except Exception as fmp_enrich_error:
            logger.warning(f"FMP enrichment unavailable for {sym}: {fmp_enrich_error}")

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
    week_52_low = _pick_optional(metric.get("52WeekLow"), basic_metric.get("52WeekLow"), fmp_quote.get("yearLow"))
    week_52_high = _pick_optional(metric.get("52WeekHigh"), basic_metric.get("52WeekHigh"), fmp_quote.get("yearHigh"))
    volume_raw = _pick_optional(quote.get("v"), metric.get("10DayAverageTradingVolume"))
    avg_volume_raw = _pick_optional(
        metric.get("3MonthAverageTradingVolume"),
        basic_metric.get("3MonthAverageTradingVolume"),
        metric.get("10DayAverageTradingVolume"),
        fmp_quote.get("avgVolume"),
    )
    market_cap_raw = _pick_optional(
        profile.get("marketCapitalization"),
        metric.get("marketCapitalization"),
        basic_metric.get("marketCapitalization"),
        fmp_profile.get("mktCap"),
    )
    beta = _pick_optional(metric.get("beta"), basic_metric.get("beta"), fmp_profile.get("beta"))
    pe_ratio = _pick_optional(
        metric.get("peTTM"),
        basic_metric.get("peTTM"),
        metric.get("peNormalizedAnnual"),
        basic_metric.get("peNormalizedAnnual"),
        metric.get("peBasicExclExtraTTM"),
        basic_metric.get("peBasicExclExtraTTM"),
        fmp_quote.get("pe"),
    )
    eps_ttm = _pick_optional(
        metric.get("epsTTM"),
        basic_metric.get("epsTTM"),
        metric.get("epsInclExtraItemsTTM"),
        basic_metric.get("epsInclExtraItemsTTM"),
        metric.get("epsBasicExclExtraItemsTTM"),
        basic_metric.get("epsBasicExclExtraItemsTTM"),
        fmp_quote.get("eps"),
    )
    dividend_yield_pct = _to_percent(
        _pick_optional(
            metric.get("dividendYieldIndicatedAnnual"),
            basic_metric.get("dividendYieldIndicatedAnnual"),
            metric.get("currentDividendYieldTTM"),
            basic_metric.get("currentDividendYieldTTM"),
            fmp_quote.get("dividendYield"),
            fmp_ratios.get("dividendYielTTM"),
        )
    )
    forward_dividend = _pick_optional(
        metric.get("dividendPerShareAnnual"),
        basic_metric.get("dividendPerShareAnnual"),
        fmp_quote.get("lastDiv"),
    )
    ex_dividend_date = metric.get("exDividendDate") or basic_metric.get("exDividendDate")
    target_price = _pick_optional(metric.get("targetMeanPrice"), basic_metric.get("targetMeanPrice"), fmp_quote.get("priceTarget"))
    revenue_ttm = _pick_optional(
        metric.get("revenueTTM"),
        basic_metric.get("revenueTTM"),
        metric.get("totalRevenueTTM"),
        basic_metric.get("totalRevenueTTM"),
        fmp_metrics.get("revenuePerShareTTM"),
    )
    free_cash_flow = _pick_optional(
        metric.get("freeCashFlowTTM"),
        basic_metric.get("freeCashFlowTTM"),
        metric.get("fcfTTM"),
        basic_metric.get("fcfTTM"),
        fmp_metrics.get("freeCashFlowPerShareTTM"),
    )
    gross_margin = _to_percent(
        _pick_optional(
            metric.get("grossMarginTTM"),
            basic_metric.get("grossMarginTTM"),
            metric.get("grossMarginAnnual"),
            basic_metric.get("grossMarginAnnual"),
            fmp_ratios.get("grossProfitMarginTTM"),
        )
    )
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

    payload = {
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
    return _cache_set(generic_ttl_cache, cache_key, payload)


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
    safe_ticker = normalize_symbol(ticker)
    if not safe_ticker:
        raise HTTPException(status_code=400, detail="ticker is required")

    try:
        stock_data = get_stock_data(safe_ticker, period)
    except HTTPException as e:
        detail = str(e.detail)
        logger.warning(
            f"/api/stock-history degraded for {safe_ticker} ({period}) [{e.status_code}]: {detail}"
        )
        return []
    except Exception as e:
        logger.warning(f"/api/stock-history degraded for {safe_ticker} ({period}): {e}")
        return []
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
    if not rows:
        logger.info(f"/api/stock-history empty for {safe_ticker} ({period})")
        return []
    return _downsample_rows(rows, max_points=140)

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
    symbol = normalize_symbol(symbol)

    def _has_meaningful_recommendation(payload: Dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False

        recommendation = str(payload.get("recommendation") or "").strip().lower()
        if recommendation and recommendation not in {"n/a", "relevant data is not available."}:
            return True

        direct_numeric_fields = (
            payload.get("confidence"),
            payload.get("ai_score"),
            payload.get("sentiment_avg"),
            payload.get("upside_pct"),
        )
        if any(value is not None for value in direct_numeric_fields):
            return True

        signals = payload.get("signals") or {}
        if isinstance(signals, dict):
            for key in (
                "technical_score",
                "news_sentiment_score",
                "momentum_score",
                "volatility_risk_score",
                "forecast_30d_pct",
            ):
                if signals.get(key) is not None:
                    return True

        technical = payload.get("technical_indicators") or {}
        if isinstance(technical, dict):
            for key in ("rsi", "macd", "macd_signal", "ma50", "ma200"):
                if technical.get(key) is not None:
                    return True

        news_dist = payload.get("news_sentiment_distribution") or {}
        if isinstance(news_dist, dict) and any(news_dist.get(key) is not None for key in ("bullish", "neutral", "bearish")):
            return True

        return False

    def _fallback_recommendation_payload(message: str) -> Dict[str, Any]:
        return jsonable_encoder({
            "symbol": symbol,
            "current_price": None,
            "target_price": None,
            "target_price_high": None,
            "target_price_low": None,
            "upside_pct": None,
            "recommendation": "N/A",
            "simple_action": "",
            "confidence": None,
            "risk_level": "N/A",
            "ai_score": None,
            "sentiment_avg": None,
            "signals": {},
            "weights": {},
            "technical_indicators": {},
            "news_sentiment_distribution": {},
            "forecast": {},
            "sources": [],
            "window_days": window_days,
            "available": False,
            "error": message,
        })

    try:
        payload = compute_recommendation(symbol, window_days=window_days)
        if payload.get("error"):
            raise ValueError(payload["error"])
        if not _has_meaningful_recommendation(payload):
            raise ValueError("Relevant data is not available.")

        rec = str(payload.get("recommendation", "Hold"))
        rec_lower = rec.lower()
        if "strong buy" in rec_lower or rec_lower == "buy" or rec_lower == "hold":
            simple_action = "ถือลงทุน"
        else:
            simple_action = "เลี่ยงหุ้น"

        return jsonable_encoder({
            "symbol": payload["symbol"],
            "current_price": payload["current_price"],
            "target_price": payload.get("target_price_mean"),
            "target_price_high": payload.get("target_price_high"),
            "target_price_low": payload.get("target_price_low"),
            "upside_pct": payload.get("upside_pct"),
            "recommendation": rec,
            "simple_action": simple_action,
            "confidence": payload.get("confidence"),
            "risk_level": payload.get("risk_level") or "Relevant data is not available.",
            "ai_score": payload.get("ai_score"),
            "sentiment_avg": payload.get("sentiment_avg"),
            "signals": payload.get("signals", {}),
            "weights": payload.get("weights", {}),
            "technical_indicators": payload.get("technical_indicators", {}),
            "news_sentiment_distribution": payload.get("news_sentiment_distribution", {}),
            "forecast": payload.get("forecast", {}),
            "sources": payload.get("sources", []),
            "window_days": window_days,
            "available": True,
        })
    except ValueError as ve:
        logger.warning(f"Logical recommendation fallback for {symbol}: {ve}")
        return _fallback_recommendation_payload(str(ve))
    except HTTPException as he:
        detail = str(he.detail)
        if he.status_code >= 500:
            logger.warning(f"Upstream market data issue in /recommend for {symbol}: {detail}")
            return _fallback_recommendation_payload(f"Recommendation unavailable for {normalize_symbol(symbol)}")
        raise
    except Exception as e:
        logger.exception(f"System error in /recommend for {symbol}: {e}")
        return _fallback_recommendation_payload("เกิดข้อผิดพลาดในการคำนวณคำแนะนำ")


# Note: `recommend_endpoint` already accepts GET and POST, no additional wrapper needed

# Run local (optional)
if __name__ == "__main__":
    if fetch_and_store and DB_TABLES_READY:
        fetch_and_store(TICKERS)
        print("Data fetched, cleaned, and stored successfully.")
    else:
        print("Skipping fetch_and_store because DB runtime is unavailable.")
