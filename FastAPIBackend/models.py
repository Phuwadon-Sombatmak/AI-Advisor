import os
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import Text, Column, String, Integer, Float, DateTime
from init_db import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.db")

def utcnow():
    # PostgreSQL รองรับ timezone-aware → ใช้ UTC
    return datetime.now(timezone.utc)

# -------------------------------------------------------
# User Table
# -------------------------------------------------------
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=utcnow)

# -------------------------------------------------------
# Stock Table
# -------------------------------------------------------
class Stock(Base):
    __tablename__ = "stocks"
    id = Column(Integer, primary_key=True)
    ticker = Column(String, unique=True, nullable=False)
    name = Column(String)
    last_updated = Column(DateTime)

# -------------------------------------------------------
# Price Table
# -------------------------------------------------------
class Price(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True)
    ticker = Column(String, nullable=False)
    name = Column(String)
    last_updated = Column(DateTime)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)
# -------------------------------------------------------
# News Table
# -------------------------------------------------------
class News(Base):
    __tablename__ = "news"
    id = Column(Integer, primary_key=True)
    ticker = Column(String)
    title = Column(String)
    summary = Column(String)
    url = Column(String)
    published_at = Column(DateTime)
    sentiment = Column(Float)


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    symbol = Column(String(16), nullable=False, index=True)
    shares = Column(Float, nullable=False)
    average_buy_price = Column(Float, nullable=False)
    purchase_date = Column(String(16), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class AIRecommendationTrade(Base):
    __tablename__ = "ai_recommendation_trades"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    symbol = Column(String(16), nullable=False, index=True)
    recommendation = Column(String(32), nullable=False)
    position = Column(String(8), nullable=False)  # long / short
    size = Column(Float, nullable=False, default=1.0)
    entry_price = Column(Float, nullable=False)
    entry_time = Column(DateTime, default=utcnow, nullable=False, index=True)
    status = Column(String(16), nullable=False, default="open", index=True)
    exit_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True, index=True)
    exit_reason = Column(String(32), nullable=True)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
