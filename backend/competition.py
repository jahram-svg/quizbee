"""
quizBee Competition Engine

six competition games:
1. Guess It
2. Impossible Question
3. The Crowd Trap
4. The Survivor
5. Dead Number
6. Impossible Choice

important architecture rules:
- Users only see the currently live stage.
- Future stages remain private.
- Stage entry is paid separately.
- A player can enter a stage only once.
- Stage results are recorded after Admin concludes the stage.
- Users can see whether they passed, failed, advanced, or won.
- Result logic is shared across ALL games.
- Secret answers are never exposed to users before conclusion.
"""

from __future__ import annotations

import os
import re
import uuid
import random
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request
from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import validate_telegram_init_data


competition_bp = Blueprint(
    "competition",
    __name__,
    url_prefix="/api/competition",
)


# ============================================================
# CONSTANTS
# ============================================================

GAME_DEFINITIONS = {
    "guess_it": {
        "id": "guess_it",
        "name": "Guess It",
        "emoji": "",
        "description": "A 7-stage survival challenge.",
        "active": True,
        "staged": True,
        "default_entry_fees": [10, 10, 10, 10, 10, 10, 30],
    },
    "impossible_question": {
        "id": "impossible_question",
        "name": "Impossible Question",
        "emoji": "",
        "description": "One difficult question. One answer. No retry.",
        "active": True,
        "staged": False,
        "default_entry_fees": [10],
    },
    "crowd_trap": {
        "id": "crowd_trap",
        "name": "The Crowd Trap",
        "emoji": "",
        "description": "Choose a number nobody else chooses.",
        "active": False,
        "staged": False,
        "default_entry_fees": [10],
    },
    "survivor": {
        "id": "survivor",
        "name": "The Survivor",
        "emoji": "",
        "description": "Choose the safe option and survive.",
        "active": False,
        "staged": True,
        "default_entry_fees": [10, 10, 10, 10, 10, 10, 30],
    },
    "dead_number": {
        "id": "dead_number",
        "name": "Dead Number",
        "emoji": "️",
        "description": "Avoid the dead numbers.",
        "active": False,
        "staged": True,
        "default_entry_fees": [10, 10, 10, 10, 10, 10, 30],
    },
    "impossible_choice": {
        "id": "impossible_choice",
        "name": "Impossible Choice",
        "emoji": "",
        "description": "Predict the crowd.",
        "active": False,
        "staged": False,
        "default_entry_fees": [10],
    },
}


STAGED_GAMES = {
    "guess_it",
    "survivor",
    "dead_number",
}


VALID_STATUSES = {
    "draft",
    "scheduled",
    "live",
    "closed",
    "settled",
    "cancelled",
}


# ============================================================
# GENERAL HELPERS
# ============================================================

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: Any) -> Optional[str]:
    if dt is None:
        return None

    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()

    return str(dt)


def parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    text = str(value).strip()

    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        return None


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_answer(value: Any) -> str:
    text = clean_text(value).lower()

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s.%+-]", "", text)

    return text.strip()


def to_number(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def unique_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []

    result = []

    for value in values:
        value = clean_text(value)

        if value and value not in result:
            result.append(value)

    return result


def public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    return only wallet information that the frontend needs.
    """

    return {
        "telegram_id": str(user.get("telegram_id", "")),
        "first_name": user.get("first_name", ""),
        "username": user.get("username", ""),
        "points": to_int(user.get("points", 0)),
        "prize_balance_usd": round(
            to_number(user.get("prize_balance_usd", 0)),
            4,
        ),
    }


def game_public(game: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": game.get("id"),
        "name": game.get("name"),
        "emoji": game.get("emoji"),
        "description": game.get("description"),
        "active": bool(game.get("active", False)),
        "staged": bool(game.get("staged", False)),
    }


# ============================================================
# AUTHENTICATION
# ============================================================

def get_init_data() -> str:
    return (
        request.headers.get("X-Telegram-Init-Data")
        or request.headers.get("X-Telegram-InitData")
        or request.args.get("init_data")
        or ""
    )


def require_user():
    init_data = get_init_data()

    if not init_data:
        raise ValueError("Telegram authentication data is missing.")

    user_data = validate_telegram_init_data(init_data)

    if not user_data:
        raise ValueError("Invalid Telegram authentication.")

    return user_data


def user_route(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            user = require_user()
            return fn(user, *args, **kwargs)
        except ValueError as exc:
            return jsonify({
                "success": False,
                "error": str(exc),
            }), 401
        except Exception as exc:
            print("Competition user route error:", repr(exc))
            return jsonify({
                "success": False,
                "error": "Unable to process request.",
            }), 500

    return wrapper


# ============================================================
# ADMIN AUTHENTICATION
# ============================================================

def configured_admin_ids() -> set[str]:
    ids = set()

    multi = os.getenv("ADMIN_TELEGRAM_IDS", "")

    for value in multi.split(","):
        value = value.strip()

        if value:
            ids.add(value)

    single = os.getenv("ADMIN_TELEGRAM_ID", "").strip()

    if single:
        ids.add(single)

    return ids


def require_admin():
    init_data = (
        request.headers.get("X-Telegram-Init-Data")
        or request.headers.get("X-Telegram-InitData")
        or request.args.get("init_data")
        or ""
    )

    if not init_data:
        raise ValueError("Admin authentication data is missing.")

    admin_bot_token = os.getenv("ADMIN_BOT_TOKEN")

    if not admin_bot_token:
        raise ValueError("ADMIN_BOT_TOKEN is not configured.")

    user_data = validate_telegram_init_data(
        init_data,
        bot_token=admin_bot_token,
    )

    if not user_data:
        raise ValueError("Invalid admin authentication.")

    telegram_id = str(
        user_data.get("id")
        or user_data.get("telegram_id")
        or ""
    )

    if telegram_id not in configured_admin_ids():
        raise ValueError("You are not authorized as an admin.")

    return user_data


def admin_route(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            admin = require_admin()
            return fn(admin, *args, **kwargs)

        except ValueError as exc:
            return jsonify({
                "success": False,
                "error": str(exc),
            }), 403

        except Exception as exc:
            print("Competition admin route error:", repr(exc))
            return jsonify({
                "success": False,
                "error": "Unable to process admin request.",
            }), 500

    return wrapper


# ============================================================
# FIRESTORE REFERENCES
# ============================================================

def games_col():
    return db.collection("competition_games")


def rounds_col():
    return db.collection("competition_rounds")


def stages_col():
    return db.collection("competition_stages")


def entries_col():
    return db.collection("competition_entries")


def results_col():
    return db.collection("competition_results")


def users_col():
    return db.collection("users")


def transactions_col():
    return db.collection("transactions")


# ============================================================
# GAME INITIALIZATION
# ============================================================

def initialize_games() -> None:
    batch = db.batch()

    for game_id, definition in GAME_DEFINITIONS.items():
        ref = games_col().document(game_id)

        batch.set(
            ref,
            {
                **definition,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    batch.commit()


def get_game(game_id: str) -> Optional[Dict[str, Any]]:
    snap = games_col().document(game_id).get()

    if not snap.exists:
        return None

    data = snap.to_dict() or {}
    data["id"] = snap.id

    return data


def ensure_game_exists(game_id: str) -> Dict[str, Any]:
    game = get_game(game_id)

    if game:
        return game

    definition = GAME_DEFINITIONS.get(game_id)

    if not definition:
        raise ValueError("Unknown competition game.")

    games_col().document(game_id).set(
        {
            **definition,
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    return get_game(game_id) or {
        **definition,
        "id": game_id,
    }


# ============================================================
# ROUND HELPERS
# ============================================================

def total_stages_for_game(game_id: str) -> int:
    return 7 if game_id in STAGED_GAMES else 1


def default_fees_for_game(game_id: str) -> List[int]:
    definition = GAME_DEFINITIONS.get(game_id)

    if not definition:
        return [10]

    return list(definition["default_entry_fees"])


def get_round(round_id: str) -> Optional[Dict[str, Any]]:
    snap = rounds_col().document(round_id).get()

    if not snap.exists:
        return None

    data = snap.to_dict() or {}
    data["id"] = snap.id

    return data


def get_stage(round_id: str, stage_no: int) -> Optional[Dict[str, Any]]:
    ref = stages_col().document(
        f"{round_id}_{int(stage_no)}"
    )

    snap = ref.get()

    if not snap.exists:
        return None

    data = snap.to_dict() or {}
    data["id"] = snap.id

    return data


def get_entry(
    round_id: str,
    stage_no: int,
    telegram_id: str,
) -> Optional[Dict[str, Any]]:
    ref = entries_col().document(
        f"{round_id}_{int(stage_no)}_{telegram_id}"
    )

    snap = ref.get()

    if not snap.exists:
        return None

    data = snap.to_dict() or {}
    data["id"] = snap.id

    return data


def get_result(
    round_id: str,
    telegram_id: str,
) -> Optional[Dict[str, Any]]:
    ref = results_col().document(
        f"{round_id}_{telegram_id}"
    )

    snap = ref.get()

    if not snap.exists:
        return None

    data = snap.to_dict() or {}
    data["id"] = snap.id

    return data


def round_stages(round_id: str) -> List[Dict[str, Any]]:
    snaps = (
        stages_col()
        .where("round_id", "==", round_id)
        .stream()
    )

    stages = []

    for snap in snaps:
        data = snap.to_dict() or {}
        data["id"] = snap.id
        stages.append(data)

    stages.sort(
        key=lambda x: to_int(x.get("stage_no"), 0)
    )

    return stages


def round_entries(
    round_id: str,
    stage_no: Optional[int] = None,
) -> List[Dict[str, Any]]:
    query = stages_col()

    snaps = entries_col().where(
        "round_id",
        "==",
        round_id,
    )

    if stage_no is not None:
        snaps = snaps.where(
            "stage_no",
            "==",
            int(stage_no),
        )

    results = []

    for snap in snaps.stream():
        data = snap.to_dict() or {}
        data["id"] = snap.id
        results.append(data)

    results.sort(
        key=lambda x: (
            to_int(x.get("stage_no")),
            str(x.get("telegram_id", "")),
        )
    )

    return results


# ============================================================
# STAGE VISIBILITY
# ============================================================

def public_stage_data(
    round_data: Dict[str, Any],
    stage: Dict[str, Any],
) -> Dict[str, Any]:
    """
    never expose secret answers before the stage is concluded.

    secret fields remain server-side.
    """

    game_id = round_data.get("game_id")

    result = {
        "id": stage.get("id"),
        "round_id": round_data.get("id"),
        "stage_no": to_int(stage.get("stage_no"), 1),
        "title": stage.get("title", ""),
        "question": stage.get("question", ""),
        "clue": stage.get("clue", ""),
        "entry_fee": to_int(stage.get("entry_fee"), 0),
        "start_at": iso(stage.get("start_at")),
        "end_at": iso(stage.get("end_at")),
        "status": stage.get("status", "draft"),
        "options": stage.get("options", []),
        "min_number": stage.get("min_number"),
        "max_number": stage.get("max_number"),
        "mechanic": stage.get("mechanic"),
        "target_percentage": stage.get("target_percentage"),
        "target_min_percentage": stage.get("target_min_percentage"),
        "target_max_percentage": stage.get("target_max_percentage"),
    }

    # These games require numbers/options but never their secrets.
    if game_id == "crowd_trap":
        result["min_number"] = to_int(
            stage.get("min_number"),
            1,
        )

        result["max_number"] = to_int(
            stage.get("max_number"),
            20,
        )

    elif game_id == "dead_number":
        result["min_number"] = to_int(
            stage.get("min_number"),
            1,
        )

        result["max_number"] = to_int(
            stage.get("max_number"),
            20,
        )

    return result


# ============================================================
# USER RESULT / ADVANCEMENT LOGIC
# ============================================================

def result_payload(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    normalize a stored result for the frontend.

    this is deliberately game-independent.
    """

    return {
        "round_id": result.get("round_id"),
        "game_id": result.get("game_id"),
        "stage_no": to_int(result.get("stage_no"), 1),
        "outcome": result.get("outcome"),
        "passed": bool(result.get("passed", False)),
        "advanced": bool(result.get("advanced", False)),
        "winner": bool(result.get("winner", False)),
        "eliminated": bool(result.get("eliminated", False)),
        "final": bool(result.get("final", False)),
        "message": result.get("message", ""),
        "correct_answer": result.get("correct_answer"),
        "submitted_answer": result.get("submitted_answer"),
        "amount_usd": to_number(
            result.get("amount_usd"),
            0,
        ),
        "settled_at": iso(result.get("settled_at")),
        "next_stage": result.get("next_stage"),
    }


def create_or_update_player_result(
    round_data: Dict[str, Any],
    stage: Dict[str, Any],
    telegram_id: str,
    outcome: str,
    passed: bool,
    advanced: bool,
    winner: bool,
    eliminated: bool,
    final: bool,
    message: str,
    submitted_answer: Any = None,
    correct_answer: Any = None,
    amount_usd: float = 0,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    round_id = round_data["id"]

    result_ref = results_col().document(
        f"{round_id}_{telegram_id}"
    )

    existing_snap = result_ref.get()
    existing = existing_snap.to_dict() if existing_snap.exists else {}

    data = {
        **existing,
        "round_id": round_id,
        "game_id": round_data.get("game_id"),
        "telegram_id": str(telegram_id),
        "stage_no": to_int(stage.get("stage_no"), 1),
        "outcome": outcome,
        "passed": passed,
        "advanced": advanced,
        "winner": winner,
        "eliminated": eliminated,
        "final": final,
        "message": message,
        "submitted_answer": submitted_answer,
        "correct_answer": correct_answer,
        "amount_usd": amount_usd,
        "settled_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }

    if extra:
        data.update(extra)

    result_ref.set(data, merge=True)

    return {
        **data,
        "round_id": round_id,
    }


# ============================================================
# ANSWER EVALUATION
# ============================================================

def accepted_answers(stage: Dict[str, Any]) -> List[str]:
    values = []

    correct = clean_text(stage.get("correct_answer"))

    if correct:
        values.append(normalize_answer(correct))

    for answer in stage.get("accepted_answers", []):
        normalized = normalize_answer(answer)

        if normalized:
            values.append(normalized)

    return list(dict.fromkeys(values))


def evaluate_guess_or_impossible(
    stage: Dict[str, Any],
    submitted: Any,
) -> bool:
    answer = normalize_answer(submitted)

    if not answer:
        return False

    return answer in accepted_answers(stage)


def evaluate_survivor(
    stage: Dict[str, Any],
    submitted: Any,
) -> bool:
    safe = normalize_answer(stage.get("safe_option"))

    if not safe:
        return False

    return normalize_answer(submitted) == safe


# ============================================================
# CROWD TRAP
# ============================================================

def evaluate_crowd_trap(
    round_id: str,
    stage_no: int,
    stage: Dict[str, Any],
) -> List[Dict[str, Any]]:
    entries = round_entries(
        round_id,
        stage_no,
    )

    number_counts: Dict[str, int] = {}

    for entry in entries:
        if entry.get("status") != "submitted":
            continue

        answer = clean_text(entry.get("answer"))

        if not answer:
            continue

        number_counts[answer] = number_counts.get(
            answer,
            0,
        ) + 1

    winners = []

    for entry in entries:
        answer = clean_text(entry.get("answer"))

        if (
            entry.get("status") == "submitted"
            and answer
            and number_counts.get(answer) == 1
        ):
            winners.append(entry)

    return winners


# ============================================================
# IMPOSSIBLE CHOICE
# ============================================================

def calculate_choice_distribution(
    entries: List[Dict[str, Any]],
) -> Dict[str, int]:
    distribution: Dict[str, int] = {}

    for entry in entries:
        if entry.get("status") != "submitted":
            continue

        answer = clean_text(entry.get("answer"))

        if not answer:
            continue

        distribution[answer] = (
            distribution.get(answer, 0) + 1
        )

    return distribution


def evaluate_impossible_choice(
    round_id: str,
    stage_no: int,
    stage: Dict[str, Any],
) -> List[Dict[str, Any]]:
    entries = round_entries(
        round_id,
        stage_no,
    )

    distribution = calculate_choice_distribution(entries)

    total = sum(distribution.values())

    if total <= 0:
        return []

    mechanic = clean_text(
        stage.get("mechanic")
    ).lower()

    winners = []

    if mechanic == "minority":
        minimum = min(distribution.values())

        winning_answers = {
            answer
            for answer, count in distribution.items()
            if count == minimum
        }

        for entry in entries:
            if (
                entry.get("status") == "submitted"
                and entry.get("answer") in winning_answers
            ):
                winners.append(entry)

    elif mechanic == "majority":
        maximum = max(distribution.values())

        winning_answers = {
            answer
            for answer, count in distribution.items()
            if count == maximum
        }

        for entry in entries:
            if (
                entry.get("status") == "submitted"
                and entry.get("answer") in winning_answers
            ):
                winners.append(entry)

    elif mechanic == "closest_target":
        target = to_number(
            stage.get("target_percentage"),
            50,
        )

        percentages = {
            answer: (count / total) * 100
            for answer, count in distribution.items()
        }

        difference = min(
            abs(percent - target)
            for percent in percentages.values()
        )

        winning_answers = {
            answer
            for answer, percent in percentages.items()
            if abs(percent - target) == difference
        }

        for entry in entries:
            if (
                entry.get("status") == "submitted"
                and entry.get("answer") in winning_answers
            ):
                winners.append(entry)

    elif mechanic == "within_range":
        minimum = to_number(
            stage.get("target_min_percentage"),
            40,
        )

        maximum = to_number(
            stage.get("target_max_percentage"),
            60,
        )

        winning_answers = {
            answer
            for answer, count in distribution.items()
            if minimum <= (count / total) * 100 <= maximum
        }

        for entry in entries:
            if (
                entry.get("status") == "submitted"
                and entry.get("answer") in winning_answers
            ):
                winners.append(entry)

    return winners


# ============================================================
# DEAD NUMBER
# ============================================================

def get_dead_numbers(
    stage: Dict[str, Any],
) -> List[str]:
    dead = []

    for value in stage.get("dead_numbers", []):
        text = clean_text(value)

        if text:
            dead.append(text)

    # If Admin chose random generation, generate only at conclusion
    # if explicit dead numbers were not supplied.
    if (
        not dead
        and stage.get("generation_mode") == "random"
    ):
        minimum = to_int(
            stage.get("min_number"),
            1,
        )

        maximum = to_int(
            stage.get("max_number"),
            20,
        )

        dead_count = min(
            max(
                to_int(
                    stage.get("dead_count"),
                    1,
                ),
                1,
            ),
            max(
                maximum - minimum + 1,
                1,
            ),
        )

        numbers = list(
            range(
                minimum,
                maximum + 1,
            )
        )

        random.shuffle(numbers)

        dead = [
            str(number)
            for number in numbers[:dead_count]
        ]

    return dead


def evaluate_dead_number(
    round_id: str,
    stage_no: int,
    stage: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], List[str]]:
    entries = round_entries(
        round_id,
        stage_no,
    )

    dead_numbers = get_dead_numbers(stage)

    dead_set = {
        normalize_answer(value)
        for value in dead_numbers
    }

    winners = []

    for entry in entries:
        answer = normalize_answer(
            entry.get("answer")
        )

        if (
            entry.get("status") == "submitted"
            and answer
            and answer not in dead_set
        ):
            winners.append(entry)

    return winners, dead_numbers


# ============================================================
# PRIZE DISTRIBUTION
# ============================================================

def distribute_prize(
    round_data: Dict[str, Any],
    winner_entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    prize = to_number(
        round_data.get("prize_pool_usd"),
        0,
    )

    if prize <= 0 or not winner_entries:
        return {
            "winner_count": len(winner_entries),
            "amount_each": 0,
            "total_distributed": 0,
        }

    unique_ids = []

    for entry in winner_entries:
        telegram_id = str(
            entry.get("telegram_id", "")
        )

        if telegram_id and telegram_id not in unique_ids:
            unique_ids.append(telegram_id)

    if not unique_ids:
        return {
            "winner_count": 0,
            "amount_each": 0,
            "total_distributed": 0,
        }

    amount_each = round(
        prize / len(unique_ids),
        6,
    )

    distributed = 0

    batch = db.batch()

    for telegram_id in unique_ids:
        user_ref = users_col().document(
            telegram_id
        )

        user_snap = user_ref.get()

        if not user_snap.exists:
            continue

        user = user_snap.to_dict() or {}

        current_balance = to_number(
            user.get("prize_balance_usd"),
            0,
        )

        new_balance = round(
            current_balance + amount_each,
            6,
        )

        batch.update(
            user_ref,
            {
                "prize_balance_usd": new_balance,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
        )

        result_ref = results_col().document(
            f"{round_data['id']}_{telegram_id}"
        )

        batch.set(
            result_ref,
            {
                "amount_usd": amount_each,
                "winner": True,
                "outcome": "winner",
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

        transaction_ref = transactions_col().document(
            f"competition_prize_{round_data['id']}_{telegram_id}"
        )

        batch.set(
            transaction_ref,
            {
                "telegram_id": telegram_id,
                "type": "competition_prize",
                "direction": "credit",
                "amount_usd": amount_each,
                "round_id": round_data["id"],
                "game_id": round_data.get("game_id"),
                "status": "completed",
                "created_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

        distributed += amount_each

    batch.commit()

    return {
        "winner_count": len(unique_ids),
        "amount_each": amount_each,
        "total_distributed": round(distributed, 6),
    }


# ============================================================
# RESULT MESSAGE GENERATION
# ============================================================

def result_message(
    game_id: str,
    stage_no: int,
    passed: bool,
    winner: bool,
    final: bool,
    next_stage: Optional[int],
    correct_answer: Any = None,
    extra_message: Optional[str] = None,
) -> str:

    if winner:
        return (
            " Congratulations! You are one of the "
            "winners of this competition."
        )

    if final and passed:
        return (
            " Congratulations! You survived the final "
            "stage and are among the winners."
        )

    if passed and next_stage:
        return (
            f" Congratulations! You passed Stage {stage_no}. "
            f"You have advanced to Stage {next_stage}."
        )

    if passed:
        return (
            f" Congratulations! You passed Stage {stage_no}."
        )

    if extra_message:
        return extra_message

    if correct_answer not in (None, ""):
        return (
            f"❌ You did not pass Stage {stage_no}. "
            f"The correct answer was: {correct_answer}"
        )

    return (
        f"❌ You did not pass Stage {stage_no}. "
        "You are out of this round."
    )


# ============================================================
# ROUND RESULT SETTLEMENT
# ============================================================

def settle_stage(
    round_data: Dict[str, Any],
    stage: Dict[str, Any],
) -> Dict[str, Any]:

    round_id = round_data["id"]
    game_id = round_data["game_id"]
    stage_no = to_int(stage.get("stage_no"), 1)
    total_stages = to_int(
        round_data.get("total_stages"),
        1,
    )

    entries = round_entries(
        round_id,
        stage_no,
    )

    winners = []
    correct_answer = None
    dead_numbers = []

    # --------------------------------------------------------
    # DETERMINE STAGE WINNERS / SURVIVORS
    # --------------------------------------------------------

    if game_id in {
        "guess_it",
        "impossible_question",
    }:
        submitted_entries = [
            entry
            for entry in entries
            if entry.get("status") == "submitted"
        ]

        for entry in submitted_entries:
            if evaluate_guess_or_impossible(
                stage,
                entry.get("answer"),
            ):
                winners.append(entry)

        correct_answer = stage.get(
            "correct_answer"
        )

    elif game_id == "survivor":
        submitted_entries = [
            entry
            for entry in entries
            if entry.get("status") == "submitted"
        ]

        for entry in submitted_entries:
            if evaluate_survivor(
                stage,
                entry.get("answer"),
            ):
                winners.append(entry)

        correct_answer = stage.get(
            "safe_option"
        )

    elif game_id == "crowd_trap":
        winners = evaluate_crowd_trap(
            round_id,
            stage_no,
            stage,
        )

    elif game_id == "dead_number":
        winners, dead_numbers = evaluate_dead_number(
            round_id,
            stage_no,
            stage,
        )

    elif game_id == "impossible_choice":
        winners = evaluate_impossible_choice(
            round_id,
            stage_no,
            stage,
        )

    winner_ids = {
        str(entry.get("telegram_id"))
        for entry in winners
    }

    # --------------------------------------------------------
    # IMPORTANT:
    # Every submitted player receives a permanent result.
    #
    # This is what fixes the original problem where users
    # could only see "next stage not started" after a timer.
    # --------------------------------------------------------

    result_count = 0

    next_stage = (
        stage_no + 1
        if stage_no < total_stages
        else None
    )

    for entry in entries:
        telegram_id = str(
            entry.get("telegram_id", "")
        )

        if not telegram_id:
            continue

        submitted = (
            entry.get("status") == "submitted"
        )

        is_winner_of_stage = (
            telegram_id in winner_ids
        )

        if not submitted:
            # Paid but failed to submit before the stage ended.
            passed = False
            eliminated = True
            advanced = False
            winner = False
            outcome = "failed"

            message = (
                f" You did not submit an answer before "
                f"Stage {stage_no} ended. You are out of this round."
            )

        elif is_winner_of_stage:
            passed = True
            eliminated = False
            advanced = next_stage is not None
            winner = next_stage is None
            outcome = (
                "winner"
                if winner
                else "advanced"
            )

            message = result_message(
                game_id,
                stage_no,
                passed=True,
                winner=winner,
                final=(next_stage is None),
                next_stage=next_stage,
                correct_answer=correct_answer,
            )

        else:
            passed = False
            eliminated = True
            advanced = False
            winner = False
            outcome = "failed"

            # Crowd Trap / Impossible Choice / Dead Number
            # do not necessarily have a conventional correct answer.
            if game_id == "crowd_trap":
                message = (
                    f"❌ Your Stage {stage_no} choice was not unique. "
                    "You are out of this round."
                )

            elif game_id == "dead_number":
                message = (
                    f"❌ You selected a dead number in Stage "
                    f"{stage_no}. You are out of this round."
                )

            elif game_id == "impossible_choice":
                message = (
                    f"❌ Your choice did not satisfy the "
                    f"Stage {stage_no} rule. You are out of this round."
                )

            else:
                message = result_message(
                    game_id,
                    stage_no,
                    passed=False,
                    winner=False,
                    final=(next_stage is None),
                    next_stage=None,
                    correct_answer=correct_answer,
                )

        create_or_update_player_result(
            round_data=round_data,
            stage=stage,
            telegram_id=telegram_id,
            outcome=outcome,
            passed=passed,
            advanced=advanced,
            winner=winner,
            eliminated=eliminated,
            final=(next_stage is None),
            message=message,
            submitted_answer=entry.get("answer"),
            correct_answer=correct_answer,
            extra={
                "dead_numbers": dead_numbers,
            },
        )

        result_count += 1

        # Keep the entry itself synchronized.
        entries_col().document(
            entry["id"]
        ).set(
            {
                "result": outcome,
                "passed": passed,
                "eliminated": eliminated,
                "settled_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    # --------------------------------------------------------
    # FINAL WINNERS
    # --------------------------------------------------------

    prize_info = {
        "winner_count": 0,
        "amount_each": 0,
        "total_distributed": 0,
    }

    if stage_no == total_stages:
        prize_info = distribute_prize(
            round_data,
            winners,
        )

        round_status = "settled"

    else:
        round_status = "closed"

    # --------------------------------------------------------
    # MARK STAGE CLOSED / SETTLED
    # --------------------------------------------------------

    stages_col().document(
        stage["id"]
    ).set(
        {
            "status": "closed",
            "closed_at": firestore.SERVER_TIMESTAMP,
            "winner_count": len(winners),
            "advanced_count": (
                len(winners)
                if stage_no < total_stages
                else 0
            ),
            "dead_numbers": dead_numbers,
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    # --------------------------------------------------------
    # UPDATE ROUND
    # --------------------------------------------------------

    round_update = {
        "status": round_status,
        "updated_at": firestore.SERVER_TIMESTAMP,
        "last_settled_stage": stage_no,
        "winner_count": (
            prize_info["winner_count"]
            if stage_no == total_stages
            else 0
        ),
    }

    if stage_no < total_stages:
        round_update["current_stage"] = stage_no

    else:
        round_update["current_stage"] = total_stages
        round_update["ended_at"] = firestore.SERVER_TIMESTAMP

    rounds_col().document(
        round_id
    ).set(
        round_update,
        merge=True,
    )

    return {
        "winner_count": len(winners),
        "advanced_count": (
            len(winners)
            if stage_no < total_stages
            else 0
        ),
        "result_count": result_count,
        "prize": prize_info,
        "dead_numbers": dead_numbers,
        "next_stage": next_stage,
        "round_status": round_status,
    }


# ============================================================
# USER: GAME STATE
# ============================================================

@competition_bp.get("/<game_id>/state")
@user_route
def competition_state(user, game_id):
    telegram_id = str(
        user.get("id")
        or user.get("telegram_id")
        or ""
    )

    game = get_game(game_id)

    if not game:
        return jsonify({
            "success": False,
            "error": "Competition game not found.",
        }), 404

    if not game.get("active", False):
        return jsonify({
            "success": True,
            "status": "locked",
            "game": game_public(game),
        })

    # --------------------------------------------------------
    # Find most relevant round.
    #
    # Prefer active rounds, then most recent round.
    # --------------------------------------------------------

    snaps = (
        rounds_col()
        .where("game_id", "==", game_id)
        .stream()
    )

    rounds = []

    for snap in snaps:
        data = snap.to_dict() or {}
        data["id"] = snap.id
        rounds.append(data)

    if not rounds:
        return jsonify({
            "success": True,
            "status": "no_round",
            "game": game_public(game),
        })

    def round_sort_key(item):
        start = parse_datetime(
            item.get("start_at")
        )

        return start or datetime.min.replace(
            tzinfo=timezone.utc
        )

    rounds.sort(
        key=round_sort_key,
        reverse=True,
    )

    round_data = None

    # Prefer rounds that aren't settled.
    for candidate in rounds:
        if candidate.get("status") not in {
            "settled",
            "cancelled",
        }:
            round_data = candidate
            break

    if round_data is None:
        round_data = rounds[0]

    round_id = round_data["id"]

    # --------------------------------------------------------
    # FIRST: Check whether this user already has a final result
    # --------------------------------------------------------

    stored_result = get_result(
        round_id,
        telegram_id,
    )

    # --------------------------------------------------------
    # Determine current stage
    # --------------------------------------------------------

    total_stages = to_int(
        round_data.get("total_stages"),
        1,
    )

    current_stage_no = to_int(
        round_data.get("current_stage"),
        1,
    )

    stage = get_stage(
        round_id,
        current_stage_no,
    )

    # --------------------------------------------------------
    # If Admin has already settled the player's result,
    # RETURN THAT RESULT BEFORE anything else.
    #
    # This is the crucial universal result behavior.
    # --------------------------------------------------------

    if stored_result:
        result_stage = to_int(
            stored_result.get("stage_no"),
            1,
        )

        # If the result is final, show final result.
        if stored_result.get("final"):
            return jsonify({
                "success": True,
                "status": (
                    "winner"
                    if stored_result.get("winner")
                    else "eliminated"
                    if stored_result.get("eliminated")
                    else "result"
                ),
                "game": game_public(game),
                "round": {
                    "id": round_id,
                    "title": round_data.get("title", ""),
                    "status": round_data.get("status"),
                    "current_stage": current_stage_no,
                    "total_stages": total_stages,
                    "prize_pool_usd": to_number(
                        round_data.get("prize_pool_usd"),
                        0,
                    ),
                },
                "result": result_payload(
                    stored_result
                ),
                "user": public_user(
                    get_user_by_telegram_id(telegram_id)
                ),
            })

        # If player advanced, don't hide the advancement behind
        # the next-stage state.
        if (
            stored_result.get("advanced")
            and result_stage == current_stage_no
        ):
            return jsonify({
                "success": True,
                "status": "advanced",
                "game": game_public(game),
                "round": {
                    "id": round_id,
                    "title": round_data.get("title", ""),
                    "status": round_data.get("status"),
                    "current_stage": current_stage_no,
                    "total_stages": total_stages,
                    "prize_pool_usd": to_number(
                        round_data.get("prize_pool_usd"),
                        0,
                    ),
                },
                "result": result_payload(
                    stored_result
                ),
                "user": public_user(
                    get_user_by_telegram_id(telegram_id)
                ),
            })

        if stored_result.get("eliminated"):
            return jsonify({
                "success": True,
                "status": "eliminated",
                "game": game_public(game),
                "round": {
                    "id": round_id,
                    "title": round_data.get("title", ""),
                    "status": round_data.get("status"),
                    "current_stage": current_stage_no,
                    "total_stages": total_stages,
                },
                "result": result_payload(
                    stored_result
                ),
                "user": public_user(
                    get_user_by_telegram_id(telegram_id)
                ),
            })

    # --------------------------------------------------------
    # If the entire round has already been settled but this
    # player has no result, they did not participate.
    # --------------------------------------------------------

    if round_data.get("status") == "settled":
        return jsonify({
            "success": True,
            "status": "finished",
            "game": game_public(game),
            "round": {
                "id": round_id,
                "title": round_data.get("title", ""),
                "status": "settled",
                "current_stage": current_stage_no,
                "total_stages": total_stages,
                "winner_count": to_int(
                    round_data.get("winner_count"),
                    0,
                ),
                "prize_pool_usd": to_number(
                    round_data.get("prize_pool_usd"),
                    0,
                ),
            },
            "user": public_user(
                get_user_by_telegram_id(telegram_id)
            ),
        })

    # --------------------------------------------------------
    # No current stage yet.
    # --------------------------------------------------------

    if not stage:
        return jsonify({
            "success": True,
            "status": "round_not_started",
            "game": game_public(game),
            "round": {
                "id": round_id,
                "title": round_data.get("title", ""),
                "status": round_data.get("status"),
                "current_stage": current_stage_no,
                "total_stages": total_stages,
            },
            "user": public_user(
                get_user_by_telegram_id(telegram_id)
            ),
        })

    # --------------------------------------------------------
    # Automatically close expired stage when user checks it.
    # --------------------------------------------------------

    end_at = parse_datetime(
        stage.get("end_at")
    )

    if (
        end_at
        and now_utc() >= end_at
        and stage.get("status") == "live"
    ):
        settle_stage(
            round_data,
            stage,
        )

        # Re-check result immediately.
        stored_result = get_result(
            round_id,
            telegram_id,
        )

        if stored_result:
            return jsonify({
                "success": True,
                "status": (
                    "winner"
                    if stored_result.get("winner")
                    else "advanced"
                    if stored_result.get("advanced")
                    else "eliminated"
                ),
                "game": game_public(game),
                "round": {
                    "id": round_id,
                    "title": round_data.get("title", ""),
                    "status": round_data.get("status"),
                    "current_stage": current_stage_no,
                    "total_stages": total_stages,
                },
                "result": result_payload(
                    stored_result
                ),
                "user": public_user(
                    get_user_by_telegram_id(telegram_id)
                ),
            })

        return jsonify({
            "success": True,
            "status": "finished",
            "game": game_public(game),
            "round": {
                "id": round_id,
                "title": round_data.get("title", ""),
                "status": round_data.get("status"),
                "current_stage": current_stage_no,
                "total_stages": total_stages,
            },
            "user": public_user(
                get_user_by_telegram_id(telegram_id)
            ),
        })

    # --------------------------------------------------------
    # Future stage hasn't started.
    # --------------------------------------------------------

    start_at = parse_datetime(
        stage.get("start_at")
    )

    if (
        stage.get("status") != "live"
        or (
            start_at
            and now_utc() < start_at
        )
    ):
        previous_result = None

        if (
            stored_result
            and stored_result.get("advanced")
            and to_int(
                stored_result.get("stage_no"),
                1,
            ) < current_stage_no
        ):
            previous_result = result_payload(
                stored_result
            )

        return jsonify({
            "success": True,
            "status": "round_not_started",
            "game": game_public(game),
            "round": {
                "id": round_id,
                "title": round_data.get("title", ""),
                "status": round_data.get("status"),
                "current_stage": current_stage_no,
                "total_stages": total_stages,
            },
            "stage": public_stage_data(
                round_data,
                stage,
            ),
            "previous_result": previous_result,
            "user": public_user(
                get_user_by_telegram_id(telegram_id)
            ),
        })

    # --------------------------------------------------------
    # Current entry
    # --------------------------------------------------------

    entry = get_entry(
        round_id,
        current_stage_no,
        telegram_id,
    )

    user_doc = get_user_by_telegram_id(
        telegram_id
    )

    if not entry:
        return jsonify({
            "success": True,
            "status": "needs_entry",
            "game": game_public(game),
            "round": {
                "id": round_id,
                "title": round_data.get("title", ""),
                "status": round_data.get("status"),
                "current_stage": current_stage_no,
                "total_stages": total_stages,
            },
            "stage": public_stage_data(
                round_data,
                stage,
            ),
            "entry_fee": to_int(
                stage.get("entry_fee"),
                0,
            ),
            "user": public_user(user_doc),
        })

    # Already paid but hasn't answered.
    if entry.get("status") == "entered":
        return jsonify({
            "success": True,
            "status": "ready",
            "game": game_public(game),
            "round": {
                "id": round_id,
                "title": round_data.get("title", ""),
                "status": round_data.get("status"),
                "current_stage": current_stage_no,
                "total_stages": total_stages,
            },
            "stage": public_stage_data(
                round_data,
                stage,
            ),
            "user": public_user(user_doc),
        })

    # Answer submitted and waiting for conclusion.
    if entry.get("status") == "submitted":
        return jsonify({
            "success": True,
            "status": "submitted",
            "game": game_public(game),
            "round": {
                "id": round_id,
                "title": round_data.get("title", ""),
                "status": round_data.get("status"),
                "current_stage": current_stage_no,
                "total_stages": total_stages,
            },
            "stage": public_stage_data(
                round_data,
                stage,
            ),
            "message": (
                "Your answer has been recorded. "
                "Wait for the stage to conclude."
            ),
            "user": public_user(user_doc),
        })

    return jsonify({
        "success": True,
        "status": "round_not_started",
        "game": game_public(game),
        "round": {
            "id": round_id,
            "title": round_data.get("title", ""),
            "status": round_data.get("status"),
            "current_stage": current_stage_no,
            "total_stages": total_stages,
        },
        "user": public_user(user_doc),
    })


# ============================================================
# USER: ENTER STAGE
# ============================================================

def get_user_ref(telegram_id: str):
    return users_col().document(
        str(telegram_id)
    )


def get_user_by_telegram_id(
    telegram_id: str,
) -> Dict[str, Any]:
    snap = get_user_ref(
        telegram_id
    ).get()

    if not snap.exists:
        return {
            "telegram_id": str(telegram_id),
            "points": 0,
            "prize_balance_usd": 0,
        }

    data = snap.to_dict() or {}

    data["telegram_id"] = str(
        data.get("telegram_id")
        or telegram_id
    )

    return data


@competition_bp.post("/<game_id>/enter")
@user_route
def competition_enter(user, game_id):
    telegram_id = str(
        user.get("id")
        or user.get("telegram_id")
        or ""
    )

    if not telegram_id:
        return jsonify({
            "success": False,
            "error": "Unable to identify Telegram user.",
        }), 400

    game = get_game(game_id)

    if not game:
        return jsonify({
            "success": False,
            "error": "Competition game not found.",
        }), 404

    if not game.get("active", False):
        return jsonify({
            "success": False,
            "error": "This game is currently locked.",
        }), 400

    # --------------------------------------------------------
    # Find current round.
    # --------------------------------------------------------

    snaps = (
        rounds_col()
        .where("game_id", "==", game_id)
        .stream()
    )

    rounds = []

    for snap in snaps:
        data = snap.to_dict() or {}
        data["id"] = snap.id

        if data.get("status") not in {
            "settled",
            "cancelled",
        }:
            rounds.append(data)

    if not rounds:
        return jsonify({
            "success": False,
            "error": "No active round is available.",
        }), 400

    rounds.sort(
        key=lambda x: (
            parse_datetime(
                x.get("start_at")
            )
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True,
    )

    round_data = rounds[0]

    round_id = round_data["id"]

    stage_no = to_int(
        round_data.get("current_stage"),
        1,
    )

    # A player eliminated in an earlier stage cannot buy their
    # way into a later stage of the same staged round.
    if game_id in STAGED_GAMES and stage_no > 1:
        previous_result = get_result(
            round_id,
            telegram_id,
        )

        if (
            previous_result
            and to_int(
                previous_result.get("stage_no"),
                1,
            ) < stage_no
            and previous_result.get("eliminated")
        ):
            return jsonify({
                "success": False,
                "error": (
                    "You were eliminated in an earlier stage "
                    "and cannot enter this stage."
                ),
            }), 400

        if (
            previous_result
            and to_int(
                previous_result.get("stage_no"),
                1,
            ) < stage_no
            and not previous_result.get("advanced")
        ):
            return jsonify({
                "success": False,
                "error": (
                    "You did not advance from the previous stage."
                ),
            }), 400

    stage = get_stage(
        round_id,
        stage_no,
    )

    if not stage:
        return jsonify({
            "success": False,
            "error": "This stage has not been prepared yet.",
        }), 400

    if stage.get("status") != "live":
        return jsonify({
            "success": False,
            "error": "Round not started yet.",
        }), 400

    start_at = parse_datetime(
        stage.get("start_at")
    )

    end_at = parse_datetime(
        stage.get("end_at")
    )

    current_time = now_utc()

    if start_at and current_time < start_at:
        return jsonify({
            "success": False,
            "error": "Round not started yet.",
        }), 400

    if end_at and current_time >= end_at:
        # Conclude the stage before accepting another entry.
        settle_stage(
            round_data,
            stage,
        )

        return jsonify({
            "success": False,
            "error": "This stage has ended.",
        }), 400

    fee = to_int(
        stage.get("entry_fee"),
        0,
    )

    if fee < 0:
        fee = 0

    user_ref = get_user_ref(
        telegram_id
    )

    entry_ref = entries_col().document(
        f"{round_id}_{stage_no}_{telegram_id}"
    )

    participant_ref = (
        rounds_col()
        .document(round_id)
        .collection("participants")
        .document(telegram_id)
    )

    transaction_id = (
        f"competition_entry_"
        f"{round_id}_{stage_no}_{telegram_id}"
    )

    transaction_ref = transactions_col().document(
        transaction_id
    )

    # --------------------------------------------------------
    # CRITICAL FIRESTORE TRANSACTION
    #
    # This is intentionally wrapped with
    # firestore.transactional.
    # --------------------------------------------------------

    @firestore.transactional
    def charge_entry(
        transaction,
    ):
        entry_snap = entry_ref.get(
            transaction=transaction
        )

        user_snap = user_ref.get(
            transaction=transaction
        )

        if entry_snap.exists:
            existing = entry_snap.to_dict() or {}

            return {
                "already_entered": True,
                "user": (
                    user_snap.to_dict()
                    if user_snap.exists
                    else {}
                ),
                "entry": existing,
            }

        if not user_snap.exists:
            raise ValueError(
                "QuizBee account not found."
            )

        user_data = user_snap.to_dict() or {}

        points = to_int(
            user_data.get("points"),
            0,
        )

        if points < fee:
            raise ValueError(
                f"You need {fee} QuizBee Points "
                "to enter this stage."
            )

        new_points = points - fee

        transaction.update(
            user_ref,
            {
                "points": new_points,
                "total_spent_points": (
                    to_int(
                        user_data.get(
                            "total_spent_points"
                        ),
                        0,
                    )
                    + fee
                ),
                "updated_at": (
                    firestore.SERVER_TIMESTAMP
                ),
            },
        )

        transaction.set(
            entry_ref,
            {
                "round_id": round_id,
                "game_id": game_id,
                "stage_no": stage_no,
                "telegram_id": telegram_id,
                "entry_fee": fee,
                "status": "entered",
                "answer": None,
                "passed": None,
                "eliminated": False,
                "created_at": (
                    firestore.SERVER_TIMESTAMP
                ),
                "updated_at": (
                    firestore.SERVER_TIMESTAMP
                ),
            },
        )

        transaction.set(
            participant_ref,
            {
                "telegram_id": telegram_id,
                "current_stage": stage_no,
                "active": True,
                "updated_at": (
                    firestore.SERVER_TIMESTAMP
                ),
            },
            merge=True,
        )

        transaction.set(
            transaction_ref,
            {
                "telegram_id": telegram_id,
                "type": "competition_entry",
                "direction": "debit",
                "amount_points": fee,
                "round_id": round_id,
                "game_id": game_id,
                "stage_no": stage_no,
                "status": "completed",
                "created_at": (
                    firestore.SERVER_TIMESTAMP
                ),
            },
            merge=True,
        )

        return {
            "already_entered": False,
            "user": {
                **user_data,
                "points": new_points,
            },
            "entry": {
                "round_id": round_id,
                "game_id": game_id,
                "stage_no": stage_no,
                "telegram_id": telegram_id,
                "entry_fee": fee,
                "status": "entered",
            },
        }

    transaction = db.transaction()

    try:
        result = charge_entry(transaction)

    except ValueError as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 400

    except Exception as exc:
        print(
            "Competition entry transaction error:",
            repr(exc),
        )

        return jsonify({
            "success": False,
            "error": "Unable to process stage entry.",
        }), 500

    return jsonify({
        "success": True,
        "already_entered": result[
            "already_entered"
        ],
        "entry": result["entry"],
        "user": public_user(
            result["user"]
        ),
    })


# ============================================================
# USER: SUBMIT ANSWER
# ============================================================

@competition_bp.post("/<game_id>/submit")
@user_route
def competition_submit(user, game_id):
    telegram_id = str(
        user.get("id")
        or user.get("telegram_id")
        or ""
    )

    game = get_game(game_id)

    if not game:
        return jsonify({
            "success": False,
            "error": "Competition game not found.",
        }), 404

    payload = request.get_json(
        silent=True
    ) or {}

    answer = payload.get("answer")

    if answer is None:
        return jsonify({
            "success": False,
            "error": "An answer is required.",
        }), 400

    answer = clean_text(answer)

    if not answer:
        return jsonify({
            "success": False,
            "error": "An answer is required.",
        }), 400

    # --------------------------------------------------------
    # Locate current round.
    # --------------------------------------------------------

    snaps = (
        rounds_col()
        .where("game_id", "==", game_id)
        .stream()
    )

    rounds = []

    for snap in snaps:
        data = snap.to_dict() or {}
        data["id"] = snap.id

        if data.get("status") not in {
            "settled",
            "cancelled",
        }:
            rounds.append(data)

    if not rounds:
        return jsonify({
            "success": False,
            "error": "No active round.",
        }), 400

    rounds.sort(
        key=lambda x: (
            parse_datetime(
                x.get("start_at")
            )
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True,
    )

    round_data = rounds[0]

    round_id = round_data["id"]

    stage_no = to_int(
        round_data.get("current_stage"),
        1,
    )

    stage = get_stage(
        round_id,
        stage_no,
    )

    if not stage:
        return jsonify({
            "success": False,
            "error": "Round not started yet.",
        }), 400

    if stage.get("status") != "live":
        return jsonify({
            "success": False,
            "error": "This stage is not live.",
        }), 400

    end_at = parse_datetime(
        stage.get("end_at")
    )

    if end_at and now_utc() >= end_at:
        # Timer ended. Settle immediately.
        settle_stage(
            round_data,
            stage,
        )

        result = get_result(
            round_id,
            telegram_id,
        )

        if result:
            return jsonify({
                "success": True,
                "status": (
                    "advanced"
                    if result.get("advanced")
                    else "winner"
                    if result.get("winner")
                    else "eliminated"
                ),
                "result": result_payload(
                    result
                ),
                "message": result.get(
                    "message"
                ),
            })

        return jsonify({
            "success": False,
            "error": "This stage has ended.",
        }), 400

    entry = get_entry(
        round_id,
        stage_no,
        telegram_id,
    )

    if not entry:
        return jsonify({
            "success": False,
            "error": "Enter the stage before answering.",
        }), 400

    if entry.get("status") == "submitted":
        return jsonify({
            "success": False,
            "error": "You have already submitted an answer.",
        }), 400

    if entry.get("status") != "entered":
        return jsonify({
            "success": False,
            "error": "This entry is no longer active.",
        }), 400

    # --------------------------------------------------------
    # Impossible Question and all other games:
    # the submitted answer is stored, but the secret is NOT
    # exposed to the client.
    # --------------------------------------------------------

    entries_col().document(
        entry["id"]
    ).set(
        {
            "status": "submitted",
            "answer": answer,
            "submitted_at": (
                firestore.SERVER_TIMESTAMP
            ),
            "updated_at": (
                firestore.SERVER_TIMESTAMP
            ),
        },
        merge=True,
    )

    return jsonify({
        "success": True,
        "status": "submitted",
        "message": (
            "Your answer has been locked. "
            "Wait for the stage to conclude."
        ),
        "user": public_user(
            get_user_by_telegram_id(
                telegram_id
            )
        ),
    })


# ============================================================
# USER: RESULT
# ============================================================

@competition_bp.get("/<game_id>/result")
@user_route
def competition_result(user, game_id):
    telegram_id = str(
        user.get("id")
        or user.get("telegram_id")
        or ""
    )

    game = get_game(game_id)

    if not game:
        return jsonify({
            "success": False,
            "error": "Competition game not found.",
        }), 404

    # Most recent rounds for this game.
    snaps = (
        rounds_col()
        .where("game_id", "==", game_id)
        .stream()
    )

    rounds = []

    for snap in snaps:
        data = snap.to_dict() or {}
        data["id"] = snap.id
        rounds.append(data)

    rounds.sort(
        key=lambda x: (
            parse_datetime(
                x.get("updated_at")
            )
            or parse_datetime(
                x.get("start_at")
            )
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True,
    )

    for round_data in rounds:
        result = get_result(
            round_data["id"],
            telegram_id,
        )

        if result:
            return jsonify({
                "success": True,
                "game": game_public(game),
                "round": {
                    "id": round_data["id"],
                    "title": round_data.get(
                        "title",
                        "",
                    ),
                    "status": round_data.get(
                        "status"
                    ),
                    "current_stage": to_int(
                        round_data.get(
                            "current_stage"
                        ),
                        1,
                    ),
                    "total_stages": to_int(
                        round_data.get(
                            "total_stages"
                        ),
                        1,
                    ),
                },
                "result": result_payload(
                    result
                ),
            })

    return jsonify({
        "success": True,
        "status": "no_result",
        "game": game_public(game),
    })


# ============================================================
# ADMIN: SETUP GAMES
# ============================================================

# This endpoint is intentionally retained because the existing
# admin frontend already knows how to call it.
# It is safe to run repeatedly.

@competition_bp.post("/admin/setup-games")
@admin_route
def admin_setup_games(admin):
    initialize_games()

    return jsonify({
        "success": True,
        "message": (
            "Competition games initialized."
        ),
        "games": [
            game_public(
                {
                    **definition,
                    "id": game_id,
                }
            )
            for game_id, definition
            in GAME_DEFINITIONS.items()
        ],
    })


# ============================================================
# ADMIN: CREATE ROUND
# ============================================================

@competition_bp.post("/admin/rounds/create")
@admin_route
def admin_create_round(admin):
    payload = request.get_json(
        silent=True
    ) or {}

    game_id = clean_text(
        payload.get("game_id")
    )

    if game_id not in GAME_DEFINITIONS:
        return jsonify({
            "success": False,
            "error": "Invalid competition game.",
        }), 400

    initialize_games()

    title = clean_text(
        payload.get("title")
    )

    if not title:
        title = (
            GAME_DEFINITIONS[game_id]["name"]
            + " Competition"
        )

    prize_pool = max(
        to_number(
            payload.get("prize_pool_usd"),
            0,
        ),
        0,
    )

    entry_fees = payload.get(
        "entry_fees"
    )

    if not isinstance(entry_fees, list):
        entry_fees = default_fees_for_game(
            game_id
        )

    cleaned_fees = []

    for fee in entry_fees:
        cleaned_fees.append(
            max(
                to_int(fee, 0),
                0,
            )
        )

    total_stages = total_stages_for_game(
        game_id
    )

    if len(cleaned_fees) < total_stages:
        defaults = default_fees_for_game(
            game_id
        )

        while len(cleaned_fees) < total_stages:
            index = len(cleaned_fees)

            if index < len(defaults):
                cleaned_fees.append(
                    defaults[index]
                )
            else:
                cleaned_fees.append(
                    30
                    if index == 6
                    else 10
                )

    cleaned_fees = cleaned_fees[
        :total_stages
    ]

    start_at = parse_datetime(
        payload.get("start_at")
    )

    if start_at is None:
        start_at = now_utc()

    round_id = uuid.uuid4().hex

    round_ref = rounds_col().document(
        round_id
    )

    round_ref.set(
        {
            "game_id": game_id,
            "title": title,
            "prize_pool_usd": prize_pool,
            "entry_fees": cleaned_fees,
            "start_at": start_at,
            "current_stage": 1,
            "total_stages": total_stages,
            "status": "draft",
            "winner_count": 0,
            "created_by": str(
                admin.get("id", "")
            ),
            "created_at": (
                firestore.SERVER_TIMESTAMP
            ),
            "updated_at": (
                firestore.SERVER_TIMESTAMP
            ),
        }
    )

    return jsonify({
        "success": True,
        "round_id": round_id,
        "round": {
            "id": round_id,
            "game_id": game_id,
            "title": title,
            "prize_pool_usd": prize_pool,
            "entry_fees": cleaned_fees,
            "start_at": iso(start_at),
            "current_stage": 1,
            "total_stages": total_stages,
            "status": "draft",
        },
    })


# ============================================================
# ADMIN: LIST ROUNDS
# ============================================================

@competition_bp.get("/admin/rounds")
@admin_route
def admin_list_rounds(admin):
    game_id = clean_text(
        request.args.get("game_id")
    )

    query = rounds_col()

    if game_id:
        query = query.where(
            "game_id",
            "==",
            game_id,
        )

    snaps = query.stream()

    rounds = []

    for snap in snaps:
        data = snap.to_dict() or {}
        data["id"] = snap.id

        rounds.append({
            "id": snap.id,
            "game_id": data.get("game_id"),
            "title": data.get("title"),
            "status": data.get("status"),
            "prize_pool_usd": to_number(
                data.get("prize_pool_usd"),
                0,
            ),
            "current_stage": to_int(
                data.get("current_stage"),
                1,
            ),
            "total_stages": to_int(
                data.get("total_stages"),
                1,
            ),
            "winner_count": to_int(
                data.get("winner_count"),
                0,
            ),
            "start_at": iso(
                data.get("start_at")
            ),
            "created_at": iso(
                data.get("created_at")
            ),
            "updated_at": iso(
                data.get("updated_at")
            ),
        })

    rounds.sort(
        key=lambda x: x.get(
            "created_at"
        ) or "",
        reverse=True,
    )

    return jsonify({
        "success": True,
        "rounds": rounds,
    })


# ============================================================
# ADMIN: GET ROUND
# ============================================================

@competition_bp.get("/admin/rounds/<round_id>")
@admin_route
def admin_get_round(admin, round_id):
    round_data = get_round(
        round_id
    )

    if not round_data:
        return jsonify({
            "success": False,
            "error": "Round not found.",
        }), 404

    stages = round_stages(
        round_id
    )

    # Admin is allowed to see secrets.
    for stage in stages:
        stage["start_at"] = iso(
            stage.get("start_at")
        )

        stage["end_at"] = iso(
            stage.get("end_at")
        )

        stage["created_at"] = iso(
            stage.get("created_at")
        )

        stage["updated_at"] = iso(
            stage.get("updated_at")
        )

    entries = round_entries(
        round_id
    )

    for entry in entries:
        entry["created_at"] = iso(
            entry.get("created_at")
        )

        entry["submitted_at"] = iso(
            entry.get("submitted_at")
        )

        entry["settled_at"] = iso(
            entry.get("settled_at")
        )

    result_snaps = (
        results_col()
        .where(
            "round_id",
            "==",
            round_id,
        )
        .stream()
    )

    results = []

    for snap in result_snaps:
        data = snap.to_dict() or {}
        data["id"] = snap.id

        data["settled_at"] = iso(
            data.get("settled_at")
        )

        results.append(data)

    return jsonify({
        "success": True,
        "round": {
            "id": round_id,
            "game_id": round_data.get(
                "game_id"
            ),
            "title": round_data.get(
                "title"
            ),
            "status": round_data.get(
                "status"
            ),
            "prize_pool_usd": to_number(
                round_data.get(
                    "prize_pool_usd"
                ),
                0,
            ),
            "entry_fees": round_data.get(
                "entry_fees",
                [],
            ),
            "start_at": iso(
                round_data.get(
                    "start_at"
                )
            ),
            "current_stage": to_int(
                round_data.get(
                    "current_stage"
                ),
                1,
            ),
            "total_stages": to_int(
                round_data.get(
                    "total_stages"
                ),
                1,
            ),
            "winner_count": to_int(
                round_data.get(
                    "winner_count"
                ),
                0,
            ),
        },
        "stages": stages,
        "entries": entries,
        "results": results,
    })


# ============================================================
# ADMIN: CREATE STAGE
# ============================================================

@competition_bp.post(
    "/admin/rounds/<round_id>/stages/create"
)
@admin_route
def admin_create_stage(
    admin,
    round_id,
):
    round_data = get_round(
        round_id
    )

    if not round_data:
        return jsonify({
            "success": False,
            "error": "Round not found.",
        }), 404

    if round_data.get("status") in {
        "settled",
        "cancelled",
    }:
        return jsonify({
            "success": False,
            "error": (
                "You cannot add a stage to a "
                "finished round."
            ),
        }), 400

    payload = request.get_json(
        silent=True
    ) or {}

    stage_no = to_int(
        payload.get("stage_no"),
        0,
    )

    total_stages = to_int(
        round_data.get(
            "total_stages"
        ),
        1,
    )

    if stage_no < 1 or stage_no > total_stages:
        return jsonify({
            "success": False,
            "error": "Invalid stage number.",
        }), 400

    existing = get_stage(
        round_id,
        stage_no,
    )

    if existing:
        return jsonify({
            "success": False,
            "error": (
                "This stage already exists. "
                "Use Edit Stage instead."
            ),
        }), 400

    game_id = round_data.get(
        "game_id"
    )

    default_fees = round_data.get(
        "entry_fees"
    ) or default_fees_for_game(
        game_id
    )

    default_fee = (
        to_int(
            default_fees[
                stage_no - 1
            ],
            30 if stage_no == 7 else 10,
        )
        if stage_no - 1 < len(default_fees)
        else (
            30
            if stage_no == 7
            else 10
        )
    )

    entry_fee = max(
        to_int(
            payload.get(
                "entry_fee"
            ),
            default_fee,
        ),
        0,
    )

    title = clean_text(
        payload.get("title")
    ) or f"Stage {stage_no}"

    question = clean_text(
        payload.get("question")
    )

    clue = clean_text(
        payload.get("clue")
    )

    options = unique_list(
        payload.get("options")
    )

    accepted = unique_list(
        payload.get(
            "accepted_answers"
        )
    )

    dead_numbers = unique_list(
        payload.get(
            "dead_numbers"
        )
    )

    generation_mode = clean_text(
        payload.get(
            "generation_mode"
        )
    ) or "admin"

    start_at = parse_datetime(
        payload.get(
            "start_at"
        )
    )

    end_at = parse_datetime(
        payload.get(
            "end_at"
        )
    )

    if start_at is None:
        start_at = now_utc()

    if end_at is None:
        # If Admin hasn't supplied an end time, don't
        # accidentally create a stage that immediately expires.
        return jsonify({
            "success": False,
            "error": (
                "End time is required."
            ),
        }), 400

    if end_at <= start_at:
        return jsonify({
            "success": False,
            "error": (
                "End time must be after start time."
            ),
        }), 400

    # --------------------------------------------------------
    # Secret values remain private.
    # --------------------------------------------------------

    correct_answer = clean_text(
        payload.get(
            "correct_answer"
        )
    )

    safe_option = clean_text(
        payload.get(
            "safe_option"
        )
    )

    minimum = to_int(
        payload.get(
            "min_number"
        ),
        1,
    )

    maximum = to_int(
        payload.get(
            "max_number"
        ),
        20,
    )

    if maximum < minimum:
        minimum, maximum = maximum, minimum

    dead_count = max(
        to_int(
            payload.get(
                "dead_count"
            ),
            1,
        ),
        1,
    )

    mechanic = clean_text(
        payload.get(
            "mechanic"
        )
    ).lower()

    if mechanic not in {
        "minority",
        "majority",
        "closest_target",
        "within_range",
    }:
        mechanic = "minority"

    target_percentage = to_number(
        payload.get(
            "target_percentage"
        ),
        50,
    )

    target_min_percentage = to_number(
        payload.get(
            "target_min_percentage"
        ),
        40,
    )

    target_max_percentage = to_number(
        payload.get(
            "target_max_percentage"
        ),
        60,
    )

    stage_id = (
        f"{round_id}_{stage_no}"
    )

    stages_col().document(
        stage_id
    ).set(
        {
            "round_id": round_id,
            "game_id": game_id,
            "stage_no": stage_no,
            "title": title,
            "question": question,
            "clue": clue,
            "entry_fee": entry_fee,
            "start_at": start_at,
            "end_at": end_at,

            # Public configuration.
            "options": options,
            "min_number": minimum,
            "max_number": maximum,
            "mechanic": mechanic,
            "target_percentage": target_percentage,
            "target_min_percentage": (
                target_min_percentage
            ),
            "target_max_percentage": (
                target_max_percentage
            ),

            # Private secrets.
            "generation_mode": generation_mode,
            "correct_answer": correct_answer,
            "accepted_answers": accepted,
            "safe_option": safe_option,
            "dead_numbers": dead_numbers,
            "dead_count": dead_count,

            # Workflow.
            "status": "draft",
            "secret_approved": False,
            "created_by": str(
                admin.get("id", "")
            ),
            "created_at": (
                firestore.SERVER_TIMESTAMP
            ),
            "updated_at": (
                firestore.SERVER_TIMESTAMP
            ),
        }
    )

    return jsonify({
        "success": True,
        "stage_id": stage_id,
        "message": (
            "Stage created as draft. "
            "Review and approve the secret before starting it."
        ),
    })


# ============================================================
# ADMIN: EDIT STAGE
# ============================================================

@competition_bp.post(
    "/admin/rounds/<round_id>/stages/<int:stage_no>/edit"
)
@admin_route
def admin_edit_stage(
    admin,
    round_id,
    stage_no,
):
    round_data = get_round(
        round_id
    )

    if not round_data:
        return jsonify({
            "success": False,
            "error": "Round not found.",
        }), 404

    stage = get_stage(
        round_id,
        stage_no,
    )

    if not stage:
        return jsonify({
            "success": False,
            "error": "Stage not found.",
        }), 404

    # --------------------------------------------------------
    # Editing is allowed until the stage becomes live.
    # Once live, the challenge is frozen.
    # --------------------------------------------------------

    if stage.get("status") == "live":
        return jsonify({
            "success": False,
            "error": (
                "This stage is already live and "
                "cannot be edited."
            ),
        }), 400

    if stage.get("status") == "closed":
        return jsonify({
            "success": False,
            "error": (
                "This stage has already been concluded "
                "and cannot be edited."
            ),
        }), 400

    if round_data.get("status") == "settled":
        return jsonify({
            "success": False,
            "error": (
                "This round has already been settled."
            ),
        }), 400

    payload = request.get_json(
        silent=True
    ) or {}

    updates: Dict[str, Any] = {}

    # --------------------------------------------------------
    # Public configuration
    # --------------------------------------------------------

    if "title" in payload:
        updates["title"] = clean_text(
            payload.get("title")
        )

    if "question" in payload:
        updates["question"] = clean_text(
            payload.get("question")
        )

    if "clue" in payload:
        updates["clue"] = clean_text(
            payload.get("clue")
        )

    if "options" in payload:
        updates["options"] = unique_list(
            payload.get("options")
        )

    if "entry_fee" in payload:
        updates["entry_fee"] = max(
            to_int(
                payload.get(
                    "entry_fee"
                ),
                0,
            ),
            0,
        )

    if "start_at" in payload:
        parsed = parse_datetime(
            payload.get("start_at")
        )

        if parsed:
            updates["start_at"] = parsed

    if "end_at" in payload:
        parsed = parse_datetime(
            payload.get("end_at")
        )

        if parsed:
            updates["end_at"] = parsed

    if "min_number" in payload:
        updates["min_number"] = to_int(
            payload.get(
                "min_number"
            ),
            1,
        )

    if "max_number" in payload:
        updates["max_number"] = to_int(
            payload.get(
                "max_number"
            ),
            20,
        )

    if "mechanic" in payload:
        updates["mechanic"] = clean_text(
            payload.get(
                "mechanic"
            )
        ).lower()

    if "target_percentage" in payload:
        updates["target_percentage"] = (
            to_number(
                payload.get(
                    "target_percentage"
                ),
                50,
            )
        )

    if "target_min_percentage" in payload:
        updates[
            "target_min_percentage"
        ] = to_number(
            payload.get(
                "target_min_percentage"
            ),
            40,
        )

    if "target_max_percentage" in payload:
        updates[
            "target_max_percentage"
        ] = to_number(
            payload.get(
                "target_max_percentage"
            ),
            60,
        )

    # --------------------------------------------------------
    # Secret configuration.
    #
    # Editing a secret automatically removes previous approval.
    # This prevents an Admin from changing the answer after
    # approval without re-approving it.
    # --------------------------------------------------------

    secret_changed = False

    if "correct_answer" in payload:
        updates["correct_answer"] = clean_text(
            payload.get(
                "correct_answer"
            )
        )
        secret_changed = True

    if "accepted_answers" in payload:
        updates[
            "accepted_answers"
        ] = unique_list(
            payload.get(
                "accepted_answers"
            )
        )
        secret_changed = True

    if "safe_option" in payload:
        updates["safe_option"] = clean_text(
            payload.get(
                "safe_option"
            )
        )
        secret_changed = True

    if "dead_numbers" in payload:
        updates[
            "dead_numbers"
        ] = unique_list(
            payload.get(
                "dead_numbers"
            )
        )
        secret_changed = True

    if "dead_count" in payload:
        updates[
            "dead_count"
        ] = max(
            to_int(
                payload.get(
                    "dead_count"
                ),
                1,
            ),
            1,
        )
        secret_changed = True

    if "generation_mode" in payload:
        updates[
            "generation_mode"
        ] = clean_text(
            payload.get(
                "generation_mode"
            )
        ) or "admin"

    if secret_changed:
        updates[
            "secret_approved"
        ] = False

    updates[
        "updated_at"
    ] = firestore.SERVER_TIMESTAMP

    stages_col().document(
        stage["id"]
    ).set(
        updates,
        merge=True,
    )

    return jsonify({
        "success": True,
        "message": (
            "Stage updated. "
            + (
                "The secret must be approved again."
                if secret_changed
                else ""
            )
        ),
    })


# ============================================================
# ADMIN: APPROVE SECRET
# ============================================================

@competition_bp.post(
    "/admin/rounds/<round_id>/stages/<int:stage_no>/approve"
)
@admin_route
def admin_approve_stage(
    admin,
    round_id,
    stage_no,
):
    round_data = get_round(
        round_id
    )

    if not round_data:
        return jsonify({
            "success": False,
            "error": "Round not found.",
        }), 404

    stage = get_stage(
        round_id,
        stage_no,
    )

    if not stage:
        return jsonify({
            "success": False,
            "error": "Stage not found.",
        }), 404

    if stage.get("status") == "live":
        return jsonify({
            "success": False,
            "error": (
                "A live stage cannot be re-approved."
            ),
        }), 400

    game_id = round_data.get(
        "game_id"
    )

    # --------------------------------------------------------
    # Validate the actual secret before approval.
    # --------------------------------------------------------

    if game_id in {
        "guess_it",
        "impossible_question",
    }:
        correct = clean_text(
            stage.get(
                "correct_answer"
            )
        )

        accepted = unique_list(
            stage.get(
                "accepted_answers"
            )
        )

        if not correct:
            return jsonify({
                "success": False,
                "error": (
                    "Enter the correct answer "
                    "before approving the stage."
                ),
            }), 400

        # Always include the official answer.
        if correct not in accepted:
            accepted.insert(
                0,
                correct,
            )

        stages_col().document(
            stage["id"]
        ).set(
            {
                "accepted_answers": accepted,
                "secret_approved": True,
                "approved_by": str(
                    admin.get("id", "")
                ),
                "approved_at": (
                    firestore.SERVER_TIMESTAMP
                ),
                "updated_at": (
                    firestore.SERVER_TIMESTAMP
                ),
            },
            merge=True,
        )

    elif game_id == "survivor":
        safe = clean_text(
            stage.get(
                "safe_option"
            )
        )

        if not safe:
            return jsonify({
                "success": False,
                "error": (
                    "Enter the safe option "
                    "before approving the stage."
                ),
            }), 400

        options = [
            clean_text(x)
            for x in stage.get(
                "options",
                [],
            )
        ]

        if options and safe not in options:
            return jsonify({
                "success": False,
                "error": (
                    "The safe option must be "
                    "one of the stage options."
                ),
            }), 400

        stages_col().document(
            stage["id"]
        ).set(
            {
                "secret_approved": True,
                "approved_by": str(
                    admin.get("id", "")
                ),
                "approved_at": (
                    firestore.SERVER_TIMESTAMP
                ),
                "updated_at": (
                    firestore.SERVER_TIMESTAMP
                ),
            },
            merge=True,
        )

    elif game_id == "dead_number":
        dead_numbers = unique_list(
            stage.get(
                "dead_numbers"
            )
        )

        if (
            not dead_numbers
            and stage.get(
                "generation_mode"
            ) != "random"
        ):
            return jsonify({
                "success": False,
                "error": (
                    "Enter the dead numbers "
                    "or select random generation."
                ),
            }), 400

        stages_col().document(
            stage["id"]
        ).set(
            {
                "secret_approved": True,
                "approved_by": str(
                    admin.get("id", "")
                ),
                "approved_at": (
                    firestore.SERVER_TIMESTAMP
                ),
                "updated_at": (
                    firestore.SERVER_TIMESTAMP
                ),
            },
            merge=True,
        )

    else:
        # Crowd Trap and Impossible Choice calculate
        # outcomes from player choices.
        stages_col().document(
            stage["id"]
        ).set(
            {
                "secret_approved": True,
                "approved_by": str(
                    admin.get("id", "")
                ),
                "approved_at": (
                    firestore.SERVER_TIMESTAMP
                ),
                "updated_at": (
                    firestore.SERVER_TIMESTAMP
                ),
            },
            merge=True,
        )

    return jsonify({
        "success": True,
        "message": (
            "Stage secret approved."
        ),
    })


# ============================================================
# ADMIN: START STAGE
# ============================================================

@competition_bp.post(
    "/admin/rounds/<round_id>/stages/<int:stage_no>/start"
)
@admin_route
def admin_start_stage(
    admin,
    round_id,
    stage_no,
):
    round_data = get_round(
        round_id
    )

    if not round_data:
        return jsonify({
            "success": False,
            "error": "Round not found.",
        }), 404

    stage = get_stage(
        round_id,
        stage_no,
    )

    if not stage:
        return jsonify({
            "success": False,
            "error": "Stage not found.",
        }), 404

    if stage.get("status") == "live":
        return jsonify({
            "success": False,
            "error": "Stage is already live.",
        }), 400

    if stage.get("secret_approved") is not True:
        return jsonify({
            "success": False,
            "error": (
                "Approve the stage secret before "
                "starting the stage."
            ),
        }), 400

    # --------------------------------------------------------
    # Do not allow a stage to be started with missing times.
    # --------------------------------------------------------

    start_at = parse_datetime(
        stage.get("start_at")
    )

    end_at = parse_datetime(
        stage.get("end_at")
    )

    if start_at is None:
        start_at = now_utc()

    if end_at is None:
        return jsonify({
            "success": False,
            "error": (
                "Stage end time is required."
            ),
        }), 400

    if end_at <= start_at:
        return jsonify({
            "success": False,
            "error": (
                "Stage end time must be after "
                "the start time."
            ),
        }), 400

    # --------------------------------------------------------
    # Start immediately when Admin presses Start.
    # This makes the admin button authoritative.
    # --------------------------------------------------------

    start_at = now_utc()

    if end_at <= start_at:
        return jsonify({
            "success": False,
            "error": (
                "The configured end time has already passed."
            ),
        }), 400

    stages_col().document(
        stage["id"]
    ).set(
        {
            "status": "live",
            "start_at": start_at,
            "started_by": str(
                admin.get("id", "")
            ),
            "started_at": (
                firestore.SERVER_TIMESTAMP
            ),
            "updated_at": (
                firestore.SERVER_TIMESTAMP
            ),
        },
        merge=True,
    )

    rounds_col().document(
        round_id
    ).set(
        {
            "status": "live",
            "current_stage": stage_no,
            "updated_at": (
                firestore.SERVER_TIMESTAMP
            ),
        },
        merge=True,
    )

    return jsonify({
        "success": True,
        "message": "Stage is now live.",
        "start_at": iso(start_at),
        "end_at": iso(end_at),
    })


# ============================================================
# ADMIN: END / SETTLE STAGE
# ============================================================

@competition_bp.post(
    "/admin/rounds/<round_id>/stages/<int:stage_no>/end"
)
@admin_route
def admin_end_stage(
    admin,
    round_id,
    stage_no,
):
    round_data = get_round(
        round_id
    )

    if not round_data:
        return jsonify({
            "success": False,
            "error": "Round not found.",
        }), 404

    stage = get_stage(
        round_id,
        stage_no,
    )

    if not stage:
        return jsonify({
            "success": False,
            "error": "Stage not found.",
        }), 404

    if stage.get("status") == "closed":
        return jsonify({
            "success": False,
            "error": (
                "This stage has already been concluded."
            ),
        }), 400

    if stage.get("status") != "live":
        return jsonify({
            "success": False,
            "error": (
                "Only a live stage can be concluded."
            ),
        }), 400

    result = settle_stage(
        round_data,
        stage,
    )

    return jsonify({
        "success": True,
        "message": (
            "Stage concluded and player results recorded."
        ),
        **result,
    })


# ============================================================
# ADMIN: PREPARE NEXT STAGE
# ============================================================

@competition_bp.post(
    "/admin/rounds/<round_id>/next-stage"
)
@admin_route
def admin_next_stage(
    admin,
    round_id,
):
    round_data = get_round(
        round_id
    )

    if not round_data:
        return jsonify({
            "success": False,
            "error": "Round not found.",
        }), 404

    total_stages = to_int(
        round_data.get(
            "total_stages"
        ),
        1,
    )

    current_stage = to_int(
        round_data.get(
            "current_stage"
        ),
        1,
    )

    if current_stage >= total_stages:
        return jsonify({
            "success": False,
            "error": (
                "This is already the final stage."
            ),
        }), 400

    current = get_stage(
        round_id,
        current_stage,
    )

    if current and current.get(
        "status"
    ) != "closed":
        return jsonify({
            "success": False,
            "error": (
                "Conclude the current stage "
                "before advancing."
            ),
        }), 400

    next_stage = current_stage + 1

    existing = get_stage(
        round_id,
        next_stage,
    )

    # --------------------------------------------------------
    # We deliberately DO NOT expose the next stage.
    # Admin must create/configure it separately.
    # --------------------------------------------------------

    rounds_col().document(
        round_id
    ).set(
        {
            "current_stage": next_stage,
            "status": "draft",
            "updated_at": (
                firestore.SERVER_TIMESTAMP
            ),
        },
        merge=True,
    )

    return jsonify({
        "success": True,
        "next_stage": next_stage,
        "message": (
            f"Stage {next_stage} is now the next "
            "stage to configure."
        ),
        "already_created": bool(
            existing
        ),
    })


# ============================================================
# ADMIN: CANCEL ROUND
# ============================================================

@competition_bp.post(
    "/admin/rounds/<round_id>/cancel"
)
@admin_route
def admin_cancel_round(
    admin,
    round_id,
):
    round_data = get_round(
        round_id
    )

    if not round_data:
        return jsonify({
            "success": False,
            "error": "Round not found.",
        }), 404

    if round_data.get(
        "status"
    ) == "settled":
        return jsonify({
            "success": False,
            "error": (
                "A settled round cannot be cancelled."
            ),
        }), 400

    rounds_col().document(
        round_id
    ).set(
        {
            "status": "cancelled",
            "cancelled_by": str(
                admin.get("id", "")
            ),
            "cancelled_at": (
                firestore.SERVER_TIMESTAMP
            ),
            "updated_at": (
                firestore.SERVER_TIMESTAMP
            ),
        },
        merge=True,
    )

    return jsonify({
        "success": True,
        "message": "Competition round cancelled.",
    })


# ============================================================
# ADMIN: FORCE SETTLE EXPIRED STAGE
# ============================================================

@competition_bp.post(
    "/admin/rounds/<round_id>/stages/<int:stage_no>/settle"
)
@admin_route
def admin_force_settle_stage(
    admin,
    round_id,
    stage_no,
):
    round_data = get_round(
        round_id
    )

    if not round_data:
        return jsonify({
            "success": False,
            "error": "Round not found.",
        }), 404

    stage = get_stage(
        round_id,
        stage_no,
    )

    if not stage:
        return jsonify({
            "success": False,
            "error": "Stage not found.",
        }), 404

    if stage.get("status") == "closed":
        return jsonify({
            "success": True,
            "message": (
                "Stage was already settled."
            ),
        })

    result = settle_stage(
        round_data,
        stage,
    )

    return jsonify({
        "success": True,
        "message": (
            "Stage settled successfully."
        ),
        **result,
    })


# ============================================================
# ADMIN: ROUND PARTICIPANTS
# ============================================================

@competition_bp.get(
    "/admin/rounds/<round_id>/participants"
)
@admin_route
def admin_round_participants(
    admin,
    round_id,
):
    round_data = get_round(
        round_id
    )

    if not round_data:
        return jsonify({
            "success": False,
            "error": "Round not found.",
        }), 404

    entries = round_entries(
        round_id
    )

    participants: Dict[str, Dict[str, Any]] = {}

    for entry in entries:
        telegram_id = str(
            entry.get("telegram_id", "")
        )

        if telegram_id not in participants:
            participants[
                telegram_id
            ] = {
                "telegram_id": telegram_id,
                "stages": [],
                "status": "active",
            }

        participants[
            telegram_id
        ]["stages"].append({
            "stage_no": to_int(
                entry.get(
                    "stage_no"
                ),
                1,
            ),
            "entry_fee": to_int(
                entry.get(
                    "entry_fee"
                ),
                0,
            ),
            "status": entry.get(
                "status"
            ),
            "answer": entry.get(
                "answer"
            ),
            "passed": entry.get(
                "passed"
            ),
            "eliminated": entry.get(
                "eliminated"
            ),
            "result": entry.get(
                "result"
            ),
        })

    results = []

    for telegram_id, participant in participants.items():
        result = get_result(
            round_id,
            telegram_id,
        )

        if result:
            participant[
                "final_result"
            ] = result_payload(
                result
            )

        results.append(
            participant
        )

    return jsonify({
        "success": True,
        "round_id": round_id,
        "participants": results,
    })


# ============================================================
# ADMIN: SET GAME ACTIVE / LOCKED
# ============================================================

@competition_bp.post(
    "/admin/games/<game_id>/toggle"
)
@admin_route
def admin_toggle_game(
    admin,
    game_id,
):
    game = get_game(
        game_id
    )

    if not game:
        game = ensure_game_exists(
            game_id
        )

    new_active = not bool(
        game.get("active", False)
    )

    games_col().document(
        game_id
    ).set(
        {
            "active": new_active,
            "updated_at": (
                firestore.SERVER_TIMESTAMP
            ),
        },
        merge=True,
    )

    return jsonify({
        "success": True,
        "game_id": game_id,
        "active": new_active,
    })


# ============================================================
# ADMIN: LIST GAMES
# ============================================================

@competition_bp.get(
    "/admin/games"
)
@admin_route
def admin_games(admin):
    initialize_games()

    games = []

    for game_id, definition in GAME_DEFINITIONS.items():
        game = get_game(
            game_id
        )

        if game:
            games.append(
                game_public(game)
            )

    return jsonify({
        "success": True,
        "games": games,
    })


# ============================================================
# ADMIN: SET PARTICIPANT VISIBILITY
# ============================================================

@competition_bp.post(
    "/admin/settings/participant-visibility"
)
@admin_route
def admin_participant_visibility(
    admin,
):
    payload = request.get_json(
        silent=True
    ) or {}

    enabled = bool(
        payload.get(
            "show_participants",
            False,
        )
    )

    db.collection(
        "competition_settings"
    ).document(
        "general"
    ).set(
        {
            "show_participants": enabled,
            "updated_by": str(
                admin.get("id", "")
            ),
            "updated_at": (
                firestore.SERVER_TIMESTAMP
            ),
        },
        merge=True,
    )

    return jsonify({
        "success": True,
        "show_participants": enabled,
    })


# ============================================================
# ADMIN: GET SETTINGS
# ============================================================

@competition_bp.get(
    "/admin/settings"
)
@admin_route
def admin_get_settings(admin):
    snap = (
        db.collection(
            "competition_settings"
        )
        .document("general")
        .get()
    )

    data = (
        snap.to_dict()
        if snap.exists
        else {}
    )

    return jsonify({
        "success": True,
        "settings": {
            "show_participants": bool(
                data.get(
                    "show_participants",
                    False,
                )
            ),
        },
    })


# ============================================================
# OPTIONAL COMPATIBILITY ENDPOINT
# ============================================================

@competition_bp.post(
    "/admin/rounds/<round_id>/advance"
)
@admin_route
def admin_advance_compat(
    admin,
    round_id,
):
    """
    compatibility alias for older admin frontend code.
    """

    return admin_next_stage(
        admin,
        round_id,
              )
