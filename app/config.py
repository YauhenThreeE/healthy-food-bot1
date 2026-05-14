from __future__ import annotations

import os


def get_admin_id() -> int | None:
    raw = (os.getenv("ADMIN_ID") or os.getenv("ADMIN_TELEGRAM_ID") or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None
