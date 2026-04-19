# Forex Copier Rankings → Telegram Poster

A small Python program that reads a Google Sheet of MT4/MT5 copier
performance, filters to today's rows, and posts the top 5 ranked copiers
to a Telegram channel as formatted "cards".

**Status:** Live. Hosted on GitHub Actions, scheduled at **08:00 Singapore
time daily** (`0 0 * * *` UTC). No local machine required for posting —
your laptop can be off.

- Repo: `Sfloydzy/forex-telegram-poster` (private)
- Workflow: `.github/workflows/daily.yml`
- Cloud setup walkthrough: see `GITHUB_SETUP.md`

---

## Sheet schema

The Google Sheet must have a header row with these columns (header text is
matched case-insensitively, in any order, and a few aliases are accepted):

    Date | Rank | Copier | Net P&L ($) | Win rate | Wins | Losses | Total trades

- `Date` — required for filtering. Format `YYYY-MM-DD` is preferred; the
  script also accepts `DD/MM/YYYY`, `MM/DD/YYYY`, `1 Jan 2026`, etc.
- `Rank` — integer. Used to order the rows; falls back to ordering by
  `Net P&L` descending if Rank is empty/zero.
- `Net P&L ($)` — display string like `$1,234.56` or `-$42`. Sign is
  detected for the up/down arrow on the post.
- `Win rate` — display string like `78%` or `78.5%`.
- `Wins` / `Losses` / `Total trades` — integers (display strings).

If the sheet has additional columns the script ignores them.

## What it posts

For each scheduled run the script:

1. Fetches all rows from the Rankings tab.
2. Filters to rows whose `Date` matches **today in Singapore time** (UTC+8).
3. Sorts the remaining rows by `Rank` (or by `Net P&L` desc if Rank is empty).
4. Takes the top `top_n` (default **5**) and posts them as formatted cards
   with gold/silver/bronze emojis on the top 3 and a red-arrow indicator
   for negative P&L.

If there are no rows for today, nothing is posted (the runner logs a
"No rows for today" message and exits cleanly).

---

## Local development

You only need this section if you want to run the script on your own
machine — to dry-run formatting changes, seed test data, or debug. The
production schedule runs in the cloud and doesn't depend on local setup.

### Install dependencies

From this folder:

    python -m venv .venv
    # Windows:
    .venv\Scripts\activate
    # macOS / Linux:
    source .venv/bin/activate

    pip install -r requirements.txt

### Configure

Copy the template and fill in your values:

    # Windows
    copy config.example.json config.json
    # macOS / Linux
    cp config.example.json config.json

`config.json`:

    {
      "telegram_bot_token": "123456789:ABC...",         // from @BotFather
      "telegram_chat_id": "-1001234567890",              // numeric or @username
      "google_sheet_id": "1AbCdEf...",                   // from sheet URL
      "google_sheet_tab": "Rankings",                    // tab name
      "service_account_path": "./service_account.json",
      "top_n": 5,
      "channel_title": "Top Forex Copiers",
      "timezone_offset_hours": 8                         // optional; default 8 (SGT)
    }

`config.json` and `service_account.json` are both in `.gitignore`.

### Run

    python post_rankings.py --dry-run    # preview the message, nothing posts
    python post_rankings.py              # post the top 5 to Telegram
    python post_rankings.py --top 10     # override top-N for one run

### How config is loaded

If `config.json` is present, it's used. Otherwise the script reads the
following environment variables (this is what GitHub Actions uses):

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GOOGLE_SHEET_ID`
- `GOOGLE_SHEET_TAB`
- `GOOGLE_SERVICE_ACCOUNT_JSON` — full JSON content of the service account key
- `TOP_N` (optional, default `5`)
- `CHANNEL_TITLE` (optional, default `Top Forex Copiers`)

So the same script runs identically on your laptop and on the GitHub runner.

---

## Cloud scheduler (already set up)

The GitHub Actions workflow at `.github/workflows/daily.yml`:

- Runs `0 0 * * *` UTC daily (08:00 Singapore, year-round, no DST).
- Can also be triggered on demand via `workflow_dispatch` with optional
  `top_n` and `dry_run` inputs.
- Reads the five secrets above from the repo's encrypted secret store.
- Forces JavaScript actions onto Node.js 24 (via
  `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true`) to silence the Node 20
  deprecation warning.

To trigger a manual test run from your terminal:

    gh workflow run "Daily Forex Rankings Post" -f dry_run=true
    gh run watch

To trigger a real post:

    gh workflow run "Daily Forex Rankings Post" -f dry_run=false

For full setup instructions (creating secrets, rotating credentials,
changing the schedule), see `GITHUB_SETUP.md`.

---

## Initial Google service account setup

Only needed once, when the project is first created. If you're working with
an existing repo, the secrets and sharing are already in place — skip this
section.

1. Go to https://console.cloud.google.com/ and sign in with the Google
   account that owns the sheet.
2. Create a new project, then enable both **Google Sheets API** and
   **Google Drive API**.
3. **APIs & Services → Credentials → Create Credentials → Service Account**.
4. Click into the new service account → **Keys → Add Key → JSON**. A file
   downloads. Rename it to `service_account.json` and put it in this folder.
5. Open the JSON, copy the `client_email`, then **Share** the Google Sheet
   with that email — Viewer is enough for the production script (Editor
   only if you also want to write back from your local machine).

## Telegram bot setup

1. Talk to `@BotFather` on Telegram, `/newbot`, save the token.
2. Add the bot to your channel as an **Administrator** with at least
   "Post Messages" permission.
3. To get a private channel's numeric ID, temporarily add `@getidsbot`
   to the channel — it'll DM you the ID. Then remove it.

---

## Troubleshooting

- **`Sheet is missing required columns`** — the header row doesn't match.
  Check it has `Rank`, `Copier`, `Net P&L ($)`, `Win rate`, `Wins`,
  `Losses`, `Total trades` (Date is optional but recommended).
- **`No rows for today`** — the date filter found zero rows for today's
  Singapore date. Either today's rows aren't in the sheet yet, or their
  `Date` cells are in an unparseable format.
- **`gspread.exceptions.APIError: ... 403`** — you forgot to share the
  sheet with the service account's `client_email`.
- **`Telegram API error: ... chat not found`** — bot isn't an admin of the
  channel, or the `telegram_chat_id` is wrong.
- **`Forbidden: bot is not a member`** — add the bot to the channel as
  admin with "Post Messages" permission.
- **GitHub Actions schedule didn't fire** — GitHub may delay scheduled
  runs by several minutes under load. Check the Actions tab. Also note
  that scheduled workflows on inactive repos (no commits in 60 days)
  get auto-disabled — push a small commit periodically to keep the
  schedule alive, or use `workflow_dispatch` to verify it's still active.

## Files

- `post_rankings.py` — the script.
- `config.example.json` — config template (copy to `config.json` for local
  use).
- `requirements.txt` — Python dependencies (`gspread`, `google-auth`,
  `requests`).
- `.github/workflows/daily.yml` — GitHub Actions scheduler.
- `.gitignore` — keeps `config.json` and `service_account.json` out of git.
- `GITHUB_SETUP.md` — full walkthrough for the cloud scheduler.
- `README.md` — this file.
