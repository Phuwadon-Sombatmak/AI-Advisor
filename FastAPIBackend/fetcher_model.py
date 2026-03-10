import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.resolve()))

from datetime import datetime, timezone
import math
from contextlib import contextmanager

import yfinance as yf
from sqlalchemy import select

from init_db import SessionLocal, engine, Base
from models import Stock, Price, News

def score_text(text):
    return 0

Base.metadata.create_all(bind=engine)

@contextmanager
def get_db_cm():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def _safe_str(val, default="Unknown"):
    if val is None or str(val).strip() == "":
        return default
    return str(val).strip()

def _safe_datetime(val=None):
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    return datetime.now(timezone.utc)

def _safe_float(x, default=0.0):
    try:
        # Prevent NaN float from leaking into JSON parsing downstream
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return default
        return float(x)
    except Exception:
        return default

def fetch_and_store(tickers: list[str]):
    print(f"Starting fetch_and_store for {len(tickers)} tickers...")
    
    with get_db_cm() as session:
        for symbol in tickers:
            try:
                stock = yf.Ticker(symbol)
                news_items = stock.news if hasattr(stock, 'news') else []
                to_add = []
                
                for n in news_items:
                    url = _safe_str(n.get("link", n.get("url")))
                    title = _safe_str(n.get("title"))
                    
                    # Ensure published_at translates flawlessly to ISO format
                    pub_raw = n.get("providerPublishTime", n.get("published_at"))
                    if isinstance(pub_raw, (int, float)):
                        published_at = datetime.fromtimestamp(pub_raw, tz=timezone.utc)
                    else:
                        published_at = _safe_datetime(pub_raw)
                        
                    dup = session.execute(
                        select(News).where(
                            News.ticker == symbol,
                            News.url == url,
                            News.published_at == published_at,
                        )
                    ).scalar_one_or_none()

                    if dup:
                        continue

                    summary = _safe_str(n.get("summary", n.get("publisher", "")))

                    to_add.append(
                        News(
                            ticker=symbol,
                            title=title[:500],
                            summary=summary[:2000],
                            url=url,
                            published_at=published_at,
                            sentiment=0.0,
                        )
                    )

                if to_add:
                    session.add_all(to_add)
                    session.commit()
                    
            except Exception as e:
                # Crucial Fix: Rollback failed transaction so next ticker doesn't crash
                print(f"Error processing {symbol}: {e}")
                session.rollback() 
                continue

    print("fetch_and_store completed successfully on PostgreSQL.")
    
if __name__ == "__main__":
    tickers = ["UNH", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AMD", "MU", "TSM", "NVO", "BRK-A"]
    fetch_and_store(tickers)