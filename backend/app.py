import os
import re
import random
import string
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS

from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import validate_telegram_init_data
from backend.wallet import wallet_bp


app = Flask(__name__)
app.register_blueprint(wallet_bp)


CORS(
    app,
    resources={
        r"/api/*": {
            "origins": "*"
        }
    },
    allow_headers=[
        "Content-Type",
        "X-Telegram-Init-Data"
    ],
    methods=[
        "GET",
        "POST",
        "OPTIONS"
    ]
)


DEV_MODE = os.getenv(
    "DEV_MODE",
    "false"
).lower() == "true"


# ============================================================
# HELPERS
# ============================================================

def now():
    return datetime.now(timezone.utc)


def normalize_answer(value):
    if value is None:
        return ""

    value = str(value).strip().lower()

    value = re.sub(r"\s+", " ", value)

    value = re.sub(
        r"[^\w\s-]",
        "",
        value
    )

    return value


def generate_referral_code():

    letters = "".join(
        random.choice(string.ascii_uppercase)
        for _ in range(3)
    )

    digits = "".join(
        random.choice(string.digits)
        for _ in range(5)
    )

    return f"TB{letters}{digits}"


def get_demo_telegram_id():
    return "999000001"


# ============================================================
# TELEGRAM AUTHENTICATION
# ============================================================

def get_authenticated_telegram_user():

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
        "last_name": user.get("last_name", ""),
        "photo_url": user.get("photo_url", "")
    }


def require_telegram_user():

    user = get_authenticated_telegram_user()

    if user:
        return user

    return None


# ============================================================
# DEVELOPMENT ONLY AUTH
# ============================================================

def get_development_user():

    if not DEV_MODE:
        return None

    telegram_id = (
        request.headers.get("X-Demo-Telegram-ID")
        or get_demo_telegram_id()
    )

    return {
        "telegram_id": str(telegram_id),
        "username": "QuizBeeUser",
        "first_name": "QuizBee",
        "last_name": ""
    }


# ============================================================
# USER DATABASE
# ============================================================

def user_ref(telegram_id):

    return db.collection(
        "users"
    ).document(
        str(telegram_id)
    )


def get_or_create_user(
    telegram_user=None,
    allow_dev_fallback=False
):

    if telegram_user is None:

        telegram_user = (
            get_authenticated_telegram_user()
        )

    if telegram_user is None and allow_dev_fallback:

        telegram_user = get_development_user()

    if telegram_user is None:

        raise PermissionError(
            "Unauthorized Telegram session."
        )

    telegram_id = str(
        telegram_user["telegram_id"]
    )

    ref = user_ref(telegram_id)

    snap = ref.get()

    if snap.exists:

        data = snap.to_dict()

        updates = {
            "telegram_id": telegram_id,
            "username": telegram_user.get(
                "username",
                ""
            ),
            "first_name": telegram_user.get(
                "first_name",
                ""
            ),
            "last_name": telegram_user.get(
                "last_name",
                ""
            ),
            "updated_at": now()
        }

        if telegram_user.get("photo_url"):
            updates["photo_url"] = (
                telegram_user["photo_url"]
            )

        ref.update(updates)

        data.update(updates)

        return data

    referral_code = generate_referral_code()

    data = {
        "telegram_id": telegram_id,

        "username": telegram_user.get(
            "username",
            ""
        ),

        "first_name": telegram_user.get(
            "first_name",
            ""
        ),

        "last_name": telegram_user.get(
            "last_name",
            ""
        ),

        "photo_url": telegram_user.get(
            "photo_url",
            ""
        ),

        "quizbee_points": 100,

        "prize_balance": 0,

        "total_earned": 0,

        "total_spent": 0,

        "referral_code": referral_code,

        "referred_by": None,

        "referrals_count": 0,

        "streak_days": 1,

        "last_login": now(),

        "created_at": now(),

        "updated_at": now()
    }

    ref.set(data)

    return data


# ============================================================
# GAME HELPERS
# ============================================================

def get_game(game_id):

    ref = db.collection(
        "games"
    ).document(game_id)

    snap = ref.get()

    if not snap.exists:
        return None

    data = snap.to_dict()

    data["id"] = game_id

    return data


def get_all_games():

    docs = (
        db.collection("games")
        .order_by("sort_order")
        .stream()
    )

    games = []

    for doc in docs:

        data = doc.to_dict()

        data["id"] = doc.id

        games.append(data)

    return games


def get_active_challenge(game_id):

    query = (
        db.collection("challenges")
        .where(
            "game_id",
            "==",
            game_id
        )
        .where(
            "active",
            "==",
            True
        )
        .limit(1)
    )

    docs = list(
        query.stream()
    )

    if not docs:
        return None

    doc = docs[0]

    data = doc.to_dict()

    data["id"] = doc.id

    return data


def has_entered_challenge(
    telegram_id,
    game_id,
    challenge_id
):

    query = (
        db.collection("entries")
        .where(
            "telegram_id",
            "==",
            str(telegram_id)
        )
        .where(
            "game_id",
            "==",
            game_id
        )
        .where(
            "challenge_id",
            "==",
            challenge_id
        )
        .limit(1)
    )

    return len(
        list(query.stream())
    ) > 0


def get_public_challenge(
    challenge
):

    data = dict(challenge)

    data.pop(
        "correct_answer",
        None
    )

    data.pop(
        "accepted_answers",
        None
    )

    return data


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():

    try:

        db.collection(
            "settings"
        ).document(
            "health"
        ).set(
            {
                "last_check": now()
            },
            merge=True
        )

        return jsonify({
            "success": True,
            "firebase": True,
            "dev_mode": DEV_MODE,
            "message": (
                "QuizBee backend is running."
            )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "firebase": False,
            "error": str(e)
        }), 500


# ============================================================
# BOOTSTRAP
# ============================================================

@app.post("/api/bootstrap")
def bootstrap():

    try:

        telegram_user = (
            require_telegram_user()
        )

        if not telegram_user:

            return jsonify({
                "success": False,
                "error": (
                    "Unauthorized Telegram session."
                )
            }), 401

        user = get_or_create_user(
            telegram_user
        )

        games = get_all_games()

        challenge = get_active_challenge(
            "impossible_question"
        )

        return jsonify({

            "success": True,

            "user": user,

            "games": games,

            "featured_challenge": (
                get_public_challenge(
                    challenge
                )
                if challenge
                else None
            )
        })

    except PermissionError as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 401

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# GAMES
# ============================================================

@app.get("/api/games")
def games():

    try:

        telegram_user = (
            require_telegram_user()
        )

        if not telegram_user:

            return jsonify({
                "success": False,
                "error": (
                    "Unauthorized Telegram session."
                )
            }), 401

        return jsonify({

            "success": True,

            "games": get_all_games()

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# GAME ENTRY
# ============================================================

@app.post("/api/games/<game_id>/enter")
def enter_game(game_id):

    try:

        telegram_user = (
            require_telegram_user()
        )

        if not telegram_user:

            return jsonify({
                "success": False,
                "error": (
                    "Unauthorized Telegram session."
                )
            }), 401

        user = get_or_create_user(
            telegram_user
        )

        game = get_game(game_id)

        if not game:

            return jsonify({
                "success": False,
                "error": "Game not found."
            }), 404

        if not game.get(
            "active",
            False
        ):

            return jsonify({
                "success": False,
                "error": (
                    "This game is coming soon."
                )
            }), 403

        challenge = get_active_challenge(
            game_id
        )

        if not challenge:

            return jsonify({
                "success": False,
                "error": (
                    "No active challenge "
                    "is available yet."
                )
            }), 404

        telegram_id = user[
            "telegram_id"
        ]

        if has_entered_challenge(
            telegram_id,
            game_id,
            challenge["id"]
        ):

            return jsonify({

                "success": True,

                "already_entered": True,

                "challenge":
                    get_public_challenge(
                        challenge
                    ),

                "user": user

            })

        entry_fee = int(
            game.get(
                "entry_fee",
                10
            )
        )

        if int(
            user.get(
                "quizbee_points",
                0
            )
        ) < entry_fee:

            return jsonify({
                "success": False,
                "error": (
                    "Not enough "
                    "QuizBee Points."
                )
            }), 400

        new_balance = (
            int(
                user.get(
                    "quizbee_points",
                    0
                )
            )
            - entry_fee
        )

        user_ref(
            telegram_id
        ).update({

            "quizbee_points":
                new_balance,

            "total_spent":
                firestore.Increment(
                    entry_fee
                ),

            "updated_at":
                now()
        })

        entry_ref = (
            db.collection(
                "entries"
            ).document()
        )

        entry_ref.set({

            "telegram_id":
                telegram_id,

            "game_id":
                game_id,

            "challenge_id":
                challenge["id"],

            "entry_fee":
                entry_fee,

            "status":
                "active",

            "created_at":
                now()
        })

        db.collection(
            "transactions"
        ).document().set({

            "telegram_id":
                telegram_id,

            "type":
                "game_entry",

            "game_id":
                game_id,

            "challenge_id":
                challenge["id"],

            "amount":
                -entry_fee,

            "currency":
                "quizbee_points",

            "created_at":
                now()
        })

        user[
            "quizbee_points"
        ] = new_balance

        return jsonify({

            "success": True,

            "already_entered": False,

            "challenge":
                get_public_challenge(
                    challenge
                ),

            "user":
                user

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# GET CHALLENGE
# ============================================================

@app.get("/api/games/<game_id>/challenge")
def challenge(game_id):

    try:

        telegram_user = (
            require_telegram_user()
        )

        if not telegram_user:

            return jsonify({
                "success": False,
                "error": (
                    "Unauthorized Telegram session."
                )
            }), 401

        game = get_game(game_id)

        if not game:

            return jsonify({
                "success": False,
                "error": "Game not found."
            }), 404

        if not game.get(
            "active",
            False
        ):

            return jsonify({
                "success": False,
                "error": (
                    "This game is coming soon."
                )
            }), 403

        challenge_data = (
            get_active_challenge(
                game_id
            )
        )

        if not challenge_data:

            return jsonify({
                "success": False,
                "error": (
                    "No active challenge."
                )
            }), 404

        return jsonify({

            "success": True,

            "game": game,

            "challenge":
                get_public_challenge(
                    challenge_data
                )

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# ANSWER SUBMISSION
# ============================================================

@app.post("/api/games/<game_id>/answer")
def answer(game_id):

    try:

        telegram_user = (
            require_telegram_user()
        )

        if not telegram_user:

            return jsonify({
                "success": False,
                "error": (
                    "Unauthorized Telegram session."
                )
            }), 401

        user = get_or_create_user(
            telegram_user
        )

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        challenge_id = body.get(
            "challenge_id"
        )

        submitted_answer = body.get(
            "answer"
        )

        if not challenge_id:

            return jsonify({
                "success": False,
                "error": (
                    "Missing challenge ID."
                )
            }), 400

        challenge_ref = (
            db.collection(
                "challenges"
            ).document(
                challenge_id
            )
        )

        challenge_snap = (
            challenge_ref.get()
        )

        if not challenge_snap.exists:

            return jsonify({
                "success": False,
                "error": (
                    "Challenge not found."
                )
            }), 404

        challenge_data = (
            challenge_snap.to_dict()
        )

        if challenge_data.get(
            "game_id"
        ) != game_id:

            return jsonify({
                "success": False,
                "error": (
                    "Invalid challenge."
                )
            }), 400

        telegram_id = user[
            "telegram_id"
        ]

        if not has_entered_challenge(
            telegram_id,
            game_id,
            challenge_id
        ):

            return jsonify({
                "success": False,
                "error": (
                    "You must enter "
                    "the game first."
                )
            }), 403

        normalized = normalize_answer(
            submitted_answer
        )

        correct_answer = (
            normalize_answer(
                challenge_data.get(
                    "correct_answer"
                )
            )
        )

        accepted_answers = (
            challenge_data.get(
                "accepted_answers",
                []
            )
        )

        accepted_normalized = [

            normalize_answer(x)

            for x in accepted_answers

        ]

        is_correct = (

            normalized == correct_answer

            or normalized
            in accepted_normalized

        )

        answer_ref = (
            db.collection(
                "answers"
            ).document()
        )

        answer_ref.set({

            "telegram_id":
                telegram_id,

            "game_id":
                game_id,

            "challenge_id":
                challenge_id,

            "answer":
                str(
                    submitted_answer
                    or ""
                ),

            "normalized_answer":
                normalized,

            "correct":
                is_correct,

            "created_at":
                now()

        })

        if not is_correct:

            return jsonify({

                "success": True,

                "correct": False,

                "reward": 0,

                "reward_points": 0,

                "message":
                    "Wrong answer. Try again."

            })

        # ----------------------------------------------------
        # CHECK WHETHER THIS USER ALREADY RECEIVED THE REWARD
        # ----------------------------------------------------

        previous_correct_query = (

            db.collection(
                "answers"
            )

            .where(
                "telegram_id",
                "==",
                telegram_id
            )

            .where(
                "challenge_id",
                "==",
                challenge_id
            )

            .where(
                "correct",
                "==",
                True
            )

        )

        previous_correct = list(
            previous_correct_query.stream()
        )

        # The answer we just created is included.
        if len(previous_correct) > 1:

            return jsonify({

                "success": True,

                "correct": True,

                "already_rewarded": True,

                "reward": 0,

                "reward_points": 0,

                "message":
                    "Correct answer."

            })

        reward = int(
            challenge_data.get(
                "reward_points",
                0
            )
        )

        if reward > 0:

            user_ref(
                telegram_id
            ).update({

                "quizbee_points":
                    firestore.Increment(
                        reward
                    ),

                "total_earned":
                    firestore.Increment(
                        reward
                    ),

                "updated_at":
                    now()

            })

            db.collection(
                "transactions"
            ).document().set({

                "telegram_id":
                    telegram_id,

                "type":
                    "game_reward",

                "game_id":
                    game_id,

                "challenge_id":
                    challenge_id,

                "amount":
                    reward,

                "currency":
                    "quizbee_points",

                "created_at":
                    now()

            })

        updated_user = (
            user_ref(
                telegram_id
            ).get().to_dict()
        )

        return jsonify({

            "success": True,

            "correct": True,

            "reward": reward,

            "reward_points": reward,

            "user":
                updated_user,

            "message":
                "Correct answer! 🎉"

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# ADS
# ============================================================

@app.post("/api/ads/mock-complete")
def mock_complete_ad():

    try:

        telegram_user = (
            require_telegram_user()
        )

        if not telegram_user:

            return jsonify({
                "success": False,
                "error": (
                    "Unauthorized Telegram session."
                )
            }), 401

        user = get_or_create_user(
            telegram_user
        )

        telegram_id = user[
            "telegram_id"
        ]

        reward = 1

        db.collection(
            "ad_rewards"
        ).document().set({

            "telegram_id":
                telegram_id,

            "reward":
                reward,

            "provider":
                "mock",

            "status":
                "completed",

            "created_at":
                now()

        })

        user_ref(
            telegram_id
        ).update({

            "quizbee_points":
                firestore.Increment(
                    reward
                ),

            "total_earned":
                firestore.Increment(
                    reward
                ),

            "updated_at":
                now()

        })

        db.collection(
            "transactions"
        ).document().set({

            "telegram_id":
                telegram_id,

            "type":
                "ad_reward",

            "amount":
                reward,

            "currency":
                "quizbee_points",

            "created_at":
                now()

        })

        updated_user = (
            user_ref(
                telegram_id
            ).get().to_dict()
        )

        return jsonify({

            "success": True,

            "reward": reward,

            "reward_points": reward,

            "user":
                updated_user,

            "message":
                "+1 QuizBee Point"

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# LEADERBOARD
# ============================================================

@app.get("/api/leaderboard")
def leaderboard():

    try:

        telegram_user = (
            require_telegram_user()
        )

        if not telegram_user:

            return jsonify({
                "success": False,
                "error": (
                    "Unauthorized Telegram session."
                )
            }), 401

        docs = (

            db.collection(
                "users"
            )

            .order_by(
                "total_earned",
                direction=
                    firestore.Query.DESCENDING
            )

            .limit(50)

            .stream()

        )

        results = []

        rank = 1

        for doc in docs:

            data = doc.to_dict()

            results.append({

                "rank":
                    rank,

                "telegram_id":
                    data.get(
                        "telegram_id"
                    ),

                "username":
                    data.get(
                        "username",
                        ""
                    ),

                "first_name":
                    data.get(
                        "first_name",
                        ""
                    ),

                "total_earned":
                    data.get(
                        "total_earned",
                        0
                    )

            })

            rank += 1

        return jsonify({

            "success": True,

            "leaderboard":
                results

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# PROFILE
# ============================================================

@app.get("/api/profile")
def profile():

    try:

        telegram_user = (
            require_telegram_user()
        )

        if not telegram_user:

            return jsonify({
                "success": False,
                "error": (
                    "Unauthorized Telegram session."
                )
            }), 401

        user = get_or_create_user(
            telegram_user
        )

        return jsonify({

            "success": True,

            "user":
                user

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# DEV ADMIN FUNCTIONS
# ============================================================

@app.post("/api/dev/setup")
def dev_setup():

    if not DEV_MODE:

        return jsonify({
            "success": False,
            "error": (
                "Development mode disabled."
            )
        }), 403

    games = [

        {
            "id":
                "guess_it",

            "name":
                "Guess It",

            "icon":
                "🎯",

            "description":
                "Use clues to identify the answer.",

            "active":
                True,

            "entry_fee":
                10,

            "sort_order":
                1
        },

        {
            "id":
                "impossible_question",

            "name":
                "Impossible Question",

            "icon":
                "💀",

            "description":
                "A question designed to test reasoning.",

            "active":
                True,

            "entry_fee":
                10,

            "sort_order":
                2
        },

        {
            "id":
                "crowd_trap",

            "name":
                "The Crowd Trap",

            "icon":
                "🧠",

            "description":
                "Predict the crowd.",

            "active":
                False,

            "entry_fee":
                10,

            "sort_order":
                3
        },

        {
            "id":
                "survivor",

            "name":
                "The Survivor",

            "icon":
                "🏆",

            "description":
                "Choose carefully and survive.",

            "active":
                False,

            "entry_fee":
                10,

            "sort_order":
                4
        },

        {
            "id":
                "dead_number",

            "name":
                "Dead Number",

            "icon":
                "☠️",

            "description":
                "Avoid the dead numbers.",

            "active":
                False,

            "entry_fee":
                10,

            "sort_order":
                5
        },

        {
            "id":
                "impossible_choice",

            "name":
                "Impossible Choice",

            "icon":
                "🤔",

            "description":
                "Choose between difficult outcomes.",

            "active":
                False,

            "entry_fee":
                10,

            "sort_order":
                6
        }

    ]

    for game in games:

        game_id = game.pop(
            "id"
        )

        game["updated_at"] = now()

        db.collection(
            "games"
        ).document(
            game_id
        ).set(
            game,
            merge=True
        )

    return jsonify({

        "success": True,

        "message":
            "Games created."

    })


@app.post("/api/dev/create-challenges")
def create_challenges():

    if not DEV_MODE:

        return jsonify({
            "success": False,
            "error":
                "Development mode disabled."
        }), 403

    existing = (
        db.collection(
            "challenges"
        ).stream()
    )

    for doc in existing:
        doc.reference.delete()

    challenges = [

        {
            "game_id":
                "guess_it",

            "title":
                "Guess the Footballer",

            "question":
                "Who is this footballer?",

            "type":
                "guess",

            "active":
                True,

            "round_id":
                "demo_round_1",

            "correct_answer":
                "Cristiano Ronaldo",

            "accepted_answers": [
                "Ronaldo",
                "CR7",
                "Cristiano Ronaldo"
            ],

            "reward_points":
                20,

            "metadata": {
                "image_url": "",
                "category": "Football"
            }
        },

        {
            "game_id":
                "impossible_question",

            "title":
                "The Sequence",

            "question":
                (
                    "What comes next?\n\n"
                    "1, 11, 21, 1211, "
                    "111221, ?"
                ),

            "type":
                "text",

            "active":
                True,

            "round_id":
                "weekly_1",

            "correct_answer":
                "312211",

            "accepted_answers": [
                "312211"
            ],

            "reward_points":
                50,

            "metadata": {
                "difficulty": "hard"
            }
        },

        {
            "game_id":
                "crowd_trap",

            "title":
                "Pick a Number",

            "question":
                "Choose a number from 1 to 20.",

            "type":
                "choice",

            "active":
                False,

            "round_id":
                "demo_round_1",

            "correct_answer":
                "7",

            "accepted_answers": [
                "7"
            ],

            "options": [
                "1", "2", "3", "4", "5",
                "6", "7", "8", "9", "10",
                "11", "12", "13", "14", "15",
                "16", "17", "18", "19", "20"
            ],

            "reward_points":
                30
        },

        {
            "game_id":
                "survivor",

            "title":
                "Choose Your Door",

            "question":
                "Choose one option.",

            "type":
                "choice",

            "active":
                False,

            "round_id":
                "demo_round_1",

            "correct_answer":
                "A",

            "accepted_answers": [
                "A"
            ],

            "options": [
                "A", "B", "C", "D", "E",
                "F", "G", "H", "I", "J",
                "K", "L", "M", "N", "O"
            ],

            "reward_points":
                50
        },

        {
            "game_id":
                "dead_number",

            "title":
                "Avoid the Dead Numbers",

            "question":
                "Choose a number from 1 to 10.",

            "type":
                "choice",

            "active":
                False,

            "round_id":
                "demo_round_1",

            "correct_answer":
                "2",

            "accepted_answers": [
                "2"
            ],

            "options": [
                "1", "2", "3", "4", "5",
                "6", "7", "8", "9", "10"
            ],

            "reward_points":
                40
        },

        {
            "game_id":
                "impossible_choice",

            "title":
                "Impossible Choice",

            "question":
                "Which would you choose?",

            "type":
                "choice",

            "active":
                False,

            "round_id":
                "demo_round_1",

            "correct_answer":
                "B",

            "accepted_answers": [
                "B"
            ],

            "options": [
                "A",
                "B",
                "C",
                "D"
            ],

            "reward_points":
                40
        }

    ]

    for challenge in challenges:

        db.collection(
            "challenges"
        ).add({

            **challenge,

            "created_at":
                now(),

            "updated_at":
                now()

        })

    return jsonify({

        "success": True,

        "message":
            "Demo challenges created."

    })


@app.post("/api/dev/unlock/<game_id>")
def unlock_game(game_id):

    if not DEV_MODE:

        return jsonify({
            "success": False,
            "error":
                "Development mode disabled."
        }), 403

    ref = (
        db.collection(
            "games"
        ).document(
            game_id
        )
    )

    if not ref.get().exists:

        return jsonify({
            "success": False,
            "error":
                "Game not found."
        }), 404

    ref.update({

        "active":
            True,

        "updated_at":
            now()

    })

    return jsonify({

        "success":
            True,

        "game_id":
            game_id,

        "active":
            True

    })


@app.post("/api/dev/lock/<game_id>")
def lock_game(game_id):

    if not DEV_MODE:

        return jsonify({
            "success": False,
            "error":
                "Development mode disabled."
        }), 403

    ref = (
        db.collection(
            "games"
        ).document(
            game_id
        )
    )

    if not ref.get().exists:

        return jsonify({
            "success": False,
            "error":
                "Game not found."
        }), 404

    ref.update({

        "active":
            False,

        "updated_at":
            now()

    })

    return jsonify({

        "success":
            True,

        "game_id":
            game_id,

        "active":
            False

    })


@app.post("/api/dev/reset")
def reset_demo():

    if not DEV_MODE:

        return jsonify({
            "success": False,
            "error":
                "Development mode disabled."
        }), 403

    telegram_id = (
        get_demo_telegram_id()
    )

    ref = user_ref(
        telegram_id
    )

    ref.set({

        "telegram_id":
            telegram_id,

        "username":
            "QuizBeeUser",

        "first_name":
            "QuizBee",

        "quizbee_points":
            100,

        "prize_balance":
            0,

        "total_earned":
            0,

        "total_spent":
            0,

        "referral_code":
            generate_referral_code(),

        "referred_by":
            None,

        "referrals_count":
            0,

        "streak_days":
            1,

        "last_login":
            now(),

        "created_at":
            now(),

        "updated_at":
            now()

    })

    return jsonify({

        "success":
            True,

        "message":
            "Demo user reset."

    })


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return jsonify({

        "success":
            True,

        "message":
            "QuizBee backend is running.",

        "health":
            "/api/health"

    })


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "5000"
        )
    )

    print(
        "===================================="
    )

    print(
        "🐝 QuizBee Firebase Backend"
    )

    print(
        "===================================="
    )

    print(
        f"DEV_MODE: {DEV_MODE}"
    )

    print(
        f"PORT: {port}"
    )

    print(
        "Firebase: initialized"
    )

    print(
        "Telegram authentication: enabled"
    )

    print(
        "===================================="
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
