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


def now():
    return datetime.now(timezone.utc)


def require_user():
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


def user_ref(telegram_id):
    return db.collection(
        "users"
    ).document(
        str(telegram_id)
    )


def get_user(telegram_id):
    snap = user_ref(
        telegram_id
    ).get()

    if not snap.exists:
        return None

    data = snap.to_dict()
    data["telegram_id"] = str(
        telegram_id
    )

    return data


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


def get_round(round_id):
    ref = db.collection(
        "daily_earning_rounds"
    ).document(
        round_id
    )

    snap = ref.get()

    if not snap.exists:
        return None

    data = snap.to_dict()
    data["id"] = round_id

    return data


def public_round(data):
    if not data:
        return None

    result = dict(data)

    result.pop(
        "correct_answer",
        None
    )

    result.pop(
        "accepted_answers",
        None
    )

    return result


def is_round_open(round_data):
    if not round_data:
        return False

    current = now()

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

    return round_data.get(
        "status"
    ) == "active"


def count_entries(round_id):
    docs = list(
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

    active_count = 0

    for doc in docs:
        data = doc.to_dict()

        if data.get("status") in (
            "pending",
            "approved",
            "submitted"
        ):
            active_count += 1

    return active_count


def get_user_entry(
    telegram_id,
    round_id
):
    query = (
        db.collection(
            "daily_earning_entries"
        )
        .where(
            "telegram_id",
            "==",
            str(telegram_id)
        )
        .where(
            "round_id",
            "==",
            round_id
        )
        .limit(1)
    )

    docs = list(
        query.stream()
    )

    if not docs:
        return None

    data = docs[0].to_dict()
    data["id"] = docs[0].id

    return data


def deduct_entry_fee(
    telegram_id
):
    ref = user_ref(
        telegram_id
    )

    transaction = db.transaction()

    @firestore.transactional
    def perform(transaction):
        snapshot = transaction.get(
            ref
        )

        if not snapshot.exists:
            raise ValueError(
                "User account not found."
            )

        data = snapshot.to_dict()

        points = int(
            data.get(
                "quizbee_points",
                0
            )
        )

        if points < ENTRY_FEE:
            raise ValueError(
                "Not enough QuizBee Points. "
                "Watch 10 ads to earn 10 points."
            )

        new_balance = (
            points - ENTRY_FEE
        )

        transaction.update(
            ref,
            {
                "quizbee_points":
                    new_balance,

                "total_spent":
                    firestore.Increment(
                        ENTRY_FEE
                    ),

                "updated_at":
                    now()
            }
        )

        return new_balance

    return perform(
        transaction
    )


def refund_entry_fee(
    telegram_id
):
    user_ref(
        telegram_id
    ).update({
        "quizbee_points":
            firestore.Increment(
                ENTRY_FEE
            ),

        "total_spent":
            firestore.Increment(
                -ENTRY_FEE
            ),

        "updated_at":
            now()
    })


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

    db.collection(
        "transactions"
    ).document().set(
        data
    )


# ============================================================
# CURRENT ROUND
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
                ["scheduled", "active"]
            )
            .order_by(
                "end_at"
            )
            .limit(1)
        )

        docs = list(
            query.stream()
        )

        if not docs:
            return jsonify({
                "success": True,
                "round": None
            })

        doc = docs[0]

        round_data = doc.to_dict()
        round_data["id"] = doc.id

        # Automatically close expired rounds.
        end_at = round_data.get(
            "end_at"
        )

        if (
            end_at
            and now() >= end_at
            and round_data.get("status")
            in ["scheduled", "active"]
        ):
            doc.reference.update({
                "status":
                    "closed",

                "closed_at":
                    now(),

                "updated_at":
                    now()
            })

            round_data["status"] = "closed"

        entry = get_user_entry(
            user["telegram_id"],
            doc.id
        )

        round_data["participant_count"] = (
            count_entries(doc.id)
        )

        round_data["user_entry"] = (
            entry
        )

        return jsonify({
            "success": True,
            "round":
                public_round(
                    round_data
                )
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
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

        existing = get_user_entry(
            user["telegram_id"],
            round_id
        )

        if existing:
            return jsonify({
                "success": True,
                "already_entered": True,
                "entry": existing
            })

        max_entries = int(
            round_data.get(
                "max_entries",
                0
            )
        )

        current_count = count_entries(
            round_id
        )

        if (
            max_entries > 0
            and current_count >= max_entries
        ):
            return jsonify({
                "success": False,
                "error":
                    "Daily Earning slots are full."
            }), 400

        try:
            new_balance = deduct_entry_fee(
                user["telegram_id"]
            )
        except ValueError as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 400

        mode = round_data.get(
            "mode",
            "question"
        )

        status = (
            "submitted"
            if mode == "question"
            else "pending"
        )

        entry_ref = db.collection(
            "daily_earning_entries"
        ).document()

        entry_ref.set({
            "telegram_id":
                user["telegram_id"],

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
                now(),

            "updated_at":
                now()
        })

        create_transaction(
            user["telegram_id"],
            "daily_earning_entry",
            -ENTRY_FEE,
            "quizbee_points",
            {
                "round_id":
                    round_id
            }
        )

        return jsonify({
            "success": True,
            "already_entered": False,
            "entry": {
                "id":
                    entry_ref.id,

                "round_id":
                    round_id,

                "mode":
                    mode,

                "status":
                    status
            },

            "quizbee_points":
                new_balance
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
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

        answer = body.get(
            "answer",
            ""
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

        entry_ref = db.collection(
            "daily_earning_entries"
        ).document(
            entry["id"]
        )

        entry_ref.update({
            "answer":
                str(answer),

            "status":
                "submitted",

            "submitted_at":
                now(),

            "updated_at":
                now()
        })

        # IMPORTANT:
        # We deliberately do NOT reveal whether
        # the answer is correct here.

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
            "error": str(e)
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

        proof_text = body.get(
            "proof_text",
            ""
        )

        proof_url = body.get(
            "proof_url",
            ""
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

        entry_ref = db.collection(
            "daily_earning_entries"
        ).document(
            entry["id"]
        )

        entry_ref.update({
            "proof_text":
                str(proof_text),

            "proof_url":
                str(proof_url),

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
            "error": str(e)
        }), 500


# ============================================================
# MY DAILY EARNING HISTORY
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
            .order_by(
                "created_at",
                direction=firestore.Query.DESCENDING
            )
            .limit(50)
            .stream()
        )

        entries = []

        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            entries.append(data)

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
# ADMIN HELPERS
# ============================================================

def is_admin(telegram_id):
    admin_id = os.getenv(
        "ADMIN_TELEGRAM_ID",
        ""
    )

    return (
        admin_id
        and str(telegram_id)
        == str(admin_id)
    )


# ============================================================
# ADMIN CREATE ROUND
# ============================================================

@daily_earning_bp.post(
    "/api/daily-earning/admin/create"
)
def admin_create_round():
    try:
        user = require_user()

        if not user or not is_admin(
            user["telegram_id"]
        ):
            return jsonify({
                "success": False,
                "error": "Admin only."
            }), 403

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        mode = body.get(
            "mode",
            "question"
        )

        if mode not in (
            "question",
            "task"
        ):
            return jsonify({
                "success": False,
                "error":
                    "Mode must be question or task."
            }), 400

        round_data = {
            "title":
                body.get(
                    "title",
                    "Daily Earning"
                ),

            "mode":
                mode,

            "question":
                body.get(
                    "question",
                    ""
                ),

            "instructions":
                body.get(
                    "instructions",
                    ""
                ),

            "correct_answer":
                body.get(
                    "correct_answer",
                    ""
                ),

            "accepted_answers":
                body.get(
                    "accepted_answers",
                    []
                ),

            "prize_pool_usd":
                float(
                    body.get(
                        "prize_pool_usd",
                        0
                    )
                ),

            "max_entries":
                int(
                    body.get(
                        "max_entries",
                        100
                    )
                ),

            "start_at":
                datetime.fromisoformat(
                    body["start_at"]
                    .replace(
                        "Z",
                        "+00:00"
                    )
                ),

            "end_at":
                datetime.fromisoformat(
                    body["end_at"]
                    .replace(
                        "Z",
                        "+00:00"
                    )
                ),

            "status":
                body.get(
                    "status",
                    "scheduled"
                ),

            "entry_fee":
                ENTRY_FEE,

            "created_at":
                now(),

            "updated_at":
                now()
        }

        ref = db.collection(
            "daily_earning_rounds"
        ).document()

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
            "error": str(e)
        }), 500


# ============================================================
# ADMIN APPROVE TASK
# ============================================================

@daily_earning_bp.post(
    "/api/daily-earning/admin/entries/<entry_id>/approve"
)
def admin_approve_entry(entry_id):
    try:
        user = require_user()

        if not user or not is_admin(
            user["telegram_id"]
        ):
            return jsonify({
                "success": False,
                "error": "Admin only."
            }), 403

        entry_ref = db.collection(
            "daily_earning_entries"
        ).document(
            entry_id
        )

        snap = entry_ref.get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "Entry not found."
            }), 404

        entry = snap.to_dict()

        if entry.get("status") != "pending":
            return jsonify({
                "success": False,
                "error":
                    "Entry is not pending."
            }), 400

        entry_ref.update({
            "status":
                "approved",

            "reviewed_at":
                now(),

            "reviewed_by":
                user["telegram_id"],

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
            "error": str(e)
        }), 500


# ============================================================
# ADMIN REJECT TASK
# ============================================================

@daily_earning_bp.post(
    "/api/daily-earning/admin/entries/<entry_id>/reject"
)
def admin_reject_entry(entry_id):
    try:
        user = require_user()

        if not user or not is_admin(
            user["telegram_id"]
        ):
            return jsonify({
                "success": False,
                "error": "Admin only."
            }), 403

        entry_ref = db.collection(
            "daily_earning_entries"
        ).document(
            entry_id
        )

        snap = entry_ref.get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "Entry not found."
            }), 404

        entry = snap.to_dict()

        if entry.get("status") != "pending":
            return jsonify({
                "success": False,
                "error":
                    "Entry is not pending."
            }), 400

        round_data = get_round(
            entry["round_id"]
        )

        # If the round is still open,
        # the user can resubmit and the
        # slot becomes available again.
        if round_data and is_round_open(
            round_data
        ):
            new_status = "rejected"
        else:
            new_status = "rejected_after_close"

        entry_ref.update({
            "status":
                new_status,

            "reviewed_at":
                now(),

            "reviewed_by":
                user["telegram_id"],

            "updated_at":
                now()
        })

        return jsonify({
            "success": True,
            "message":
                "Entry rejected."
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# SETTLE ROUND
# ============================================================

@daily_earning_bp.post(
    "/api/daily-earning/admin/<round_id>/settle"
)
def settle_round(round_id):
    try:
        user = require_user()

        if not user or not is_admin(
            user["telegram_id"]
        ):
            return jsonify({
                "success": False,
                "error": "Admin only."
            }), 403

        round_ref = db.collection(
            "daily_earning_rounds"
        ).document(
            round_id
        )

        snap = round_ref.get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "Round not found."
            }), 404

        round_data = snap.to_dict()

        if round_data.get(
            "status"
        ) == "settled":
            return jsonify({
                "success": True,
                "message":
                    "Round already settled."
            })

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

        round_ref.update({
            "status":
                "settling",

            "settling_at":
                now(),

            "updated_at":
                now()
        })

        entries = []

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

        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            entries.append(data)

        winners = []

        if round_data.get(
            "mode"
        ) == "question":

            correct = normalize_answer(
                round_data.get(
                    "correct_answer",
                    ""
                )
            )

            accepted = [
                normalize_answer(x)
                for x in round_data.get(
                    "accepted_answers",
                    []
                )
            ]

            for entry in entries:
                if entry.get(
                    "status"
                ) not in (
                    "submitted",
                    "approved"
                ):
                    continue

                submitted = normalize_answer(
                    entry.get(
                        "answer",
                        ""
                    )
                )

                if (
                    submitted == correct
                    or submitted in accepted
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

        prize_pool = Decimal(
            str(
                round_data.get(
                    "prize_pool_usd",
                    0
                )
            )
        )

        pool_cents = int(
            (
                prize_pool * 100
            ).quantize(
                Decimal("1"),
                rounding=ROUND_DOWN
            )
        )

        winner_count = len(
            winners
        )

        if winner_count == 0:
            round_ref.update({
                "status":
                    "settled",

                "winner_count":
                    0,

                "amount_per_winner":
                    0,

                "settled_at":
                    now(),

                "updated_at":
                    now()
            })

            return jsonify({
                "success": True,
                "winner_count": 0,
                "message":
                    "Round settled with no winners."
            })

        base_cents = (
            pool_cents
            // winner_count
        )

        remainder = (
            pool_cents
            % winner_count
        )

        results = []

        for index, winner in enumerate(
            winners
        ):

            cents = base_cents

            # Any leftover cents are
            # distributed one by one to
            # the earliest correct entries.
            if index < remainder:
                cents += 1

            amount = (
                Decimal(cents)
                / Decimal(100)
            )

            amount_float = float(
                amount
            )

            telegram_id = str(
                winner["telegram_id"]
            )

            user_ref(
                telegram_id
            ).update({
                "prize_balance":
                    firestore.Increment(
                        amount_float
                    ),

                "total_earned":
                    firestore.Increment(
                        amount_float
                    ),

                "updated_at":
                    now()
            })

            create_transaction(
                telegram_id,
                "daily_earning_prize",
                amount_float,
                "usd",
                {
                    "round_id":
                        round_id,

                    "winner_index":
                        index + 1
                }
            )

            result_ref = db.collection(
                "daily_earning_results"
            ).document()

            result_ref.set({
                "round_id":
                    round_id,

                "telegram_id":
                    telegram_id,

                "entry_id":
                    winner["id"],

                "amount_usd":
                    amount_float,

                "created_at":
                    now()
            })

            results.append({
                "telegram_id":
                    telegram_id,

                "amount_usd":
                    amount_float
            })

        amount_per_winner = (
            float(
                Decimal(base_cents)
                / Decimal(100)
            )
        )

        round_ref.update({
            "status":
                "settled",

            "winner_count":
                winner_count,

            "amount_per_winner":
                amount_per_winner,

            "prize_pool_usd":
                float(prize_pool),

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
                float(prize_pool),

            "results":
                results
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
