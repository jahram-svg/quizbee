import os
import re
import random
import string
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request
from flask_cors import CORS

from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import validate_telegram_init_data
from backend.wallet import wallet_bp
from backend.daily_earning import daily_earning_bp
from backend.admin import (
    admin_bp,
    get_app_settings,
    is_maintenance_bypass
)
from backend.competition import competition_bp
from backend.raffle import raffle_bp
from backend.notifications import notifications_bp
from backend.referral_streak import (
    referral_streak_bp,
    process_referral,
    record_game_participation,
)


app = Flask(__name__)

app.register_blueprint(wallet_bp)
app.register_blueprint(daily_earning_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(competition_bp)
app.register_blueprint(raffle_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(referral_streak_bp)


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
        "DELETE",
        "OPTIONS"
    ]
)


DEV_MODE = os.getenv(
    "DEV_MODE",
    "false"
).lower() == "true"


# ============================================================
# BASIC REQUEST SIZE LIMIT
# ============================================================

app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024


# ============================================================
# GLOBAL MAINTENANCE GATE
# ============================================================

@app.before_request
def maintenance_gate():

    path = request.path or ""

    # --------------------------------------------------------
    # NEVER BLOCK THESE
    # --------------------------------------------------------

    # Admin must always be able to manage the platform.
    if path.startswith(
        "/api/admin"
    ):
        return None

    # Competition Admin routes must remain available.
    if path.startswith(
        "/api/competition/admin"
    ):
        return None

    # Health check must remain available.
    if path == "/api/health":
        return None

    # --------------------------------------------------------
    # CORS PREFLIGHT
    # --------------------------------------------------------

    if request.method == "OPTIONS":
        return None

    # Non-API requests are irrelevant here.
    if not path.startswith(
        "/api/"
    ):
        return None

    try:

        settings = get_app_settings()

        maintenance_mode = bool(
            settings.get(
                "maintenance_mode",
                False
            )
        )

        if not maintenance_mode:
            return None

        # ----------------------------------------------------
        # AUTHENTICATE USER
        # ----------------------------------------------------

        user = get_authenticated_telegram_user()

        if not user:

            return jsonify({
                "success": False,
                "error": settings.get(
                    "maintenance_message",
                    "QuizBee is currently under maintenance."
                ),
                "code": "MAINTENANCE",
                "maintenance": True
            }), 503

        telegram_id = str(
            user["telegram_id"]
        )

        # ----------------------------------------------------
        # TEST USER BYPASS
        # ----------------------------------------------------

        if is_maintenance_bypass(
            telegram_id
        ):
            return None

        # ----------------------------------------------------
        # NORMAL USER
        # ----------------------------------------------------

        return jsonify({
            "success": False,
            "error": settings.get(
                "maintenance_message",
                "QuizBee is currently under maintenance."
            ),
            "code": "MAINTENANCE",
            "maintenance": True
        }), 503

    except Exception as e:

        print(
            "Maintenance gate error:",
            repr(e)
        )

        # Fail closed.
        return jsonify({
            "success": False,
            "error": "QuizBee is temporarily unavailable.",
            "code": "MAINTENANCE_CHECK_FAILED"
        }), 503


# ============================================================
# SECURITY RESPONSE HEADERS
# ============================================================

@app.after_request
def security_headers(response):

    response.headers["X-Content-Type-Options"] = "nosniff"

    response.headers["X-Frame-Options"] = "SAMEORIGIN"

    response.headers["Referrer-Policy"] = (
        "strict-origin-when-cross-origin"
    )

    response.headers["Permissions-Policy"] = (
        "camera=(), "
        "microphone=(), "
        "geolocation=()"
    )

    return response


# ============================================================
# HELPERS
# ============================================================

def now():
    return datetime.now(timezone.utc)


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


def generate_referral_code():

    letters = "".join(
        random.choice(
            string.ascii_uppercase
        )
        for _ in range(3)
    )

    digits = "".join(
        random.choice(
            string.digits
        )
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

    result = {
        "telegram_id": str(
            user["id"]
        ),
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
        "photo_url": user.get(
            "photo_url",
            ""
        )
    }

    # Preserve validated referral/deep-link parameter
    # supplied by telegram_auth.py.
    if user.get("_start_param"):
        result["_start_param"] = user[
            "_start_param"
        ]

    return result


def require_telegram_user():

    user = get_authenticated_telegram_user()

    if not user:
        return None

    try:

        ref = user_ref(
            user["telegram_id"]
        )

        snap = ref.get()

        if snap.exists:

            data = snap.to_dict() or {}

            if data.get(
                "blocked",
                False
            ):
                return None

    except Exception:

        # Do not silently grant access if
        # account-status verification fails.
        return None

    return user


# ============================================================
# DEVELOPMENT ONLY AUTH
# ============================================================

def get_development_user():

    if not DEV_MODE:
        return None

    telegram_id = (
        request.headers.get(
            "X-Demo-Telegram-ID"
        )
        or get_demo_telegram_id()
    )

    return {
        "telegram_id": str(
            telegram_id
        ),
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

    if (
        telegram_user is None
        and allow_dev_fallback
    ):

        telegram_user = (
            get_development_user()
        )

    if telegram_user is None:

        raise PermissionError(
            "Unauthorized Telegram session."
        )

    telegram_id = str(
        telegram_user["telegram_id"]
    )

    ref = user_ref(
        telegram_id
    )

    snap = ref.get()

    # --------------------------------------------------------
    # EXISTING USER
    # --------------------------------------------------------

    if snap.exists:

        data = snap.to_dict() or {}

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

        if telegram_user.get(
            "photo_url"
        ):

            updates["photo_url"] = (
                telegram_user[
                    "photo_url"
                ]
            )

        # ----------------------------------------------------
        # PHASE 8 MIGRATION
        #
        # Older QuizBee accounts may have had a streak value
        # from login/account creation. That was not a real
        # game streak, so reset it when no real game date
        # exists.
        # ----------------------------------------------------

        if (
            "last_game_date"
            not in data
        ):

            updates[
                "streak_days"
            ] = 0

            updates[
                "last_game_date"
            ] = None

            updates[
                "last_game_at"
            ] = None

            updates[
                "streak_month"
            ] = None

            updates[
                "streak_month_best"
            ] = 0

        # ----------------------------------------------------
        # EXISTING ACCOUNTS ARE CONSIDERED ALREADY PROCESSED
        # FOR REFERRALS.
        #
        # This prevents an old account from becoming a referral
        # simply by opening somebody else's referral link.
        # ----------------------------------------------------

        if (
            "referral_processed"
            not in data
        ):

            updates[
                "referral_processed"
            ] = True

        # ----------------------------------------------------
        # PHASE 8 GAME COUNT MIGRATION
        # ----------------------------------------------------

        if (
            "games_played_count"
            not in data
        ):

            updates[
                "games_played_count"
            ] = 0

        ref.update(
            updates
        )

        data.update(
            updates
        )

        return data

    # --------------------------------------------------------
    # NEW USER
    # --------------------------------------------------------

    referral_code = generate_referral_code()

    data = {

        "telegram_id":
            telegram_id,

        "username":
            telegram_user.get(
                "username",
                ""
            ),

        "first_name":
            telegram_user.get(
                "first_name",
                ""
            ),

        "last_name":
            telegram_user.get(
                "last_name",
                ""
            ),

        "photo_url":
            telegram_user.get(
                "photo_url",
                ""
            ),

        "quizbee_points":
            0,

        "wins":
            0,

        "prize_balance":
            0,

        "total_earned":
            0,

        "total_spent":
            0,

        # ----------------------------------------------------
        # REFERRAL
        # ----------------------------------------------------

        "referral_code":
            referral_code,

        "referred_by":
            None,

        "referrals_count":
            0,

        "referral_processed":
            False,

        "referral_joined_at":
            None,

        # ----------------------------------------------------
        # STREAK
        # ----------------------------------------------------

        "streak_days":
            0,

        "last_game_date":
            None,

        "last_game_at":
            None,

        "streak_month":
            None,

        "streak_month_best":
            0,

        "games_played_count":
            0,

        # ----------------------------------------------------
        # ACCOUNT DATES
        # ----------------------------------------------------

        "last_login":
            now(),

        "created_at":
            now(),

        "updated_at":
            now()
    }

    ref.set(
        data
    )

    return data


# ============================================================
# GAME HELPERS
# ============================================================

def get_game(game_id):

    ref = db.collection(
        "games"
    ).document(
        game_id
    )

    snap = ref.get()

    if not snap.exists:
        return None

    data = snap.to_dict()

    data["id"] = game_id

    return data


def get_all_games():

    docs = (
        db.collection(
            "games"
        )
        .order_by(
            "sort_order"
        )
        .stream()
    )

    games = []

    for doc in docs:

        data = doc.to_dict()

        data["id"] = doc.id

        games.append(
            data
        )

    return games


def get_active_challenge(game_id):

    query = (
        db.collection(
            "challenges"
        )
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
        db.collection(
            "entries"
        )
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
        list(
            query.stream()
        )
    ) > 0


def get_public_challenge(
    challenge
):

    data = dict(
        challenge
    )

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

            "success":
                True,

            "firebase":
                True,

            "dev_mode":
                DEV_MODE,

            "message":
                "QuizBee backend is running."

        })

    except Exception as e:

        return jsonify({

            "success":
                False,

            "firebase":
                False,

            "error":
                str(e)

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

                "success":
                    False,

                "error":
                    "Unauthorized Telegram session."

            }), 401

        # ----------------------------------------------------
        # GET OR CREATE USER
        # ----------------------------------------------------

        user = get_or_create_user(
            telegram_user
        )

        # ----------------------------------------------------
        # PHASE 8 REFERRAL ATTRIBUTION
        #
        # start_param was extracted from VALIDATED Telegram
        # initData by telegram_auth.py.
        # ----------------------------------------------------

        process_referral(
            user["telegram_id"],
            telegram_user.get(
                "_start_param",
                ""
            )
        )

        # ----------------------------------------------------
        # REFRESH USER AFTER REFERRAL PROCESSING
        # ----------------------------------------------------

        user = get_or_create_user(
            telegram_user
        )

        games = get_all_games()

        challenge = get_active_challenge(
            "impossible_question"
        )

        return jsonify({

            "success":
                True,

            "user":
                user,

            "games":
                games,

            "featured_challenge":
                (
                    get_public_challenge(
                        challenge
                    )
                    if challenge
                    else None
                )

        })

    except PermissionError as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 401

    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# GAME HISTORY
# ============================================================

@app.get("/api/game-history")
def game_history():

    try:

        telegram_user = (
            require_telegram_user()
        )

        if not telegram_user:

            return jsonify({
                "success": False,
                "error":
                    "Unauthorized Telegram session."
            }), 401

        telegram_id = str(
            telegram_user["telegram_id"]
        )

        docs = list(
            db.collection(
                "transactions"
            )
            .where(
                "telegram_id",
                "==",
                telegram_id
            )
            .limit(300)
            .stream()
        )

        history = []

        for doc in docs:

            data = (
                doc.to_dict()
                or {}
            )

            tx_type = str(
                data.get(
                    "type",
                    ""
                )
            )

            if tx_type not in {
                "game_entry",
                "game_reward",
                "competition_prize"
            }:

                continue

            history.append({

                "id":
                    doc.id,

                "type":
                    tx_type,

                "game_id":
                    data.get(
                        "game_id",
                        ""
                    ),

                "challenge_id":
                    data.get(
                        "challenge_id",
                        ""
                    ),

                "amount":
                    data.get(
                        "amount",
                        data.get(
                            "amount_usd",
                            0
                        )
                    ),

                "currency":
                    data.get(
                        "currency",
                        "quizbee_points"
                    ),

                "description":
                    data.get(
                        "description",
                        ""
                    ),

                "status":
                    data.get(
                        "status",
                        "completed"
                    ),

                "created_at":
                    (
                        data.get(
                            "created_at"
                        ).isoformat()
                        if isinstance(
                            data.get(
                                "created_at"
                            ),
                            datetime
                        )
                        else str(
                            data.get(
                                "created_at",
                                ""
                            )
                        )
                    )

            })

        history.sort(
            key=lambda item:
                item.get(
                    "created_at",
                    ""
                ),
            reverse=True
        )

        return jsonify({

            "success":
                True,

            "history":
                history[:100]

        })

    except Exception as e:

        print(
            "Game history error:",
            repr(e)
        )

        return jsonify({

            "success":
                False,

            "error":
                "Unable to load game history."

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

                "success":
                    False,

                "error":
                    "Unauthorized Telegram session."

            }), 401

        return jsonify({

            "success":
                True,

            "games":
                get_all_games()

        })

    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

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

                "success":
                    False,

                "error":
                    "Unauthorized Telegram session."

            }), 401

        user = get_or_create_user(
            telegram_user
        )

        game = get_game(
            game_id
        )

        if not game:

            return jsonify({

                "success":
                    False,

                "error":
                    "Game not found."

            }), 404

        # ----------------------------------------------------
        # GAME MAINTENANCE
        # ----------------------------------------------------

        if (
            game.get(
                "maintenance_mode",
                False
            )
            and not is_maintenance_bypass(
                telegram_user[
                    "telegram_id"
                ]
            )
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "This game is currently under maintenance.",

                "code":
                    "GAME_MAINTENANCE",

                "maintenance":
                    True,

                "game_id":
                    game_id

            }), 503

        # ----------------------------------------------------
        # GAME LOCK
        # ----------------------------------------------------

        if not game.get(
            "active",
            False
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "This game is coming soon."

            }), 403

        # ----------------------------------------------------
        # ACTIVE CHALLENGE
        # ----------------------------------------------------

        challenge = get_active_challenge(
            game_id
        )

        if not challenge:

            return jsonify({

                "success":
                    False,

                "error":
                    "No active challenge is available yet."

            }), 404

        telegram_id = user[
            "telegram_id"
        ]

        # ----------------------------------------------------
        # PREVENT DUPLICATE ENTRY
        #
        # IMPORTANT:
        # Re-entering the same challenge does NOT count as
        # another game participation or streak day.
        # ----------------------------------------------------

        if has_entered_challenge(
            telegram_id,
            game_id,
            challenge["id"]
        ):

            return jsonify({

                "success":
                    True,

                "already_entered":
                    True,

                "challenge":
                    get_public_challenge(
                        challenge
                    ),

                "user":
                    user

            })

        # ----------------------------------------------------
        # ENTRY FEE
        # ----------------------------------------------------

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

                "success":
                    False,

                "error":
                    "Not enough QuizBee Points."

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

        # ----------------------------------------------------
        # UPDATE USER BALANCE
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # CREATE GAME ENTRY
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # TRANSACTION RECORD
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # PHASE 8 STREAK
        #
        # Only a genuinely NEW successful game entry counts
        # as game participation.
        # ----------------------------------------------------

        participation = (
            record_game_participation(
                telegram_id
            )
        )

        user.update(
            participation
        )

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return jsonify({

            "success":
                True,

            "already_entered":
                False,

            "challenge":
                get_public_challenge(
                    challenge
                ),

            "user":
                user

        })

    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

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

                "success":
                    False,

                "error":
                    "Unauthorized Telegram session."

            }), 401

        game = get_game(
            game_id
        )

        if not game:

            return jsonify({

                "success":
                    False,

                "error":
                    "Game not found."

            }), 404

        if (
            game.get(
                "maintenance_mode",
                False
            )
            and not is_maintenance_bypass(
                telegram_user[
                    "telegram_id"
                ]
            )
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "This game is currently under maintenance.",

                "code":
                    "GAME_MAINTENANCE",

                "maintenance":
                    True,

                "game_id":
                    game_id

            }), 503

        if not game.get(
            "active",
            False
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "This game is coming soon."

            }), 403

        challenge_data = (
            get_active_challenge(
                game_id
            )
        )

        if not challenge_data:

            return jsonify({

                "success":
                    False,

                "error":
                    "No active challenge."

            }), 404

        return jsonify({

            "success":
                True,

            "game":
                game,

            "challenge":
                get_public_challenge(
                    challenge_data
                )

        })

    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

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

                "success":
                    False,

                "error":
                    "Unauthorized Telegram session."

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

                "success":
                    False,

                "error":
                    "Missing challenge ID."

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

                "success":
                    False,

                "error":
                    "Challenge not found."

            }), 404

        challenge_data = (
            challenge_snap.to_dict()
        )

        if challenge_data.get(
            "game_id"
        ) != game_id:

            return jsonify({

                "success":
                    False,

                "error":
                    "Invalid challenge."

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

                "success":
                    False,

                "error":
                    "You must enter the game first."

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

            normalize_answer(
                x
            )

            for x in accepted_answers

        ]

        is_correct = (

            normalized == correct_answer

            or normalized
            in accepted_normalized

        )

        # ----------------------------------------------------
        # STORE ANSWER
        # ----------------------------------------------------

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

                "success":
                    True,

                "correct":
                    False,

                "reward":
                    0,

                "reward_points":
                    0,

                "message":
                    "Wrong answer. Try again."

            })

        # ----------------------------------------------------
        # CHECK WHETHER USER ALREADY RECEIVED REWARD
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

        # The answer just created is included.
        if len(
            previous_correct
        ) > 1:

            return jsonify({

                "success":
                    True,

                "correct":
                    True,

                "already_rewarded":
                    True,

                "reward":
                    0,

                "reward_points":
                    0,

                "message":
                    "Correct answer."

            })

        reward = int(
            challenge_data.get(
                "reward_points",
                0
            )
        )

        update_data = {
            "updated_at":
                now()
        }

        if reward > 0:

            update_data[
                "quizbee_points"
            ] = firestore.Increment(
                reward
            )

            update_data[
                "total_earned"
            ] = firestore.Increment(
                reward
            )

        # Record leaderboard win.
        update_data[
            "wins"
        ] = firestore.Increment(
            1
        )

        user_ref(
            telegram_id
        ).update(
            update_data
        )

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

            "success":
                True,

            "correct":
                True,

            "reward":
                reward,

            "reward_points":
                reward,

            "user":
                updated_user,

            "message":
                "Correct answer! 🎉"

        })

    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# ADS
# ============================================================

ADS_TIMEZONE = ZoneInfo(
    "Africa/Lagos"
)


def get_ads_today():

    return datetime.now(
        ADS_TIMEZONE
    ).date().isoformat()


def get_ads_settings():

    settings = get_app_settings()

    return {

        "enabled":
            settings.get(
                "ads_enabled",
                True
            ),

        "reward_points":
            max(
                1,
                int(
                    settings.get(
                        "ads_reward_points",
                        1
                    )
                )
            ),

        "daily_limit":
            max(
                1,
                int(
                    settings.get(
                        "ads_daily_limit",
                        10
                    )
                )
            )
    }


@app.get("/api/ads/status")
def ads_status():

    try:

        telegram_user = require_telegram_user()

        if not telegram_user:

            return jsonify({
                "success": False,
                "error":
                    "Unauthorized Telegram session."
            }), 401


        user = get_or_create_user(
                telegram_user
            )


        telegram_id = user["telegram_id"]


        settings = get_ads_settings()


        today = get_ads_today()


        docs = (
            db.collection(
                "ad_rewards"
            )
            .where(
                "telegram_id",
                "==",
                telegram_id
            )
            .stream()
        )


        watched = 0


        for doc in docs:

            data = doc.to_dict() or {}

            if (
                data.get(
                    "ad_day"
                ) == today
                and data.get(
                    "status"
                ) == "completed"
            ):

                watched += 1


        return jsonify({

            "success":
                True,

            "enabled":
                settings["enabled"],

            "reward_points":
                settings["reward_points"],

            "daily_limit":
                settings["daily_limit"],

            "ads_watched":
                watched
        })


    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


@app.post("/api/ads/start")
def start_ad():

    try:

        telegram_user = require_telegram_user()

        if not telegram_user:
            return jsonify({
                "success": False,
                "error":
                    "Unauthorized Telegram session."
            }), 401

        user = get_or_create_user(
            telegram_user
        )

        telegram_id = user["telegram_id"]

        settings = get_ads_settings()

        if not settings["enabled"]:
            return jsonify({
                "success": False,
                "error":
                    "Ads are currently disabled."
            }), 403

        today = get_ads_today()

        # ----------------------------------------------------
        # Daily limit
        # ----------------------------------------------------

        docs = (
            db.collection(
                "ad_rewards"
            )
            .where(
                "telegram_id",
                "==",
                telegram_id
            )
            .stream()
        )

        watched = 0

        for doc in docs:

            data = doc.to_dict() or {}

            if (
                data.get("ad_day") == today
                and
                data.get("status") == "completed"
            ):
                watched += 1

        if watched >= settings["daily_limit"]:

            return jsonify({
                "success": False,
                "error":
                    "You have reached today's ad limit.",

                "ads_watched":
                    watched,

                "daily_limit":
                    settings["daily_limit"]
            }), 429

        session_ref = (
            db.collection(
                "ad_sessions"
            ).document()
        )

        session_ref.set({
            "telegram_id":
                telegram_id,

            "ad_day":
                today,

            "status":
                "pending",

            "provider":
                "monetag",

            "zone_id":
                "11853919",

            "created_at":
                now(),

            "expires_at":
                now() + __import__(
                    "datetime"
                ).timedelta(
                    minutes=5
                )
        })

        return jsonify({
            "success": True,

            "ad_session_id":
                session_ref.id,

            "reward_points":
                settings["reward_points"],

            "ads_watched":
                watched,

            "daily_limit":
                settings["daily_limit"]
        })

    except Exception as e:

        print(
            "Ad start error:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error":
                "Unable to start ad session."
        }), 500


@app.post("/api/ads/reward")
def reward_ad():

    try:

        telegram_user = require_telegram_user()

        if not telegram_user:
            return jsonify({
                "success": False,
                "error":
                    "Unauthorized Telegram session."
            }), 401

        user = get_or_create_user(
            telegram_user
        )

        telegram_id = user["telegram_id"]

        settings = get_ads_settings()

        if not settings["enabled"]:
            return jsonify({
                "success": False,
                "error":
                    "Ads are currently disabled."
            }), 403

        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        ad_session_id = str(
            body.get(
                "ad_session_id",
                ""
            )
        ).strip()

        if not ad_session_id:
            return jsonify({
                "success": False,
                "error":
                    "Ad session is required."
            }), 400

        today = get_ads_today()

        session_ref = (
            db.collection(
                "ad_sessions"
            )
            .document(
                ad_session_id
            )
        )

        ad_ref = (
            db.collection(
                "ad_rewards"
            ).document()
        )

        transaction_ref = (
            db.collection(
                "transactions"
            )
            .document()
        )

        user_ref_value = (
            db.collection(
                "users"
            )
            .document(
                telegram_id
            )
        )

        firestore_transaction = db.transaction()

        @firestore.transactional
        def reward_transaction(tx):

            session_snapshot = session_ref.get(
                transaction=tx
            )

            if not session_snapshot.exists:
                raise ValueError(
                    "Invalid ad session."
                )

            session = (
                session_snapshot.to_dict()
                or {}
            )

            if str(
                session.get(
                    "telegram_id",
                    ""
                )
            ) != telegram_id:
                raise ValueError(
                    "Invalid ad session."
                )

            if session.get("ad_day") != today:
                raise ValueError(
                    "This ad session has expired."
                )

            if session.get("status") != "pending":
                raise ValueError(
                    "This ad session has already been used."
                )

            expires_at = session.get(
                "expires_at"
            )

            if expires_at:

                current_time = now()

                try:
                    if current_time > expires_at:
                        raise ValueError(
                            "This ad session has expired."
                        )
                except TypeError:
                    pass

            # ------------------------------------------------
            # Count today's rewards inside the transaction.
            # ------------------------------------------------

            reward_docs = (
                db.collection(
                    "ad_rewards"
                )
                .where(
                    "telegram_id",
                    "==",
                    telegram_id
                )
                .stream()
            )

            watched = 0

            for doc in reward_docs:

                data = (
                    doc.to_dict()
                    or {}
                )

                if (
                    data.get("ad_day") == today
                    and
                    data.get("status") == "completed"
                ):
                    watched += 1

            if watched >= settings["daily_limit"]:
                raise ValueError(
                    "You have reached today's ad limit."
                )

            reward = settings[
                "reward_points"
            ]

            # ------------------------------------------------
            # Mark session used BEFORE granting reward.
            # ------------------------------------------------

            tx.update(
                session_ref,
                {
                    "status":
                        "completed",

                    "completed_at":
                        firestore.SERVER_TIMESTAMP
                }
            )

            tx.set(
                ad_ref,
                {
                    "telegram_id":
                        telegram_id,

                    "reward":
                        reward,

                    "provider":
                        "monetag",

                    "zone_id":
                        "11853919",

                    "monetag_site_id":
                        "3499970",

                    "status":
                        "completed",

                    "ad_day":
                        today,

                    "ad_session_id":
                        ad_session_id,

                    "created_at":
                        firestore.SERVER_TIMESTAMP
                }
            )

            tx.update(
                user_ref_value,
                {
                    "quizbee_points":
                        firestore.Increment(
                            reward
                        ),

                    "total_earned":
                        firestore.Increment(
                            reward
                        ),

                    "updated_at":
                        firestore.SERVER_TIMESTAMP
                }
            )

            tx.set(
                transaction_ref,
                {
                    "telegram_id":
                        telegram_id,

                    "type":
                        "ad_reward",

                    "amount":
                        reward,

                    "currency":
                        "quizbee_points",

                    "provider":
                        "monetag",

                    "zone_id":
                        "11853919",

                    "reference":
                        ad_ref.id,

                    "ad_session_id":
                        ad_session_id,

                    "created_at":
                        firestore.SERVER_TIMESTAMP
                }
            )

            return {
                "reward":
                    reward,

                "ads_watched":
                    watched + 1
            }

        result = reward_transaction(
            firestore_transaction
        )

        updated_user = (
            user_ref_value
            .get()
            .to_dict()
        )

        return jsonify({
            "success": True,

            "reward":
                result["reward"],

            "reward_points":
                result["reward"],

            "ads_watched":
                result["ads_watched"],

            "daily_limit":
                settings["daily_limit"],

            "user":
                updated_user,

            "message":
                (
                    f"+{result['reward']} "
                    "QuizBee Point"
                )
        })

    except ValueError as exc:

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400

    except Exception as exc:

        print(
            "Ad reward transaction error:",
            repr(exc)
        )

        return jsonify({
            "success": False,
            "error":
                "Unable to process ad reward."
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

                "success":
                    False,

                "error":
                    "Unauthorized Telegram session."

            }), 401

        users = (
            db.collection(
                "users"
            ).stream()
        )

        leaderboard_data = []

        for snap in users:

            data = snap.to_dict() or {}

            wins = int(
                data.get(
                    "wins",
                    0
                ) or 0
            )

            leaderboard_data.append({

                "telegram_id":
                    str(
                        data.get(
                            "telegram_id",
                            snap.id
                        )
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

                "wins":
                    wins

            })

        leaderboard_data.sort(
            key=lambda x: x["wins"],
            reverse=True
        )

        leaderboard_data = (
            leaderboard_data[:50]
        )

        for index, player in enumerate(
            leaderboard_data,
            start=1
        ):

            player[
                "rank"
            ] = index

        return jsonify({

            "success":
                True,

            "leaderboard":
                leaderboard_data

        })

    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

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

                "success":
                    False,

                "error":
                    "Unauthorized Telegram session."

            }), 401

        user = get_or_create_user(
            telegram_user
        )

        return jsonify({

            "success":
                True,

            "user":
                user

        })

    except Exception as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# DEV ADMIN FUNCTIONS
# ============================================================

@app.post("/api/dev/setup")
def dev_setup():

    if not DEV_MODE:

        return jsonify({

            "success":
                False,

            "error":
                "Development mode disabled."

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

        "success":
            True,

        "message":
            "Games created."

    })


@app.post("/api/dev/create-challenges")
def create_challenges():

    if not DEV_MODE:

        return jsonify({

            "success":
                False,

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
                "image_url":
                    "",

                "category":
                    "Football"
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
                "difficulty":
                    "hard"
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

        "success":
            True,

        "message":
            "Demo challenges created."

    })


@app.post("/api/dev/unlock/<game_id>")
def unlock_game(game_id):

    if not DEV_MODE:

        return jsonify({

            "success":
                False,

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

            "success":
                False,

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

            "success":
                False,

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

            "success":
                False,

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

            "success":
                False,

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

        "last_name":
            "",

        "quizbee_points":
            0,

        "wins":
            0,

        "prize_balance":
            0,

        "total_earned":
            0,

        "total_spent":
            0,

        # ----------------------------------------------------
        # REFERRAL
        # ----------------------------------------------------

        "referral_code":
            generate_referral_code(),

        "referred_by":
            None,

        "referrals_count":
            0,

        "referral_processed":
            False,

        "referral_joined_at":
            None,

        # ----------------------------------------------------
        # STREAK
        #
        # IMPORTANT:
        # Reset starts at ZERO.
        # It does NOT award a streak for merely creating
        # or logging into the demo account.
        # ----------------------------------------------------

        "streak_days":
            0,

        "last_game_date":
            None,

        "last_game_at":
            None,

        "streak_month":
            None,

        "streak_month_best":
            0,

        "games_played_count":
            0,

        # ----------------------------------------------------
        # DATES
        # ----------------------------------------------------

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
