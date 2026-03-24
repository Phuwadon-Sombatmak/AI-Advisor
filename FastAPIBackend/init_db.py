# init_db.py
from sqlalchemy import create_engine, text
from contextlib import contextmanager
from sqlalchemy.orm import Session, sessionmaker, declarative_base
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# ใช้ DATABASE_URL จาก environment หรือ SQLite เริ่มต้น
DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_FALLBACK_URL = f"sqlite:///{(Path(__file__).resolve().parent / 'local_fallback.db').as_posix()}"

# ตรวจสอบว่ารันใน Docker หรือไม่ และแก้ไข localhost เป็นชื่อ service 'project-db' โดยอัตโนมัติ
if DATABASE_URL and os.path.exists("/.dockerenv"):
    if "localhost" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("localhost", "project-db")
    elif "127.0.0.1" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.replace("127.0.0.1", "project-db")

def _make_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def _select_database_url() -> str:
    primary = DATABASE_URL or SQLITE_FALLBACK_URL
    if primary.startswith("sqlite"):
        return primary
    try:
        test_engine = _make_engine(primary)
        with test_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return primary
    except Exception:
        return SQLITE_FALLBACK_URL


ACTIVE_DATABASE_URL = _select_database_url()
engine = _make_engine(ACTIVE_DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True
)

Base = declarative_base()

@contextmanager
def get_db():
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except:
        db.rollback()
        raise
    finally:
        db.close()
