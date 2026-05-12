# bm-ban-feed

Polls the [BattleMetrics](https://www.battlemetrics.com) API for new bans and announces them to a Discord channel via webhook.

## How it works

- On first run, the current ban list is cached silently (no announcements).
- Every `POLL_INTERVAL` seconds, new bans are fetched and posted to Discord.
- Ban notes that end in **hidden** will not be announced.
- Seen ban IDs are persisted in `sent_bans_ids.txt` to survive restarts.
- Names with links will have the *https* and *.com* removed.
- Removes text after a | symbol (Example: "Rule violation | Appeal @ Discord.gg/server" -> "reason": "Rule violation")

## Configuration

Copy `.env` and fill in the values:

| Variable | Required | Description |
|---|---|---|
| `BM_TOKEN` | Yes | BattleMetrics API token |
| `WEBHOOK` | Yes | Discord webhook URL |
| `BM_ORG_ID` | No | Filter bans to a specific BattleMetrics organization ID |
| `POLL_INTERVAL` | No | Seconds between polls (default: `60`) |

## Running

### With Python

```bash
pip install -r requirements.txt
python main.py
```

### With Docker

```bash
docker build -t bm-ban-feed .
docker run --env-file .env bm-ban-feed
```
