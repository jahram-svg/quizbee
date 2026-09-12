import os
from datetime import datetime, timezone

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
                serialize_value(
                    active_round
                )
                if active_round
                else None
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

        limit = int(
            request.args.get(
                "limit",
                100
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

            results.append(
                serialize_value(data)
            )

            if len(results) >= limit:
                break

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

@admin_bp.get("/settings")
def get_settings():

    admin, error = require_admin()

    if error:
        return admin_error(error)

    try:

        ref = (
            db.collection("settings")
            .document("app")
        )

        snap = ref.get()

        if not snap.exists:

            settings = {
                "participant_visibility":
                    "hidden",

                "maintenance_mode":
                    False,

                "daily_earning_enabled":
                    True
            }

            ref.set({
                **settings,
                "updated_at": now()
            })

        else:
            settings = snap.to_dict() or {}

        return jsonify({
            "success": True,
            "settings":
                serialize_value(settings)
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# UPDATE SETTINGS
# ============================================================

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

        allowed = [
            "participant_visibility",
            "maintenance_mode",
            "daily_earning_enabled"
        ]

        updates = {}

        for key in allowed:

            if key in body:
                updates[key] = body[key]

        if (
            "participant_visibility"
            in updates
        ):

            if updates[
                "participant_visibility"
            ] not in (
                "hidden",
                "total",
                "per_game"
            ):

                return jsonify({
                    "success": False,
                    "error":
                        "Invalid participant visibility."
                }), 400

        updates["updated_at"] = now()
        updates["updated_by"] = (
            admin["telegram_id"]
        )

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
            "settings":
                serialize_value(updates)
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
