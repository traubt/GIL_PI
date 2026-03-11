from datetime import datetime, timezone
from flask import current_app
from .models import db, TOCUserActivity


def log_user_activity(user_data: dict | None, activity: str, shop: str | None = None, commit: bool = False):
    """
    Generic helper to write to toc_user_activity.

    Args:
        user_data: session user dict
        activity: text to save in toc_user_activity.activity
        shop: optional explicit shop override
        commit: if True, commits immediately. Usually keep False and let caller commit.
    """
    try:
        user_data = user_data or {}

        user_name = (
            user_data.get("username")
            or user_data.get("user")
            or user_data.get("name")
            or user_data.get("full_name")
            or user_data.get("email")
            or "unknown"
        )

        user_shop = (
            shop
            or user_data.get("shop")
            or user_data.get("shop_id")
            or user_data.get("blName")
            or "GIL-PI"
        )

        row = TOCUserActivity(
            actv_date=datetime.now(timezone.utc),
            user=user_name,
            shop=user_shop,
            activity=(activity or "").strip()[:100]
        )

        db.session.add(row)

        if commit:
            db.session.commit()

        return row

    except Exception:
        current_app.logger.exception("log_user_activity failed")
        return None