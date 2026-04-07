#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "FastAPIBackend"
OUTPUT_DIR = REPO_ROOT / "qa" / "results"
OUTPUT_FILE = OUTPUT_DIR / "ai_backtest_backup_latest.json"
ARCHIVE_DIR = OUTPUT_DIR / "history"


def main() -> int:
    sys.path.insert(0, str(BACKEND_DIR))

    import main as backend_main  # pylint: disable=import-error

    generated_at = datetime.now(timezone.utc).isoformat()
    report_7 = backend_main.ai_backtest_report("7", 500)
    report_14 = backend_main.ai_backtest_report("14", 500)
    historical_7 = backend_main.ai_backtest_historical(7, 500, 100000.0)
    historical_14 = backend_main.ai_backtest_historical(14, 500, 100000.0)

    payload = {
        "generated_at": generated_at,
        "reports": {
            "7d": report_7,
            "14d": report_14,
        },
        "historical": {
            "7d": historical_7,
            "14d": historical_14,
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    archive_file = ARCHIVE_DIR / f"ai_backtest_backup_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    archive_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {
        "generated_at": generated_at,
        "report_7_open": ((report_7 or {}).get("summary") or {}).get("open_snapshots"),
        "report_14_open": ((report_14 or {}).get("summary") or {}).get("open_snapshots"),
        "historical_7_status": historical_7.get("status"),
        "historical_14_status": historical_14.get("status"),
        "output_file": str(OUTPUT_FILE),
        "archive_file": str(archive_file),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
