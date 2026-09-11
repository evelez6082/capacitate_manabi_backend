from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg
from psycopg.rows import dict_row

from app.config import get_settings
from app.whatsapp_reports import REPORT_SLOT_LABELS, WhatsAppReportError, run_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Envía el reporte programado por WhatsApp y correo.")
    parser.add_argument("--slot", required=True, choices=REPORT_SLOT_LABELS.keys())
    args = parser.parse_args()
    settings = get_settings()

    try:
        with psycopg.connect(settings.database_url, row_factory=dict_row) as conn:
            result = run_report(conn, settings, args.slot)
    except WhatsAppReportError as exc:
        parser.exit(1, f"Error: {exc}\n")
    except psycopg.Error as exc:
        parser.exit(1, f"Error de base de datos: {exc}\n")

    print(json.dumps(result, ensure_ascii=False))
    return 1 if result["status"] in {"partial", "failed"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
