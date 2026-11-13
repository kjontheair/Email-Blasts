"""Connection check: confirms the Kit key works and lists every tag with its
subscriber count. Writes reports/kit-check.json (no email addresses)."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
KEY = os.environ.get("KIT_API_KEY", "")


def get(path):
    req = Request("https://api.kit.com/v4" + path,
                  headers={"X-Kit-Api-Key": KEY, "Accept": "application/json"})
    with urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    report = {"checked_at": datetime.now(timezone.utc).isoformat()}
    try:
        acct = get("/account")
        report["ok"] = True
        report["account_name"] = acct.get("account", {}).get("name")
        report["plan"] = acct.get("account", {}).get("plan_type") or acct.get("plan")
        subs = get("/subscribers?per_page=1&include_total_count=true")
        report["total_subscribers"] = subs.get("pagination", {}).get("total_count")
        tags, after = [], None
        while True:
            page = get("/tags?per_page=1000" + (f"&after={after}" if after else ""))
            tags += page.get("tags", [])
            p = page.get("pagination", {})
            if not p.get("has_next_page"):
                break
            after = p.get("end_cursor")
        out = []
        for t in tags:
            c = get(f"/tags/{t['id']}/subscribers?per_page=1&include_total_count=true")
            out.append({"name": t["name"], "id": t["id"],
                        "count": c.get("pagination", {}).get("total_count")})
        report["tags"] = sorted(out, key=lambda x: -(x["count"] or 0))
    except HTTPError as e:
        report["ok"] = False
        report["error"] = f"{e.code}: {e.read().decode()[:300]}"
    path = ROOT / "reports" / "kit-check.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "tags"}, indent=2))


if __name__ == "__main__":
    main()
