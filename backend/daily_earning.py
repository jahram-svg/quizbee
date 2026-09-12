import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

from flask import Blueprint, jsonify, request
from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import validate_telegram_init_data


daily_earning_bp = Blueprint(
    "daily_earning",
    __name__
)

ENTRY_FEE = 10


# ============================================================
# TIME / SERIALIZATION
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


# ============================================================
# TELEGRAM AUTH
# ============================================================

def require_user():
    """
    Authenticate normal QuizBee Mini App users with BOT_TOKEN.
    """
    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        ""
    )

    if not init_data:
        return None

    user = validate_telegram_init_data(
        init_data
    )

    if not user:
        return None

    return {
        "telegram_id": str(user["id"]),
        "username": user.get("username", ""),
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", "")
    }


def require_admin_user():
    """
    Authenticate Admin Mini App users with ADMIN_BOT_TOKEN,
    then verify their Telegram ID is an allowed admin.
    """
    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        ""
    )

    if not init_data:
        return None

    admin_bot_token = os.getenv(
        "ADMIN_BOT_TOKEN",
        ""
    ).strip()

    if not admin_bot_token:
        return None

    user = validate_telegram_init_data(
        init_data,
        bot_token=admin_bot_token
    )

    if not user:
        return None

    telegram_id = str(user["id"])

    if not is_admin(telegram_id):
        return None

    return {
        "telegram_id": telegram_id,
        "username": user.get("username", ""),
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", "")
    }


# ============================================================
# FIRESTORE HELPERS
# ============================================================

def user_ref(telegram_id):
    return (
        db.collection("users")
        .document(str(telegram_id))
    )


def get_user(telegram_id):
    snap = user_ref(
        telegram_id
    ).get()

    if not snap.exists:
        return None

    data = snap.to_dict() or {}
    data["telegram_id"] = str(
        telegram_id
    )

    return data


def get_round(round_id):
    snap = (
        db.collection(
            "daily_earning_rounds"
        )
        .document(round_id)
        .get()
    )

    if not snap.exists:
        return None

    data = snap.to_dict() or {}
    data["id"] = round_id

    return data


def entry_document_id(
    round_id,
    telegram_id
):
    """
    Deterministic entry ID.

    One Telegram account can therefore have
    only one Daily Earning entry per round.
    """
    return (
        f"{round_id}_{str(telegram_id)}"
    )


def entry_ref(
    round_id,
    telegram_id
):
    return (
        db.collection(
            "daily_earning_entries"
        )
        .document(
            entry_document_id(
                round_id,
                telegram_id
            )
        )
    )


def get_user_entry(
    telegram_id,
    round_id
):
    ref = entry_ref(
        round_id,
        telegram_id
    )

    snap = ref.get()

    if not snap.exists:
        return None

    data = snap.to_dict() or {}
    data["id"] = snap.id

    return data


# ============================================================
# ANSWER NORMALIZATION
# ============================================================

def normalize_answer(value):
    if value is None:
        return ""

    value = str(value).strip().lower()

    import re

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    value = re.sub(
        r"[^\w\s-]",
        "",
        value
    )

    return value


def accepted_answer_set(round_data):
    answers = set()

    correct = normalize_answer(
        round_data.get(
            "correct_answer",
            ""
        )
    )

    if correct:
        answers.add(correct)

    accepted = round_data.get(
        "accepted_answers",
        []
    )

    if isinstance(
        accepted,
        str
    ):
        accepted = [
            x.strip()
            for x in accepted.split(",")
            if x.strip()
        ]

    for answer in accepted:
        normalized = normalize_answer(
            answer
        )

        if normalized:
            answers.add(normalized)

    return answers


# ============================================================
# ROUND STATE
# ============================================================

def is_round_open(round_data):
    if not round_data:
        return False

    current = now()

    status = round_data.get(
        "status"
    )

    if status != "active":
        return False

    start_at = round_data.get(
        "start_at"
    )

    end_at = round_data.get(
        "end_at"
    )

    if start_at and current < start_at:
        return False

    if end_at and current >= end_at:
        return False

    return True


def count_entries(round_id):
    round_data = get_round(
        round_id
    )

    if round_data:
        stored = round_data.get(
            "entry_count"
        )

        if stored is not None:
            return max(
                0,
                int(stored)
            )

    # Fallback for old rounds created
    # before entry_count existed.
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

    count = 0

    for doc in docs:
        data = doc.to_dict() or {}

        if data.get(
            "status"
        ) in (
            "pending",
            "approved",
            "submitted"
        ):
            count += 1

    return count


# ============================================================
# PUBLIC ROUND
# ============================================================

def public_round(
    data,
    participant_visibility="hidden"
):
    if not data:
        return None

    result = dict(data)

    # NEVER expose answers to users.
    result.pop(
        "correct_answer",
        None
    )

    result.pop(
        "accepted_answers",
        None
    )

    if participant_visibility == "hidden":
        result.pop(
            "participant_count",
            None
        )

    return serialize_value(
        result
    )


def get_app_settings():
    ref = (
        db.collection("settings")
        .document("app")
    )

    snap = ref.get()

    if not snap.exists:
        return {
            "participant_visibility":
                "hidden",
            "maintenance_mode":
                False,
            "daily_earning_enabled":
                True
        }

    return snap.to_dict() or {}


# ============================================================
# TRANSACTIONS
# ============================================================

def create_transaction(
    telegram_id,
    transaction_type,
    amount,
    currency,
    metadata=None
):
    data = {
        "telegram_id":
            str(telegram_id),
        "type":
            transaction_type,
        "amount":
            amount,
        "currency":
            currency,
        "created_at":
            now()
    }

    if metadata:
        data["metadata"] = metadata

    (
        db.collection("transactions")
        .document()
        .set(data)
    )


# ============================================================
# ATOMIC DAILY ENTRY
# ============================================================

def reserve_daily_entry(
    telegram_id,
    round_id,
    mode
):
    """
    Atomically:
      - checks the round
      - checks the deterministic entry document
      - checks the user's points
      - checks the participant slot
      - deducts 10 points
      - increments entry_count
      - creates the entry

    This prevents duplicate entries and
    overselling the final slot.
    """

    user_reference = user_ref(
        telegram_id
    )

    round_reference = (
        db.collection(
            "daily_earning_rounds"
        )
        .document(round_id)
    )

    entry_reference = entry_ref(
        round_id,
        telegram_id
    )

    transaction = db.transaction()

    @firestore.transactional
    def perform(transaction):

        user_snapshot = transaction.get(
            user_reference
        )

        round_snapshot = transaction.get(
            round_reference
        )

        entry_snapshot = transaction.get(
            entry_reference
        )

        if not user_snapshot.exists:
            raise ValueError(
                "User account not found."
            )

        if not round_snapshot.exists:
            raise ValueError(
                "Daily Earning round not found."
            )

        round_data = (
            round_snapshot.to_dict()
            or {}
        )

        user_data = (
            user_snapshot.to_dict()
            or {}
        )

        current = now()

        if round_data.get(
            "status"
        ) != "active":
            raise ValueError(
                "This Daily Earning round is not active."
            )

        start_at = round_data.get(
            "start_at"
        )

        end_at = round_data.get(
            "end_at"
        )

        if (
            start_at
            and current < start_at
        ):
            raise ValueError(
                "This Daily Earning round has not started yet."
            )

        if (
            end_at
            and current >= end_at
        ):
            raise ValueError(
                "The Daily Earning timer has ended."
            )

        # ----------------------------------------------------
        # ONE ACCOUNT = ONE ENTRY
        # ----------------------------------------------------

        if entry_snapshot.exists:

            existing = (
                entry_snapshot.to_dict()
                or {}
            )

            return {
                "already_entered": True,
                "entry_id":
                    entry_reference.id,
                "status":
                    existing.get(
                        "status",
                        "entered"
                    ),
                "quizbee_points":
                    int(
                        user_data.get(
                            "quizbee_points",
                            0
                        )
                    )
            }

        # ----------------------------------------------------
        # POINT BALANCE
        # ----------------------------------------------------

        points = int(
            user_data.get(
                "quizbee_points",
                0
            )
        )

        if points < ENTRY_FEE:
            raise ValueError(
                "Not enough QuizBee Points. "
                "Watch 10 ads to earn 10 points."
            )

        # ----------------------------------------------------
        # SLOT COUNT
        # ----------------------------------------------------

        max_entries = int(
            round_data.get(
                "max_entries",
                0
            )
        )

        current_count = int(
            round_data.get(
                "entry_count",
                0
            )
        )

        if (
            max_entries > 0
            and current_count >= max_entries
        ):
            raise ValueError(
                "Daily Earning slots are full."
            )

        # ----------------------------------------------------
        # DEDUCT POINTS
        # ----------------------------------------------------

        new_balance = (
            points - ENTRY_FEE
        )

        transaction.update(
            user_reference,
            {
                "quizbee_points":
                    new_balance,
                "total_spent":
                    firestore.Increment(
                        ENTRY_FEE
                    ),
                "updated_at":
                    current
            }
        )

        # ----------------------------------------------------
        # RESERVE SLOT
        # ----------------------------------------------------

        transaction.update(
            round_reference,
            {
                "entry_count":
                    firestore.Increment(
                        1
                    ),
                "updated_at":
                    current
            }
        )

        status = (
            "submitted"
            if mode == "question"
            else "pending"
        )

        # ----------------------------------------------------
        # CREATE DETERMINISTIC ENTRY
        # ----------------------------------------------------

        transaction.set(
            entry_reference,
            {
                "telegram_id":
                    str(telegram_id),
                "round_id":
                    round_id,
                "mode":
                    mode,
                "status":
                    status,
                "answer":
                    "",
                "proof_text":
                    "",
                "proof_url":
                    "",
                "created_at":
                    current,
                "updated_at":
                    current
            }
        )

        return {
            "already_entered":
                False,
            "entry_id":
                entry_reference.id,
            "status":
                status,
            "quizbee_points":
                new_balance
        }

    return perform(
        transaction
    )


# ============================================================
# CURRENT DAILY ROUND
# ============================================================

@daily_earning_bp.get(
    "/api/daily-earning/current"
)
def current_round():

    try:

        user = require_user()

        if not user:
            return jsonify({
                "success": False,
                "error":
                    "Unauthorized Telegram session."
            }), 401

        settings = get_app_settings()

        if not settings.get(
            "daily_earning_enabled",
            True
        ):
            return jsonify({
                "success": True,
                "round": None
            })

        docs = list(
            (
                db.collection(
                    "daily_earning_rounds"
                )
                .where(
                    "status",
                    "in",
                    [
                        "scheduled",
                        "active"
                    ]
                )
                .stream()
            )
        )

        if not docs:
            return jsonify({
                "success": True,
                "round": None
            })

        # Pick the round with the earliest
        # upcoming/end time.
        docs.sort(
            key=lambda doc:
                (
                    doc.to_dict()
                    or {}
                ).get(
                    "end_at"
                )
                or datetime.max.replace(
                    tzinfo=timezone.utc
                )
        )

        doc = docs[0]

        round_data = (
            doc.to_dict()
            or {}
        )

        round_data["id"] = doc.id

        # ----------------------------------------------------
        # EXPIRE ROUND
        # ----------------------------------------------------

        end_at = round_data.get(
            "end_at"
        )

        if (
            end_at
            and now() >= end_at
            and round_data.get(
                "status"
            ) in (
                "scheduled",
                "active"
            )
        ):

            (
                doc.reference.update({
                    "status":
                        "closed",
                    "settlement_status":
                        "pending",
                    "closed_at":
                        now(),
                    "updated_at":
                        now()
                })
            )

            round_data["status"] = (
                "closed"
            )

            round_data[
                "settlement_status"
            ] = "pending"

        entry = get_user_entry(
            user["telegram_id"],
            doc.id
        )

        round_data[
            "participant_count"
        ] = count_entries(
            doc.id
        )

        round_data[
            "user_entry"
        ] = entry

        return jsonify({
            "success": True,
            "round":
                public_round(
                    round_data,
                    settings.get(
                        "participant_visibility",
                        "hidden"
                    )
                )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# ENTER DAILY EARNING
# ============================================================

@daily_earning_bp.post(
    "/api/daily-earning/enter"
)
def enter_daily_earning():

    try:

        user = require_user()

        if not user:
            return jsonify({
                "success": False,
                "error":
                    "Unauthorized Telegram session."
            }), 401

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        round_id = body.get(
            "round_id"
        )

        if not round_id:
            return jsonify({
                "success": False,
                "error":
                    "Missing round ID."
            }), 400

        round_data = get_round(
            round_id
        )

        if not round_data:
            return jsonify({
                "success": False,
                "error":
                    "Daily Earning round not found."
            }), 404

        if not is_round_open(
            round_data
        ):
            return jsonify({
                "success": False,
                "error":
                    "This Daily Earning round is not open."
            }), 400

        mode = round_data.get(
            "mode",
            "question"
        )

        try:

            result = reserve_daily_entry(
                user["telegram_id"],
                round_id,
                mode
            )

        except ValueError as e:

            return jsonify({
                "success": False,
                "error":
                    str(e)
            }), 400

        if not result[
            "already_entered"
        ]:
            create_transaction(
                user["telegram_id"],
                "daily_earning_entry",
                -ENTRY_FEE,
                "quizbee_points",
                {
                    "round_id":
                        round_id,
                    "entry_id":
                        result["entry_id"]
                }
            )

        return jsonify({
            "success": True,
            "already_entered":
                result[
                    "already_entered"
                ],
            "entry": {
                "id":
                    result["entry_id"],
                "round_id":
                    round_id,
                "mode":
                    mode,
                "status":
                    result["status"]
            },
            "quizbee_points":
                result["quizbee_points"]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# QUESTION SUBMISSION
# ============================================================

@daily_earning_bp.post(
    "/api/daily-earning/answer"
)
def submit_answer():

    try:

        user = require_user()

        if not user:
            return jsonify({
                "success": False,
                "error":
                    "Unauthorized Telegram session."
            }), 401

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        round_id = body.get(
            "round_id"
        )

        answer = str(
            body.get(
                "answer",
                ""
            )
        ).strip()

        if not round_id:
            return jsonify({
                "success": False,
                "error":
                    "Missing round ID."
            }), 400

        if not answer:
            return jsonify({
                "success": False,
                "error":
                    "Answer is required."
            }), 400

        round_data = get_round(
            round_id
        )

        if not round_data:
            return jsonify({
                "success": False,
                "error":
                    "Round not found."
            }), 404

        if round_data.get(
            "mode"
        ) != "question":
            return jsonify({
                "success": False,
                "error":
                    "This is not a question round."
            }), 400

        if not is_round_open(
            round_data
        ):
            return jsonify({
                "success": False,
                "error":
                    "The timer has ended."
            }), 400

        entry = get_user_entry(
            user["telegram_id"],
            round_id
        )

        if not entry:
            return jsonify({
                "success": False,
                "error":
                    "Enter Daily Earning first."
            }), 403

        if entry.get(
            "status"
        ) in (
            "rejected",
            "rejected_after_close"
        ):
            return jsonify({
                "success": False,
                "error":
                    "This entry is no longer active."
            }), 400

        entry_ref(
            round_id,
            user["telegram_id"]
        ).update({
            "answer":
                answer,
            "status":
                "submitted",
            "submitted_at":
                now(),
            "updated_at":
                now()
        })

        return jsonify({
            "success": True,
            "message":
                "Answer submitted successfully. "
                "Your result will be revealed "
                "when the timer ends."
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# TASK PROOF SUBMISSION
# ============================================================

@daily_earning_bp.post(
    "/api/daily-earning/proof"
)
def submit_proof():

    try:

        user = require_user()

        if not user:
            return jsonify({
                "success": False,
                "error":
                    "Unauthorized Telegram session."
            }), 401

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        round_id = body.get(
            "round_id"
        )

        proof_text = str(
            body.get(
                "proof_text",
                ""
            )
        ).strip()

        proof_url = str(
            body.get(
                "proof_url",
                ""
            )
        ).strip()

        if not round_id:
            return jsonify({
                "success": False,
                "error":
                    "Missing round ID."
            }), 400

        if not proof_text and not proof_url:
            return jsonify({
                "success": False,
                "error":
                    "Submit your proof first."
            }), 400

        round_data = get_round(
            round_id
        )

        if not round_data:
            return jsonify({
                "success": False,
                "error":
                    "Round not found."
            }), 404

        if round_data.get(
            "mode"
        ) != "task":
            return jsonify({
                "success": False,
                "error":
                    "This is not a task round."
            }), 400

        if not is_round_open(
            round_data
        ):
            return jsonify({
                "success": False,
                "error":
                    "The timer has ended."
            }), 400

        entry = get_user_entry(
            user["telegram_id"],
            round_id
        )

        if not entry:
            return jsonify({
                "success": False,
                "error":
                    "Enter Daily Earning first."
            }), 403

        if entry.get(
            "status"
        ) in (
            "rejected",
            "rejected_after_close"
        ):
            return jsonify({
                "success": False,
                "error":
                    "This entry is no longer active."
            }), 400

        entry_ref(
            round_id,
            user["telegram_id"]
        ).update({
            "proof_text":
                proof_text,
            "proof_url":
                proof_url,
            "status":
                "pending",
            "submitted_at":
                now(),
            "updated_at":
                now()
        })

        return jsonify({
            "success": True,
            "message":
                "Proof submitted. "
                "Your entry is pending review."
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# USER HISTORY
# ============================================================

@daily_earning_bp.get(
    "/api/daily-earning/history"
)
def history():

    try:

        user = require_user()

        if not user:
            return jsonify({
                "success": False,
                "error":
                    "Unauthorized Telegram session."
            }), 401

        docs = (
            db.collection(
                "daily_earning_entries"
            )
            .where(
                "telegram_id",
                "==",
                user["telegram_id"]
            )
            .stream()
        )

        entries = []

        for doc in docs:

            data = doc.to_dict() or {}
            data["id"] = doc.id

            entries.append(
                serialize_value(
                    data
                )
            )

        entries.sort(
            key=lambda item:
                item.get(
                    "created_at",
                    ""
                ),
            reverse=True
        )

        return jsonify({
            "success": True,
            "entries":
                entries[:50]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# ADMIN AUTH
# ============================================================

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
        item.strip()
        for item in admin_ids.split(",")
        if item.strip()
    }

    return str(
        telegram_id
    ) in allowed_ids


def admin_error():

    return jsonify({
        "success": False,
        "error":
            "Admin access required."
    }), 403


# ============================================================
# ADMIN CREATE ROUND
# ============================================================

@daily_earning_bp.post(
    "/api/daily-earning/admin/create"
)
def admin_create_round():

    try:

        admin = require_admin_user()

        if not admin:
            return admin_error()

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        mode = str(
            body.get(
                "mode",
                "question"
            )
        ).strip().lower()

        if mode not in (
            "question",
            "task"
        ):
            return jsonify({
                "success": False,
                "error":
                    "Mode must be question or task."
            }), 400

        title = str(
            body.get(
                "title",
                "Daily Earning"
            )
        ).strip()

        if not title:
            return jsonify({
                "success": False,
                "error":
                    "Round title is required."
            }), 400

        try:
            prize_pool_usd = float(
                body.get(
                    "prize_pool_usd",
                    0
                )
            )
        except (
            TypeError,
            ValueError
        ):
            return jsonify({
                "success": False,
                "error":
                    "Prize pool must be a valid number."
            }), 400

        if prize_pool_usd <= 0:
            return jsonify({
                "success": False,
                "error":
                    "Prize pool must be greater than $0."
            }), 400

        try:
            max_entries = int(
                body.get(
                    "max_entries",
                    100
                )
            )
        except (
            TypeError,
            ValueError
        ):
            return jsonify({
                "success": False,
                "error":
                    "Maximum participants must be a valid number."
            }), 400

        if max_entries <= 0:
            return jsonify({
                "success": False,
                "error":
                    "Maximum participants must be greater than 0."
            }), 400

        question = str(
            body.get(
                "question",
                ""
            )
        ).strip()

        instructions = str(
            body.get(
                "instructions",
                ""
            )
        ).strip()

        correct_answer = str(
            body.get(
                "correct_answer",
                ""
            )
        ).strip()

        accepted_answers = body.get(
            "accepted_answers",
            []
        )

        if isinstance(
            accepted_answers,
            str
        ):
            accepted_answers = [
                item.strip()
                for item in accepted_answers.split(",")
                if item.strip()
            ]

        if not isinstance(
            accepted_answers,
            list
        ):
            accepted_answers = []

        if mode == "question":

            if not question:
                return jsonify({
                    "success": False,
                    "error":
                        "Question is required."
                }), 400

            if not correct_answer:
                return jsonify({
                    "success": False,
                    "error":
                        "Correct answer is required."
                }), 400

        if mode == "task":

            if not instructions:
                return jsonify({
                    "success": False,
                    "error":
                        "Task instructions are required."
                }), 400

        start_raw = body.get(
            "start_at"
        )

        end_raw = body.get(
            "end_at"
        )

        if not start_raw or not end_raw:
            return jsonify({
                "success": False,
                "error":
                    "Start and end time are required."
            }), 400

        try:

            start_at = datetime.fromisoformat(
                str(start_raw).replace(
                    "Z",
                    "+00:00"
                )
            )

            end_at = datetime.fromisoformat(
                str(end_raw).replace(
                    "Z",
                    "+00:00"
                )
            )

        except ValueError:

            return jsonify({
                "success": False,
                "error":
                    "Invalid start or end time."
            }), 400

        if start_at.tzinfo is None:
            start_at = start_at.replace(
                tzinfo=timezone.utc
            )

        if end_at.tzinfo is None:
            end_at = end_at.replace(
                tzinfo=timezone.utc
            )

        if end_at <= start_at:
            return jsonify({
                "success": False,
                "error":
                    "End time must be after start time."
            }), 400

        requested_status = str(
            body.get(
                "status",
                "scheduled"
            )
        ).strip().lower()

        if requested_status not in (
            "scheduled",
            "active"
        ):
            requested_status = "scheduled"

        round_data = {

            "title":
                title,

            "mode":
                mode,

            "question":
                question,

            "instructions":
                instructions,

            "correct_answer":
                correct_answer,

            "accepted_answers":
                accepted_answers,

            "prize_pool_usd":
                prize_pool_usd,

            "max_entries":
                max_entries,

            "entry_fee":
                ENTRY_FEE,

            "start_at":
                start_at,

            "end_at":
                end_at,

            "status":
                requested_status,

            "entry_count":
                0,

            "winner_count":
                0,

            "amount_per_winner":
                0,

            "settlement_status":
                "not_settled",

            "created_by":
                admin["telegram_id"],

            "created_at":
                now(),

            "updated_at":
                now()
        }

        ref = (
            db.collection(
                "daily_earning_rounds"
            )
            .document()
        )

        ref.set(
            round_data
        )

        return jsonify({
            "success": True,
            "round_id":
                ref.id
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# ADMIN ACTIVATE ROUND
# ============================================================

@daily_earning_bp.post(
    "/api/daily-earning/admin/<round_id>/activate"
)
def admin_activate_round(
    round_id
):

    try:

        admin = require_admin_user()

        if not admin:
            return admin_error()

        ref = (
            db.collection(
                "daily_earning_rounds"
            )
            .document(round_id)
        )

        snap = ref.get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "Round not found."
            }), 404

        data = snap.to_dict() or {}

        if data.get(
            "settlement_status"
        ) == "settled":
            return jsonify({
                "success": False,
                "error":
                    "A settled round cannot be activated."
            }), 400

        if data.get(
            "status"
        ) == "closed":
            return jsonify({
                "success": False,
                "error":
                    "A closed round cannot be activated."
            }), 400

        current = now()

        if data.get(
            "end_at"
        ) and current >= data["end_at"]:
            return jsonify({
                "success": False,
                "error":
                    "The round end time has already passed."
            }), 400

        ref.update({
            "status":
                "active",
            "activated_at":
                current,
            "activated_by":
                admin["telegram_id"],
            "updated_at":
                current
        })

        return jsonify({
            "success": True,
            "message":
                "Round activated."
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# ADMIN APPROVE TASK
# ============================================================

@daily_earning_bp.post(
    "/api/daily-earning/admin/entries/<entry_id>/approve"
)
def admin_approve_entry(
    entry_id
):

    try:

        admin = require_admin_user()

        if not admin:
            return admin_error()

        ref = (
            db.collection(
                "daily_earning_entries"
            )
            .document(entry_id)
        )

        snap = ref.get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "Entry not found."
            }), 404

        entry = snap.to_dict() or {}

        if entry.get(
            "status"
        ) != "pending":
            return jsonify({
                "success": False,
                "error":
                    "Entry is not pending."
            }), 400

        round_data = get_round(
            entry.get(
                "round_id",
                ""
            )
        )

        if not round_data:
            return jsonify({
                "success": False,
                "error":
                    "Round not found."
            }), 404

        if not is_round_open(
            round_data
        ):
            return jsonify({
                "success": False,
                "error":
                    "The round is no longer open."
            }), 400

        ref.update({
            "status":
                "approved",
            "reviewed_at":
                now(),
            "reviewed_by":
                admin["telegram_id"],
            "updated_at":
                now()
        })

        return jsonify({
            "success": True,
            "message":
                "Entry approved."
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# ADMIN REJECT TASK
# ============================================================

@daily_earning_bp.post(
    "/api/daily-earning/admin/entries/<entry_id>/reject"
)
def admin_reject_entry(
    entry_id
):

    try:

        admin = require_admin_user()

        if not admin:
            return admin_error()

        ref = (
            db.collection(
                "daily_earning_entries"
            )
            .document(entry_id)
        )

        snap = ref.get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "Entry not found."
            }), 404

        entry = snap.to_dict() or {}

        if entry.get(
            "status"
        ) != "pending":
            return jsonify({
                "success": False,
                "error":
                    "Entry is not pending."
            }), 400

        round_id = entry.get(
            "round_id"
        )

        if not round_id:
            return jsonify({
                "success": False,
                "error":
                    "Entry has no round."
            }), 400

        round_ref = (
            db.collection(
                "daily_earning_rounds"
            )
            .document(round_id)
        )

        transaction = db.transaction()

        @firestore.transactional
        def reject_transaction(
            transaction
        ):

            entry_snapshot = (
                transaction.get(
                    ref
                )
            )

            round_snapshot = (
                transaction.get(
                    round_ref
                )
            )

            if not entry_snapshot.exists:
                raise ValueError(
                    "Entry not found."
                )

            if not round_snapshot.exists:
                raise ValueError(
                    "Round not found."
                )

            current_entry = (
                entry_snapshot.to_dict()
                or {}
            )

            current_round = (
                round_snapshot.to_dict()
                or {}
            )

            if current_entry.get(
                "status"
            ) != "pending":
                raise ValueError(
                    "Entry is not pending."
                )

            open_now = (
                current_round.get(
                    "status"
                ) == "active"
                and (
                    not current_round.get(
                        "start_at"
                    )
                    or now()
                    >= current_round[
                        "start_at"
                    ]
                )
                and (
                    not current_round.get(
                        "end_at"
                    )
                    or now()
                    < current_round[
                        "end_at"
                    ]
                )
            )

            updates = {
                "status":
                    (
                        "rejected"
                        if open_now
                        else
                        "rejected_after_close"
                    ),
                "reviewed_at":
                    now(),
                "reviewed_by":
                    admin["telegram_id"],
                "admin_note":
                    str(
                        (
                            request.get_json(
                                silent=True
                            )
                            or {}
                        ).get(
                            "admin_note",
                            ""
                        )
                    ).strip(),
                "updated_at":
                    now()
            }

            transaction.update(
                ref,
                updates
            )

            # Rejected submissions free the slot
            # while the round is still open.
            if open_now:

                current_count = int(
                    current_round.get(
                        "entry_count",
                        0
                    )
                )

                transaction.update(
                    round_ref,
                    {
                        "entry_count":
                            max(
                                0,
                                current_count - 1
                            ),
                        "updated_at":
                            now()
                    }
                )

            return updates[
                "status"
            ]

        status = reject_transaction(
            transaction
        )

        return jsonify({
            "success": True,
            "status":
                status,
            "message":
                "Entry rejected."
        })

    except ValueError as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 400

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# SETTLEMENT HELPERS
# ============================================================

def settlement_result_ref(
    round_id,
    telegram_id
):
    return (
        db.collection(
            "daily_earning_results"
        )
        .document(
            f"{round_id}_{str(telegram_id)}"
        )
    )


def determine_winners(
    round_data,
    entries
):
    winners = []

    if round_data.get(
        "mode"
    ) == "question":

        accepted = accepted_answer_set(
            round_data
        )

        if not accepted:
            return winners

        for entry in entries:

            if entry.get(
                "status"
            ) not in (
                "submitted",
                "approved"
            ):
                continue

            answer = normalize_answer(
                entry.get(
                    "answer",
                    ""
                )
            )

            if (
                answer
                and answer in accepted
            ):
                winners.append(
                    entry
                )

    else:

        for entry in entries:

            if entry.get(
                "status"
            ) == "approved":
                winners.append(
                    entry
                )

    winners.sort(
        key=lambda item:
            item.get(
                "submitted_at"
            )
            or item.get(
                "created_at"
            )
            or now()
    )

    return winners


def calculate_prize_split(
    prize_pool_usd,
    winner_count
):
    if winner_count <= 0:
        return []

    pool = Decimal(
        str(prize_pool_usd)
    )

    pool_cents = int(
        (
            pool * 100
        ).quantize(
            Decimal("1"),
            rounding=ROUND_DOWN
        )
    )

    base = (
        pool_cents
        // winner_count
    )

    remainder = (
        pool_cents
        % winner_count
    )

    amounts = []

    for index in range(
        winner_count
    ):

        cents = base

        if index < remainder:
            cents += 1

        amounts.append(
            float(
                Decimal(cents)
                / Decimal(100)
            )
        )

    return amounts


# ============================================================
# SETTLE ROUND
# ============================================================

@daily_earning_bp.post(
    "/api/daily-earning/admin/<round_id>/settle"
)
def settle_round(
    round_id
):

    try:

        admin = require_admin_user()

        if not admin:
            return admin_error()

        round_ref = (
            db.collection(
                "daily_earning_rounds"
            )
            .document(round_id)
        )

        snap = round_ref.get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "Round not found."
            }), 404

        round_data = snap.to_dict() or {}

        end_at = round_data.get(
            "end_at"
        )

        if (
            end_at
            and now() < end_at
        ):
            return jsonify({
                "success": False,
                "error":
                    "Round has not ended yet."
            }), 400

        # ----------------------------------------------------
        # ATOMIC SETTLEMENT LOCK
        # ----------------------------------------------------

        transaction = db.transaction()

        @firestore.transactional
        def lock_round(
            transaction
        ):

            current_snapshot = (
                transaction.get(
                    round_ref
                )
            )

            if not current_snapshot.exists:
                raise ValueError(
                    "Round not found."
                )

            current = (
                current_snapshot.to_dict()
                or {}
            )

            status = current.get(
                "status"
            )

            settlement_status = (
                current.get(
                    "settlement_status"
                )
            )

            if (
                status == "settled"
                or settlement_status
                == "settled"
            ):
                return (
                    "already_settled",
                    current
                )

            if (
                status == "settling"
            ):
                return (
                    "already_settling",
                    current
                )

            transaction.update(
                round_ref,
                {
                    "status":
                        "settling",
                    "settlement_status":
                        "processing",
                    "settling_at":
                        now(),
                    "settled_by":
                        admin[
                            "telegram_id"
                        ],
                    "updated_at":
                        now()
                }
            )

            return (
                "locked",
                current
            )

        lock_status, locked_round = (
            lock_round(
                transaction
            )
        )

        if lock_status == (
            "already_settled"
        ):
            return jsonify({
                "success": True,
                "winner_count":
                    locked_round.get(
                        "winner_count",
                        0
                    ),
                "message":
                    "Round already settled."
            })

        if lock_status == (
            "already_settling"
        ):
            return jsonify({
                "success": False,
                "error":
                    "This round is already being settled."
            }), 409

        # ----------------------------------------------------
        # LOAD ENTRIES
        # ----------------------------------------------------

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

        entries = []

        for doc in docs:

            data = doc.to_dict() or {}
            data["id"] = doc.id

            entries.append(
                data
            )

        winners = determine_winners(
            locked_round,
            entries
        )

        amounts = calculate_prize_split(
            locked_round.get(
                "prize_pool_usd",
                0
            ),
            len(winners)
        )

        # ----------------------------------------------------
        # CREDIT WINNERS
        #
        # Each winner uses a deterministic
        # result document. This makes settlement
        # resumable if the server stops halfway.
        # ----------------------------------------------------

        results = []

        for index, winner in enumerate(
            winners
        ):

            telegram_id = str(
                winner[
                    "telegram_id"
                ]
            )

            amount = amounts[
                index
            ]

            result_ref = (
                settlement_result_ref(
                    round_id,
                    telegram_id
                )
            )

            credit_transaction = (
                db.transaction()
            )

            @firestore.transactional
            def credit_winner(
                transaction,
                result_ref=result_ref,
                telegram_id=telegram_id,
                amount=amount,
                winner=winner,
                index=index
            ):

                result_snapshot = (
                    transaction.get(
                        result_ref
                    )
                )

                if result_snapshot.exists:
                    return False

                winner_user_ref = user_ref(
                    telegram_id
                )

                user_snapshot = (
                    transaction.get(
                        winner_user_ref
                    )
                )

                if not user_snapshot.exists:
                    raise ValueError(
                        "Winner user account not found."
                    )

                transaction.update(
                    winner_user_ref,
                    {
                        "prize_balance":
                            firestore.Increment(
                                amount
                            ),
                        "total_earned":
                            firestore.Increment(
                                amount
                            ),
                        "updated_at":
                            now()
                    }
                )

                transaction.set(
                    result_ref,
                    {
                        "round_id":
                            round_id,
                        "telegram_id":
                            telegram_id,
                        "entry_id":
                            winner["id"],
                        "amount_usd":
                            amount,
                        "winner_index":
                            index + 1,
                        "created_at":
                            now()
                    }
                )

                return True

            created = credit_winner(
                credit_transaction
            )

            if created:

                create_transaction(
                    telegram_id,
                    "daily_earning_prize",
                    amount,
                    "usd",
                    {
                        "round_id":
                            round_id,
                        "entry_id":
                            winner["id"],
                        "winner_index":
                            index + 1
                    }
                )

            results.append({
                "telegram_id":
                    telegram_id,
                "amount_usd":
                    amount
            })

        # ----------------------------------------------------
        # FINALIZE ROUND
        # ----------------------------------------------------

        winner_count = len(
            winners
        )

        amount_per_winner = (
            amounts[0]
            if amounts
            else 0
        )

        round_ref.update({
            "status":
                "settled",

            "settlement_status":
                "settled",

            "winner_count":
                winner_count,

            "amount_per_winner":
                amount_per_winner,

            "prize_pool_usd":
                float(
                    locked_round.get(
                        "prize_pool_usd",
                        0
                    )
                ),

            "settled_at":
                now(),

            "updated_at":
                now()
        })

        return jsonify({
            "success": True,
            "winner_count":
                winner_count,
            "prize_pool_usd":
                float(
                    locked_round.get(
                        "prize_pool_usd",
                        0
                    )
                ),
            "amount_per_winner":
                amount_per_winner,
            "results":
                results
        })

    except ValueError as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 400

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500
