import os
import re
import hmac
import hashlib
import json
import time
import random
from datetime import datetime, timezone

from flask import Flask, request, jsonify
from flask_cors import CORS


app = Flask(__name__)
CORS(app)

DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"

ENTRY_POINTS_DEFAULT = 10


GAMES = {
    "guess_it": {
        "id": "guess_it",
        "name": "Guess It",
        "emoji": "🎯",
        "status": "active",
        "entry_points": 10,
        "type": "guess_it"
    },

    "impossible_question": {
        "id": "impossible_question",
        "name": "Impossible Question",
        "emoji": "💀",
        "status": "active",
        "entry_points": 10,
        "type": "impossible_question"
    },

    "crowd_trap": {
        "id": "crowd_trap",
        "name": "The Crowd Trap",
        "emoji": "🧠",
        "status": "locked",
        "entry_points": 10,
        "type": "crowd_trap"
    },

    "survivor": {
        "id": "survivor",
        "name": "The Survivor",
        "emoji": "🏆",
        "status": "locked",
        "entry_points": 10,
        "type": "survivor"
    },

    "dead_number": {
        "id": "dead_number",
        "name": "Dead Number",
        "emoji": "☠️",
        "status": "locked",
        "entry_points": 10,
        "type": "dead_number"
    },

    "impossible_choice": {
        "id": "impossible_choice",
        "name": "Impossible Choice",
        "emoji": "🤔",
        "status": "locked",
        "entry_points": 10,
        "type": "impossible_choice"
    }
}


USERS = {}

ENTRIES = {}

ANSWERS = {}

ADS = {}


DEMO_CHALLENGES = {

    "guess_it": {
        "type": "guess_it",
        "prompt": "Which footballer is commonly known as CR7?",
        "clue": "The Portuguese superstar has won multiple Ballon d'Or awards.",
        "correct_answer": "cristiano ronaldo",
        "accepted_answers": [
            "cristiano ronaldo",
            "ronaldo",
            "cr7"
        ]
    },

    "impossible_question": {
        "type": "impossible_question",
        "prompt": "I am thinking of a number. What number comes next in this sequence: 1, 11, 21, 1211, 111221, ?",
        "correct_answer": "312211",
        "accepted_answers": [
            "312211"
        ]
    },

    "crowd_trap": {
        "type": "crowd_trap",
        "prompt": "Choose a number nobody else chooses.",
        "min": 1,
        "max": 20
    },

    "survivor": {
        "type": "survivor",
        "round": 1,
        "prompt": "Choose the one option that keeps you alive.",
        "options": [
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "I",
            "J",
            "K",
            "L",
            "M",
            "N",
            "O"
        ]
    },

    "dead_number": {
        "type": "dead_number",
        "prompt": "Choose a number. Some numbers are DEAD.",
        "min": 1,
        "max": 10
    },

    "impossible_choice": {
        "type": "impossible_choice",
        "prompt": "Which option do you think the majority of players will choose?",
        "options": [
            "A — Get ₦500 tomorrow",
            "B — Get ₦150 today",
            "C — Get ₦1,000 in 7 days",
            "D — Get ₦100 every day for 5 days"
        ]
    }
}


def normalize(value):

    value = str(value or "").lower().strip()

    value = re.sub(r"\s+", " ", value)

    return value


def get_user():

    telegram_user = request.json.get("telegram_user", {})

    telegram_id = telegram_user.get("id")

    if not telegram_id:
        telegram_id = 999000001

    telegram_id = str(telegram_id)

    if telegram_id not in USERS:

        USERS[telegram_id] = {
            "telegram_id": telegram_id,
            "first_name": telegram_user.get(
                "first_name",
                "Demo"
            ),
            "username": telegram_user.get(
                "username",
                "demo_player"
            ),
            "points": 100,
            "prize_balance": 0,
            "score": 0,
            "streak": 1,
            "referrals": 0,
            "created_at": time.time()
        }

    return USERS[telegram_id]


@app.get("/api/health")
def health():

    return jsonify({
        "status": "ok",
        "service": "QuizBee API",
        "dev_mode": DEV_MODE
    })


@app.post("/api/bootstrap")
def bootstrap():

    user = get_user()

    return jsonify({
        "user": user,
        "games": list(GAMES.values())
    })


@app.get("/api/games")
def games():

    return jsonify({
        "games": list(GAMES.values())
    })


@app.post("/api/games/<game_id>/enter")
def enter_game(game_id):

    if game_id not in GAMES:
        return jsonify({
            "error": "Game not found."
        }), 404

    game = GAMES[game_id]

    if game["status"] != "active":
        return jsonify({
            "error": "This game is currently locked."
        }), 403

    user = get_user()

    entry_cost = game["entry_points"]

    if user["points"] < entry_cost:

        return jsonify({
            "error": "Not enough QuizBee Points."
        }), 400

    entry_key = (
        f'{user["telegram_id"]}:'
        f'{game_id}'
    )

    if entry_key in ENTRIES:

        return jsonify({
            "error": "You have already entered this round."
        }), 400

    user["points"] -= entry_cost

    ENTRIES[entry_key] = {
        "telegram_id": user["telegram_id"],
        "game_id": game_id,
        "entered_at": time.time()
    }

    return jsonify({
        "success": True,
        "points": user["points"]
    })


@app.get("/api/games/<game_id>/challenge")
def challenge(game_id):

    if game_id not in GAMES:
        return jsonify({
            "error": "Game not found."
        }), 404

    challenge_data = dict(
        DEMO_CHALLENGES[game_id]
    )

    # Never expose secret answers.
    challenge_data.pop("correct_answer", None)
    challenge_data.pop("accepted_answers", None)

    return jsonify(challenge_data)


@app.post("/api/games/<game_id>/answer")
def answer(game_id):

    if game_id not in GAMES:
        return jsonify({
            "error": "Game not found."
        }), 404

    user = get_user()

    entry_key = (
        f'{user["telegram_id"]}:'
        f'{game_id}'
    )

    if entry_key not in ENTRIES:
        return jsonify({
            "error": "Enter the game first."
        }), 400

    body = request.json or {}

    submitted = normalize(
        body.get("answer", "")
    )

    if not submitted:
        return jsonify({
            "error": "Answer is required."
        }), 400

    game = GAMES[game_id]

    # -------------------------
    # GUESS IT
    # -------------------------

    if game_id == "guess_it":

        correct = submitted in [
            normalize(x)
            for x in DEMO_CHALLENGES[game_id]
            ["accepted_answers"]
        ]

        if correct:

            user["score"] += 100

            return jsonify({
                "correct": True,
                "message": "Correct! 🎉",
                "score": user["score"],
                "points": user["points"]
            })

        return jsonify({
            "correct": False,
            "message": "❌ Wrong answer."
        })


    # -------------------------
    # IMPOSSIBLE QUESTION
    # -------------------------

    if game_id == "impossible_question":

        correct = submitted in [
            normalize(x)
            for x in DEMO_CHALLENGES[game_id]
            ["accepted_answers"]
        ]

        if correct:

            user["score"] += 250

            return jsonify({
                "correct": True,
                "message": "🔥 You solved the Impossible Question!",
                "score": user["score"],
                "points": user["points"]
            })

        return jsonify({
            "correct": False,
            "message": "❌ That's wrong. Try again."
        })


    # -------------------------
    # CROWD TRAP
    # -------------------------

    if game_id == "crowd_trap":

        try:
            number = int(submitted)
        except ValueError:
            return jsonify({
                "error": "Choose a valid number."
            }), 400

        minimum = DEMO_CHALLENGES[game_id]["min"]
        maximum = DEMO_CHALLENGES[game_id]["max"]

        if number < minimum or number > maximum:

            return jsonify({
                "error": f"Choose between {minimum} and {maximum}."
            }), 400

        ANSWERS.setdefault(game_id, {})[
            user["telegram_id"]
        ] = number

        return jsonify({
            "correct": False,
            "message":
                "🔒 Choice locked. Results are revealed when the round closes."
        })


    # -------------------------
    # SURVIVOR
    # -------------------------

    if game_id == "survivor":

        ANSWERS.setdefault(game_id, {})[
            user["telegram_id"]
        ] = submitted

        return jsonify({
            "correct": False,
            "message":
                "🔒 Choice locked. The safe option will be revealed later."
        })


    # -------------------------
    # DEAD NUMBER
    # -------------------------

    if game_id == "dead_number":

        try:
            number = int(submitted)
        except ValueError:
            return jsonify({
                "error": "Choose a valid number."
            }), 400

        minimum = DEMO_CHALLENGES[game_id]["min"]
        maximum = DEMO_CHALLENGES[game_id]["max"]

        if number < minimum or number > maximum:

            return jsonify({
                "error": f"Choose between {minimum} and {maximum}."
            }), 400

        ANSWERS.setdefault(game_id, {})[
            user["telegram_id"]
        ] = number

        return jsonify({
            "correct": False,
            "message":
                "☠️ Choice locked. Dead Numbers will be revealed later."
        })


    # -------------------------
    # IMPOSSIBLE CHOICE
    # -------------------------

    if game_id == "impossible_choice":

        ANSWERS.setdefault(game_id, {})[
            user["telegram_id"]
        ] = submitted

        return jsonify({
            "correct": False,
            "message":
                "🔒 Prediction locked. The crowd result will be revealed later."
        })


    return jsonify({
        "error": "Unsupported game."
    }), 400


@app.post("/api/ads/mock-complete")
def mock_ad_complete():

    user = get_user()

    user_id = user["telegram_id"]

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    key = f"{user_id}:{today}"

    watched = ADS.get(key, 0)

    if watched >= 10:

        return jsonify({
            "error":
                "Today's ad reward limit is complete."
        }), 400

    ADS[key] = watched + 1

    user["points"] += 1

    return jsonify({
        "success": True,
        "points": user["points"],
        "ads_watched": ADS[key]
    })


@app.get("/api/leaderboard")
def leaderboard():

    players = []

    for user in USERS.values():

        players.append({
            "name": user["first_name"],
            "score": user["score"]
        })

    players.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return jsonify({
        "players": players[:50]
    })


# ------------------------------------
# DEVELOPMENT CONTROLS
# ------------------------------------

@app.post("/api/dev/unlock/<game_id>")
def dev_unlock(game_id):

    if not DEV_MODE:
        return jsonify({
            "error": "Development mode disabled."
        }), 403

    if game_id not in GAMES:
        return jsonify({
            "error": "Game not found."
        }), 404

    GAMES[game_id]["status"] = "active"

    return jsonify({
        "success": True,
        "game": GAMES[game_id]
    })


@app.post("/api/dev/lock/<game_id>")
def dev_lock(game_id):

    if not DEV_MODE:
        return jsonify({
            "error": "Development mode disabled."
        }), 403

    if game_id not in GAMES:
        return jsonify({
            "error": "Game not found."
        }), 404

    GAMES[game_id]["status"] = "locked"

    return jsonify({
        "success": True
    })


@app.post("/api/dev/reset")
def dev_reset():

    if not DEV_MODE:
        return jsonify({
            "error": "Development mode disabled."
        }), 403

    USERS.clear()
    ENTRIES.clear()
    ANSWERS.clear()
    ADS.clear()

    return jsonify({
        "success": True,
        "message": "Development data reset."
    })


@app.post("/api/dev/resolve/<game_id>")
def dev_resolve(game_id):

    if not DEV_MODE:
        return jsonify({
            "error": "Development mode disabled."
        }), 403

    if game_id not in GAMES:
        return jsonify({
            "error": "Game not found."
        }), 404

    results = {}

    submitted = ANSWERS.get(game_id, {})

    # CROWD TRAP
    if game_id == "crowd_trap":

        counts = {}

        for number in submitted.values():
            counts[number] = counts.get(number, 0) + 1

        winners = [
            user_id
            for user_id, number in submitted.items()
            if counts[number] == 1
        ]

        for user_id in winners:
            USERS[user_id]["score"] += 150

        results = {
            "winner_count": len(winners),
            "winners": winners,
            "counts": counts
        }


    # SURVIVOR
    elif game_id == "survivor":

        safe = "A"

        winners = [
            user_id
            for user_id, choice in submitted.items()
            if choice == safe
        ]

        for user_id in winners:
            USERS[user_id]["score"] += 200

        results = {
            "safe_option": safe,
            "survivors": winners
        }


    # DEAD NUMBER
    elif game_id == "dead_number":

        dead_numbers = [2, 5, 7]

        survivors = [
            user_id
            for user_id, number in submitted.items()
            if number not in dead_numbers
        ]

        for user_id in survivors:
            USERS[user_id]["score"] += 200

        results = {
            "dead_numbers": dead_numbers,
            "survivors": survivors
        }


    # IMPOSSIBLE CHOICE
    elif game_id == "impossible_choice":

        counts = {}

        for choice in submitted.values():
            counts[choice] = counts.get(choice, 0) + 1

        if counts:

            highest = max(counts.values())

            winners = [
                user_id
                for user_id, choice in submitted.items()
                if counts[choice] == highest
            ]

        else:
            winners = []

        for user_id in winners:
            USERS[user_id]["score"] += 200

        results = {
            "counts": counts,
            "winners": winners
        }


    else:

        return jsonify({
            "error":
                "This game does not use round resolution."
        }), 400


    ANSWERS[game_id] = {}

    return jsonify({
        "success": True,
        "results": results
    })


if __name__ == "__main__":

    port = int(
        os.getenv("PORT", "5000")
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
)
