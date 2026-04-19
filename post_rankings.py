"""
Forex Copier Rankings -> Telegram Channel Poster

Reads a Google Sheet with columns:
    Rank | Copier | Net P&L ($) | Win rate | Wins | Losses | Total trades

Formats the top N rows as detailed "cards" and posts to a Telegram channel
via the Bot API.

Intended to be run on-demand today, and on a scheduler (cron / Task Scheduler /
Cowork schedule / GitHub Actions) later.

Usage:
    python post_rankings.py              # posts to Telegram
    python post_rankings.py --dry-run    # prints the message, does not post
    python post_rankings.py --top 10     # override top-N (default from config)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import gspread
import requests
from google.oauth2.service_account import Credentials

CONFIG_PATH = Path(__file__).with_name("config.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Expected column headers in the sheet (case-insensitive match).
EXPECTED_COLUMNS = {
    "rank":         ["rank", "#"],
    "copier":       ["copier", "name", "trader"],
    "net_pnl":      ["net p&l ($)", "net p&l", "pnl", "p&l", "profit"],
    "win_rate":     ["win rate", "win%", "winrate"],
    "wins":         ["wins", "won"],
    "losses":       ["losses", "lost"],
    "total_trades": ["total trades", "trades", "total"],
}


# ------------------------------ config ---------------------------------------


def load_config() -> dict[str, Any]:
    """Load config from config.json if present, else from environment variables.

    Env vars (used by CI / GitHub Actions):
      TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
      GOOGLE_SHEET_ID, GOOGLE_SHEET_TAB,
      GOOGLE_SERVICE_ACCOUNT_JSON  (full JSON content of the service account key),
      TOP_N (optional), CHANNEL_TITLE (optional)
    """
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
        required = [
            "telegram_bot_token",
            "telegram_chat_id",
            "google_sheet_id",
            "google_sheet_tab",
            "service_account_path",
        ]
        missing = [k for k in required if not cfg.get(k)]
        if missing:
            sys.exit(f"config.json is missing required keys: {', '.join(missing)}")
    else:
        cfg = {
            "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
            "google_sheet_id": os.environ.get("GOOGLE_SHEET_ID", ""),
            "google_sheet_tab": os.environ.get("GOOGLE_SHEET_TAB", ""),
            "service_account_json": os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", ""),
            "top_n": int(os.environ.get("TOP_N", "5")),
            "channel_title": os.environ.get("CHANNEL_TITLE", "Top Forex Copiers"),
        }
        required = [
            "telegram_bot_token",
            "telegram_chat_id",
            "google_sheet_id",
            "google_sheet_tab",
            "service_account_json",
        ]
        missing = [k for k in required if not cfg.get(k)]
        if missing:
            sys.exit(
                "No config.json found and the following environment variables are "
                "missing: " + ", ".join(k.upper() for k in missing)
            )
    cfg.setdefault("top_n", 5)
    cfg.setdefault("channel_title", "Top Forex Copiers")
    return cfg


# ------------------------------ sheet ----------------------------------------


def fetch_rows(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Return rows as a list of dicts keyed by canonical column name."""
    if cfg.get("service_account_path"):
        creds = Credentials.from_service_account_file(
            cfg["service_account_path"], scopes=SCOPES
        )
    else:
        info = json.loads(cfg["service_account_json"])
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss = client.open_by_key(cfg["google_sheet_id"])
    ws = ss.worksheet(cfg["google_sheet_tab"])

    # get_all_values preserves the exact strings, incl. "$" and "%" which we
    # want to display as-is but also parse numerically for sorting.
    values = ws.get_all_values()
    if not values or len(values) < 2:
        return []

    header = [h.strip() for h in values[0]]
    header_map = _map_headers(header)

    rows: list[dict[str, Any]] = []
    for raw in values[1:]:
        if not any(cell.strip() for cell in raw):
            continue  # skip blank rows
        rec = {}
        for canonical, idx in header_map.items():
            rec[canonical] = raw[idx].strip() if idx < len(raw) else ""
        rec["_rank_num"] = _to_number(rec.get("rank", ""))
        rec["_pnl_num"] = _to_number(rec.get("net_pnl", ""))
        rows.append(rec)

    return rows


def _map_headers(header: list[str]) -> dict[str, int]:
    lowered = [h.lower().strip() for h in header]
    mapping: dict[str, int] = {}
    for canonical, aliases in EXPECTED_COLUMNS.items():
        for alias in aliases:
            if alias in lowered:
                mapping[canonical] = lowered.index(alias)
                break
    missing = [c for c in EXPECTED_COLUMNS if c not in mapping]
    if missing:
        sys.exit(
            f"Sheet is missing expected columns: {', '.join(missing)}. "
            f"Found headers: {header}"
        )
    return mapping


def _to_number(s: str) -> float:
    """Pull a number out of strings like '$1,234.56', '-$42', '67%', '12'."""
    if not s:
        return 0.0
    cleaned = s.replace("$", "").replace(",", "").replace("%", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


# ------------------------------ formatting -----------------------------------


def select_top(rows: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    """Order by sheet rank if available, otherwise by P&L descending."""
    if any(r["_rank_num"] > 0 for r in rows):
        rows = sorted(rows, key=lambda r: r["_rank_num"] or 1e9)
    else:
        rows = sorted(rows, key=lambda r: r["_pnl_num"], reverse=True)
    return rows[:top_n]


MEDALS = {1: "\U0001F947", 2: "\U0001F948", 3: "\U0001F949"}  # gold / silver / bronze


def build_message(top_rows: list[dict[str, Any]], cfg: dict[str, Any]) -> str:
    today = datetime.now(timezone.utc).strftime("%A, %b %d %Y")
    title = cfg.get("channel_title", "Top Forex Copiers")
    top_n = len(top_rows)

    lines = [
        f"<b>\U0001F3C6 {escape_html(title)} \u2014 Top {top_n}</b>",
        f"<i>{escape_html(today)} UTC</i>",
        "",
    ]

    for idx, r in enumerate(top_rows, start=1):
        medal = MEDALS.get(idx, f"#{idx}")
        copier = escape_html(r.get("copier") or "\u2014")

        pnl_raw = r.get("net_pnl") or ""
        pnl_num = r["_pnl_num"]
        pnl_display = pnl_raw if pnl_raw else f"${pnl_num:,.2f}"
        pnl_arrow = "\U0001F4C8" if pnl_num >= 0 else "\U0001F4C9"

        win_rate = escape_html(r.get("win_rate") or "\u2014")
        wins = escape_html(r.get("wins") or "0")
        losses = escape_html(r.get("losses") or "0")
        trades = escape_html(r.get("total_trades") or "0")

        lines.append(f"{medal} <b>{copier}</b>")
        lines.append(f"   {pnl_arrow} Net P&amp;L: <b>{escape_html(pnl_display)}</b>")
        lines.append(f"   \U0001F3AF Win rate: {win_rate}  ({wins}W / {losses}L)")
        lines.append(f"   \U0001F4CA Total trades: {trades}")
        lines.append("")

    # Trim trailing blank line for a cleaner post.
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def escape_html(s: str) -> str:
    # Telegram HTML parse_mode only requires these to be escaped.
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ------------------------------ telegram -------------------------------------


def send_to_telegram(message: str, cfg: dict[str, Any]) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{cfg['telegram_bot_token']}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": cfg["telegram_chat_id"],
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data


# ------------------------------ main -----------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Post forex copier rankings to Telegram.")
    parser.add_argument("--dry-run", action="store_true", help="Print the message but do not post.")
    parser.add_argument("--top", type=int, default=None, help="Override top N (default from config).")
    args = parser.parse_args()

    cfg = load_config()
    top_n = args.top or cfg.get("top_n", 5)

    rows = fetch_rows(cfg)
    if not rows:
        print("No data rows found in sheet. Nothing to post.")
        return

    top_rows = select_top(rows, top_n)
    message = build_message(top_rows, cfg)

    if args.dry_run:
        print("---- DRY RUN ----")
        print(message)
        print("---- END ----")
        return

    result = send_to_telegram(message, cfg)
    msg_id = result.get("result", {}).get("message_id")
    print(f"Posted successfully. message_id={msg_id}")


if __name__ == "__main__":
    main()
