# @author: panadodev 2026

import asyncio
import logging
import os
import re
import urllib.parse
from pathlib import Path
import sentry_sdk
import aiohttp
from dotenv import load_dotenv
from sentry_sdk.integrations.logging import LoggingIntegration

load_dotenv()


BM_TOKEN = os.getenv("BM_TOKEN")
WEBHOOK = os.getenv("WEBHOOK")
BM_ORG_ID = os.getenv("BM_ORG_ID")
CACHE_FILE = Path("sent_bans_ids.txt")
LOG_FILE = Path("ban_feed.log")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", 60))

# Initialize Sentry if DSN is provided
if os.getenv("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        send_default_pii=True,
        max_request_body_size="always",
        traces_sample_rate=1.0,
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        ],
    )
else:
    print("Warning: SENTRY_DSN not set. Errors will not be sent to Sentry.")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def load_seen_ids() -> set[str]:
    if CACHE_FILE.exists() and CACHE_FILE.stat().st_size > 0:
        return set(CACHE_FILE.read_text().split())
    return set()


def save_seen_ids(seen: set[str]) -> None:
    CACHE_FILE.write_text("\n".join(sorted(seen)))


async def bm_fetch(session: aiohttp.ClientSession, url: str) -> dict:
    log.debug("GET %s", url)
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json()


async def send_webhook(session: aiohttp.ClientSession, message: str) -> None:
    log.debug("Sending webhook message: %s", message)
    for attempt in range(5):
        async with session.post(WEBHOOK, json={"content": message}) as response:
            if response.status == 429:
                data = await response.json()
                retry_after = data.get("retry_after", 1)
                log.warning(
                    "Rate limited by Discord. Retrying after %.2fs...", retry_after
                )
                await asyncio.sleep(retry_after)
                continue
            response.raise_for_status()
            return
    log.error("Failed to send webhook after retries: %s", message)


async def fetch_latest_bans(session: aiohttp.ClientSession) -> list[tuple]:
    params_dict = {
        "page[size]": 10,
        "sort": "-timestamp",
        "include": "player",
    }
    if BM_ORG_ID:
        params_dict["filter[organization]"] = BM_ORG_ID
    params = urllib.parse.urlencode(params_dict)
    data = await bm_fetch(session, f"https://api.battlemetrics.com/bans?{params}")

    player_names = {
        item["id"]: item.get("attributes", {}).get("name", "Unknown")
        for item in data.get("included", [])
        if item.get("type") == "player"
    }

    results = []
    for ban in data.get("data", []):
        ban_id = ban["id"]
        attrs = ban.get("attributes", {})
        rels = ban.get("relationships", {})
        note = attrs.get("note", "") or ""
        note_text = re.sub(r"<[^>]+>", "", note).strip()
        if note_text.lower().endswith("hidden"):
            log.info("Skipping hidden ban %s", ban_id)
            continue

        player_id = rels.get("player", {}).get("data", {}).get("id")
        player_name = player_names.get(player_id, "Unknown") if player_id else "Unknown"
        player_name = (
            player_name.replace("https://", "").replace(".com", "").replace("@", "")
        )
        raw_reason = attrs.get("reason", "No reason given")
        reason = raw_reason.split("|")[0].strip()
        uid = attrs.get("uid", ban_id)
        results.append((ban_id, player_name, reason, uid))

    return results


async def poll_loop(session: aiohttp.ClientSession, seen_ids: set[str]) -> None:
    while True:
        try:
            bans = await fetch_latest_bans(session)
            new_bans = [
                (bid, name, reason, uid)
                for bid, name, reason, uid in bans
                if bid not in seen_ids
            ]

            for ban_id, player_name, reason, uid in new_bans:
                message = f"{player_name} - {reason}"
                await send_webhook(session, message)
                seen_ids.add(ban_id)
                log.info("Announced: %s", message)
                await asyncio.sleep(1)

            if new_bans:
                save_seen_ids(seen_ids)

        except Exception as e:
            sentry_sdk.capture_exception(e)
            log.exception("Error during poll")

        log.info("No new bans found. Next check in %ds...", POLL_INTERVAL)

        await asyncio.sleep(POLL_INTERVAL)


async def main() -> None:
    if not BM_TOKEN:
        raise SystemExit("Error: BM_TOKEN not set in .env")
    if not WEBHOOK:
        raise SystemExit("Error: WEBHOOK not set in .env")

    headers = {"Authorization": f"Bearer {BM_TOKEN}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        seen_ids = load_seen_ids()

        if not seen_ids:
            log.info("First run — seeding cache with current bans (not announcing)")
            initial = await fetch_latest_bans(session)
            seen_ids = {ban_id for ban_id, *_ in initial}
            save_seen_ids(seen_ids)
            log.info(
                "Cached %d existing ban ID(s). Now polling for new bans...",
                len(seen_ids),
            )
        else:
            log.info(
                "Loaded %d cached ban ID(s). Polling every %ds...",
                len(seen_ids),
                POLL_INTERVAL,
            )

        await poll_loop(session, seen_ids)


if __name__ == "__main__":
    asyncio.run(main())
