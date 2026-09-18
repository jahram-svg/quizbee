"""
QuizBee Referral + Streak System

Phase 8 rules:

REFERRALS
- Referral links are based on Telegram Mini App startapp.
- No referral rewards.
- No referral notifications.
- A referral is counted only once.
- Self-referrals are rejected.
- Existing users cannot be retroactively assigned a referrer.
- Weekly/monthly referral leaderboards are Admin-only.

STREAKS
- A streak increases only when the user successfully enters a game.
- Opening QuizBee does not count.
- Opening Profile does not count.
- Watching ads does not count.
- Daily Earning does not count.
- Raffle activity does not count.
- No streak rewards.
- No streak reward transactions.
- Monthly best streak is stored for Admin reporting.
"""

from __future__ import annotations

import os

from datetime import (
    datetime,
    timezone,
    timedelta,
)

from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    jsonify,
    request,
)

from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import (
    validate_telegram_init_data,
)
from backend.admin import require_admin


referral_streak_bp = Blueprint(
    "referral_streak",
    __name__,
    url_prefix="/api",
)


# ============================================================
# TIME
# ============================================================

def platform_timezone():
    timezone_name = os.getenv(
        "QUIZBEE_TIMEZONE",
        "Africa/Lagos",
    ).strip()

    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return ZoneInfo("Africa/Lagos")


def platform_now():
    return datetime.now(
        timezone.utc
    ).astimezone(
        platform_timezone()
    )


def today_key():
    return platform_now().date().isoformat()


def month_key():
    return platform_now().strftime(
        "%Y-%m"
    )


# ============================================================
# HELPERS
# ============================================================

def user_ref(telegram_id):
    return (
        db.collection("users")
        .document(str(telegram_id))
    )


def serialize_datetime(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        ).isoformat()

    return value


def serialize_user_datetime(data):
    result = dict(data)

    for key in (
        "created_at",
        "updated_at",
        "referral_joined_at",
        "last_game_at",
    ):
        if key in result:
            result[key] = serialize_datetime(
                result[key]
            )

    return result


def parse_datetime(value):
    if not value:
        return None

    if isinstance(
        value,
        datetime,
    ):
        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc
            )

        return value.astimezone(
            timezone.utc
        )

    try:

        text = str(value)

        if text.endswith("Z"):
            text = (
                text[:-1]
                + "+00:00"
            )

        parsed = datetime.fromisoformat(
            text
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    except Exception:
        return None


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


# ============================================================
# TELEGRAM USER AUTH
# ============================================================

def require_user():

    init_data = (
        request.headers.get(
            "X-Telegram-Init-Data"
        )
        or request.headers.get(
            "X-Telegram-InitData"
        )
        or ""
    )

    if not init_data:
        return None

    user = validate_telegram_init_data(
        init_data
    )

    if not user:
        return None

    return user


# ============================================================
# REFERRAL PROCESSING
# ============================================================

def find_referrer_by_code(
    referral_code,
):

    code = str(
        referral_code or ""
    ).strip()

    if not code:
        return None

    docs = list(
        db.collection("users")
        .where(
            "referral_code",
            "==",
            code,
        )
        .limit(1)
        .stream()
    )

    if not docs:
        return None

    snap = docs[0]

    data = snap.to_dict() or {}

    data["telegram_id"] = str(
        data.get(
            "telegram_id",
            snap.id,
        )
    )

    data["_ref"] = snap.reference

    return data


def process_referral(
    telegram_id,
    referral_code,
):
    """
    Process the first referral attribution for a newly
    created QuizBee account.

    This function is intentionally silent:
    no notification is sent to the referrer.
    """

    telegram_id = str(
        telegram_id
    )

    referral_code = str(
        referral_code or ""
    ).strip()

    user_reference = user_ref(
        telegram_id
    )

    user_snapshot = user_reference.get()

    if not user_snapshot.exists:
        return False

    user_data = (
        user_snapshot.to_dict()
        or {}
    )

    # Already processed.
    if user_data.get(
        "referral_processed",
        False,
    ):
        return False

    # Find the referrer before the transaction.
    referrer = find_referrer_by_code(
        referral_code
    )

    # No usable referral code.
    if not referrer:

        user_reference.update({
            "referral_processed": True,
            "updated_at":
                firestore.SERVER_TIMESTAMP,
        })

        return False

    referrer_id = str(
        referrer.get(
            "telegram_id",
            "",
        )
    )

    # Self referral.
    if (
        not referrer_id
        or referrer_id == telegram_id
    ):

        user_reference.update({
            "referral_processed": True,
            "updated_at":
                firestore.SERVER_TIMESTAMP,
        })

        return False

    referrer_reference = (
        referrer["_ref"]
    )

    transaction = db.transaction()

    @firestore.transactional
    def attach_referral(
        tx,
    ):

        current_user = (
            user_reference.get(
                transaction=tx
            )
        )

        if not current_user.exists:
            return False

        current_data = (
            current_user.to_dict()
            or {}
        )

        # Another request already processed it.
        if current_data.get(
            "referral_processed",
            False,
        ):
            return False

        tx.update(
            user_reference,
            {
                "referred_by":
                    referrer_id,

                "referral_joined_at":
                    firestore.SERVER_TIMESTAMP,

                "referral_processed":
                    True,

                "updated_at":
                    firestore.SERVER_TIMESTAMP,
            },
        )

        tx.update(
            referrer_reference,
            {
                "referrals_count":
                    firestore.Increment(1),

                "updated_at":
                    firestore.SERVER_TIMESTAMP,
            },
        )

        return True

    return bool(
        attach_referral(
            transaction
        )
    )


# ============================================================
# GAME PARTICIPATION + STREAK
# ============================================================

def record_game_participation(
    telegram_id,
):
    """
    Call this ONLY after a successful new game entry.

    Returns the updated streak information.
    """

    telegram_id = str(
        telegram_id
    )

    reference = user_ref(
        telegram_id
    )

    current_date = (
        platform_now().date()
    )

    current_date_key = (
        current_date.isoformat()
    )

    current_month = (
        current_date.strftime(
            "%Y-%m"
        )
    )

    transaction = db.transaction()

    @firestore.transactional
    def update_participation(
        tx,
    ):

        snapshot = reference.get(
            transaction=tx
        )

        if not snapshot.exists:
            return {
                "streak_days": 0,
                "games_played_count": 0,
                "streak_month_best": 0,
            }

        data = (
            snapshot.to_dict()
            or {}
        )

        last_game_date = str(
            data.get(
                "last_game_date",
                "",
            )
            or ""
        )

        current_streak = safe_int(
            data.get(
                "streak_days",
                0,
            ),
            0,
        )

        # Same day:
        # participation increases, but streak does not.
        if last_game_date == current_date_key:

            new_streak = max(
                current_streak,
                1,
            )

        else:

            yesterday_key = (
                current_date
                - timedelta(days=1)
            ).isoformat()

            if (
                last_game_date
                == yesterday_key
            ):
                new_streak = (
                    current_streak + 1
                )

            else:
                new_streak = 1

        previous_month = str(
            data.get(
                "streak_month",
                "",
            )
            or ""
        )

        previous_month_best = safe_int(
            data.get(
                "streak_month_best",
                0,
            ),
            0,
        )

        if previous_month != current_month:

            new_month_best = new_streak

        else:

            new_month_best = max(
                previous_month_best,
                new_streak,
            )

        games_played = (
            safe_int(
                data.get(
                    "games_played_count",
                    0,
                ),
                0,
            )
            + 1
        )

        tx.update(
            reference,
            {
                "games_played_count":
                    games_played,

                "last_game_date":
                    current_date_key,

                "last_game_at":
                    firestore.SERVER_TIMESTAMP,

                "streak_days":
                    new_streak,

                "streak_month":
                    current_month,

                "streak_month_best":
                    new_month_best,

                "updated_at":
                    firestore.SERVER_TIMESTAMP,
            },
        )

        return {
            "streak_days":
                new_streak,

            "games_played_count":
                games_played,

            "streak_month_best":
                new_month_best,
        }

    return update_participation(
        transaction
    )


# ============================================================
# USER REFERRAL API
# ============================================================

@referral_streak_bp.get(
    "/referral"
)
def get_referral():

    user = require_user()

    if not user:
        return jsonify({
            "success": False,
            "error":
                "Unauthorized Telegram session.",
        }), 401

    telegram_id = str(
        user.get("id")
        or ""
    )

    snapshot = user_ref(
        telegram_id
    ).get()

    if not snapshot.exists:

        return jsonify({
            "success": False,
            "error":
                "QuizBee account not found.",
        }), 404

    data = (
        snapshot.to_dict()
        or {}
    )

    referral_code = str(
        data.get(
            "referral_code",
            "",
        )
    ).strip()

    bot_username = os.getenv(
        "TELEGRAM_BOT_USERNAME",
        "",
    ).strip().lstrip("@")

    referral_link = ""

    if bot_username and referral_code:

        referral_link = (
            "https://t.me/"
            f"{bot_username}"
            "?startapp="
            f"{referral_code}"
        )

    return jsonify({
        "success": True,

        "referral_code":
            referral_code,

        "referral_link":
            referral_link,

        "referrals_count":
            safe_int(
                data.get(
                    "referrals_count",
                    0,
                ),
                0,
            ),

        "streak_days":
            safe_int(
                data.get(
                    "streak_days",
                    0,
                ),
                0,
            ),
    })


# ============================================================
# ADMIN HELPERS
# ============================================================

def admin_auth():

    admin, error = require_admin()

    if error:

        return None, (
            jsonify({
                "success": False,
                "error":
                    "Admin access required.",
            }),
            403,
        )

    if not admin:

        return None, (
            jsonify({
                "success": False,
                "error":
                    "Unauthorized Telegram session.",
            }),
            401,
        )

    return admin, None


def period_start(
    period,
):

    now_local = platform_now()

    if period == "monthly":

        return datetime(
            now_local.year,
            now_local.month,
            1,
            tzinfo=platform_timezone(),
        )

    # Weekly = Monday 00:00.
    monday = (
        now_local.date()
        - timedelta(
            days=now_local.weekday()
        )
    )

    return datetime(
        monday.year,
        monday.month,
        monday.day,
        tzinfo=platform_timezone(),
    )


# ============================================================
# ADMIN: REFERRAL LEADERBOARD
# ============================================================

@referral_streak_bp.get(
    "/admin/referral-streak/referrals"
)
def admin_referral_leaderboard():

    admin, error = admin_auth()

    if error:
        return error

    period = request.args.get(
        "period",
        "weekly",
    ).lower()

    if period not in {
        "weekly",
        "monthly",
    }:
        return jsonify({
            "success": False,
            "error":
                "Period must be weekly or monthly.",
        }), 400

    start = period_start(
        period
    ).astimezone(
        timezone.utc
    )

    now_utc = datetime.now(
        timezone.utc
    )

    users = list(
        db.collection("users")
        .stream()
    )

    users_by_id = {}

    for snap in users:

        data = (
            snap.to_dict()
            or {}
        )

        user_id = str(
            data.get(
                "telegram_id",
                snap.id,
            )
        )

        users_by_id[
            user_id
        ] = data

    counts = {}

    for snap in users:

        data = (
            snap.to_dict()
            or {}
        )

        referrer_id = str(
            data.get(
                "referred_by",
                "",
            )
            or ""
        )

        if not referrer_id:
            continue

        joined_at = parse_datetime(
            data.get(
                "referral_joined_at"
            )
        )

        if not joined_at:
            continue

        if (
            joined_at < start
            or joined_at > now_utc
        ):
            continue

        counts[
            referrer_id
        ] = (
            counts.get(
                referrer_id,
                0,
            )
            + 1
        )

    leaderboard = []

    for referrer_id, count in counts.items():

        referrer = users_by_id.get(
            referrer_id,
            {},
        )

        username = str(
            referrer.get(
                "username",
                "",
            )
            or ""
        ).strip()

        leaderboard.append({
            "telegram_id":
                referrer_id,

            "username":
                username,

            "display_username":
                (
                    f"@{username}"
                    if username
                    else "No username"
                ),

            "referrals":
                count,
        })

    leaderboard.sort(
        key=lambda item: (
            -item["referrals"],
            item["display_username"]
                .lower(),
        )
    )

    leaderboard = leaderboard[
        :100
    ]

    for index, item in enumerate(
        leaderboard,
        start=1,
    ):
        item["rank"] = index

    return jsonify({
        "success": True,
        "period": period,
        "leaderboard": leaderboard,
    })


# ============================================================
# ADMIN: REFERRER DETAILS
# ============================================================

def funding_for_users(
    telegram_ids,
):
    """
    Read point_orders once and aggregate successful
    funding by user.

    Successful funding statuses:
    paid / completed / approved
    """

    target_ids = {
        str(item)
        for item in telegram_ids
    }

    funding = {
        item: {}
        for item in target_ids
    }

    if not target_ids:
        return funding

    docs = (
        db.collection(
            "point_orders"
        )
        .stream()
    )

    for snap in docs:

        data = (
            snap.to_dict()
            or {}
        )

        telegram_id = str(
            data.get(
                "telegram_id",
                "",
            )
            or ""
        )

        if telegram_id not in target_ids:
            continue

        status = str(
            data.get(
                "status",
                "",
            )
            or ""
        ).lower()

        if status not in {
            "paid",
            "completed",
            "approved",
        }:
            continue

        currency = str(
            data.get(
                "currency",
                "",
            )
            or "UNKNOWN"
        ).upper()

        amount = data.get(
            "amount",
            0,
        )

        try:
            amount = float(
                amount or 0
            )
        except Exception:
            amount = 0

        if amount <= 0:
            continue

        user_funding = funding.setdefault(
            telegram_id,
            {},
        )

        user_funding[
            currency
        ] = (
            user_funding.get(
                currency,
                0,
            )
            + amount
        )

    return funding


def format_funding(
    funding,
):
    if not funding:
        return "0"

    symbols = {
        "NGN": "₦",
        "USD": "$",
        "XTR": "⭐",
    }

    parts = []

    for currency in sorted(
        funding.keys()
    ):

        amount = funding[
            currency
        ]

        symbol = symbols.get(
            currency,
            f"{currency} ",
        )

        if float(amount).is_integer():

            formatted = (
                f"{int(amount):,}"
            )

        else:

            formatted = (
                f"{amount:,.2f}"
            )

        parts.append(
            f"{symbol}{formatted}"
        )

    return " + ".join(parts)


@referral_streak_bp.get(
    "/admin/referral-streak/referrer/<telegram_id>"
)
def admin_referrer_details(
    telegram_id,
):

    admin, error = admin_auth()

    if error:
        return error

    telegram_id = str(
        telegram_id
    )

    referrer_snapshot = (
        user_ref(
            telegram_id
        ).get()
    )

    if not referrer_snapshot.exists:

        return jsonify({
            "success": False,
            "error":
                "Referrer not found.",
        }), 404

    referrer = (
        referrer_snapshot.to_dict()
        or {}
    )

    docs = list(
        db.collection("users")
        .where(
            "referred_by",
            "==",
            telegram_id,
        )
        .stream()
    )

    referred_users = []

    ids = []

    for snap in docs:

        data = (
            snap.to_dict()
            or {}
        )

        referred_id = str(
            data.get(
                "telegram_id",
                snap.id,
            )
        )

        ids.append(
            referred_id
        )

        referred_users.append({
            "telegram_id":
                referred_id,

            "username":
                str(
                    data.get(
                        "username",
                        "",
                    )
                    or ""
                ).strip(),

            "display_username":
                (
                    "@"
                    + str(
                        data.get(
                            "username",
                            "",
                        )
                        or ""
                    ).strip()
                    if str(
                        data.get(
                            "username",
                            "",
                        )
                        or ""
                    ).strip()
                    else "No username"
                ),

            "games_played_count":
                safe_int(
                    data.get(
                        "games_played_count",
                        0,
                    ),
                    0,
                ),

            "referral_joined_at":
                serialize_datetime(
                    data.get(
                        "referral_joined_at"
                    )
                ),
        })

    funding = funding_for_users(
        ids
    )

    for item in referred_users:

        user_funding = funding.get(
            item["telegram_id"],
            {},
        )

        item["funding"] = (
            user_funding
        )

        item["funded_amount"] = (
            format_funding(
                user_funding
            )
        )

        item["funded"] = bool(
            user_funding
        )

        item["played"] = (
            item["games_played_count"]
            > 0
        )

    # Funded users first.
    # Then most recently joined.
    referred_users.sort(
        key=lambda item: (
            not item["funded"],
            not item["played"],
            -(
                safe_int(
                    item.get(
                        "games_played_count",
                        0,
                    ),
                    0,
                )
            ),
            item[
                "display_username"
            ].lower(),
        )
    )

    return jsonify({
        "success": True,

        "referrer": {
            "telegram_id":
                telegram_id,

            "username":
                str(
                    referrer.get(
                        "username",
                        "",
                    )
                    or ""
                ).strip(),

            "display_username":
                (
                    "@"
                    + str(
                        referrer.get(
                            "username",
                            "",
                        )
                        or ""
                    ).strip()
                    if str(
                        referrer.get(
                            "username",
                            "",
                        )
                        or ""
                    ).strip()
                    else "No username"
                ),

            "referrals_count":
                len(
                    referred_users
                ),
        },

        "users":
            referred_users,
    })


# ============================================================
# ADMIN: MONTHLY STREAK LEADERBOARD
# ============================================================

@referral_streak_bp.get(
    "/admin/referral-streak/streaks"
)
def admin_streak_leaderboard():

    admin, error = admin_auth()

    if error:
        return error

    current_month = month_key()

    docs = list(
        db.collection("users")
        .stream()
    )

    leaderboard = []

    for snap in docs:

        data = (
            snap.to_dict()
            or {}
        )

        if str(
            data.get(
                "streak_month",
                "",
            )
            or ""
        ) != current_month:
            continue

        best = safe_int(
            data.get(
                "streak_month_best",
                0,
            ),
            0,
        )

        if best <= 0:
            continue

        telegram_id = str(
            data.get(
                "telegram_id",
                snap.id,
            )
        )

        username = str(
            data.get(
                "username",
                "",
            )
            or ""
        ).strip()

        leaderboard.append({
            "telegram_id":
                telegram_id,

            "username":
                username,

            "display_username":
                (
                    f"@{username}"
                    if username
                    else "No username"
                ),

            "streak":
                best,
        })

    leaderboard.sort(
        key=lambda item: (
            -item["streak"],
            item["display_username"]
                .lower(),
        )
    )

    leaderboard = leaderboard[
        :10
    ]

    for index, item in enumerate(
        leaderboard,
        start=1,
    ):
        item["rank"] = index

    return jsonify({
        "success": True,

        "month":
            current_month,

        "leaderboard":
            leaderboard,
    })
