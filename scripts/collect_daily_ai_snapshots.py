#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "FastAPIBackend"
LOG_DIR = REPO_ROOT / "qa" / "results"
LOG_FILE = LOG_DIR / "ai_backtest_collection_history.jsonl"
BACKUP_FILE = LOG_DIR / "ai_backtest_backup_latest.json"
ARCHIVE_DIR = LOG_DIR / "history"


def main() -> int:
    sys.path.insert(0, str(BACKEND_DIR))

    import main as backend_main  # pylint: disable=import-error

    symbols = [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "GOOGL",
        "META",
        "TSLA",
        "JPM",
        "XOM",
        "UNH",
    ]
    horizons = [7, 14]

    result = backend_main._collect_ai_recommendation_snapshots(  # noqa: SLF001
        symbols=symbols,
        horizons=horizons,
        window_days=14,
    )

    payload = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        **result,
    }

    backup_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reports": {
            "7d": backend_main.ai_backtest_report("7", 500),
            "14d": backend_main.ai_backtest_report("14", 500),
        },
        "historical": {
            "7d": backend_main.ai_backtest_historical(7, 500, 100000.0),
            "14d": backend_main.ai_backtest_historical(14, 500, 100000.0),
        },
    }

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    BACKUP_FILE.write_text(json.dumps(backup_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    archive_file = ARCHIVE_DIR / f"ai_backtest_backup_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    archive_file.write_text(json.dumps(backup_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        **payload,
        "backup_report_file": str(BACKUP_FILE),
        "backup_archive_file": str(archive_file),
        "historical_7_status": backup_payload["historical"]["7d"].get("status"),
        "historical_14_status": backup_payload["historical"]["14d"].get("status"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
