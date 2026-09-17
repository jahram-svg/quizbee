import os
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import requests
from flask import Blueprint, jsonify, request
from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import validate_telegram_init_data
from backend.admin import require_admin, admin_error


notifications_bp = Blueprint(
    "notifications",
    __name__,
    url_prefix="/api/notifications"
)


def now():
    return datetime.now(timezone.utc)


def serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: serialize(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            serialize(item)
            for item in value
        ]

    return value


def get_authenticated_user():
    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        ""
    )

    if not init_data:
        return None

    user = validate_telegram_init_data(init_data)

    if not user:
        return None

    return {
        "telegram_id": str(user["id"])
    }


def make_notification_id(
    user_id,
    dedupe_key=None
):
    if dedupe_key:
        raw = (
            f"{user_id}:{dedupe_key}"
        ).encode("utf-8")

        return (
            "evt_"
            + hashlib.sha256(raw)
            .hexdigest()[:40]
        )

    return "ntf_" + uuid4().hex


def create_notification(
    user_id,
    title,
    message,
    notification_type="general",
    action_url="",
    button_text="",
    dedupe_key=None,
    send_telegram=False
):
    user_id = str(user_id)

    notification_id = make_notification_id(
        user_id,
        dedupe_key
    )

    ref = (
        db.collection("notifications")
        .document(notification_id)
    )

    existing = ref.get()

    if existing.exists:
        data = existing.to_dict() or {}

        return serialize({
            "id": notification_id,
            **data
        })

    payload = {
        "user_id": user_id,
        "title": str(title)[:120],
        "message": str(message)[:4000],
        "type": str(notification_type)[:50],
        "action_url": str(action_url or "")[:500],
        "button_text": str(button_text or "")[:80],
        "read": False,
        "created_at": now(),
        "updated_at": now()
    }

    if dedupe_key:
        payload["dedupe_key"] = str(
            dedupe_key
        )[:200]

    ref.set(payload)

    if send_telegram:
        send_telegram_message(
            user_id,
            f"<b>{payload['title']}</b>\n\n"
            f"{payload['message']}",
            button_text=payload["button_text"],
            button_url=payload["action_url"]
        )

    return serialize({
        "id": notification_id,
        **payload
    })


def send_telegram_message(
    chat_id,
    text,
    button_text="",
    button_url=""
):
    token = os.getenv(
        "BOT_TOKEN",
        ""
    ).strip()

    if not token:
        return {
            "ok": False,
            "error": "BOT_TOKEN is not configured."
        }

    payload = {
        "chat_id": str(chat_id),
        "text": str(text)[:4096],
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    if button_text and button_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[
                {
                    "text": str(button_text)[:64],
                    "url": str(button_url)
                }
            ]]
        }

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=15
        )

        return response.json()

    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc)
        }


# ============================================================
# USER NOTIFICATIONS
# ============================================================

@notifications_bp.get("")
def get_notifications():

    user = get_authenticated_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    try:

        docs = (
            db.collection("notifications")
            .where(
                "user_id",
                "==",
                user["telegram_id"]
            )
            .order_by(
                "created_at",
                direction=firestore.Query.DESCENDING
            )
            .limit(50)
            .stream()
        )

        notifications = []
        unread_count = 0

        for doc in docs:

            data = doc.to_dict() or {}

            item = serialize({
                "id": doc.id,
                **data
            })

            notifications.append(item)

            if not data.get("read", False):
                unread_count += 1

        return jsonify({
            "success": True,
            "notifications": notifications,
            "unread_count": unread_count
        })

    except Exception as exc:

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500


@notifications_bp.post(
    "/<notification_id>/read"
)
def mark_notification_read(
    notification_id
):

    user = get_authenticated_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    try:

        ref = (
            db.collection("notifications")
            .document(notification_id)
        )

        snapshot = ref.get()

        if not snapshot.exists:
            return jsonify({
                "success": False,
                "error": "Notification not found."
            }), 404

        data = snapshot.to_dict() or {}

        if str(data.get("user_id")) != user["telegram_id"]:
            return jsonify({
                "success": False,
                "error": "Notification not found."
            }), 404

        ref.update({
            "read": True,
            "updated_at": now()
        })

        return jsonify({
            "success": True
        })

    except Exception as exc:

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500


@notifications_bp.post(
    "/read-all"
)
def mark_all_notifications_read():

    user = get_authenticated_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    try:

        docs = (
            db.collection("notifications")
            .where(
                "user_id",
                "==",
                user["telegram_id"]
            )
            .where(
                "read",
                "==",
                False
            )
            .stream()
        )

        batch = db.batch()
        count = 0

        for doc in docs:

            batch.update(
                doc.reference,
                {
                    "read": True,
                    "updated_at": now()
                }
            )

            count += 1

            if count >= 400:
                batch.commit()
                batch = db.batch()
                count = 0

        if count:
            batch.commit()

        return jsonify({
            "success": True,
            "marked_read": count
        })

    except Exception as exc:

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500


# ============================================================
# ADMIN — SEND TO ONE USER
# ============================================================

@notifications_bp.post(
    "/admin/user"
)
def admin_send_to_user():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        body = request.get_json(
            silent=True
        ) or {}

        user_id = str(
            body.get("user_id", "")
        ).strip()

        title = str(
            body.get("title", "")
        ).strip()

        message = str(
            body.get("message", "")
        ).strip()

        notification_type = str(
            body.get(
                "type",
                "general"
            )
        ).strip()

        action_url = str(
            body.get(
                "action_url",
                ""
            )
        ).strip()

        button_text = str(
            body.get(
                "button_text",
                ""
            )
        ).strip()

        send_telegram = bool(
            body.get(
                "send_telegram",
                True
            )
        )

        dedupe_key = str(
            body.get(
                "dedupe_key",
                ""
            )
        ).strip() or None

        if not user_id:
            return jsonify({
                "success": False,
                "error": "User ID is required."
            }), 400

        if not title:
            return jsonify({
                "success": False,
                "error": "Title is required."
            }), 400

        if not message:
            return jsonify({
                "success": False,
                "error": "Message is required."
            }), 400

        user_ref = (
            db.collection("users")
            .document(user_id)
        )

        user_snapshot = user_ref.get()

        if not user_snapshot.exists:
            return jsonify({
                "success": False,
                "error": "User not found."
            }), 404

        notification = create_notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url,
            button_text=button_text,
            dedupe_key=dedupe_key,
            send_telegram=send_telegram
        )

        return jsonify({
            "success": True,
            "notification": notification
        })

    except Exception as exc:

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500


# ============================================================
# ADMIN — BROADCAST
# ============================================================

@notifications_bp.post(
    "/admin/broadcast"
)
def admin_broadcast():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        body = request.get_json(
            silent=True
        ) or {}

        title = str(
            body.get("title", "")
        ).strip()

        message = str(
            body.get("message", "")
        ).strip()

        notification_type = str(
            body.get(
                "type",
                "announcement"
            )
        ).strip()

        action_url = str(
            body.get(
                "action_url",
                ""
            )
        ).strip()

        button_text = str(
            body.get(
                "button_text",
                ""
            )
        ).strip()

        send_telegram = bool(
            body.get(
                "send_telegram",
                True
            )
        )

        dedupe_key = str(
            body.get(
                "dedupe_key",
                ""
            )
        ).strip() or None

        if not title or not message:
            return jsonify({
                "success": False,
                "error": "Title and message are required."
            }), 400

        users = list(
            db.collection("users")
            .stream()
        )

        created = 0
        telegram_sent = 0
        telegram_failed = 0

        for user_doc in users:

            user_id = str(
                user_doc.id
            )

            notification = create_notification(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                action_url=action_url,
                button_text=button_text,
                dedupe_key=dedupe_key,
                send_telegram=False
            )

            if notification:
                created += 1

            if send_telegram:

                result = send_telegram_message(
                    user_id,
                    f"<b>{title}</b>\n\n{message}",
                    button_text=button_text,
                    button_url=action_url
                )

                if result.get("ok") is True:
                    telegram_sent += 1
                else:
                    telegram_failed += 1

        return jsonify({
            "success": True,
            "created": created,
            "telegram_sent": telegram_sent,
            "telegram_failed": telegram_failed,
            "created_by": str(
                admin["telegram_id"]
            )
        })

    except Exception as exc:

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500
