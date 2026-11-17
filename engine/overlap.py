"""For people on a protected list (e.g. Grayson Foundation updates), count
which other tags they also have. Saves counts only, no email addresses, to
reports/<group>-overlap.json."""
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from check import ROOT, get  # noqa: E402  (paced Kit GET with 429 retry)
from send import PROTECTED  # noqa: E402


def tag_ids_by_name():
    out, after = {}, None
    while True:
        page = get("/tags?per_page=1000" + (f"&after={after}" if after else ""))
        for t in page.get("tags", []):
            out[t["name"].strip().lower()] = t["id"]
        p = page.get("pagination", {})
        if not p.get("has_next_page"):
            return out
        after = p.get("end_cursor")


def members(tag_id):
    ids, after = [], None
    while True:
        page = get(f"/tags/{tag_id}/subscribers?per_page=1000"
                   + (f"&after={after}" if after else ""))
        ids += [s["id"] for s in page.get("subscribers", [])]
        p = page.get("pagination", {})
        if not p.get("has_next_page"):
            return ids
        after = p.get("end_cursor")


def main():
    names = tag_ids_by_name()
    for group, tag_names in PROTECTED.items():
        own = {names[n.strip().lower()] for n in tag_names}
        people = sorted({sid for tid in own for sid in members(tid)})
        other_tags, only_this = Counter(), 0
        for sid in people:
            tags = [t["name"] for t in get(f"/subscribers/{sid}/tags?per_page=1000").get("tags", [])
                    if t["id"] not in own]
            if not tags:
                only_this += 1
            other_tags.update(tags)
        report = {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "group": group,
            "protected_tags": tag_names,
            "people": len(people),
            "people_with_no_other_tag": only_this,
            "other_tags": other_tags.most_common(),
        }
        out = ROOT / "reports" / f"{group}-overlap.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(report, indent=2))
        print(json.dumps({k: v for k, v in report.items() if k != "other_tags"}))


if __name__ == "__main__":
    main()
