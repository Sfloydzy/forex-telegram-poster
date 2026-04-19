# GitHub Actions — Free Daily Scheduler Setup

This guide wires the project up to run on GitHub's free scheduled runners at
**08:00 Singapore time every day** (`0 0 * * *` UTC, since SGT is UTC+8 year
round). Cost: $0 on a private repo — this uses ~15 seconds per run against a
2,000-minute monthly free tier.

You'll use the `gh` CLI for everything. Total time: ~5 minutes.

---

## What GitHub Actions will do

Every day at 00:00 UTC, GitHub spins up a fresh Ubuntu VM, installs Python,
runs `post_rankings.py --top 10` using your secrets, and destroys the VM. You
pay nothing, maintain nothing, and the post goes out even if your laptop is
off.

You can also click a button in the GitHub UI to run it on demand at any time.

---

## 1. Confirm gh CLI is authenticated

    gh auth status

If it says you're not signed in, run `gh auth login` and pick HTTPS + your
web browser. Come back here when `gh auth status` shows you signed in.

## 2. Create a private repo and push this folder

From inside `forex-telegram-poster/`:

    # Initialize git
    git init -b main
    git add .
    git commit -m "Initial commit: forex rankings poster"

    # Create a PRIVATE GitHub repo and push in one shot
    gh repo create forex-telegram-poster --private --source=. --remote=origin --push

After this, `gh repo view --web` will open the new repo in your browser.

### Sanity check: verify secrets are NOT in the commit

    git log --stat

Confirm **neither** `config.json` **nor** `service_account.json` appear in the
list. They shouldn't — the project's `.gitignore` already excludes them. If
they *did* get committed by mistake, stop here and rotate both credentials
(new bot token from BotFather, new service account key from Google Cloud)
before pushing to GitHub.

## 3. Add the five repository secrets

Run each of these from inside the project folder. They read the values
directly from your local `config.json` / `service_account.json` and pipe them
into GitHub's encrypted secret store.

    # Telegram
    gh secret set TELEGRAM_BOT_TOKEN --body "$(jq -r .telegram_bot_token config.json)"
    gh secret set TELEGRAM_CHAT_ID   --body "$(jq -r .telegram_chat_id   config.json)"

    # Google Sheet
    gh secret set GOOGLE_SHEET_ID  --body "$(jq -r .google_sheet_id  config.json)"
    gh secret set GOOGLE_SHEET_TAB --body "$(jq -r .google_sheet_tab config.json)"

    # Service account (entire JSON file, piped in)
    gh secret set GOOGLE_SERVICE_ACCOUNT_JSON < service_account.json

Verify:

    gh secret list

You should see all five. Their values are encrypted — GitHub never reveals
them again, only the workflow can read them at runtime.

> Don't have `jq`? On macOS: `brew install jq`. On Windows: install via scoop
> or just copy the values into the commands by hand.

## 4. Trigger a test run (manual, dry-run)

Don't wait until tomorrow morning to find out something's wrong. Run it once
manually in dry-run mode first — the workflow will print the formatted
message to the Actions log without posting to Telegram.

    gh workflow run "Daily Forex Rankings Post" -f dry_run=true -f top_n=10

Watch the run:

    gh run watch

Or view in the browser:

    gh run list --workflow="Daily Forex Rankings Post"
    gh run view --web

If the log shows the formatted top-10 message, you're done — secrets are
plumbed correctly.

## 5. Trigger a real manual run (posts to Telegram)

    gh workflow run "Daily Forex Rankings Post" -f dry_run=false -f top_n=10
    gh run watch

Check your Telegram channel — a new post should appear within ~30 seconds.

## 6. Done — it now runs daily

The scheduled trigger is already active. Tomorrow at 00:00 UTC (08:00 SGT)
it will run automatically. You can leave the computer off; the runner is
hosted on GitHub's infrastructure.

---

## Changing the schedule later

Edit the `cron:` line in `.github/workflows/daily.yml`, commit, and push.
GitHub picks up the new schedule on the next push. Cron is always **UTC** in
GitHub Actions — there is no way to specify a local timezone.

Common conversions (no DST in Singapore, so these don't shift):

| Local time you want (SGT) | Cron line (UTC)    |
|---------------------------|--------------------|
| 06:00 SGT                 | `0 22 * * *`       |
| 07:00 SGT                 | `0 23 * * *`       |
| 08:00 SGT (current)       | `0 0  * * *`       |
| 09:00 SGT                 | `0 1  * * *`       |
| 12:00 SGT (midday)        | `0 4  * * *`       |
| 18:00 SGT                 | `0 10 * * *`       |

You can also have multiple schedules, e.g. morning + evening:

    - cron: "0 0 * * *"    # 08:00 SGT
    - cron: "0 10 * * *"   # 18:00 SGT

### A note on scheduling accuracy

GitHub Actions scheduled runs **can be delayed by several minutes** when the
service is under heavy load. For a copier rankings post this is fine. If you
ever need minute-precise posting, move to an always-on host (small VPS,
Cloudflare Workers cron, etc.) — but for daily cadence, Actions is plenty
reliable.

---

## Rotating credentials

If the bot token ever leaks:

    # Get a new token from @BotFather (/revoke → /token)
    gh secret set TELEGRAM_BOT_TOKEN --body "NEW_TOKEN_HERE"

If the service account key leaks, create a new key in Google Cloud Console
(IAM → Service Accounts → Keys → Add Key → delete the old one) and then:

    gh secret set GOOGLE_SERVICE_ACCOUNT_JSON < new_service_account.json

## Cost and quota

- **Private repo**: 2,000 free Actions minutes/month. One run ≈ 15s ≈ 0.25
  minutes. Daily for a month ≈ 7.5 minutes. You'd burn **0.4% of the quota**.
- **Public repo**: Actions minutes are unlimited for public repos.
- **Storage for the workflow logs**: negligible (<10 MB).

So: free, effectively forever.

## Stopping the schedule

Three options, in increasing levels of permanence:

1. Disable the workflow (keeps the code, pauses the schedule):
   `gh workflow disable "Daily Forex Rankings Post"`
2. Re-enable later with `gh workflow enable "Daily Forex Rankings Post"`.
3. Delete the workflow file and push.
