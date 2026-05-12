import json
import os
import re
import urllib.parse
import urllib.request
from dotenv import load_dotenv

load_dotenv()

BM_TOKEN = os.getenv("BM_TOKEN")
BM_ORG_ID = os.getenv("BM_ORG_ID")

if not BM_TOKEN:
    raise SystemExit(
        "Error: BM_TOKEN not set.\n"
        "Add it to your .env file: BM_TOKEN=your_token_here"
    )


def fetch(url):
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {BM_TOKEN}"},
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read())


# Print raw full response for debugging
params_dict = {
    "page[size]": 10,
    "sort": "-timestamp",
    "include": "player,server",
}
if BM_ORG_ID:
    params_dict["filter[organization]"] = BM_ORG_ID
params = urllib.parse.urlencode(params_dict)
url = f"https://api.battlemetrics.com/bans?{params}"
print(f"Requesting: {url}\n")
data = fetch(url)
print("Raw response:")
print(json.dumps(data, indent=2))
print()
bans = data.get("data", [])
meta = data.get("meta", {})

print(
    f"Fetched {len(bans)} ban(s)  (active={meta.get('active', '?')}, total={meta.get('total', '?')})\n"
)

for i, ban in enumerate(bans, 1):
    attrs = ban.get("attributes", {})
    rels = ban.get("relationships", {})

    note = attrs.get("note", "") or ""
    note_text = re.sub(r"<[^>]+>", "", note).strip()
    if note_text.lower().endswith("hidden"):
        print(f"[{i}] Ban ID {ban['id']} skipped (hidden)")
        continue

    player_id = rels.get("player", {}).get("data", {}).get("id", "N/A")
    server_id = rels.get("server", {}).get("data", {}).get("id", "N/A")

    print(f"[{i}] Ban ID    : {ban['id']}")
    print(f"     UID       : {attrs.get('uid', 'N/A')}")
    print(f"     Player ID : {player_id}")
    print(f"     Server ID : {server_id}")
    raw_reason = attrs.get("reason", "N/A")
    reason = raw_reason.split("|")[0].strip() if raw_reason != "N/A" else "N/A"
    print(f"     Reason    : {reason}")
    print(f"     Timestamp : {attrs.get('timestamp', 'N/A')}")
    print(f"     Expires   : {attrs.get('expires', 'N/A')}")
    print()
    print(f"     Native       : {attrs.get('nativeEnabled', 'N/A')}")
    print()
