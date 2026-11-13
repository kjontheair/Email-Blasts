"""Sends any issue marked `status: send` to Kit, once.

Run by GitHub Actions whenever an issue file changes. Each issue that is
handed to Kit gets a receipt in sent/ so it can never go out twice.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).parent))
from build import ROOT, email_html, parse_issue, send_time_utc  # noqa: E402

API = "https://api.kit.com/v4/broadcasts"


def post_to_kit(payload: dict, key: str) -> dict:
    req = Request(API, data=json.dumps(payload).encode(), method="POST", headers={
        "X-Kit-Api-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urlopen(req, timeout=60) as r:
            return json.load(r)
    except HTTPError as e:
        raise SystemExit(f"Kit said no ({e.code}): {e.read().decode()[:500]}")


def kit_tags(key: str) -> dict:
    """Tag name (lowercase) → id, so issues can say `to: PurrCon Partners`."""
    tags, after = {}, None
    while True:
        url = "https://api.kit.com/v4/tags?per_page=1000" + (f"&after={after}" if after else "")
        req = Request(url, headers={"X-Kit-Api-Key": key, "Accept": "application/json"})
        with urlopen(req, timeout=60) as r:
            data = json.load(r)
        for t in data.get("tags", []):
            tags[t["name"].strip().lower()] = t["id"]
        page = data.get("pagination", {})
        if not page.get("has_next_page"):
            return tags
        after = page.get("end_cursor")


# Tags whose people only get emails about that topic. An "everyone" email
# leaves them out unless the issue says `include: grayson` (or the tag name).
PROTECTED = {
    "grayson": ["KJ's Krew:Send me Grayson Foundation updates"],
}


def _names(value):
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def _ids(names, tags):
    missing = [n for n in names if n.strip().lower() not in tags]
    if missing:
        raise SystemExit(f"No Kit tag named: {', '.join(missing)} — nothing was sent")
    return [tags[n.strip().lower()] for n in names]


def audience_filter(meta, key: str):
    """Who gets it.

    to: missing/'everyone'  -> whole list minus PROTECTED groups (unless included)
    to: tag or list of tags -> only people with any of those tags
    include: grayson        -> an 'everyone' email also goes to Grayson-only people
    """
    to = _names(meta.get("to", "everyone"))
    included = {n.strip().lower() for n in _names(meta.get("include"))}
    tags = kit_tags(key)

    if [n.strip().lower() for n in to] == ["everyone"]:
        skip = [t for group, names in PROTECTED.items() if group not in included
                for t in names if t.strip().lower() not in included]
        if not skip:
            return None
        return [{"none": [{"type": "tag", "ids": _ids(skip, tags)}]}]

    return [{"any": [{"type": "tag", "ids": _ids(to, tags)}]}]


def main():
    key = os.environ.get("KIT_API_KEY")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not key:
        raise SystemExit("KIT_API_KEY secret is missing")
    receipts = ROOT / "sent"
    receipts.mkdir(exist_ok=True)

    for issue in sorted((ROOT / "issues").glob("*.md")):
        receipt = receipts / (issue.stem + ".json")
        meta, body = parse_issue(issue)
        status = str(meta.get("status", "draft")).lower()
        if status not in ("send", "kit-draft"):
            print(f"skip (not marked send): {issue.name}")
            continue
        if receipt.exists():
            print(f"skip (already sent): {issue.name}")
            continue

        send_at = send_time_utc(meta)
        if status == "send" and send_at < datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"):
            raise SystemExit(f"{issue.name}: send_at {meta.get('send_at')} is in the past")

        payload = {
            "subject": meta["subject"],
            "preview_text": meta["preview"],
            "description": f"SuPURR Community · Pawsitive Vibes — {issue.stem}",
            "content": email_html(meta, body, repo),
            "public": bool(meta.get("public", True)),
            "published_at": send_at,
            "send_at": None if status == "kit-draft" else send_at,
        }
        audience = audience_filter(meta, key)
        if audience:
            payload["subscriber_filter"] = audience
            if _names(meta.get("to", "everyone")) != ["everyone"]:
                payload["public"] = bool(meta.get("public", False))  # group emails stay private
        result = post_to_kit(payload, key)
        bid = result.get("broadcast", {}).get("id")
        receipt.write_text(json.dumps(
            {"broadcast_id": bid, "send_at": payload["send_at"], "status": status, "subject": meta["subject"]},
            indent=2))
        print(f"{'saved as Kit draft (not sent)' if status == 'kit-draft' else 'scheduled'} {issue.name} → Kit broadcast {bid} at {send_at} UTC")


if __name__ == "__main__":
    main()
