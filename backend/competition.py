# backend/competition.py

from __future__ import annotations

import math
import random
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request
from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import validate_telegram_init_data


competition_bp = Blueprint("competition", __name__)

USER_COLLECTION = "users"
GAME_COLLECTION = "games"
ROUND_COLLECTION = "competition_rounds"
STAGE_COLLECTION = "competition_stages"
ENTRY_COLLECTION = "competition_entries"
PARTICIPANT_COLLECTION = "competition_participants"
RESULT_COLLECTION = "competition_results"
TRANSACTION_COLLECTION = "transactions"

USER_INIT_HEADER = "X-Telegram-Init-Data"

STAGED_GAMES = {
    "guess_it",
    "survivor",
    "dead_number",
}

SINGLE_STAGE_GAMES = {
    "impossible_question",
    "crowd_trap",
    "impossible_choice",
}

ALL_COMPETITION_GAMES = [
    "guess_it",
    "impossible_question",
    "crowd_trap",
    "survivor",
    "dead_number",
    "impossible_choice",
]

GAME_META = {
    "guess_it": {
        "name": "Guess It",
        "emoji": "🎯",
        "total_stages": 7,
        "description": "A 7-stage elimination challenge. Answer correctly to survive.",
    },
    "impossible_question": {
        "name": "Impossible Question",
        "emoji": "💀",
        "total_stages": 1,
        "description": "One difficult question. One answer. No retries.",
    },
    "crowd_trap": {
        "name": "The Crowd Trap",
        "emoji": "🧠",
        "total_stages": 1,
        "description": "Choose a number nobody else chooses.",
    },
    "survivor": {
        "name": "The Survivor",
        "emoji": "🏆",
        "total_stages": 7,
        "description": "Choose the safe option and survive each stage.",
    },
    "dead_number": {
        "name": "Dead Number",
        "emoji": "☠️",
        "total_stages": 7,
        "description": "Avoid the dead numbers and survive.",
    },
    "impossible_choice": {
        "name": "Impossible Choice",
        "emoji": "🤔",
        "total_stages": 1,
        "description": "Predict the crowd using psychology and probability.",
    },
}


# ============================================================
# BASIC HELPERS
# ============================================================

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return now_utc().isoformat()


def parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    if hasattr(value, "to_datetime"):
        dt = value.to_datetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    text = str(value).strip()

    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except Exception:
        return None


def is_time_before(value: Any) -> bool:
    dt = parse_datetime(value)
    if not dt:
        return False
    return now_utc() < dt


def is_time_after(value: Any) -> bool:
    dt = parse_datetime(value)
    if not dt:
        return False
    return now_utc() >= dt


def serialize_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    if hasattr(value, "isoformat") and not isinstance(value, (str, int, float)):
        try:
            return value.isoformat()
        except Exception:
            pass

    if isinstance(value, dict):
        return {str(k): serialize_value(v) for k, v in value.items()}

    if isinstance(value, list):
        return [serialize_value(v) for v in value]

    if isinstance(value, tuple):
        return [serialize_value(v) for v in value]

    return value


def doc_dict(snapshot) -> Dict[str, Any]:
    if not snapshot.exists:
        return {}

    data = snapshot.to_dict() or {}
    data["id"] = snapshot.id
    return serialize_value(data)


def clean_string(value: Any) -> str:
    return str(value or "").strip()


def normalize_answer(value: Any) -> str:
    text = clean_string(value).lower()

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s.%+-]", "", text)

    return text.strip()


def safe_number(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def game_meta(game_id: str) -> Dict[str, Any]:
    return GAME_META.get(
        game_id,
        {
            "name": game_id,
            "emoji": "🎮",
            "total_stages": 1,
            "description": "",
        },
    )


def game_display(game_id: str) -> str:
    meta = game_meta(game_id)
    return f"{meta['emoji']} {meta['name']}"


# ============================================================
# TELEGRAM AUTHENTICATION
# ============================================================

def get_telegram_user() -> Dict[str, Any]:
    init_data = request.headers.get(USER_INIT_HEADER, "").strip()

    if not init_data:
        raise ValueError("Telegram authentication data is missing.")

    user = validate_telegram_init_data(init_data)

    if not user:
        raise ValueError("Invalid Telegram authentication data.")

    return user


def telegram_id_from_user(user: Dict[str, Any]) -> str:
    telegram_id = (
        user.get("id")
        or user.get("telegram_id")
        or user.get("user_id")
    )

    if telegram_id is None:
        raise ValueError("Telegram user ID is missing.")

    return str(telegram_id)


def current_user_document():
    telegram_user = get_telegram_user()
    telegram_id = telegram_id_from_user(telegram_user)

    ref = db.collection(USER_COLLECTION).document(telegram_id)
    snap = ref.get()

    if not snap.exists:
        raise ValueError("QuizBee user account was not found.")

    return telegram_user, telegram_id, ref, snap


# ============================================================
# ERROR / RESPONSE HELPERS
# ============================================================

def error_response(message: str, status: int = 400):
    return jsonify({
        "success": False,
        "error": message,
    }), status


def success_response(data: Optional[Dict[str, Any]] = None):
    payload = {
        "success": True,
    }

    if data:
        payload.update(data)

    return jsonify(payload)


# ============================================================
# USER RESPONSE
# ============================================================

def user_public_data(user_data: Dict[str, Any], telegram_id: str) -> Dict[str, Any]:
    points = safe_int(
        user_data.get(
            "points",
            user_data.get("quizbee_points", 0),
        )
    )

    prize_balance = safe_number(
        user_data.get(
            "prize_balance_usd",
            user_data.get("prize_balance", 0),
        )
    )

    return {
        "telegram_id": str(telegram_id),
        "points": points,
        "quizbee_points": points,
        "prize_balance_usd": prize_balance,
        "prize_balance": prize_balance,
        "first_name": user_data.get("first_name", ""),
        "username": user_data.get("username", ""),
    }


# ============================================================
# GAME SETUP
# ============================================================

def build_game_document(game_id: str) -> Dict[str, Any]:
    meta = game_meta(game_id)

    active = game_id in {
        "guess_it",
        "impossible_question",
    }

    return {
        "id": game_id,
        "name": meta["name"],
        "emoji": meta["emoji"],
        "description": meta["description"],
        "active": active,
        "competition_enabled": True,
        "total_stages": meta["total_stages"],
        "default_entry_fee": 10,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }


@competition_bp.route("/api/admin/competition/setup-games", methods=["POST"])
def admin_setup_games():
    try:
        _require_admin()

        batch = db.batch()

        for game_id in ALL_COMPETITION_GAMES:
            ref = db.collection(GAME_COLLECTION).document(game_id)
            batch.set(
                ref,
                build_game_document(game_id),
                merge=True,
            )

        batch.commit()

        return success_response({
            "message": "Competition games initialized.",
            "games": ALL_COMPETITION_GAMES,
        })

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# FIND ROUND / STAGE
# ============================================================

def get_round_ref(round_id: str):
    return db.collection(ROUND_COLLECTION).document(round_id)


def get_stage_ref(round_id: str, stage_no: int):
    return db.collection(STAGE_COLLECTION).document(
        f"{round_id}_{stage_no}"
    )


def get_entry_ref(round_id: str, stage_no: int, telegram_id: str):
    return db.collection(ENTRY_COLLECTION).document(
        f"{round_id}_{stage_no}_{telegram_id}"
    )


def get_participant_ref(round_id: str, telegram_id: str):
    return db.collection(PARTICIPANT_COLLECTION).document(
        f"{round_id}_{telegram_id}"
    )


def get_active_round(game_id: str):
    query = (
        db.collection(ROUND_COLLECTION)
        .where("game_id", "==", game_id)
        .where("status", "in", ["waiting", "live"])
        .limit(10)
    )

    docs = list(query.stream())

    if not docs:
        return None, None

    docs.sort(
        key=lambda s: str(
            (s.to_dict() or {}).get("created_at", "")
        ),
        reverse=True,
    )

    for snap in docs:
        data = snap.to_dict() or {}

        if data.get("status") in {"waiting", "live"}:
            return snap.reference, data

    return None, None


def get_current_stage(round_data: Dict[str, Any]):
    round_id = str(round_data.get("id", ""))
    stage_no = safe_int(round_data.get("current_stage", 1), 1)

    if not round_id:
        return None, None

    ref = get_stage_ref(round_id, stage_no)
    snap = ref.get()

    if not snap.exists:
        return ref, None

    return ref, snap.to_dict() or {}


# ============================================================
# STAGE STATUS
# ============================================================

def stage_is_live(stage: Dict[str, Any]) -> bool:
    status = stage.get("status")

    if status != "live":
        return False

    start_at = stage.get("start_at")
    end_at = stage.get("end_at")

    if start_at and is_time_before(start_at):
        return False

    if end_at and is_time_after(end_at):
        return False

    return True


def stage_has_started(stage: Dict[str, Any]) -> bool:
    start_at = stage.get("start_at")

    if not start_at:
        return True

    return not is_time_before(start_at)


def stage_has_ended(stage: Dict[str, Any]) -> bool:
    end_at = stage.get("end_at")

    if not end_at:
        return False

    return is_time_after(end_at)


# ============================================================
# ROUND STATE FOR USER
# ============================================================

def determine_user_stage_state(
    game_id: str,
    round_ref,
    round_data: Dict[str, Any],
    telegram_id: str,
):
    round_id = round_ref.id

    status = round_data.get("status", "waiting")

    if status in {"settled", "finished"}:
        return {
            "status": "finished",
            "round": {
                **round_data,
                "id": round_id,
            },
        }

    current_stage_no = safe_int(
        round_data.get("current_stage", 1),
        1,
    )

    stage_ref = get_stage_ref(
        round_id,
        current_stage_no,
    )

    stage_snap = stage_ref.get()

    if not stage_snap.exists:
        return {
            "status": "round_not_started",
            "round": {
                **round_data,
                "id": round_id,
            },
        }

    stage = stage_snap.to_dict() or {}
    stage["id"] = stage_snap.id

    if stage.get("status") not in {"live", "closed"}:
        return {
            "status": "round_not_started",
            "round": {
                **round_data,
                "id": round_id,
            },
            "stage": stage,
        }

    participant_ref = get_participant_ref(
        round_id,
        telegram_id,
    )

    participant_snap = participant_ref.get()

    if participant_snap.exists:
        participant = participant_snap.to_dict() or {}

        participant_status = participant.get("status")

        if participant_status in {
            "eliminated",
            "failed",
            "forfeited",
        }:
            return {
                "status": "eliminated",
                "message": participant.get(
                    "message",
                    "You are out of this round.",
                ),
                "round": {
                    **round_data,
                    "id": round_id,
                },
                "stage": stage,
            }

    entry_ref = get_entry_ref(
        round_id,
        current_stage_no,
        telegram_id,
    )

    entry_snap = entry_ref.get()

    if not entry_snap.exists:
        if stage.get("status") != "live":
            return {
                "status": "round_not_started",
                "round": {
                    **round_data,
                    "id": round_id,
                },
                "stage": stage,
            }

        if stage_has_ended(stage):
            return {
                "status": "round_not_started",
                "round": {
                    **round_data,
                    "id": round_id,
                },
                "stage": stage,
            }

        return {
            "status": "needs_entry",
            "round": {
                **round_data,
                "id": round_id,
            },
            "stage": stage,
            "entry_fee": safe_int(stage.get("entry_fee", 0)),
        }

    entry = entry_snap.to_dict() or {}

    if entry.get("status") == "submitted":
        return {
            "status": "submitted",
            "message": "Your answer has been recorded. Wait for the stage to finish.",
            "round": {
                **round_data,
                "id": round_id,
            },
            "stage": stage,
        }

    if entry.get("status") in {
        "correct",
        "survived",
        "winner",
    }:
        return {
            "status": "submitted",
            "message": "Your participation for this stage is already recorded.",
            "round": {
                **round_data,
                "id": round_id,
            },
            "stage": stage,
        }

    if stage.get("status") == "live":
        return {
            "status": "ready",
            "round": {
                **round_data,
                "id": round_id,
            },
            "stage": stage,
            "entry_fee": safe_int(stage.get("entry_fee", 0)),
        }

    return {
        "status": "round_not_started",
        "round": {
            **round_data,
            "id": round_id,
        },
        "stage": stage,
    }


# ============================================================
# USER STATE
# ============================================================

@competition_bp.route(
    "/api/competition/<game_id>/state",
    methods=["GET"],
)
def competition_state(game_id: str):
    try:
        telegram_user, telegram_id, user_ref, user_snap = (
            current_user_document()
        )

        game_id = clean_string(game_id)

        if game_id not in ALL_COMPETITION_GAMES:
            return error_response("Competition game not found.", 404)

        game_ref = db.collection(GAME_COLLECTION).document(game_id)
        game_snap = game_ref.get()

        if not game_snap.exists:
            return error_response("Competition game has not been initialized.", 404)

        game = game_snap.to_dict() or {}
        game["id"] = game_snap.id

        if not game.get("active", False):
            return success_response({
                "status": "no_round",
                "game": game,
                "user": user_public_data(
                    user_snap.to_dict() or {},
                    telegram_id,
                ),
            })

        round_ref, round_data = get_active_round(game_id)

        if not round_ref or not round_data:
            return success_response({
                "status": "no_round",
                "game": game,
                "user": user_public_data(
                    user_snap.to_dict() or {},
                    telegram_id,
                ),
            })

        round_data["id"] = round_ref.id

        state = determine_user_stage_state(
            game_id,
            round_ref,
            round_data,
            telegram_id,
        )

        state["game"] = game

        state["user"] = user_public_data(
            user_snap.to_dict() or {},
            telegram_id,
        )

        return success_response(state)

    except ValueError as exc:
        return error_response(str(exc), 401)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# TRANSACTIONAL ENTRY CHARGE
# ============================================================

@firestore.transactional
def _charge_competition_entry(
    transaction,
    user_ref,
    entry_ref,
    participant_ref,
    transaction_ref,
    telegram_id: str,
    telegram_user: Dict[str, Any],
    round_id: str,
    game_id: str,
    stage_no: int,
    fee: int,
):
    """
    Atomically:
      1. checks whether this user already entered the stage
      2. checks the user's points
      3. deducts the entry fee
      4. creates the entry
      5. creates/updates participant
      6. creates transaction history

    This MUST be called through firestore.transactional.
    """

    entry_snap = entry_ref.get(transaction=transaction)

    if entry_snap.exists:
        user_snap = user_ref.get(transaction=transaction)

        return {
            "already_entered": True,
            "user": user_snap.to_dict() or {},
        }

    user_snap = user_ref.get(transaction=transaction)

    if not user_snap.exists:
        raise ValueError("QuizBee user account was not found.")

    user_data = user_snap.to_dict() or {}

    current_points = safe_int(
        user_data.get(
            "points",
            user_data.get("quizbee_points", 0),
        )
    )

    if current_points < fee:
        raise ValueError(
            f"You need {fee} QuizBee Points to enter this stage."
        )

    new_points = current_points - fee

    transaction.update(
        user_ref,
        {
            "points": new_points,
            "quizbee_points": new_points,
            "total_spent": firestore.Increment(fee),
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
    )

    entry_data = {
        "id": entry_ref.id,
        "round_id": round_id,
        "game_id": game_id,
        "stage_no": stage_no,
        "telegram_id": telegram_id,
        "status": "entered",
        "answer": None,
        "entered_at": firestore.SERVER_TIMESTAMP,
        "submitted_at": None,
        "fee": fee,
    }

    transaction.set(
        entry_ref,
        entry_data,
    )

    participant_data = {
        "round_id": round_id,
        "game_id": game_id,
        "telegram_id": telegram_id,
        "status": "active",
        "current_stage": stage_no,
        "joined_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }

    transaction.set(
        participant_ref,
        participant_data,
        merge=True,
    )

    transaction.set(
        transaction_ref,
        {
            "type": "competition_entry",
            "category": "game_entry",
            "telegram_id": telegram_id,
            "game_id": game_id,
            "round_id": round_id,
            "stage_no": stage_no,
            "amount_points": fee,
            "direction": "debit",
            "status": "completed",
            "description": (
                f"{game_display(game_id)} "
                f"Stage {stage_no} entry"
            ),
            "created_at": firestore.SERVER_TIMESTAMP,
        },
    )

    user_data["points"] = new_points
    user_data["quizbee_points"] = new_points

    return {
        "already_entered": False,
        "user": user_data,
    }


# ============================================================
# USER ENTER
# ============================================================

@competition_bp.route(
    "/api/competition/<game_id>/enter",
    methods=["POST"],
)
def competition_enter(game_id: str):
    try:
        telegram_user, telegram_id, user_ref, user_snap = (
            current_user_document()
        )

        game_id = clean_string(game_id)

        if game_id not in ALL_COMPETITION_GAMES:
            return error_response("Competition game not found.", 404)

        game_ref = db.collection(GAME_COLLECTION).document(game_id)
        game_snap = game_ref.get()

        if not game_snap.exists:
            return error_response(
                "Competition game has not been initialized.",
                404,
            )

        game = game_snap.to_dict() or {}

        if not game.get("active", False):
            return error_response(
                "This competition is currently unavailable.",
                400,
            )

        round_ref, round_data = get_active_round(game_id)

        if not round_ref or not round_data:
            return error_response(
                "No active round is available.",
                400,
            )

        round_id = round_ref.id

        if round_data.get("status") not in {
            "waiting",
            "live",
        }:
            return error_response(
                "This round is not currently open.",
                400,
            )

        stage_no = safe_int(
            round_data.get("current_stage", 1),
            1,
        )

        stage_ref = get_stage_ref(
            round_id,
            stage_no,
        )

        stage_snap = stage_ref.get()

        if not stage_snap.exists:
            return error_response(
                "Round not started yet.",
                400,
            )

        stage = stage_snap.to_dict() or {}

        if stage.get("status") != "live":
            return error_response(
                "Round not started yet.",
                400,
            )

        if not stage_has_started(stage):
            return error_response(
                "Round not started yet.",
                400,
            )

        if stage_has_ended(stage):
            return error_response(
                "This stage has ended.",
                400,
            )

        participant_ref = get_participant_ref(
            round_id,
            telegram_id,
        )

        participant_snap = participant_ref.get()

        if participant_snap.exists:
            participant = participant_snap.to_dict() or {}

            if participant.get("status") in {
                "eliminated",
                "failed",
                "forfeited",
            }:
                return error_response(
                    "You are already out of this round.",
                    400,
                )

        fee = safe_int(
            stage.get(
                "entry_fee",
                game.get("default_entry_fee", 10),
            ),
            10,
        )

        if fee < 0:
            fee = 0

        entry_ref = get_entry_ref(
            round_id,
            stage_no,
            telegram_id,
        )

        # Deterministic transaction document ID prevents duplicate
        # transaction records when Firestore retries the transaction.
        transaction_ref = db.collection(
            TRANSACTION_COLLECTION
        ).document(
            f"competition_entry_{round_id}_{stage_no}_{telegram_id}"
        )

        transaction = db.transaction()

        result = _charge_competition_entry(
            transaction,
            user_ref,
            entry_ref,
            participant_ref,
            transaction_ref,
            telegram_id,
            telegram_user,
            round_id,
            game_id,
            stage_no,
            fee,
        )

        return success_response({
            "already_entered": result["already_entered"],
            "message": (
                "You already entered this stage."
                if result["already_entered"]
                else "Entry successful! 🎉"
            ),
            "user": user_public_data(
                result["user"],
                telegram_id,
            ),
        })

    except ValueError as exc:
        return error_response(str(exc), 400)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ANSWER EVALUATION HELPERS
# ============================================================

def accepted_answers(stage: Dict[str, Any]) -> List[str]:
    answers = []

    correct = stage.get("correct_answer")

    if correct not in (None, ""):
        answers.append(normalize_answer(correct))

    for value in stage.get("accepted_answers", []) or []:
        normalized = normalize_answer(value)

        if normalized:
            answers.append(normalized)

    return list(dict.fromkeys(
        x for x in answers if x
    ))


def answer_is_correct(
    game_id: str,
    stage: Dict[str, Any],
    answer: str,
) -> bool:
    normalized = normalize_answer(answer)

    if game_id in {
        "guess_it",
        "impossible_question",
    }:
        return normalized in accepted_answers(stage)

    if game_id == "survivor":
        safe_option = normalize_answer(
            stage.get("safe_option", "")
        )

        return (
            bool(safe_option)
            and normalized == safe_option
        )

    return False


# ============================================================
# CROWD TRAP
# ============================================================

def valid_number_for_stage(
    stage: Dict[str, Any],
    value: Any,
) -> Tuple[bool, Optional[int]]:
    try:
        number = int(str(value).strip())
    except Exception:
        return False, None

    minimum = safe_int(
        stage.get("min_number", 1),
        1,
    )

    maximum = safe_int(
        stage.get("max_number", 20),
        20,
    )

    if minimum > maximum:
        minimum, maximum = maximum, minimum

    if number < minimum or number > maximum:
        return False, number

    return True, number


# ============================================================
# IMPOSSIBLE CHOICE
# ============================================================

def calculate_choice_winners(
    entries: List[Dict[str, Any]],
    stage: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not entries:
        return []

    counts: Dict[str, int] = {}

    for entry in entries:
        answer = clean_string(entry.get("answer"))

        if not answer:
            continue

        key = normalize_answer(answer)
        counts[key] = counts.get(key, 0) + 1

    if not counts:
        return []

    total = sum(counts.values())

    mechanic = stage.get(
        "mechanic",
        "minority",
    )

    winner_keys: List[str] = []

    if mechanic == "majority":
        highest = max(counts.values())

        winner_keys = [
            key
            for key, count in counts.items()
            if count == highest
        ]

    elif mechanic == "minority":
        lowest = min(counts.values())

        winner_keys = [
            key
            for key, count in counts.items()
            if count == lowest
        ]

    elif mechanic == "closest_target":
        target = safe_number(
            stage.get("target_percentage", 50),
            50,
        )

        differences = {}

        for key, count in counts.items():
            percentage = (count / total) * 100
            differences[key] = abs(
                percentage - target
            )

        closest = min(differences.values())

        winner_keys = [
            key
            for key, difference in differences.items()
            if math.isclose(
                difference,
                closest,
                abs_tol=0.0001,
            )
        ]

    elif mechanic == "within_range":
        minimum = safe_number(
            stage.get("target_min_percentage", 40),
            40,
        )

        maximum = safe_number(
            stage.get("target_max_percentage", 60),
            60,
        )

        for key, count in counts.items():
            percentage = (count / total) * 100

            if minimum <= percentage <= maximum:
                winner_keys.append(key)

    return [
        entry
        for entry in entries
        if normalize_answer(entry.get("answer", ""))
        in winner_keys
    ]


# ============================================================
# DEAD NUMBER
# ============================================================

def calculate_dead_numbers(
    stage: Dict[str, Any],
) -> List[str]:
    existing = stage.get("dead_numbers", []) or []

    cleaned = []

    for value in existing:
        text = clean_string(value)

        if text:
            cleaned.append(text)

    if cleaned:
        return list(dict.fromkeys(cleaned))

    minimum = safe_int(
        stage.get("min_number", 1),
        1,
    )

    maximum = safe_int(
        stage.get("max_number", 20),
        20,
    )

    count = safe_int(
        stage.get("dead_count", 1),
        1,
    )

    if minimum > maximum:
        minimum, maximum = maximum, minimum

    numbers = list(
        range(
            minimum,
            maximum + 1,
        )
    )

    if not numbers:
        return []

    count = min(
        max(count, 1),
        len(numbers),
    )

    generated = random.sample(
        numbers,
        count,
    )

    return [
        str(number)
        for number in generated
    ]


# ============================================================
# USER SUBMIT
# ============================================================

@competition_bp.route(
    "/api/competition/<game_id>/submit",
    methods=["POST"],
)
def competition_submit(game_id: str):
    try:
        telegram_user, telegram_id, user_ref, user_snap = (
            current_user_document()
        )

        game_id = clean_string(game_id)

        if game_id not in ALL_COMPETITION_GAMES:
            return error_response(
                "Competition game not found.",
                404,
            )

        body = request.get_json(silent=True) or {}

        answer = body.get("answer")

        if answer is None:
            return error_response(
                "Answer is required.",
                400,
            )

        answer = clean_string(answer)

        if not answer:
            return error_response(
                "Answer cannot be empty.",
                400,
            )

        round_ref, round_data = get_active_round(game_id)

        if not round_ref or not round_data:
            return error_response(
                "No active round is available.",
                400,
            )

        round_id = round_ref.id

        stage_no = safe_int(
            round_data.get("current_stage", 1),
            1,
        )

        stage_ref = get_stage_ref(
            round_id,
            stage_no,
        )

        stage_snap = stage_ref.get()

        if not stage_snap.exists:
            return error_response(
                "Round not started yet.",
                400,
            )

        stage = stage_snap.to_dict() or {}

        if stage.get("status") != "live":
            return error_response(
                "This stage is not live.",
                400,
            )

        if stage_has_ended(stage):
            return error_response(
                "This stage has ended.",
                400,
            )

        entry_ref = get_entry_ref(
            round_id,
            stage_no,
            telegram_id,
        )

        entry_snap = entry_ref.get()

        if not entry_snap.exists:
            return error_response(
                "You must enter this stage before submitting an answer.",
                400,
            )

        entry = entry_snap.to_dict() or {}

        if entry.get("status") == "submitted":
            return error_response(
                "You have already submitted your answer.",
                400,
            )

        if entry.get("status") in {
            "correct",
            "wrong",
            "eliminated",
            "winner",
            "survived",
        }:
            return error_response(
                "Your answer for this stage is already locked.",
                400,
            )

        submitted_at = firestore.SERVER_TIMESTAMP

        # --------------------------------------------------------
        # CROWD TRAP / DEAD NUMBER
        # --------------------------------------------------------

        if game_id in {
            "crowd_trap",
            "dead_number",
        }:
            valid, number = valid_number_for_stage(
                stage,
                answer,
            )

            if not valid:
                return error_response(
                    "Choose a valid number in the allowed range.",
                    400,
                )

            answer = str(number)

        # --------------------------------------------------------
        # IMPOSSIBLE CHOICE OPTIONS
        # --------------------------------------------------------

        if game_id == "impossible_choice":
            options = [
                clean_string(x)
                for x in stage.get("options", []) or []
            ]

            normalized_options = {
                normalize_answer(x)
                for x in options
                if x
            }

            if normalize_answer(answer) not in normalized_options:
                return error_response(
                    "Choose one of the available options.",
                    400,
                )

        # --------------------------------------------------------
        # SAVE ANSWER
        # --------------------------------------------------------

        entry_ref.update({
            "answer": answer,
            "status": "submitted",
            "submitted_at": submitted_at,
        })

        participant_ref = get_participant_ref(
            round_id,
            telegram_id,
        )

        participant_ref.set(
            {
                "round_id": round_id,
                "game_id": game_id,
                "telegram_id": telegram_id,
                "current_stage": stage_no,
                "last_answer": answer,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

        # --------------------------------------------------------
        # DO NOT REVEAL CORRECTNESS FOR IMPOSSIBLE QUESTION
        # --------------------------------------------------------

        if game_id == "impossible_question":
            return success_response({
                "message": (
                    "Answer submitted. 🔒 "
                    "You will not see the result until the competition ends."
                ),
            })

        # --------------------------------------------------------
        # OPEN ANSWER GAMES
        # --------------------------------------------------------

        if game_id == "guess_it":
            if answer_is_correct(
                game_id,
                stage,
                answer,
            ):
                entry_ref.update({
                    "status": "correct",
                    "outcome": "survived",
                })

                participant_ref.set(
                    {
                        "status": "active",
                        "current_stage": stage_no,
                        "updated_at": firestore.SERVER_TIMESTAMP,
                    },
                    merge=True,
                )

                return success_response({
                    "message": (
                        "Answer submitted. 🔒 "
                        "Your result will be confirmed when the stage closes."
                    ),
                })

            entry_ref.update({
                "status": "submitted",
            })

            return success_response({
                "message": (
                    "Answer submitted. 🔒 "
                    "Your result will be revealed when the stage closes."
                ),
            })

        # --------------------------------------------------------
        # SURVIVOR
        # --------------------------------------------------------

        if game_id == "survivor":
            entry_ref.update({
                "status": "submitted",
            })

            return success_response({
                "message": (
                    "Choice locked. 🔒 "
                    "Your result will be revealed when the stage closes."
                ),
            })

        # --------------------------------------------------------
        # DEAD NUMBER
        # --------------------------------------------------------

        if game_id == "dead_number":
            entry_ref.update({
                "status": "submitted",
            })

            return success_response({
                "message": (
                    "Number locked. 🔒 "
                    "The dead numbers will be evaluated when the stage closes."
                ),
            })

        # --------------------------------------------------------
        # CROWD TRAP
        # --------------------------------------------------------

        if game_id == "crowd_trap":
            entry_ref.update({
                "status": "submitted",
            })

            return success_response({
                "message": (
                    "Number locked. 🧠 "
                    "The final winners will be determined when the stage closes."
                ),
            })

        # --------------------------------------------------------
        # IMPOSSIBLE CHOICE
        # --------------------------------------------------------

        if game_id == "impossible_choice":
            entry_ref.update({
                "status": "submitted",
            })

            return success_response({
                "message": (
                    "Choice locked. 🤔 "
                    "The result will be calculated when the competition ends."
                ),
            })

        return success_response({
            "message": "Answer submitted.",
        })

    except ValueError as exc:
        return error_response(str(exc), 400)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ADMIN AUTH
# ============================================================

def _admin_ids() -> List[str]:
    import os

    values = []

    raw_many = os.getenv(
        "ADMIN_TELEGRAM_IDS",
        "",
    )

    for item in raw_many.split(","):
        item = item.strip()

        if item:
            values.append(item)

    raw_single = os.getenv(
        "ADMIN_TELEGRAM_ID",
        "",
    ).strip()

    if raw_single:
        values.append(raw_single)

    return list(dict.fromkeys(values))


def _require_admin():
    import os

    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        "",
    ).strip()

    if not init_data:
        raise ValueError(
            "Admin Telegram authentication data is missing."
        )

    # Admin panel uses ADMIN_BOT_TOKEN.
    admin_user = validate_telegram_init_data(
        init_data,
        bot_token=os.getenv("ADMIN_BOT_TOKEN"),
    )

    if not admin_user:
        raise ValueError(
            "Invalid admin Telegram authentication."
        )

    telegram_id = str(
        admin_user.get("id")
        or admin_user.get("telegram_id")
        or ""
    )

    if telegram_id not in _admin_ids():
        raise ValueError(
            "You are not authorized to access the competition admin panel."
        )

    return admin_user


# ============================================================
# ADMIN CREATE ROUND
# ============================================================

@competition_bp.route(
    "/api/admin/competition/rounds/create",
    methods=["POST"],
)
def admin_create_round():
    try:
        _require_admin()

        body = request.get_json(silent=True) or {}

        game_id = clean_string(
            body.get("game_id")
        )

        if game_id not in ALL_COMPETITION_GAMES:
            return error_response(
                "Invalid competition game.",
                400,
            )

        meta = game_meta(game_id)

        round_id = (
            f"{game_id}_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_"
            f"{uuid.uuid4().hex[:6]}"
        )

        title = clean_string(
            body.get("title")
        ) or (
            f"{meta['name']} Competition"
        )

        prize_pool = max(
            0,
            safe_number(
                body.get("prize_pool_usd", 0),
                0,
            ),
        )

        entry_fees = body.get(
            "entry_fees",
            [],
        )

        if not isinstance(entry_fees, list):
            entry_fees = []

        cleaned_fees = []

        for value in entry_fees:
            cleaned_fees.append(
                max(
                    0,
                    safe_int(value, 0),
                )
            )

        if game_id in STAGED_GAMES:
            while len(cleaned_fees) < 7:
                stage_no = len(cleaned_fees) + 1

                cleaned_fees.append(
                    30
                    if stage_no == 7
                    else 10
                )

            cleaned_fees = cleaned_fees[:7]

            total_stages = 7

        else:
            if not cleaned_fees:
                cleaned_fees = [10]

            total_stages = 1

        start_at = body.get("start_at")

        round_data = {
            "id": round_id,
            "game_id": game_id,
            "title": title,
            "status": "waiting",
            "current_stage": 1,
            "total_stages": total_stages,
            "entry_fees": cleaned_fees,
            "prize_pool_usd": prize_pool,
            "winner_count": 0,
            "winner_amount_usd": 0,
            "start_at": start_at,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "created_by": str(
                _admin_ids()[0]
                if _admin_ids()
                else ""
            ),
        }

        db.collection(
            ROUND_COLLECTION
        ).document(round_id).set(
            round_data
        )

        return success_response({
            "round_id": round_id,
            "round": serialize_value(round_data),
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ADMIN LIST ROUNDS
# ============================================================

@competition_bp.route(
    "/api/admin/competition/rounds",
    methods=["GET"],
)
def admin_list_rounds():
    try:
        _require_admin()

        game_id = clean_string(
            request.args.get("game_id")
        )

        query = db.collection(
            ROUND_COLLECTION
        )

        if game_id:
            query = query.where(
                "game_id",
                "==",
                game_id,
            )

        docs = list(
            query.limit(100).stream()
        )

        rounds = []

        for snap in docs:
            data = snap.to_dict() or {}
            data["id"] = snap.id

            rounds.append(
                serialize_value(data)
            )

        rounds.sort(
            key=lambda item: str(
                item.get(
                    "created_at",
                    "",
                )
            ),
            reverse=True,
        )

        return success_response({
            "rounds": rounds,
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ADMIN ROUND DETAIL
# ============================================================

@competition_bp.route(
    "/api/admin/competition/rounds/<round_id>",
    methods=["GET"],
)
def admin_round_detail(round_id: str):
    try:
        _require_admin()

        round_ref = get_round_ref(round_id)
        round_snap = round_ref.get()

        if not round_snap.exists:
            return error_response(
                "Competition round not found.",
                404,
            )

        round_data = round_snap.to_dict() or {}
        round_data["id"] = round_snap.id

        stage_docs = list(
            db.collection(
                STAGE_COLLECTION
            )
            .where(
                "round_id",
                "==",
                round_id,
            )
            .stream()
        )

        stages = []

        for snap in stage_docs:
            data = snap.to_dict() or {}
            data["id"] = snap.id
            stages.append(
                serialize_value(data)
            )

        stages.sort(
            key=lambda item: safe_int(
                item.get("stage_no", 0),
                0,
            )
        )

        entry_docs = list(
            db.collection(
                ENTRY_COLLECTION
            )
            .where(
                "round_id",
                "==",
                round_id,
            )
            .limit(500)
            .stream()
        )

        entries = []

        for snap in entry_docs:
            data = snap.to_dict() or {}
            data["id"] = snap.id

            entries.append(
                serialize_value(data)
            )

        entries.sort(
            key=lambda item: (
                safe_int(
                    item.get("stage_no", 0),
                    0,
                ),
                str(
                    item.get(
                        "telegram_id",
                        "",
                    )
                ),
            )
        )

        result_docs = list(
            db.collection(
                RESULT_COLLECTION
            )
            .where(
                "round_id",
                "==",
                round_id,
            )
            .limit(500)
            .stream()
        )

        results = []

        for snap in result_docs:
            data = snap.to_dict() or {}
            data["id"] = snap.id

            results.append(
                serialize_value(data)
            )

        return success_response({
            "round": serialize_value(round_data),
            "stages": stages,
            "entries": entries,
            "results": results,
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ADMIN CREATE STAGE
# ============================================================

@competition_bp.route(
    "/api/admin/competition/rounds/<round_id>/stages/create",
    methods=["POST"],
)
def admin_create_stage(round_id: str):
    try:
        _require_admin()

        round_ref = get_round_ref(round_id)
        round_snap = round_ref.get()

        if not round_snap.exists:
            return error_response(
                "Competition round not found.",
                404,
            )

        round_data = round_snap.to_dict() or {}

        game_id = clean_string(
            round_data.get("game_id")
        )

        body = request.get_json(
            silent=True
        ) or {}

        stage_no = safe_int(
            body.get("stage_no", 1),
            1,
        )

        total_stages = safe_int(
            round_data.get("total_stages", 1),
            1,
        )

        if stage_no < 1 or stage_no > total_stages:
            return error_response(
                "Invalid stage number.",
                400,
            )

        stage_ref = get_stage_ref(
            round_id,
            stage_no,
        )

        if stage_ref.get().exists:
            return error_response(
                "This stage has already been created.",
                400,
            )

        title = clean_string(
            body.get("title")
        ) or f"Stage {stage_no}"

        question = clean_string(
            body.get("question")
        )

        entry_fee = max(
            0,
            safe_int(
                body.get("entry_fee", 10),
                10,
            ),
        )

        options = body.get(
            "options",
            [],
        )

        if not isinstance(options, list):
            options = []

        options = [
            clean_string(x)
            for x in options
            if clean_string(x)
        ]

        accepted = body.get(
            "accepted_answers",
            [],
        )

        if not isinstance(accepted, list):
            accepted = []

        accepted = [
            clean_string(x)
            for x in accepted
            if clean_string(x)
        ]

        dead_numbers = body.get(
            "dead_numbers",
            [],
        )

        if not isinstance(dead_numbers, list):
            dead_numbers = []

        dead_numbers = [
            clean_string(x)
            for x in dead_numbers
            if clean_string(x)
        ]

        generation_mode = clean_string(
            body.get(
                "generation_mode",
                "admin",
            )
        )

        correct_answer = clean_string(
            body.get("correct_answer")
        )

        safe_option = clean_string(
            body.get("safe_option")
        )

        minimum = safe_int(
            body.get("min_number", 1),
            1,
        )

        maximum = safe_int(
            body.get("max_number", 20),
            20,
        )

        if minimum > maximum:
            minimum, maximum = maximum, minimum

        dead_count = max(
            1,
            safe_int(
                body.get("dead_count", 1),
                1,
            ),
        )

        mechanic = clean_string(
            body.get(
                "mechanic",
                "minority",
            )
        )

        if mechanic not in {
            "minority",
            "majority",
            "closest_target",
            "within_range",
        }:
            mechanic = "minority"

        target_percentage = safe_number(
            body.get(
                "target_percentage",
                50,
            ),
            50,
        )

        target_min_percentage = safe_number(
            body.get(
                "target_min_percentage",
                40,
            ),
            40,
        )

        target_max_percentage = safe_number(
            body.get(
                "target_max_percentage",
                60,
            ),
            60,
        )

        # Random generation is allowed for number games.
        if (
            generation_mode == "random"
            and game_id == "dead_number"
            and not dead_numbers
        ):
            numbers = list(
                range(
                    minimum,
                    maximum + 1,
                )
            )

            if numbers:
                dead_numbers = [
                    str(x)
                    for x in random.sample(
                        numbers,
                        min(
                            dead_count,
                            len(numbers),
                        ),
                    )
                ]

        stage_data = {
            "id": stage_ref.id,
            "round_id": round_id,
            "game_id": game_id,
            "stage_no": stage_no,
            "title": title,
            "question": question,
            "status": "draft",
            "entry_fee": entry_fee,
            "start_at": body.get("start_at"),
            "end_at": body.get("end_at"),
            "clue": clean_string(
                body.get("clue")
            ),
            "generation_mode": generation_mode,
            "options": options,
            "correct_answer": correct_answer,
            "accepted_answers": accepted,
            "safe_option": safe_option,
            "min_number": minimum,
            "max_number": maximum,
            "dead_numbers": dead_numbers,
            "dead_count": dead_count,
            "mechanic": mechanic,
            "target_percentage": target_percentage,
            "target_min_percentage": target_min_percentage,
            "target_max_percentage": target_max_percentage,
            "secret_approved": False,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        stage_ref.set(stage_data)

        return success_response({
            "stage_id": stage_ref.id,
            "stage": serialize_value(stage_data),
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ADMIN APPROVE SECRET
# ============================================================

@competition_bp.route(
    "/api/admin/competition/rounds/<round_id>/stages/<int:stage_no>/approve",
    methods=["POST"],
)
def admin_approve_stage(round_id: str, stage_no: int):
    try:
        _require_admin()

        stage_ref = get_stage_ref(
            round_id,
            stage_no,
        )

        snap = stage_ref.get()

        if not snap.exists:
            return error_response(
                "Stage not found.",
                404,
            )

        stage = snap.to_dict() or {}

        game_id = stage.get("game_id")

        if game_id in {
            "guess_it",
            "impossible_question",
        }:
            if not clean_string(
                stage.get("correct_answer")
            ):
                return error_response(
                    "Add the correct answer before approval.",
                    400,
                )

        elif game_id == "survivor":
            if not clean_string(
                stage.get("safe_option")
            ):
                return error_response(
                    "Add the safe option before approval.",
                    400,
                )

        elif game_id == "dead_number":
            dead = stage.get(
                "dead_numbers",
                [],
            ) or []

            if not dead:
                stage["dead_numbers"] = calculate_dead_numbers(
                    stage
                )

        # For Crowd Trap and Impossible Choice there is
        # no secret answer to approve.

        stage_ref.update({
            "secret_approved": True,
            "updated_at": firestore.SERVER_TIMESTAMP,
            "dead_numbers": stage.get(
                "dead_numbers",
                [],
            ),
        })

        return success_response({
            "message": "Stage secret approved.",
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ADMIN START STAGE
# ============================================================

@competition_bp.route(
    "/api/admin/competition/rounds/<round_id>/stages/<int:stage_no>/start",
    methods=["POST"],
)
def admin_start_stage(round_id: str, stage_no: int):
    try:
        _require_admin()

        round_ref = get_round_ref(
            round_id
        )

        round_snap = round_ref.get()

        if not round_snap.exists:
            return error_response(
                "Round not found.",
                404,
            )

        round_data = round_snap.to_dict() or {}

        stage_ref = get_stage_ref(
            round_id,
            stage_no,
        )

        stage_snap = stage_ref.get()

        if not stage_snap.exists:
            return error_response(
                "Stage not found.",
                404,
            )

        stage = stage_snap.to_dict() or {}

        if not stage.get("secret_approved"):
            game_id = stage.get("game_id")

            # Games without a hidden secret can start without approval.
            if game_id not in {
                "crowd_trap",
                "impossible_choice",
            }:
                return error_response(
                    "Approve the stage secret before starting it.",
                    400,
                )

        if stage.get("status") == "live":
            return success_response({
                "message": "Stage is already live.",
            })

        start_at = stage.get("start_at")

        if start_at and is_time_before(start_at):
            return error_response(
                "Stage start time has not arrived yet.",
                400,
            )

        stage_ref.update({
            "status": "live",
            "started_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

        round_ref.update({
            "status": "live",
            "current_stage": stage_no,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

        return success_response({
            "message": "Stage is now live.",
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# SETTLEMENT HELPERS
# ============================================================

def entries_for_stage(
    round_id: str,
    stage_no: int,
) -> List[Dict[str, Any]]:
    docs = list(
        db.collection(
            ENTRY_COLLECTION
        )
        .where(
            "round_id",
            "==",
            round_id,
        )
        .where(
            "stage_no",
            "==",
            stage_no,
        )
        .stream()
    )

    entries = []

    for snap in docs:
        data = snap.to_dict() or {}
        data["id"] = snap.id
        entries.append(data)

    return entries


def mark_participant(
    telegram_id: str,
    round_id: str,
    status: str,
    stage_no: int,
    message: Optional[str] = None,
):
    ref = get_participant_ref(
        round_id,
        telegram_id,
    )

    update = {
        "status": status,
        "current_stage": stage_no,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }

    if message:
        update["message"] = message

    ref.set(
        update,
        merge=True,
    )


def distribute_prize(
    round_id: str,
    game_id: str,
    winner_ids: List[str],
    prize_pool: float,
):
    unique_winners = list(
        dict.fromkeys(
            str(x)
            for x in winner_ids
            if x is not None
        )
    )

    if not unique_winners:
        return 0

    if prize_pool <= 0:
        return 0

    amount_each = (
        prize_pool / len(unique_winners)
    )

    count = 0

    for telegram_id in unique_winners:
        result_ref = db.collection(
            RESULT_COLLECTION
        ).document(
            f"{round_id}_{telegram_id}"
        )

        existing = result_ref.get()

        if existing.exists:
            continue

        user_ref = db.collection(
            USER_COLLECTION
        ).document(
            telegram_id
        )

        user_snap = user_ref.get()

        if not user_snap.exists:
            continue

        user_ref.update({
            "prize_balance_usd": firestore.Increment(
                amount_each
            ),
            "prize_balance": firestore.Increment(
                amount_each
            ),
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

        result_ref.set({
            "round_id": round_id,
            "game_id": game_id,
            "telegram_id": telegram_id,
            "amount_usd": amount_each,
            "status": "credited",
            "created_at": firestore.SERVER_TIMESTAMP,
        })

        count += 1

    return count


# ============================================================
# ADMIN END / SETTLE STAGE
# ============================================================

@competition_bp.route(
    "/api/admin/competition/rounds/<round_id>/stages/<int:stage_no>/end",
    methods=["POST"],
)
def admin_end_stage(
    round_id: str,
    stage_no: int,
):
    try:
        _require_admin()

        round_ref = get_round_ref(
            round_id
        )

        round_snap = round_ref.get()

        if not round_snap.exists:
            return error_response(
                "Round not found.",
                404,
            )

        round_data = round_snap.to_dict() or {}
        game_id = round_data.get("game_id")

        stage_ref = get_stage_ref(
            round_id,
            stage_no,
        )

        stage_snap = stage_ref.get()

        if not stage_snap.exists:
            return error_response(
                "Stage not found.",
                404,
            )

        stage = stage_snap.to_dict() or {}

        if stage.get("status") == "closed":
            return success_response({
                "message": "Stage is already closed.",
                "winner_count": 0,
            })

        entries = entries_for_stage(
            round_id,
            stage_no,
        )

        winners: List[Dict[str, Any]] = []

        # --------------------------------------------------------
        # GUESS IT
        # --------------------------------------------------------

        if game_id == "guess_it":
            for entry in entries:
                answer = entry.get("answer", "")

                correct = answer_is_correct(
                    game_id,
                    stage,
                    answer,
                )

                if correct:
                    winners.append(entry)

                    db.collection(
                        ENTRY_COLLECTION
                    ).document(
                        entry["id"]
                    ).update({
                        "status": "correct",
                        "outcome": "survived",
                        "evaluated_at": firestore.SERVER_TIMESTAMP,
                    })

                    mark_participant(
                        entry["telegram_id"],
                        round_id,
                        "active",
                        stage_no,
                    )

                else:
                    db.collection(
                        ENTRY_COLLECTION
                    ).document(
                        entry["id"]
                    ).update({
                        "status": "wrong",
                        "outcome": "eliminated",
                        "evaluated_at": firestore.SERVER_TIMESTAMP,
                    })

                    mark_participant(
                        entry["telegram_id"],
                        round_id,
                        "eliminated",
                        stage_no,
                        "You failed this stage.",
                    )

            # Anyone who entered but did not answer also fails.
            entered_ids = {
                str(x.get("telegram_id"))
                for x in entries
            }

            answered_ids = {
                str(x.get("telegram_id"))
                for x in entries
                if clean_string(x.get("answer"))
            }

            for telegram_id in entered_ids - answered_ids:
                mark_participant(
                    telegram_id,
                    round_id,
                    "forfeited",
                    stage_no,
                    "You did not submit before the stage ended.",
                )

        # --------------------------------------------------------
        # SURVIVOR
        # --------------------------------------------------------

        elif game_id == "survivor":
            safe = normalize_answer(
                stage.get("safe_option", "")
            )

            for entry in entries:
                answer = normalize_answer(
                    entry.get("answer", "")
                )

                if answer and answer == safe:
                    winners.append(entry)

                    db.collection(
                        ENTRY_COLLECTION
                    ).document(
                        entry["id"]
                    ).update({
                        "status": "survived",
                        "outcome": "survived",
                        "evaluated_at": firestore.SERVER_TIMESTAMP,
                    })

                    mark_participant(
                        entry["telegram_id"],
                        round_id,
                        "active",
                        stage_no,
                    )

                else:
                    db.collection(
                        ENTRY_COLLECTION
                    ).document(
                        entry["id"]
                    ).update({
                        "status": "eliminated",
                        "outcome": "eliminated",
                        "evaluated_at": firestore.SERVER_TIMESTAMP,
                    })

                    mark_participant(
                        entry["telegram_id"],
                        round_id,
                        "eliminated",
                        stage_no,
                        "You chose an unsafe option.",
                    )

        # --------------------------------------------------------
        # DEAD NUMBER
        # --------------------------------------------------------

        elif game_id == "dead_number":
            dead_numbers = {
                normalize_answer(x)
                for x in calculate_dead_numbers(
                    stage
                )
            }

            # Save generated values if needed.
            stage_ref.update({
                "dead_numbers": list(
                    dead_numbers
                ),
            })

            for entry in entries:
                answer = normalize_answer(
                    entry.get("answer", "")
                )

                if answer and answer not in dead_numbers:
                    winners.append(entry)

                    db.collection(
                        ENTRY_COLLECTION
                    ).document(
                        entry["id"]
                    ).update({
                        "status": "survived",
                        "outcome": "survived",
                        "evaluated_at": firestore.SERVER_TIMESTAMP,
                    })

                    mark_participant(
                        entry["telegram_id"],
                        round_id,
                        "active",
                        stage_no,
                    )

                else:
                    db.collection(
                        ENTRY_COLLECTION
                    ).document(
                        entry["id"]
                    ).update({
                        "status": "eliminated",
                        "outcome": "dead_number",
                        "evaluated_at": firestore.SERVER_TIMESTAMP,
                    })

                    mark_participant(
                        entry["telegram_id"],
                        round_id,
                        "eliminated",
                        stage_no,
                        "You selected a dead number.",
                    )

        # --------------------------------------------------------
        # IMPOSSIBLE QUESTION
        # --------------------------------------------------------

        elif game_id == "impossible_question":
            for entry in entries:
                correct = answer_is_correct(
                    game_id,
                    stage,
                    entry.get("answer", ""),
                )

                if correct:
                    winners.append(entry)

                    db.collection(
                        ENTRY_COLLECTION
                    ).document(
                        entry["id"]
                    ).update({
                        "status": "correct",
                        "outcome": "winner",
                        "evaluated_at": firestore.SERVER_TIMESTAMP,
                    })

                else:
                    db.collection(
                        ENTRY_COLLECTION
                    ).document(
                        entry["id"]
                    ).update({
                        "status": "wrong",
                        "outcome": "eliminated",
                        "evaluated_at": firestore.SERVER_TIMESTAMP,
                    )

        # --------------------------------------------------------
        # CROWD TRAP
        # --------------------------------------------------------

        elif game_id == "crowd_trap":
            counts: Dict[str, int] = {}

            for entry in entries:
                answer = normalize_answer(
                    entry.get("answer", "")
                )

                if answer:
                    counts[answer] = (
                        counts.get(answer, 0) + 1
                    )

            unique_numbers = [
                key
                for key, count in counts.items()
                if count == 1
            ]

            for entry in entries:
                answer = normalize_answer(
                    entry.get("answer", "")
                )

                if answer in unique_numbers:
                    winners.append(entry)

                    db.collection(
                        ENTRY_COLLECTION
                    ).document(
                        entry["id"]
                    ).update({
                        "status": "winner",
                        "outcome": "winner",
                        "evaluated_at": firestore.SERVER_TIMESTAMP,
                    })

                    mark_participant(
                        entry["telegram_id"],
                        round_id,
                        "active",
                        stage_no,
                    )

                else:
                    db.collection(
                        ENTRY_COLLECTION
                    ).document(
                        entry["id"]
                    ).update({
                        "status": "eliminated",
                        "outcome": "not_unique",
                        "evaluated_at": firestore.SERVER_TIMESTAMP,
                    })

        # --------------------------------------------------------
        # IMPOSSIBLE CHOICE
        # --------------------------------------------------------

        elif game_id == "impossible_choice":
            winners = calculate_choice_winners(
                entries,
                stage,
            )

            winner_ids = {
                str(x.get("telegram_id"))
                for x in winners
            }

            for entry in entries:
                telegram_id = str(
                    entry.get("telegram_id")
                )

                if telegram_id in winner_ids:
                    db.collection(
                        ENTRY_COLLECTION
                    ).document(
                        entry["id"]
                    ).update({
                        "status": "winner",
                        "outcome": "winner",
                        "evaluated_at": firestore.SERVER_TIMESTAMP,
                    })
                else:
                    db.collection(
                        ENTRY_COLLECTION
                    ).document(
                        entry["id"]
                    ).update({
                        "status": "eliminated",
                        "outcome": "not_winner",
                        "evaluated_at": firestore.SERVER_TIMESTAMP,
                    })

        # --------------------------------------------------------
        # CLOSE STAGE
        # --------------------------------------------------------

        stage_ref.update({
            "status": "closed",
            "closed_at": firestore.SERVER_TIMESTAMP,
            "winner_count": len(winners),
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

        winner_ids = [
            str(
                entry.get("telegram_id")
            )
            for entry in winners
        ]

        total_stages = safe_int(
            round_data.get(
                "total_stages",
                1,
            ),
            1,
        )

        # --------------------------------------------------------
        # FINAL STAGE
        # --------------------------------------------------------

        if stage_no >= total_stages:
            prize_pool = safe_number(
                round_data.get(
                    "prize_pool_usd",
                    0,
                ),
                0,
            )

            credited_count = distribute_prize(
                round_id,
                game_id,
                winner_ids,
                prize_pool,
            )

            round_ref.update({
                "status": "settled",
                "winner_count": len(winner_ids),
                "winner_amount_usd": (
                    prize_pool / len(winner_ids)
                    if winner_ids
                    else 0
                ),
                "settled_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            })

            for telegram_id in winner_ids:
                mark_participant(
                    telegram_id,
                    round_id,
                    "winner",
                    stage_no,
                )

            return success_response({
                "message": "Final stage closed and round settled.",
                "winner_count": len(winner_ids),
                "credited_count": credited_count,
            })

        # --------------------------------------------------------
        # NON-FINAL STAGE
        # --------------------------------------------------------

        if not winner_ids:
            # Nobody survived. Round ends.
            round_ref.update({
                "status": "settled",
                "winner_count": 0,
                "winner_amount_usd": 0,
                "settled_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            })

            return success_response({
                "message": (
                    "Stage closed. No players survived."
                ),
                "winner_count": 0,
            })

        # Keep round alive, but DO NOT automatically reveal
        # or start the next stage.
        round_ref.update({
            "status": "waiting",
            "current_stage": stage_no,
            "survivor_count": len(winner_ids),
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

        return success_response({
            "message": (
                "Stage closed. Survivors can continue "
                "when the next stage is prepared."
            ),
            "winner_count": len(winner_ids),
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ADMIN PREPARE NEXT STAGE
# ============================================================

@competition_bp.route(
    "/api/admin/competition/rounds/<round_id>/next-stage",
    methods=["POST"],
)
def admin_prepare_next_stage(round_id: str):
    try:
        _require_admin()

        round_ref = get_round_ref(
            round_id
        )

        snap = round_ref.get()

        if not snap.exists:
            return error_response(
                "Round not found.",
                404,
            )

        round_data = snap.to_dict() or {}

        current_stage = safe_int(
            round_data.get(
                "current_stage",
                1,
            ),
            1,
        )

        total_stages = safe_int(
            round_data.get(
                "total_stages",
                1,
            ),
            1,
        )

        if current_stage >= total_stages:
            return error_response(
                "There is no next stage.",
                400,
            )

        next_stage = current_stage + 1

        current_ref = get_stage_ref(
            round_id,
            current_stage,
        )

        current_snap = current_ref.get()

        if current_snap.exists:
            current_data = (
                current_snap.to_dict()
                or {}
            )

            if current_data.get("status") != "closed":
                return error_response(
                    "The current stage must be closed first.",
                    400,
                )

        next_ref = get_stage_ref(
            round_id,
            next_stage,
        )

        if next_ref.get().exists:
            return success_response({
                "next_stage": next_stage,
                "message": (
                    "Next stage is already prepared."
                ),
            })

        game_id = round_data.get(
            "game_id"
        )

        fees = round_data.get(
            "entry_fees",
            [],
        ) or []

        if len(fees) >= next_stage:
            fee = safe_int(
                fees[next_stage - 1],
                10,
            )
        else:
            fee = 30 if next_stage == 7 else 10

        stage_data = {
            "id": next_ref.id,
            "round_id": round_id,
            "game_id": game_id,
            "stage_no": next_stage,
            "title": f"Day {next_stage}",
            "question": "",
            "status": "draft",
            "entry_fee": fee,
            "start_at": None,
            "end_at": None,
            "clue": "",
            "generation_mode": "admin",
            "options": [],
            "correct_answer": "",
            "accepted_answers": [],
            "safe_option": "",
            "min_number": 1,
            "max_number": 20,
            "dead_numbers": [],
            "dead_count": 1,
            "mechanic": "minority",
            "target_percentage": 50,
            "target_min_percentage": 40,
            "target_max_percentage": 60,
            "secret_approved": False,
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        next_ref.set(
            stage_data
        )

        round_ref.update({
            "current_stage": next_stage,
            "status": "waiting",
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

        return success_response({
            "next_stage": next_stage,
            "message": (
                "Next stage is ready for configuration."
            ),
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ADMIN DELETE / CANCEL ROUND
# ============================================================

@competition_bp.route(
    "/api/admin/competition/rounds/<round_id>/cancel",
    methods=["POST"],
)
def admin_cancel_round(round_id: str):
    try:
        _require_admin()

        round_ref = get_round_ref(
            round_id
        )

        snap = round_ref.get()

        if not snap.exists:
            return error_response(
                "Round not found.",
                404,
            )

        round_ref.update({
            "status": "cancelled",
            "cancelled_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

        return success_response({
            "message": "Competition round cancelled.",
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ADMIN GAME ACTIVATE / DEACTIVATE
# ============================================================

@competition_bp.route(
    "/api/admin/competition/games/<game_id>/activate",
    methods=["POST"],
)
def admin_activate_game(game_id: str):
    try:
        _require_admin()

        if game_id not in ALL_COMPETITION_GAMES:
            return error_response(
                "Game not found.",
                404,
            )

        db.collection(
            GAME_COLLECTION
        ).document(
            game_id
        ).set(
            {
                "active": True,
                "competition_enabled": True,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

        return success_response({
            "message": f"{game_display(game_id)} activated.",
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


@competition_bp.route(
    "/api/admin/competition/games/<game_id>/deactivate",
    methods=["POST"],
)
def admin_deactivate_game(game_id: str):
    try:
        _require_admin()

        if game_id not in ALL_COMPETITION_GAMES:
            return error_response(
                "Game not found.",
                404,
            )

        db.collection(
            GAME_COLLECTION
        ).document(
            game_id
        ).set(
            {
                "active": False,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

        return success_response({
            "message": f"{game_display(game_id)} deactivated.",
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ADMIN PARTICIPANTS
# ============================================================

@competition_bp.route(
    "/api/admin/competition/rounds/<round_id>/participants",
    methods=["GET"],
)
def admin_round_participants(round_id: str):
    try:
        _require_admin()

        docs = list(
            db.collection(
                PARTICIPANT_COLLECTION
            )
            .where(
                "round_id",
                "==",
                round_id,
            )
            .limit(1000)
            .stream()
        )

        participants = []

        for snap in docs:
            data = snap.to_dict() or {}
            data["id"] = snap.id

            participants.append(
                serialize_value(data)
            )

        return success_response({
            "participants": participants,
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ADMIN FORCE ELIMINATE USER
# ============================================================

@competition_bp.route(
    "/api/admin/competition/rounds/<round_id>/participants/<telegram_id>/eliminate",
    methods=["POST"],
)
def admin_eliminate_participant(
    round_id: str,
    telegram_id: str,
):
    try:
        _require_admin()

        ref = get_participant_ref(
            round_id,
            telegram_id,
        )

        snap = ref.get()

        if not snap.exists:
            return error_response(
                "Participant not found.",
                404,
            )

        ref.set(
            {
                "status": "eliminated",
                "message": "Removed by QuizBee Admin.",
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

        return success_response({
            "message": "Participant eliminated.",
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)


# ============================================================
# ADMIN RESET STAGE
# ============================================================

@competition_bp.route(
    "/api/admin/competition/rounds/<round_id>/stages/<int:stage_no>/reset",
    methods=["POST"],
)
def admin_reset_stage(
    round_id: str,
    stage_no: int,
):
    try:
        _require_admin()

        stage_ref = get_stage_ref(
            round_id,
            stage_no,
        )

        snap = stage_ref.get()

        if not snap.exists:
            return error_response(
                "Stage not found.",
                404,
            )

        stage_ref.update({
            "status": "draft",
            "secret_approved": False,
            "started_at": None,
            "closed_at": None,
            "winner_count": 0,
            "updated_at": firestore.SERVER_TIMESTAMP,
        })

        return success_response({
            "message": "Stage reset to draft.",
        })

    except ValueError as exc:
        return error_response(str(exc), 403)

    except Exception as exc:
        return error_response(str(exc), 500)
