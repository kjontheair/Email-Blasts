# Pawsitive Vibes

KJ's newsletter, built and sent from Claude.

- `issues/` — one file per newsletter. `status: draft` = preview only; `status: kit-draft` = saved in Kit as an unsent draft; `status: send` = goes out at `send_at` (Eastern, or `now`). `to:` = tag(s), or omit for everyone. Everyone-emails skip Grayson-only people unless `include: grayson`.
- `images/` — photos used in issues.
- `sent/` — receipts the robot writes after handing an issue to Kit. An issue with a receipt never sends again.
- `engine/` — turns issues into branded email and hands them to Kit.

One-time setup: add a repository secret named `KIT_API_KEY` (Settings → Secrets and variables → Actions) containing a Kit V4 API key.
