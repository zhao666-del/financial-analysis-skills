#!/usr/bin/env python3
"""Fetch Eastmoney mutual-fund NAV history through system curl.

The script deliberately avoids binding research logic to AKShare field names.
It requests pages sequentially, keeps source metadata, and writes normalized CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode


API = "https://api.fund.eastmoney.com/f10/lsjz"


def fetch_page(code: str, page: int, page_size: int = 100) -> dict:
    params = {
        "fundCode": code,
        "pageIndex": page,
        "pageSize": page_size,
        "startDate": "",
        "endDate": "",
    }
    url = f"{API}?{urlencode(params)}"
    cmd = [
        "curl.exe",
        "-fsSL",
        "-H",
        "Referer: https://fundf10.eastmoney.com/",
        "-H",
        "User-Agent: Mozilla/5.0",
        url,
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True)
    return json.loads(proc.stdout.decode("utf-8"))


def fetch_all(code: str, sleep_seconds: float = 0.15) -> tuple[list[dict], dict]:
    first = fetch_page(code, 1)
    total = int(first.get("TotalCount") or 0)
    page_size = int(first.get("PageSize") or 20)
    pages = max(1, (total + page_size - 1) // page_size)
    rows = list((first.get("Data") or {}).get("LSJZList") or [])

    for page in range(2, pages + 1):
        time.sleep(sleep_seconds)
        payload = fetch_page(code, page)
        rows.extend((payload.get("Data") or {}).get("LSJZList") or [])

    rows.sort(key=lambda row: row.get("FSRQ") or "")
    metadata = {
        "fund_code": code,
        "source": "东方财富基金历史净值接口",
        "source_url": API,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(rows),
        "first_date": rows[0]["FSRQ"] if rows else None,
        "last_date": rows[-1]["FSRQ"] if rows else None,
        "notes": "二级数据源；重大区间收益需与基金定期报告抽样核对。",
    }
    return rows, metadata


def write_outputs(rows: list[dict], metadata: dict, csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "nav", "accumulated_nav", "daily_growth_pct"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "date": row.get("FSRQ"),
                    "nav": row.get("DWJZ"),
                    "accumulated_nav": row.get("LJJZ"),
                    "daily_growth_pct": row.get("JZZZL"),
                }
            )
    csv_path.with_suffix(".meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("code", help="Six-digit fund code")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--sleep", type=float, default=0.15)
    args = parser.parse_args()
    rows, metadata = fetch_all(args.code, args.sleep)
    write_outputs(rows, metadata, args.out)
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
