import os
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN

from flask import Blueprint, jsonify, request
from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import validate_telegram_init_data
from backend.notifications import create_notification


daily_earning_bp = Blueprint(
    "daily_earning",
    __name__
)


ENTRY_FEE = 10


# ============================================================
# GENERAL HELPERS
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


def normalize_answer(value):
    if value is None:
        return ""

    value = str(value).strip().lower()

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
    answers = []

    correct = round_data.get(
        "correct_answer",
        ""
    )

    if correct:
        answers.append(correct)

    extra = round_data.get(
        "accepted_answers",
        []
    )

    if isinstance(extra, str):
        extra = [
            item.strip()
            for item in extra.split(",")
            if item.strip()
        ]

    if isinstance(extra, list):
        answers.extend(extra)

    return {
        normalize_answer(answer)
        for answer in answers
        if normalize_answer(answer)
    }


# ============================================================
# USER AUTH
# ============================================================

def require_user():

    """
    Authenticate normal QuizBee Mini App users
    and reject blocked accounts.
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

    telegram_id = str(
        user["id"]
    )

    try:

        snap = (
            db.collection("users")
            .document(
                telegram_id
            )
            .get()
        )

        if snap.exists:

            data = snap.to_dict() or {}

            if data.get(
                "blocked",
                False
            ):
                return None

    except Exception:

        return None

    return {
        "telegram_id":
            telegram_id,

        "username":
            user.get(
                "username",
                ""
            ),

        "first_name":
            user.get(
                "first_name",
                ""
            ),

        "last_name":
            user.get(
                "last_name",
                ""
            )
    }


def user_ref(telegram_id):

    return (
        db.collection(
            "users"
        )
        .document(
            str(telegram_id)
        )
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

    return (
        str(telegram_id)
        in allowed_ids
    )


def require_admin_user():

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

    telegram_id = str(
        user["id"]
    )

    if not is_admin(
        telegram_id
    ):
        return None

    return {
        "telegram_id": telegram_id,
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
        )
    }


def admin_error():

    return jsonify({
        "success": False,
        "error":
            "Admin access required."
    }), 403


# ============================================================
# ROUND REFERENCES
# ============================================================

def round_ref(round_id):

    return (
        db.collection(
            "daily_earning_rounds"
        )
        .document(
            str(round_id)
        )
    )


def entry_document_id(
    round_id,
    telegram_id
):

    return (
        f"{round_id}_{str(telegram_id)}"
    )


def get_entry_ref(
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


# ============================================================
# ROUND STATE
# ============================================================

def get_round(
    round_id,
    update_state=True
):

    ref = round_ref(
        round_id
    )

    snap = ref.get()

    if not snap.exists:
        return None

    data = snap.to_dict() or {}

    data["id"] = str(
        round_id
    )

    current = now()

    status = data.get(
        "status",
        "scheduled"
    )

    start_at = data.get(
        "start_at"
    )

    end_at = data.get(
        "end_at"
    )

    # --------------------------------------------------------
    # AUTOMATIC ACTIVATION
    # --------------------------------------------------------

    if (
        update_state
        and status == "scheduled"
        and start_at
        and current >= start_at
        and (
            not end_at
            or current < end_at
        )
    ):

        ref.update({
            "status":
                "active",

            "activated_at":
                current,

            "updated_at":
                current
        })

        data["status"] = "active"

    # --------------------------------------------------------
    # AUTOMATIC CLOSURE
    # --------------------------------------------------------

    if (
        update_state
        and status in (
            "scheduled",
            "active"
        )
        and end_at
        and current >= end_at
    ):

        ref.update({
            "status":
                "closed",

            "settlement_status":
                (
                    data.get(
                        "settlement_status",
                        "not_settled"
                    )
                    if data.get(
                        "settlement_status"
                    ) == "settled"
                    else "pending"
                ),

            "closed_at":
                current,

            "updated_at":
                current
        })

        data["status"] = "closed"

    return data


def public_round(data):

    if not data:
        return None

    result = dict(data)

    # Never expose answers to users.
    result.pop(
        "correct_answer",
        None
    )

    result.pop(
        "accepted_answers",
        None
    )

    return serialize_value(
        result
    )


def is_round_open(
    round_data
):

    if not round_data:
        return False

    status = round_data.get(
        "status"
    )

    if status != "active":
        return False

    current = now()

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
        return False

    if (
        end_at
        and current >= end_at
    ):
        return False

    return True


# ============================================================
# ENTRY HELPERS
# ============================================================

def get_user_entry(
    telegram_id,
    round_id
):

    ref = get_entry_ref(
        round_id,
        telegram_id
    )

    snap = ref.get()

    if not snap.exists:
        return None

    data = snap.to_dict() or {}

    data["id"] = snap.id

    return data


def count_entries(
    round_id
):

    round_data = get_round(
        round_id
    )

    if round_data:

        stored_count = (
            round_data.get(
                "entry_count"
            )
        )

        if stored_count is not None:
            return int(
                stored_count
            )

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

        data = (
            doc.to_dict()
            or {}
        )

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
# POINT TRANSACTION
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
        db.collection(
            "transactions"
        )
        .document()
        .set(
            data
        )
    )


# ============================================================
# ATOMIC DAILY ENTRY
# ============================================================

def reserve_daily_entry(
    telegram_id,
    round_id,
    mode
):

    user_document = user_ref(
        telegram_id
    )

    daily_round_ref = round_ref(
        round_id
    )

    entry_document = get_entry_ref(
        round_id,
        telegram_id
    )

    transaction = db.transaction()

    @firestore.transactional
    def perform(
        transaction
    ):

        # IMPORTANT:
        # firebase-admin 7.5.0 uses:
        # document_ref.get(transaction=transaction)
        #
        # Do NOT use:
        # transaction.get(document_ref)

        user_snapshot = (
            user_document.get(
                transaction=transaction
            )
        )

        if not user_snapshot.exists:
            raise ValueError(
                "User account not found."
            )

        round_snapshot = (
            daily_round_ref.get(
                transaction=transaction
            )
        )

        if not round_snapshot.exists:
            raise ValueError(
                "Daily Earning round not found."
            )

        entry_snapshot = (
            entry_document.get(
                transaction=transaction
            )
        )

        if entry_snapshot.exists:

            raise ValueError(
                "You have already entered this round."
            )

        user_data = (
            user_snapshot.to_dict()
            or {}
        )

        round_data = (
            round_snapshot.to_dict()
            or {}
        )

        current = now()

        status = round_data.get(
            "status",
            "scheduled"
        )

        start_at = round_data.get(
            "start_at"
        )

        end_at = round_data.get(
            "end_at"
        )

        # ----------------------------------------------------
        # AUTOMATIC START
        # ----------------------------------------------------

        if (
            status == "scheduled"
            and start_at
            and current >= start_at
            and (
                not end_at
                or current < end_at
            )
        ):

            status = "active"

            transaction.update(
                daily_round_ref,
                {
                    "status":
                        "active",

                    "activated_at":
                        current,

                    "updated_at":
                        current
                }
            )

        # ----------------------------------------------------
        # ROUND TIME CHECK
        # ----------------------------------------------------

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

            transaction.update(
                daily_round_ref,
                {
                    "status":
                        "closed",

                    "settlement_status":
                        "pending",

                    "closed_at":
                        current,

                    "updated_at":
                        current
                }
            )

            raise ValueError(
                "The Daily Earning timer has ended."
            )

        if status != "active":

            raise ValueError(
                "This Daily Earning round is not active."
            )

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

        entry_status = (
            "submitted"
            if mode == "question"
            else "pending"
        )

        # ----------------------------------------------------
        # DEDUCT POINTS
        # ----------------------------------------------------

        transaction.update(
            user_document,
            {
                "quizbee_points":
                    points - ENTRY_FEE,

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
            daily_round_ref,
            {
                "entry_count":
                    firestore.Increment(1),

                "updated_at":
                    current
            }
        )

        # ----------------------------------------------------
        # CREATE ENTRY
        # ----------------------------------------------------

        transaction.set(
            entry_document,
            {
                "telegram_id":
                    str(telegram_id),

                "round_id":
                    str(round_id),

                "mode":
                    mode,

                "status":
                    entry_status,

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
            "entry_id":
                entry_document.id,

            "quizbee_points":
                points - ENTRY_FEE
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

        query = (
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

        candidates = []

        for doc in query:

            data = doc.to_dict() or {}

            data["id"] = doc.id

            candidates.append(
                data
            )

        if not candidates:

            return jsonify({
                "success": True,
                "round": None
            })

        # Sort by start time.
        candidates.sort(
            key=lambda item:
                item.get(
                    "start_at"
                )
                or now()
        )

        selected = None

        for candidate in candidates:

            updated = get_round(
                candidate["id"]
            )

            if not updated:
                continue

            if updated.get(
                "status"
            ) in (
                "scheduled",
                "active"
            ):

                selected = updated

                break

        if not selected:

            return jsonify({
                "success": True,
                "round": None
            })

        entry = get_user_entry(
            user["telegram_id"],
            selected["id"]
        )

        selected[
            "participant_count"
        ] = count_entries(
            selected["id"]
        )

        selected[
            "user_entry"
        ] = entry

        return jsonify({
            "success": True,
            "round":
                public_round(
                    selected
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

            existing = get_user_entry(
                user["telegram_id"],
                round_id
            )

            if existing:

                return jsonify({
                    "success": True,
                    "already_entered":
                        True,
                    "entry":
                        serialize_value(
                            existing
                        )
                })

            return jsonify({
                "success": False,
                "error":
                    str(e)
            }), 400

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
                False,

            "entry": {
                "id":
                    result["entry_id"],

                "round_id":
                    round_id,

                "mode":
                    mode,

                "status":
                    (
                        "submitted"
                        if mode == "question"
                        else "pending"
                    )
            },

            "quizbee_points":
                result[
                    "quizbee_points"
                ]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                str(e)
        }), 500


# ============================================================
# QUESTION ANSWER
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

        entry_ref = get_entry_ref(
            round_id,
            user["telegram_id"]
        )

        entry_ref.update({
            "answer":
                answer,

            "status":
                "submitted",

            "submitted_at":
                now(),

            "updated_at":
                now()
        })

        # IMPORTANT:
        # Never reveal correctness before settlement.

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
# TASK PROOF
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

        entry_ref = get_entry_ref(
            round_id,
            user["telegram_id"]
        )

        entry_ref.update({
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

            data = (
                doc.to_dict()
                or {}
            )

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
                str(
                    start_raw
                ).replace(
                    "Z",
                    "+00:00"
                )
            )

            end_at = datetime.fromisoformat(
                str(
                    end_raw
                ).replace(
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

        # ----------------------------------------------------
        # IMPORTANT:
        # New rounds are scheduled.
        # The backend automatically activates them
        # when start_at arrives.
        # ----------------------------------------------------

        requested_status = "scheduled"

        current = now()

        if (
            current >= start_at
            and current < end_at
        ):
            requested_status = "active"

        if current >= end_at:

            return jsonify({
                "success": False,
                "error":
                    "The round end time has already passed."
            }), 400

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
                current,

            "updated_at":
                current
        }

        if requested_status == "active":

            round_data[
                "activated_at"
            ] = current

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
# ADMIN MANUAL ACTIVATE
#
# Kept for compatibility with the Admin Mini App.
# It is OPTIONAL.
# Automatic activation is the normal behavior.
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

        ref = round_ref(
            round_id
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
        ) in (
            "closed",
            "settling",
            "settled"
        ):

            return jsonify({
                "success": False,
                "error":
                    "This round can no longer be activated."
            }), 400

        current = now()

        if (
            data.get("end_at")
            and current >= data["end_at"]
        ):

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
            .document(
                entry_id
            )
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

        # Approval is allowed while the round is still
        # open OR after the timer if the entry was submitted
        # before the timer ended.
        #
        # We deliberately do not require the round to still
        # be active here.

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

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        admin_note = str(
            body.get(
                "admin_note",
                ""
            )
        ).strip()

        entry_ref = (
            db.collection(
                "daily_earning_entries"
            )
            .document(
                entry_id
            )
        )

        snap = entry_ref.get()

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

        daily_round_ref = round_ref(
            round_id
        )

        transaction = db.transaction()

        @firestore.transactional
        def reject_transaction(
            transaction
        ):

            entry_snapshot = (
                entry_ref.get(
                    transaction=transaction
                )
            )

            round_snapshot = (
                daily_round_ref.get(
                    transaction=transaction
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

            current = now()

            end_at = current_round.get(
                "end_at"
            )

            round_is_open = (
                current_round.get(
                    "status"
                ) == "active"
                and (
                    not end_at
                    or current < end_at
                )
            )

            status = (
                "rejected"
                if round_is_open
                else "rejected_after_close"
            )

            transaction.update(
                entry_ref,
                {
                    "status":
                        status,

                    "reviewed_at":
                        current,

                    "reviewed_by":
                        admin["telegram_id"],

                    "admin_note":
                        admin_note,

                    "updated_at":
                        current
                }
            )

            # Rejected entries free the slot ONLY
            # while the round is still open.

            if round_is_open:

                current_count = int(
                    current_round.get(
                        "entry_count",
                        0
                    )
                )

                transaction.update(
                    daily_round_ref,
                    {
                        "entry_count":
                            max(
                                0,
                                current_count - 1
                            ),

                        "updated_at":
                            current
                    }
                )

            return status

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
# DETERMINE WINNERS
# ============================================================

def determine_winners(
    round_data,
    entries
):

    winners = []

    mode = round_data.get(
        "mode"
    )

    if mode == "question":

        accepted = accepted_answer_set(
            round_data
        )

        if not accepted:
            return []

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


# ============================================================
# PRIZE SPLIT
# ============================================================

def calculate_prize_split(
    prize_pool_usd,
    winner_count
):

    if winner_count <= 0:
        return []

    pool = Decimal(
        str(
            prize_pool_usd
        )
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

        daily_round_ref = round_ref(
            round_id
        )

        # ----------------------------------------------------
        # FIRST CHECK
        # ----------------------------------------------------

        initial_snapshot = (
            daily_round_ref.get()
        )

        if not initial_snapshot.exists:

            return jsonify({
                "success": False,
                "error":
                    "Round not found."
            }), 404

        initial_data = (
            initial_snapshot.to_dict()
            or {}
        )

        end_at = initial_data.get(
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
        # SETTLEMENT LOCK
        #
        # IMPORTANT:
        # We use:
        #     ref.get(transaction=transaction)
        #
        # NOT:
        #     transaction.get(ref)
        # ----------------------------------------------------

        transaction = db.transaction()

        @firestore.transactional
        def lock_round(
            transaction
        ):

            snapshot = (
                daily_round_ref.get(
                    transaction=transaction
                )
            )

            if not snapshot.exists:

                raise ValueError(
                    "Round not found."
                )

            current_data = (
                snapshot.to_dict()
                or {}
            )

            current_status = (
                current_data.get(
                    "status"
                )
            )

            settlement_status = (
                current_data.get(
                    "settlement_status",
                    "not_settled"
                )
            )

            # Already completely settled.
            if (
                current_status == "settled"
                or settlement_status == "settled"
            ):

                return (
                    "already_settled",
                    current_data
                )

            # If processing from an earlier request,
            # allow this request to resume settlement.
            if (
                settlement_status
                == "processing"
            ):

                return (
                    "resume",
                    current_data
                )

            current = now()

            transaction.update(
                daily_round_ref,
                {
                    "status":
                        "settling",

                    "settlement_status":
                        "processing",

                    "settling_at":
                        current,

                    "settled_by":
                        admin["telegram_id"],

                    "updated_at":
                        current
                }
            )

            current_data[
                "status"
            ] = "settling"

            current_data[
                "settlement_status"
            ] = "processing"

            return (
                "locked",
                current_data
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

            data = (
                doc.to_dict()
                or {}
            )

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

        results = []

        # ----------------------------------------------------
        # CREDIT EACH WINNER
        # ----------------------------------------------------

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

            winner_user_ref = user_ref(
                telegram_id
            )

            credit_transaction = (
                db.transaction()
            )

            @firestore.transactional
            def credit_winner(
                transaction,
                result_ref=result_ref,
                winner_user_ref=winner_user_ref,
                telegram_id=telegram_id,
                amount=amount,
                winner=winner,
                index=index
            ):

                # ------------------------------------------------
                # IMPORTANT:
                # Read using ref.get(transaction=transaction)
                # ------------------------------------------------

                result_snapshot = (
                    result_ref.get(
                        transaction=transaction
                    )
                )

                # Already credited.
                if result_snapshot.exists:

                    return False

                user_snapshot = (
                    winner_user_ref.get(
                        transaction=transaction
                    )
                )

                if not user_snapshot.exists:

                    raise ValueError(
                        "Winner user account not found."
                    )

                current = now()

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
                            current
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
                            current
                    }
                )

                return True

            created = credit_winner(
                credit_transaction
            )

            # Only create the transaction ledger
            # record when money was actually credited.

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

                create_notification(
                    user_id=telegram_id,
                    title="💰 Daily Earning Prize!",
                    message=(
                        f"Congratulations! You won "
                        f"${amount:.2f} from Daily Earning. "
                        f"The prize has been credited to "
                        f"your Prize Balance."
                    ),
                    notification_type="prize",
                    action_url="",
                    button_text="",
                    dedupe_key=(
                        f"daily-earning-prize:"
                        f"{round_id}:"
                        f"{telegram_id}"
                    ),
                    send_telegram=True,
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

        current = now()

        daily_round_ref.update({
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
                current,

            "updated_at":
                current
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
