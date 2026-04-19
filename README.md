# Forex Copier Rankings → Telegram Poster

A small Python program that reads a Google Sheet of MT4/MT5 copier performance
and posts the top-ranked copiers to a Telegram channel. Designed to run on your
computer now and move to a scheduler (cron, Task Scheduler, GitHub Actions,
Cowork schedule) later without code changes.

The sheet must have these columns (header row, in any order, case-insensitive):

    Rank | Copier | Net P&L ($) | Win rate | Wins | Losses | Total trades

---

## 1. Install Python dependencies

From this folder, in a terminal:

    python -m venv .venv
    # Windows:
    .venv\Scripts\activate
    # macOS / Linux:
    source .venv/bin/activate

    pip install -r requirements.txt

## 2. Create a Google service account (one-time, ~5 min)

1. Go to https://console.cloud.google.com/ and sign in with the Google account
   that owns the sheet.
2. Create a new project (top bar → "New Project"), name it anything.
3. In the search bar, find **"Google Sheets API"** and click **Enable**. Do the
   same for **"Google Drive API"**.
4. Go to **APIs & Services → Credentials → Create Credentials → Service
   Account**. Give it a name (e.g. `forex-poster`). No roles needed, just
   click **Done**.
5. Click the service account you just made → **Keys** tab → **Add Key → Create
   new key → JSON**. A file downloads. Rename it to `service_account.json`
   and put it **in this folder**.
6. Open the JSON and copy the `client_email` (looks like
   `forex-poster@your-project.iam.gserviceaccount.com`).
7. Open your Google Sheet → **Share** → paste that email → give **Viewer**
   access. This is what lets the bot read your sheet.

## 3. Get the Google Sheet ID and tab name

The sheet URL looks like:

    https://docs.google.com/spreadsheets/d/THIS_IS_THE_SHEET_ID/edit#gid=0

Copy the `THIS_IS_THE_SHEET_ID` part.

The tab name is whatever is shown on the tab at the bottom of the sheet (e.g.
`Sheet1`, `Rankings`).

## 4. Get your Telegram channel ID

You already have a bot token — good. The bot needs to be an **admin** of the
channel you want to post to (Channel settings → Administrators → Add Admin →
search for your bot by username).

For the chat ID you have two options:

- **Public channel**: use `@your_channel_username` (including the `@`).
- **Private channel**: you need the numeric ID (looks like `-1001234567890`).
  Fastest way: add `@getidsbot` to the channel temporarily, it will DM you the
  ID, then remove it.

## 5. Fill in config.json

Copy the template:

    # Windows
    copy config.example.json config.json
    # macOS / Linux
    cp config.example.json config.json

Open `config.json` and fill in:

    {
      "telegram_bot_token": "123456789:ABC...",          # from BotFather
      "telegram_chat_id": "@my_forex_channel",            # or -100...
      "google_sheet_id": "1AbCdEf...",                    # from step 3
      "google_sheet_tab": "Sheet1",                       # tab name
      "service_account_path": "./service_account.json",
      "top_n": 5,
      "channel_title": "Top Forex Copiers"
    }

`config.json` and `service_account.json` are both in `.gitignore` so you don't
accidentally commit them.

## 6. Dry run — preview without posting

    python post_rankings.py --dry-run

This prints the formatted message to your terminal so you can check the top 5
look right. If the output looks good, you're ready to post live.

## 7. Run it for real

    python post_rankings.py

Check the Telegram channel — a new ranked post should appear. On success the
script prints `Posted successfully. message_id=...`.

## 8. Schedule it daily (future iteration)

Since you're running on your own computer for now, here are the options for
when you're ready to automate. No code changes needed — all options just run
`python post_rankings.py` on a schedule.

### Option A — Windows Task Scheduler

1. Open Task Scheduler → Create Basic Task → "Post Forex Rankings".
2. Trigger: Daily, pick the time.
3. Action: Start a program.
   - Program: `C:\path\to\forex-telegram-poster\.venv\Scripts\python.exe`
   - Arguments: `post_rankings.py`
   - Start in: `C:\path\to\forex-telegram-poster`

### Option B — macOS / Linux cron

Edit your crontab (`crontab -e`) and add, for example, 9:00am daily:

    0 9 * * * cd /path/to/forex-telegram-poster && .venv/bin/python post_rankings.py >> poster.log 2>&1

### Option C — GitHub Actions (cloud, always-on)

Push this folder (minus `config.json` and `service_account.json`) to a private
GitHub repo. Store the secrets as repository secrets. Add a workflow at
`.github/workflows/daily.yml` that runs on a schedule and calls the script —
happy to generate this when you're ready.

### Option D — Cowork scheduled task

Ask me to "schedule this to run daily at 9am" inside Cowork once you've
confirmed the script works locally.

---

## Troubleshooting

- **`Missing config.json`** — you haven't copied `config.example.json` yet.
- **`Sheet is missing expected columns`** — the header row in your sheet
  doesn't match. Make sure the exact text (or a listed alias) is there:
  `Rank`, `Copier`, `Net P&L ($)`, `Win rate`, `Wins`, `Losses`, `Total trades`.
- **`gspread.exceptions.APIError: ... 403`** — you forgot to share the sheet
  with the service account's `client_email`.
- **`Telegram API error: ... chat not found`** — bot isn't an admin of the
  channel, or the `telegram_chat_id` is wrong.
- **`Forbidden: bot is not a member`** — add the bot to the channel as admin
  with "Post Messages" permission.

## Files in this project

- `post_rankings.py` — the script.
- `config.example.json` — template config, copy to `config.json`.
- `requirements.txt` — Python dependencies.
- `.gitignore` — keeps secrets out of git.
- `README.md` — this file.
