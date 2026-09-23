import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import validate_telegram_init_data


admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/api/admin"
)


# ============================================================
# HELPERS
# ============================================================

def now():
    return datetime.now(timezone.utc)


ONLINE_WINDOW_SECONDS = 90


def is_user_online(last_seen):

    if not last_seen:
        return False

    try:

        if isinstance(
            last_seen,
            datetime
        ):

            seen_at = last_seen

        else:

            seen_at = datetime.fromisoformat(
                str(last_seen)
                .replace(
                    "Z",
                    "+00:00"
                )
            )

        if seen_at.tzinfo is None:

            seen_at = seen_at.replace(
                tzinfo=timezone.utc
            )

        age = (
            now()
            - seen_at
        ).total_seconds()

        return (
            age <=
            ONLINE_WINDOW_SECONDS
        )

    except Exception:

        return False


def get_online_members(users):

    online = []

    for doc in users:

        data = doc.to_dict() or {}

        if not is_user_online(
            data.get("last_seen")
        ):
            continue

        online.append({

            "telegram_id":
                str(
                    data.get(
                        "telegram_id",
                        doc.id
                    )
                ),

            "username":
                str(
                    data.get(
                        "username",
                        ""
                    )
                    or ""
                ),

            "first_name":
                str(
                    data.get(
                        "first_name",
                        ""
                    )
                    or ""
                ),

            "last_name":
                str(
                    data.get(
                        "last_name",
                        ""
                    )
                    or ""
                ),

            "last_seen":
                (
                    data["last_seen"].isoformat()
                    if isinstance(
                        data.get("last_seen"),
                        datetime
                    )
                    else str(
                        data.get(
                            "last_seen",
                            ""
                        )
                    )
                )

        })

    online.sort(
        key=lambda item:
            item.get(
                "last_seen",
                ""
            ),
        reverse=True
    )

    return online


def serialize_value(value):
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {
            key: serialize_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            serialize_value(item)
            for item in value
        ]

    return value


def serialize_doc(doc):
    data = doc.to_dict() or {}
    data["id"] = doc.id
    return serialize_value(data)


def get_authenticated_user():
    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        ""
    )

    if not init_data:
        return None

    admin_bot_token = os.getenv("ADMIN_BOT_TOKEN", "").strip()

    if not admin_bot_token:
        return None

    user = validate_telegram_init_data(
        init_data,
        bot_token=admin_bot_token
    )

    if not user:
        return None

    return {
        "telegram_id": str(user["id"]),
        "username": user.get(
            "username",
            ""
        ),
        "first_name": user.get(
            "first_name",
            ""
        ),
        "last_name": user.get(
            "last_name",
            ""
        ),
    }


def is_admin(telegram_id):
    admin_ids = os.getenv(
        "ADMIN_TELEGRAM_IDS",
        ""
    ).strip()

    if not admin_ids:
        admin_ids = os.getenv(
            "ADMIN_TELEGRAM_ID",
            ""
        ).strip()

    allowed_ids = {
        x.strip()
        for x in admin_ids.split(",")
        if x.strip()
    }

    return str(telegram_id) in allowed_ids


def require_admin():
    user = get_authenticated_user()

    if not user:
        return None, "UNAUTHORIZED"

    if not is_admin(
        user["telegram_id"]
    ):
        return None, "FORBIDDEN"

    return user, None


def admin_error(error):
    if error == "UNAUTHORIZED":
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    return jsonify({
        "success": False,
        "error": "Admin access required."
    }), 403


# ============================================================
# ADMIN BOOTSTRAP / DASHBOARD
# ============================================================

@admin_bp.get("/bootstrap")
def bootstrap():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        users = list(
            db.collection("users")
            .stream()
        )

        games = list(
            db.collection("games")
            .stream()
        )

        withdrawals = list(
            db.collection("withdrawals")
            .where(
                "status",
                "==",
                "pending"
            )
            .stream()
        )

        point_orders = list(
            db.collection("point_orders")
            .where(
                "status",
                "==",
                "pending"
            )
            .stream()
        )

        daily_rounds = list(
            db.collection(
                "daily_earning_rounds"
            )
            .stream()
        )

        total_points = 0
        total_prize_balance = 0

        for doc in users:

            data = doc.to_dict() or {}

            total_points += float(
                data.get(
                    "quizbee_points",
                    0
                ) or 0
            )

            total_prize_balance += float(
                data.get(
                    "prize_balance",
                    0
                ) or 0
            )

        active_games = 0

        for doc in games:

            data = doc.to_dict() or {}

            if data.get(
                "active",
                False
            ):
                active_games += 1

        active_round = None

        for doc in daily_rounds:

            data = doc.to_dict() or {}

            status = data.get(
                "status"
            )

            if status in (
                "active",
                "scheduled",
                "settling"
            ):

                data["id"] = doc.id

                if active_round is None:
                    active_round = data
                else:
                    old_start = active_round.get(
                        "start_at"
                    )
                    new_start = data.get(
                        "start_at"
                    )

                    if (
                        new_start
                        and old_start
                        and new_start > old_start
                    ):
                        active_round = data

                online_members = get_online_members(
            users
        )

        return jsonify({
            "success": True,

            "admin": {
                "telegram_id":
                    admin["telegram_id"],
                "username":
                    admin.get(
                        "username",
                        ""
                    ),
                "first_name":
                    admin.get(
                        "first_name",
                        ""
                    )
            },

            "stats": {
                "users":
                    len(users),

                "online_users":
                    len(online_members),

                "active_games":
                    active_games,

                "total_games":
                    len(games),

                "total_points":
                    total_points,

                "total_prize_balance":
                    total_prize_balance,

                "pending_withdrawals":
                    len(withdrawals),

                "pending_point_orders":
                    len(point_orders)
            },

            "active_daily_round":
                serialize_value(active_round)
                if active_round
                else None,

            "online_members":
                online_members,

            "raffle_enabled":
                bool(
                    (
                        db.collection("settings")
                        .document("general")
                        .get()
                        .to_dict()
                        or {}
                    ).get(
                        "raffle_enabled",
                        False
                    )
                )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# USERS
# ============================================================

@admin_bp.get("/users")
def list_users():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        search = request.args.get(
            "search",
            ""
        ).strip().lower()

        try:
            limit = int(
                request.args.get(
                    "limit",
                    100
                )
            )
        except (
            TypeError,
            ValueError
        ):
            limit = 100

        limit = max(
            1,
            min(
                limit,
                200
            )
        )

        docs = list(
            db.collection(
                "users"
            )
            .stream()
        )

        results = []

        for doc in docs:

            data = doc.to_dict() or {}

            telegram_id = str(
                data.get(
                    "telegram_id",
                    doc.id
                )
            )

            username = str(
                data.get(
                    "username",
                    ""
                )
            )

            first_name = str(
                data.get(
                    "first_name",
                    ""
                )
            )

            last_name = str(
                data.get(
                    "last_name",
                    ""
                )
            )

            searchable = " ".join([
                telegram_id,
                username,
                first_name,
                last_name
            ]).lower()

            if search and search not in searchable:
                continue

            data["telegram_id"] = telegram_id
            data["id"] = doc.id

            data["online"] = is_user_online(
                 data.get("last_seen")
                        )

            results.append(
                serialize_value(data)
            )

            if len(results) >= limit:
                break

        results.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )

        return jsonify({
            "success": True,
            "users": results
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# SINGLE USER
# ============================================================

@admin_bp.get("/users/<telegram_id>")
def get_user(telegram_id):

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        ref = (
            db.collection("users")
            .document(
                str(telegram_id)
            )
        )

        snap = ref.get()

        if not snap.exists:

            return jsonify({
                "success": False,
                "error": "User not found."
            }), 404

        user = snap.to_dict() or {}

        transactions = list(
            db.collection(
                "transactions"
            )
            .where(
                "telegram_id",
                "==",
                str(telegram_id)
            )
            .stream()
        )

        entries = list(
            db.collection(
                "daily_earning_entries"
            )
            .where(
                "telegram_id",
                "==",
                str(telegram_id)
            )
            .stream()
        )

        user["telegram_id"] = str(
            telegram_id
        )

        return jsonify({
            "success": True,
            "user":
                serialize_value(user),

            "transactions": [
                serialize_doc(doc)
                for doc in transactions
            ],

            "daily_entries": [
                serialize_doc(doc)
                for doc in entries
            ]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# USER MANAGEMENT
# ============================================================

def create_admin_action(
    admin,
    action,
    target_telegram_id,
    reason="",
    details=None
):
    """
    Record an important Admin action.

    This creates an audit trail for manual account
    management actions such as balance adjustments
    and blocking/unblocking users.
    """

    data = {
        "admin_telegram_id":
            str(admin["telegram_id"]),

        "admin_username":
            admin.get("username", ""),

        "admin_first_name":
            admin.get("first_name", ""),

        "action":
            str(action),

        "target_telegram_id":
            str(target_telegram_id),

        "reason":
            str(reason or "").strip(),

        "details":
            details or {},

        "created_at":
            now()
    }

    ref = (
        db.collection(
            "admin_actions"
        ).document()
    )

    ref.set(data)

    return ref.id


def get_user_ref(telegram_id):
    return (
        db.collection("users")
        .document(str(telegram_id))
    )


# ------------------------------------------------------------
# ADJUST USER BALANCE
# ------------------------------------------------------------

@admin_bp.post(
    "/users/<telegram_id>/adjust-balance"
)
def adjust_user_balance(telegram_id):

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        telegram_id = str(
            telegram_id
        ).strip()

        if not telegram_id:
            return jsonify({
                "success": False,
                "error": "Telegram ID is required."
            }), 400

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        balance_type = str(
            body.get(
                "balance_type",
                ""
            )
        ).strip()

        action = str(
            body.get(
                "action",
                ""
            )
        ).strip().lower()

        reason = str(
            body.get(
                "reason",
                ""
            )
        ).strip()

        raw_amount = body.get(
            "amount"
        )

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if balance_type not in (
            "points",
            "prize_balance"
        ):
            return jsonify({
                "success": False,
                "error":
                    "Invalid balance type."
            }), 400

        if action not in (
            "add",
            "deduct"
        ):
            return jsonify({
                "success": False,
                "error":
                    "Action must be add or deduct."
            }), 400

        if not reason:
            return jsonify({
                "success": False,
                "error":
                    "A reason is required."
            }), 400

        try:
            amount = float(
                raw_amount
            )
        except (
            TypeError,
            ValueError
        ):
            return jsonify({
                "success": False,
                "error":
                    "Invalid amount."
            }), 400

        if amount <= 0:
            return jsonify({
                "success": False,
                "error":
                    "Amount must be greater than zero."
            }), 400

        # Points must always be whole numbers.
        if balance_type == "points":

            if not amount.is_integer():
                return jsonify({
                    "success": False,
                    "error":
                        "Points must be a whole number."
                }), 400

            amount = int(amount)

        else:
            # Prize balance is kept to 2 decimals.
            amount = round(
                amount,
                2
            )

        ref = get_user_ref(
            telegram_id
        )

        snap = ref.get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "User not found."
            }), 404

        user = snap.to_dict() or {}

        field = (
            "quizbee_points"
            if balance_type == "points"
            else "prize_balance"
        )

        current_balance = float(
            user.get(
                field,
                0
            ) or 0
        )

        if action == "deduct":

            if current_balance < amount:
                return jsonify({
                    "success": False,
                    "error":
                        "Insufficient balance for this deduction.",
                    "current_balance":
                        current_balance
                }), 400

            new_balance = (
                current_balance
                - amount
            )

            delta = -amount

        else:

            new_balance = (
                current_balance
                + amount
            )

            delta = amount

        # ----------------------------------------------------
        # UPDATE USER
        # ----------------------------------------------------

        ref.update({
            field:
                firestore.Increment(
                    delta
                ),

            "updated_at":
                now()
        })

        # ----------------------------------------------------
        # TRANSACTION RECORD
        # ----------------------------------------------------

        currency = (
            "quizbee_points"
            if balance_type == "points"
            else "usd"
        )

        transaction_type = (
            "admin_points_adjustment"
            if balance_type == "points"
            else "admin_prize_balance_adjustment"
        )

        signed_amount = (
            amount
            if action == "add"
            else -amount
        )

        tx_ref = (
            db.collection(
                "transactions"
            ).document()
        )

        tx_ref.set({
            "telegram_id":
                telegram_id,

            "type":
                transaction_type,

            "amount":
                signed_amount,

            "currency":
                currency,

            "balance_type":
                balance_type,

            "status":
                "completed",

            "provider":
                "admin",

            "description":
                reason,

            "admin_telegram_id":
                str(
                    admin["telegram_id"]
                ),

            "created_at":
                now(),

            "updated_at":
                now()
        })

        # ----------------------------------------------------
        # ADMIN AUDIT LOG
        # ----------------------------------------------------

        action_id = create_admin_action(
            admin=admin,
            action=(
                "add_points"
                if balance_type == "points"
                and action == "add"
                else
                "deduct_points"
                if balance_type == "points"
                and action == "deduct"
                else
                "add_prize_balance"
                if balance_type == "prize_balance"
                and action == "add"
                else
                "deduct_prize_balance"
            ),
            target_telegram_id=
                telegram_id,
            reason=reason,
            details={
                "amount":
                    amount,

                "balance_type":
                    balance_type,

                "old_balance":
                    current_balance,

                "new_balance":
                    new_balance,

                "transaction_id":
                    tx_ref.id
            }
        )

        return jsonify({
            "success": True,

            "telegram_id":
                telegram_id,

            "balance_type":
                balance_type,

            "action":
                action,

            "amount":
                amount,

            "old_balance":
                current_balance,

            "new_balance":
                new_balance,

            "transaction_id":
                tx_ref.id,

            "admin_action_id":
                action_id
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ------------------------------------------------------------
# BLOCK / UNBLOCK USER
# ------------------------------------------------------------

@admin_bp.post(
    "/users/<telegram_id>/block"
)
def block_user(telegram_id):

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        telegram_id = str(
            telegram_id
        ).strip()

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        reason = str(
            body.get(
                "reason",
                ""
            )
        ).strip()

        if not reason:
            return jsonify({
                "success": False,
                "error":
                    "A reason is required."
            }), 400

        ref = get_user_ref(
            telegram_id
        )

        snap = ref.get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "User not found."
            }), 404

        ref.update({
            "blocked": True,

            "blocked_at":
                now(),

            "blocked_by":
                str(
                    admin["telegram_id"]
                ),

            "blocked_reason":
                reason,

            "updated_at":
                now()
        })

        action_id = create_admin_action(
            admin=admin,
            action="block_user",
            target_telegram_id=
                telegram_id,
            reason=reason
        )

        return jsonify({
            "success": True,
            "telegram_id":
                telegram_id,
            "blocked":
                True,
            "admin_action_id":
                action_id
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


@admin_bp.post(
    "/users/<telegram_id>/unblock"
)
def unblock_user(telegram_id):

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        telegram_id = str(
            telegram_id
        ).strip()

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        reason = str(
            body.get(
                "reason",
                ""
            )
        ).strip()

        if not reason:
            return jsonify({
                "success": False,
                "error":
                    "A reason is required."
            }), 400

        ref = get_user_ref(
            telegram_id
        )

        snap = ref.get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "User not found."
            }), 404

        ref.update({
            "blocked": False,

            "unblocked_at":
                now(),

            "unblocked_by":
                str(
                    admin["telegram_id"]
                ),

            "unblocked_reason":
                reason,

            "updated_at":
                now()
        })

        action_id = create_admin_action(
            admin=admin,
            action="unblock_user",
            target_telegram_id=
                telegram_id,
            reason=reason
        )

        return jsonify({
            "success": True,
            "telegram_id":
                telegram_id,
            "blocked":
                False,
            "admin_action_id":
                action_id
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ------------------------------------------------------------
# ADMIN ACTION HISTORY FOR A USER
# ------------------------------------------------------------

@admin_bp.get(
    "/users/<telegram_id>/admin-actions"
)
def user_admin_actions(telegram_id):

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        docs = (
            db.collection(
                "admin_actions"
            )
            .where(
                "target_telegram_id",
                "==",
                str(telegram_id)
            )
            .stream()
        )

        actions = [
            serialize_doc(doc)
            for doc in docs
        ]

        actions.sort(
            key=lambda x:
                x.get(
                    "created_at",
                    ""
                ),
            reverse=True
        )

        return jsonify({
            "success": True,
            "actions":
                actions[:100]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# GAMES
# ============================================================

@admin_bp.get("/games")
def list_games():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        docs = (
            db.collection("games")
            .stream()
        )

        games = [
            serialize_doc(doc)
            for doc in docs
        ]

        games.sort(
            key=lambda x:
                int(
                    x.get(
                        "sort_order",
                        999
                    )
                )
        )

        return jsonify({
            "success": True,
            "games": games
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# UPDATE GAME
# ============================================================

@admin_bp.post("/games/<game_id>/update")
def update_game(game_id):

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        ref = (
            db.collection("games")
            .document(game_id)
        )

        snap = ref.get()

        if not snap.exists:

            return jsonify({
                "success": False,
                "error": "Game not found."
            }), 404

        updates = {}

        allowed_fields = [
    "name",
    "description",
    "active",
    "maintenance_mode",
    "entry_fee",
    "sort_order"
        ]

        for field in allowed_fields:

            if field in body:
                updates[field] = body[field]

        if "entry_fee" in updates:
            updates["entry_fee"] = int(
                updates["entry_fee"]
            )

        if "sort_order" in updates:
            updates["sort_order"] = int(
                updates["sort_order"]
            )

        if "maintenance_mode" in updates:
            updates["maintenance_mode"] = bool(
                updates["maintenance_mode"]
            )

        updates["updated_at"] = now()

        ref.update(updates)

        return jsonify({
            "success": True,
            "game_id": game_id,
            "updates": serialize_value(
                updates
            )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# CHALLENGES
# ============================================================

@admin_bp.get("/challenges")
def list_challenges():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        game_id = request.args.get(
            "game_id",
            ""
        ).strip()

        docs = (
            db.collection(
                "challenges"
            )
            .stream()
        )

        challenges = []

        for doc in docs:

            data = doc.to_dict() or {}

            if (
                game_id
                and data.get(
                    "game_id"
                ) != game_id
            ):
                continue

            data["id"] = doc.id

            challenges.append(
                serialize_value(data)
            )

        challenges.sort(
            key=lambda x:
                x.get(
                    "created_at",
                    ""
                ),
            reverse=True
        )

        return jsonify({
            "success": True,
            "challenges": challenges
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# CREATE CHALLENGE
# ============================================================

@admin_bp.post("/challenges/create")
def create_challenge():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        game_id = str(
            body.get(
                "game_id",
                ""
            )
        ).strip()

        title = str(
            body.get(
                "title",
                ""
            )
        ).strip()

        question = str(
            body.get(
                "question",
                ""
            )
        ).strip()

        if not game_id:
            return jsonify({
                "success": False,
                "error":
                    "Game ID is required."
            }), 400

        if not title:
            return jsonify({
                "success": False,
                "error":
                    "Challenge title is required."
            }), 400

        if not question:
            return jsonify({
                "success": False,
                "error":
                    "Question is required."
            }), 400

        game_ref = (
            db.collection("games")
            .document(game_id)
        )

        if not game_ref.get().exists:
            return jsonify({
                "success": False,
                "error":
                    "Game not found."
            }), 404

        accepted_answers = body.get(
            "accepted_answers",
            []
        )

        if isinstance(
            accepted_answers,
            str
        ):
            accepted_answers = [
                x.strip()
                for x in accepted_answers.split(
                    ","
                )
                if x.strip()
            ]

        challenge = {

            "game_id":
                game_id,

            "title":
                title,

            "question":
                question,

            "type":
                body.get(
                    "type",
                    "text"
                ),

            "active":
                bool(
                    body.get(
                        "active",
                        False
                    )
                ),

            "round_id":
                body.get(
                    "round_id",
                    ""
                ),

            "correct_answer":
                body.get(
                    "correct_answer",
                    ""
                ),

            "accepted_answers":
                accepted_answers,

            "options":
                body.get(
                    "options",
                    []
                ),

            "reward_points":
                int(
                    body.get(
                        "reward_points",
                        0
                    )
                ),

            "metadata":
                body.get(
                    "metadata",
                    {}
                ),

            "created_at":
                now(),

            "updated_at":
                now(),

            "created_by":
                admin["telegram_id"]
        }

        ref = (
            db.collection(
                "challenges"
            )
            .document()
        )

        ref.set(challenge)

        return jsonify({
            "success": True,
            "challenge_id":
                ref.id
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# UPDATE CHALLENGE
# ============================================================

@admin_bp.post(
    "/challenges/<challenge_id>/update"
)
def update_challenge(challenge_id):

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        ref = (
            db.collection(
                "challenges"
            )
            .document(
                challenge_id
            )
        )

        snap = ref.get()

        if not snap.exists:

            return jsonify({
                "success": False,
                "error":
                    "Challenge not found."
            }), 404

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        allowed_fields = [
            "title",
            "question",
            "type",
            "active",
            "round_id",
            "correct_answer",
            "accepted_answers",
            "options",
            "reward_points",
            "metadata"
        ]

        updates = {}

        for field in allowed_fields:

            if field in body:
                updates[field] = body[field]

        if "reward_points" in updates:
            updates["reward_points"] = int(
                updates["reward_points"]
            )

        updates["updated_at"] = now()
        updates["updated_by"] = (
            admin["telegram_id"]
        )

        ref.update(updates)

        return jsonify({
            "success": True,
            "challenge_id":
                challenge_id
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# DAILY EARNING ROUNDS
# ============================================================

@admin_bp.get("/daily-rounds")
def daily_rounds():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        docs = (
            db.collection(
                "daily_earning_rounds"
            )
            .stream()
        )

        rounds = [
            serialize_doc(doc)
            for doc in docs
        ]

        rounds.sort(
            key=lambda x:
                x.get(
                    "created_at",
                    ""
                ),
            reverse=True
        )

        return jsonify({
            "success": True,
            "rounds": rounds
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# DAILY EARNING ENTRIES
# ============================================================

@admin_bp.get(
    "/daily-rounds/<round_id>/entries"
)
def daily_entries(round_id):

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        docs = (
            db.collection(
                "daily_earning_entries"
            )
            .where(
                "round_id",
                "==",
                round_id
            )
            .stream()
        )

        entries = [
            serialize_doc(doc)
            for doc in docs
        ]

        entries.sort(
            key=lambda x:
                x.get(
                    "created_at",
                    ""
                ),
            reverse=True
        )

        return jsonify({
            "success": True,
            "entries": entries
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# DAILY EARNING RESULTS
# ============================================================

@admin_bp.get(
    "/daily-rounds/<round_id>/results"
)
def daily_results(round_id):

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        docs = (
            db.collection(
                "daily_earning_results"
            )
            .where(
                "round_id",
                "==",
                round_id
            )
            .stream()
        )

        results = [
            serialize_doc(doc)
            for doc in docs
        ]

        results.sort(
            key=lambda x:
                x.get(
                    "created_at",
                    ""
                ),
            reverse=True
        )

        return jsonify({
            "success": True,
            "results": results
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@admin_bp.get(
    "/daily-rounds/pending-settlement"
)
def pending_daily_settlements():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        docs = (
            db.collection(
                "daily_earning_rounds"
            )
            .where(
                "status",
                "==",
                "closed"
            )
            .stream()
        )

        rounds = []

        for doc in docs:

            data = (
                doc.to_dict()
                or {}
            )

            if data.get(
                "settlement_status"
            ) != "pending":
                continue

            data["id"] = doc.id

            rounds.append(
                serialize_value(
                    data
                )
            )

        rounds.sort(
            key=lambda x:
                x.get(
                    "end_at",
                    ""
                )
        )

        return jsonify({
            "success": True,
            "rounds":
                rounds
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# TRANSACTIONS
# ============================================================

@admin_bp.get("/transactions")
def transactions():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        telegram_id = request.args.get(
            "telegram_id",
            ""
        ).strip()

        limit = int(
            request.args.get(
                "limit",
                100
            )
        )

        query = db.collection(
            "transactions"
        )

        if telegram_id:
            query = query.where(
                "telegram_id",
                "==",
                telegram_id
            )

        docs = list(
            query.stream()
        )

        results = [
            serialize_doc(doc)
            for doc in docs
        ]

        results.sort(
            key=lambda x:
                x.get(
                    "created_at",
                    ""
                ),
            reverse=True
        )

        return jsonify({
            "success": True,
            "transactions":
                results[:limit]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# SETTINGS
# ============================================================

DEFAULT_APP_SETTINGS = {

    "participant_visibility":
        "hidden",

    "maintenance_mode":
        False,

    "maintenance_message":
        "QuizBee is currently under maintenance. Please check back soon.",

    "maintenance_exceptions":
        [],

    "daily_earning_enabled":
        True,

    "ads_enabled":
        True,

    "ads_reward_points":
        1,

    "ads_daily_limit":
        10,

    "telegram_channel_url":
        "",

    "customer_support_url":
        ""
}


def get_app_settings():

    ref = (
        db.collection(
            "settings"
        )
        .document("app")
    )

    snap = ref.get()

    if not snap.exists:

        ref.set({
            **DEFAULT_APP_SETTINGS,
            "updated_at": now()
        })

        return dict(
            DEFAULT_APP_SETTINGS
        )

    settings = snap.to_dict() or {}

    merged = dict(
        DEFAULT_APP_SETTINGS
    )

    merged.update(
        settings
    )

    return merged


def normalize_maintenance_ids(
    values
):

    if values is None:
        return []

    if isinstance(
        values,
        str
    ):

        values = (
            values
            .replace(",", "\n")
            .splitlines()
        )

    if not isinstance(
        values,
        list
    ):
        return []

    result = []

    for value in values:

        value = str(
            value
        ).strip()

        if not value:
            continue

        # Telegram user IDs are numeric.
        if not value.isdigit():
            continue

        if value not in result:
            result.append(value)

    return result


def is_maintenance_bypass(
    telegram_id
):

    settings = get_app_settings()

    exceptions = (
        settings.get(
            "maintenance_exceptions",
            []
        )
    )

    exceptions = (
        normalize_maintenance_ids(
            exceptions
        )
    )

    return (
        str(telegram_id)
        in exceptions
    )


# ------------------------------------------------------------
# GET SETTINGS
# ------------------------------------------------------------

@admin_bp.get("/settings")
def get_settings():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        settings = (
            get_app_settings()
        )

        return jsonify({
            "success": True,

            "settings":
                serialize_value(
                    settings
                )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ------------------------------------------------------------
# UPDATE SETTINGS
# ------------------------------------------------------------

@admin_bp.post("/settings")
def update_settings():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        updates = {}

        # ----------------------------------------------------
        # PARTICIPANT VISIBILITY
        # ----------------------------------------------------

        if (
            "participant_visibility"
            in body
        ):

            visibility = str(
                body.get(
                    "participant_visibility",
                    ""
                )
            ).strip()

            if visibility not in (
                "hidden",
                "total",
                "per_game"
            ):

                return jsonify({
                    "success": False,
                    "error":
                        "Invalid participant visibility."
                }), 400

            updates[
                "participant_visibility"
            ] = visibility

        # ----------------------------------------------------
        # GLOBAL MAINTENANCE
        # ----------------------------------------------------

        if (
            "maintenance_mode"
            in body
        ):

            updates[
                "maintenance_mode"
            ] = bool(
                body.get(
                    "maintenance_mode"
                )
            )

        # ----------------------------------------------------
        # MAINTENANCE MESSAGE
        # ----------------------------------------------------

        if (
            "maintenance_message"
            in body
        ):

            message = str(
                body.get(
                    "maintenance_message",
                    ""
                )
            ).strip()

            if not message:

                message = (
                    "QuizBee is currently "
                    "under maintenance. "
                    "Please check back soon."
                )

            if len(message) > 500:

                return jsonify({
                    "success": False,
                    "error":
                        "Maintenance message is too long."
                }), 400

            updates[
                "maintenance_message"
            ] = message

        # ----------------------------------------------------
        # MAINTENANCE EXCEPTIONS
        # ----------------------------------------------------

        if (
            "maintenance_exceptions"
            in body
        ):

            exceptions = (
                normalize_maintenance_ids(
                    body.get(
                        "maintenance_exceptions"
                    )
                )
            )

            if len(exceptions) > 100:

                return jsonify({
                    "success": False,
                    "error":
                        "Maximum of 100 maintenance test users allowed."
                }), 400

            updates[
                "maintenance_exceptions"
            ] = exceptions

        # ----------------------------------------------------
        # DAILY EARNING
        # ----------------------------------------------------

        if (
            "daily_earning_enabled"
            in body
        ):

            updates[
                "daily_earning_enabled"
            ] = bool(
                body.get(
                    "daily_earning_enabled"
                )
            )

                # ----------------------------------------------------
        # ADS & MONETIZATION
        # ----------------------------------------------------

        if (
            "ads_enabled"
            in body
        ):

            updates[
                "ads_enabled"
            ] = bool(
                body.get(
                    "ads_enabled"
                )
            )


        if (
            "ads_reward_points"
            in body
        ):

            try:

                reward_points = int(
                    body.get(
                        "ads_reward_points"
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                return jsonify({
                    "success": False,
                    "error":
                        "Invalid ad reward."
                }), 400


            if not 1 <= reward_points <= 100:

                return jsonify({
                    "success": False,
                    "error":
                        "Ad reward must be between 1 and 100 points."
                }), 400


            updates[
                "ads_reward_points"
            ] = reward_points


        if (
            "ads_daily_limit"
            in body
        ):

            try:

                daily_limit = int(
                    body.get(
                        "ads_daily_limit"
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                return jsonify({
                    "success": False,
                    "error":
                        "Invalid daily ad limit."
                }), 400


            if not 1 <= daily_limit <= 10000:

                return jsonify({
                    "success": False,
                    "error":
                        "Daily ad limit must be between 1 and 10000."
                }), 400


            updates[
                "ads_daily_limit"
            ] = daily_limit

        # ----------------------------------------------------
# TELEGRAM CHANNEL
# ----------------------------------------------------

if (
    "telegram_channel_url"
    in body
):

    telegram_channel_url = str(
        body.get(
            "telegram_channel_url",
            ""
        )
    ).strip()

    if (
        telegram_channel_url
        and not (
            telegram_channel_url.startswith(
                "https://t.me/"
            )
            or telegram_channel_url.startswith(
                "https://telegram.me/"
            )
        )
    ):

        return jsonify({
            "success": False,
            "error":
                "Telegram channel must be a valid Telegram link."
        }), 400

    updates[
        "telegram_channel_url"
    ] = telegram_channel_url


# ----------------------------------------------------
# CUSTOMER SUPPORT
# ----------------------------------------------------

if (
    "customer_support_url"
    in body
):

    customer_support_url = str(
        body.get(
            "customer_support_url",
            ""
        )
    ).strip()

    if (
        customer_support_url
        and not (
            customer_support_url.startswith(
                "https://t.me/"
            )
            or customer_support_url.startswith(
                "https://telegram.me/"
            )
        )
    ):

        return jsonify({
            "success": False,
            "error":
                "Customer support must be a valid Telegram link."
        }), 400

    updates[
        "customer_support_url"
    ] = customer_support_url 
    
        # ----------------------------------------------------
        # AUDIT
        # ----------------------------------------------------

        updates[
            "updated_at"
        ] = now()

        updates[
            "updated_by"
        ] = admin[
            "telegram_id"
        ]

        ref = (
            db.collection(
                "settings"
            )
            .document("app")
        )

        ref.set(
            updates,
            merge=True
        )

        # ----------------------------------------------------
        # ADMIN AUDIT LOG
        # ----------------------------------------------------

        create_admin_action(
            admin=admin,

            action=
                "update_app_settings",

            target_telegram_id=
                "SYSTEM",

            reason=
                "Admin settings updated.",

            details={
                key:
                    serialize_value(
                        value
                    )
                for key, value
                in updates.items()
                if key not in (
                    "updated_at"
                )
            }
        )

        return jsonify({
            "success": True,

            "settings":
                serialize_value(
                    updates
                )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# ADS ACTIVITY
# ============================================================

ADS_TIMEZONE = ZoneInfo(
    "Africa/Lagos"
)


@admin_bp.get("/ads/activity")
def get_ads_activity():

    admin, error = require_admin()

    if error:
        return error

    try:

        sort_by = (
            request.args.get(
                "sort",
                "today"
            )
            .strip()
            .lower()
        )

        if sort_by not in (
            "today",
            "weekly",
            "monthly"
        ):

            sort_by = "today"


        now_local = datetime.now(
            ADS_TIMEZONE
        )

        today = (
            now_local.date()
        )

        week_start = (
            today
            - __import__(
                "datetime"
            ).timedelta(
                days=today.weekday()
            )
        )

        month_start = today.replace(
            day=1
        )


        # ----------------------------------------------------
        # COLLECT AD ACTIVITY
        # ----------------------------------------------------

        activity = {}


        ad_docs = (
            db.collection(
                "ad_rewards"
            )
            .stream()
        )


        for doc in ad_docs:

            data = (
                doc.to_dict()
                or {}
            )


            if data.get(
                "status"
            ) != "completed":

                continue


            telegram_id = str(
                data.get(
                    "telegram_id",
                    ""
                )
            )


            if not telegram_id:
                continue


            if telegram_id not in activity:

                activity[
                    telegram_id
                ] = {
                    "ads_today": 0,
                    "weekly_ads": 0,
                    "monthly_ads": 0,
                    "last_ad_at": None
                }


            ad_day_value = (
                data.get(
                    "ad_day"
                )
            )


            try:

                ad_date = (
                    datetime.strptime(
                        str(
                            ad_day_value
                        ),
                        "%Y-%m-%d"
                    ).date()
                )

            except Exception:

                continue


            if ad_date == today:

                activity[
                    telegram_id
                ][
                    "ads_today"
                ] += 1


            if ad_date >= week_start:

                activity[
                    telegram_id
                ][
                    "weekly_ads"
                ] += 1


            if ad_date >= month_start:

                activity[
                    telegram_id
                ][
                    "monthly_ads"
                ] += 1


            created_at = (
                data.get(
                    "created_at"
                )
            )


            if created_at:

                previous = (
                    activity[
                        telegram_id
                    ].get(
                        "last_ad_at"
                    )
                )


                if (
                    previous is None
                    or created_at > previous
                ):

                    activity[
                        telegram_id
                    ][
                        "last_ad_at"
                    ] = created_at


        # ----------------------------------------------------
        # ADD USER INFORMATION
        # ----------------------------------------------------

        users = []

        user_docs = (
            db.collection(
                "users"
            )
            .stream()
        )


        for doc in user_docs:

            user = (
                doc.to_dict()
                or {}
            )


            telegram_id = str(
                user.get(
                    "telegram_id",
                    doc.id
                )
            )


            stats = activity.get(
                telegram_id,
                {
                    "ads_today": 0,
                    "weekly_ads": 0,
                    "monthly_ads": 0,
                    "last_ad_at": None
                }
            )


            username = (
                user.get(
                    "username",
                    ""
                )
                or ""
            ).strip()


            first_name = (
                user.get(
                    "first_name",
                    ""
                )
                or ""
            ).strip()


            if username:

                display_name = (
                    f"@{username}"
                )

            elif first_name:

                display_name = first_name

            else:

                display_name = (
                    f"User {telegram_id}"
                )


            last_ad_at = (
                stats.get(
                    "last_ad_at"
                )
            )


            if isinstance(
                last_ad_at,
                datetime
            ):

                last_ad_at = (
                    last_ad_at.astimezone(
                        ADS_TIMEZONE
                    ).isoformat()
                )


            users.append({

                "telegram_id":
                    telegram_id,

                "user":
                    display_name,

                "ads_today":
                    stats[
                        "ads_today"
                    ],

                "weekly_ads":
                    stats[
                        "weekly_ads"
                    ],

                "monthly_ads":
                    stats[
                        "monthly_ads"
                    ],

                "last_ad":
                    last_ad_at

            })


        # ----------------------------------------------------
        # SORT
        # ----------------------------------------------------

        sort_field = {

            "today":
                "ads_today",

            "weekly":
                "weekly_ads",

            "monthly":
                "monthly_ads"

        }[
            sort_by
        ]


        users.sort(
            key=lambda item: (
                item.get(
                    sort_field,
                    0
                ),
                item.get(
                    "monthly_ads",
                    0
                ),
                item.get(
                    "weekly_ads",
                    0
                ),
                item.get(
                    "ads_today",
                    0
                )
            ),
            reverse=True
        )


        return jsonify({

            "success":
                True,

            "sort":
                sort_by,

            "users":
                users

        })


    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500

# ============================================================
# RAFFLE SETTINGS
# ============================================================

@admin_bp.post("/raffle/settings")
def update_raffle_settings():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        enabled = body.get(
            "raffle_enabled"
        )

        if not isinstance(
            enabled,
            bool
        ):
            return jsonify({
                "success": False,
                "error":
                    "raffle_enabled must be true or false."
            }), 400

        ref = (
            db.collection(
                "settings"
            )
            .document(
                "general"
            )
        )

        ref.set({
            "raffle_enabled":
                enabled,

            "updated_at":
                now(),

            "updated_by":
                str(
                    admin[
                        "telegram_id"
                    ]
                )
        }, merge=True)

        return jsonify({
            "success": True,

            "raffle_enabled":
                enabled
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# FUNDING PAYMENT SETTINGS
# ============================================================

@admin_bp.get(
    "/funding-settings"
)
def get_funding_settings():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        snap = (
            db.collection("settings")
            .document("app")
            .get()
        )

        data = (
            snap.to_dict()
            or {}
        )

        return jsonify({
            "success": True,
            "settings": {

                "funding_ngn_bank_name":
                    data.get(
                        "funding_ngn_bank_name",
                        ""
                    ),

                "funding_ngn_account_name":
                    data.get(
                        "funding_ngn_account_name",
                        ""
                    ),

                "funding_ngn_account_number":
                    data.get(
                        "funding_ngn_account_number",
                        ""
                    ),

                "funding_ngn_instructions":
                    data.get(
                        "funding_ngn_instructions",
                        ""
                    ),

                "funding_usdt_network":
                    data.get(
                        "funding_usdt_network",
                        "BEP20"
                    ),

                "funding_usdt_address":
                    data.get(
                        "funding_usdt_address",
                        ""
                    ),

                "funding_usdt_instructions":
                    data.get(
                        "funding_usdt_instructions",
                        ""
                    )

            }
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@admin_bp.post(
    "/funding-settings"
)
def update_funding_settings():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        updates = {

            "funding_ngn_bank_name":
                str(
                    body.get(
                        "funding_ngn_bank_name",
                        ""
                    )
                ).strip(),

            "funding_ngn_account_name":
                str(
                    body.get(
                        "funding_ngn_account_name",
                        ""
                    )
                ).strip(),

            "funding_ngn_account_number":
                str(
                    body.get(
                        "funding_ngn_account_number",
                        ""
                    )
                ).strip(),

            "funding_ngn_instructions":
                str(
                    body.get(
                        "funding_ngn_instructions",
                        ""
                    )
                ).strip(),

            "funding_usdt_network":
                str(
                    body.get(
                        "funding_usdt_network",
                        "BEP20"
                    )
                ).strip(),

            "funding_usdt_address":
                str(
                    body.get(
                        "funding_usdt_address",
                        ""
                    )
                ).strip(),

            "funding_usdt_instructions":
                str(
                    body.get(
                        "funding_usdt_instructions",
                        ""
                    )
                ).strip(),

            "updated_at":
                now(),

            "updated_by":
                str(
                    admin[
                        "telegram_id"
                    ]
                )

        }

        (
            db.collection("settings")
            .document("app")
            .set(
                updates,
                merge=True
            )
        )

        return jsonify({
            "success": True,
            "message":
                "Funding payment settings saved."
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
        
