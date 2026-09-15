import os
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import validate_telegram_init_data


raffle_bp = Blueprint(
    "raffle",
    __name__,
    url_prefix="/api/raffles"
)


# ============================================================
# CONSTANTS
# ============================================================

TICKET_PRICE = 100

DEFAULT_RAFFLE_ENABLED = False

RAFFLE_COLLECTION = "raffles"


# ============================================================
# TIME
# ============================================================

def now():
    return datetime.now(timezone.utc)


# ============================================================
# SERIALIZATION
# ============================================================

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
# RAFFLE ENABLED
# ============================================================

def raffle_is_enabled():

    ref = (
        db.collection("settings")
        .document("general")
    )

    snap = ref.get()

    if not snap.exists:
        return DEFAULT_RAFFLE_ENABLED

    data = snap.to_dict() or {}

    return bool(
        data.get(
            "raffle_enabled",
            DEFAULT_RAFFLE_ENABLED
        )
    )


# ============================================================
# TELEGRAM USER AUTH
# ============================================================

def get_authenticated_user():

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
        "telegram_id":
            str(user["id"]),

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


def require_user():

    user = get_authenticated_user()

    if not user:
        return None

    try:

        ref = (
            db.collection("users")
            .document(
                user["telegram_id"]
            )
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

        return None

    return user


# ============================================================
# USER REF
# ============================================================

def user_ref(telegram_id):

    return (
        db.collection("users")
        .document(
            str(telegram_id)
        )
    )


# ============================================================
# RAFFLE REF
# ============================================================

def raffle_ref(raffle_id):

    return (
        db.collection(
            RAFFLE_COLLECTION
        )
        .document(
            str(raffle_id)
        )
    )


# ============================================================
# RAFFLE STATUS
# ============================================================

def get_raffle_status(data):

    start_at = data.get(
        "start_at"
    )

    end_at = data.get(
        "end_at"
    )

    current = now()

    if not start_at or not end_at:
        return "invalid"

    if current < start_at:
        return "scheduled"

    if current >= end_at:
        return "ended"

    return "live"


# ============================================================
# PUBLIC RAFFLE DATA
# ============================================================

def public_raffle_data(
    raffle_id,
    data
):

    result = dict(data)

    result["raffle_id"] = raffle_id

    result["status"] = get_raffle_status(
        data
    )

    result["ticket_price"] = TICKET_PRICE

    result.pop(
        "ticket_counter",
        None
    )

    return serialize_value(
        result
    )


# ============================================================
# CURRENT RAFFLE
# ============================================================

@raffle_bp.get("/current")
def current_raffle():

    try:

        if not raffle_is_enabled():

            return jsonify({
                "success": True,
                "enabled": False,
                "raffle": None
            })

        docs = list(
            db.collection(
                RAFFLE_COLLECTION
            )
            .order_by(
                "start_at",
                direction=firestore.Query.DESCENDING
            )
            .limit(10)
            .stream()
        )

        current = None

        for doc in docs:

            data = doc.to_dict() or {}

            status = get_raffle_status(
                data
            )

            if status in (
                "live",
                "scheduled"
            ):

                current = (
                    doc.id,
                    data
                )

                break

        if not current:

            return jsonify({
                "success": True,
                "enabled": True,
                "raffle": None
            })

        raffle_id, data = current

        return jsonify({

            "success": True,

            "enabled": True,

            "raffle":
                public_raffle_data(
                    raffle_id,
                    data
                )

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# USER TICKETS
# ============================================================

@raffle_bp.get(
    "/<raffle_id>/my-tickets"
)
def my_tickets(raffle_id):

    user = require_user()

    if not user:

        return jsonify({
            "success": False,
            "error":
                "Unauthorized Telegram session."
        }), 401

    try:

        raffle = raffle_ref(
            raffle_id
        ).get()

        if not raffle.exists:

            return jsonify({
                "success": False,
                "error":
                    "Raffle not found."
            }), 404

        docs = (
            raffle_ref(
                raffle_id
            )
            .collection("tickets")
            .where(
                "telegram_id",
                "==",
                user["telegram_id"]
            )
            .order_by(
                "created_at",
                direction=firestore.Query.ASCENDING
            )
            .stream()
        )

        tickets = []

        for doc in docs:

            data = doc.to_dict() or {}

            data["ticket_id"] = doc.id

            tickets.append(
                serialize_value(data)
            )

        return jsonify({

            "success": True,

            "raffle_id":
                raffle_id,

            "ticket_count":
                len(tickets),

            "tickets":
                tickets

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# BUY TICKETS
# ============================================================

@raffle_bp.post(
    "/<raffle_id>/tickets"
)
def buy_tickets(raffle_id):

    user = require_user()

    if not user:

        return jsonify({
            "success": False,
            "error":
                "Unauthorized Telegram session."
        }), 401

    if not raffle_is_enabled():

        return jsonify({
            "success": False,
            "error":
                "Raffle Draw is currently unavailable.",
            "code":
                "RAFFLE_DISABLED"
        }), 403

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )

    raw_quantity = body.get(
        "quantity"
    )

    try:

        quantity = int(
            raw_quantity
        )

    except (
        TypeError,
        ValueError
    ):

        return jsonify({
            "success": False,
            "error":
                "Invalid ticket quantity."
        }), 400

    if quantity < 1:

        return jsonify({
            "success": False,
            "error":
                "You must buy at least one ticket."
        }), 400

    if quantity > 100:

        return jsonify({
            "success": False,
            "error":
                "You can buy a maximum of 100 tickets at once."
        }), 400

    purchase_id = str(
        body.get(
            "purchase_id",
            ""
        )
    ).strip()

    if not purchase_id:

        return jsonify({
            "success": False,
            "error":
                "Purchase ID is required."
        }), 400

    telegram_id = user[
        "telegram_id"
    ]

    raffle_reference = raffle_ref(
        raffle_id
    )

    user_reference = user_ref(
        telegram_id
    )

    purchase_reference = (
        raffle_reference
        .collection("purchases")
        .document(purchase_id)
    )

    try:

        @firestore.transactional
        def process_purchase(transaction):

            raffle_snapshot = (
                raffle_reference.get(
                    transaction=transaction
                )
            )

            if not raffle_snapshot.exists:

                raise ValueError(
                    "RAFFLE_NOT_FOUND"
                )

            raffle_data = (
                raffle_snapshot.to_dict()
                or {}
            )

            status = get_raffle_status(
                raffle_data
            )

            if status != "live":

                if status == "scheduled":

                    raise ValueError(
                        "RAFFLE_NOT_STARTED"
                    )

                if status == "ended":

                    raise ValueError(
                        "RAFFLE_ENDED"
                    )

                raise ValueError(
                    "RAFFLE_INVALID"
                )

            # ----------------------------------------------
            # IDEMPOTENCY
            # ----------------------------------------------

            existing_purchase = (
                purchase_reference.get(
                    transaction=transaction
                )
            )

            if existing_purchase.exists:

                return {
                    "duplicate": True,
                    "purchase":
                        existing_purchase.to_dict()
                        or {}
                }

            # ----------------------------------------------
            # USER
            # ----------------------------------------------

            user_snapshot = (
                user_reference.get(
                    transaction=transaction
                )
            )

            if not user_snapshot.exists:

                raise ValueError(
                    "USER_NOT_FOUND"
                )

            user_data = (
                user_snapshot.to_dict()
                or {}
            )

            current_points = int(
                user_data.get(
                    "quizbee_points",
                    0
                )
                or 0
            )

            total_cost = (
                quantity
                * TICKET_PRICE
            )

            if current_points < total_cost:

                raise ValueError(
                    "INSUFFICIENT_POINTS"
                )

            # ----------------------------------------------
            # TICKET COUNTER
            # ----------------------------------------------

            current_counter = int(
                raffle_data.get(
                    "ticket_counter",
                    0
                )
                or 0
            )

            first_ticket_number = (
                current_counter + 1
            )

            last_ticket_number = (
                current_counter
                + quantity
            )

            # ----------------------------------------------
            # UPDATE COUNTER
            # ----------------------------------------------

            transaction.update(
                raffle_reference,
                {
                    "ticket_counter":
                        last_ticket_number,

                    "updated_at":
                        now()
                }
            )

            # ----------------------------------------------
            # DEDUCT POINTS
            # ----------------------------------------------

            transaction.update(
                user_reference,
                {
                    "quizbee_points":
                        firestore.Increment(
                            -total_cost
                        ),

                    "total_spent":
                        firestore.Increment(
                            total_cost
                        ),

                    "updated_at":
                        now()
                }
            )

            # ----------------------------------------------
            # CREATE TICKETS
            # ----------------------------------------------

            created_tickets = []

            for number in range(
                first_ticket_number,
                last_ticket_number + 1
            ):

                ticket_id = (
                    f"QB-RF-{number:06d}"
                )

                ticket_reference = (
                    raffle_reference
                    .collection("tickets")
                    .document(ticket_id)
                )

                ticket_data = {

                    "ticket_id":
                        ticket_id,

                    "raffle_id":
                        raffle_id,

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
                        ),

                    "ticket_price":
                        TICKET_PRICE,

                    "status":
                        "active",

                    "purchase_id":
                        purchase_id,

                    "created_at":
                        now()

                }

                transaction.set(
                    ticket_reference,
                    ticket_data
                )

                created_tickets.append(
                    ticket_id
                )

            # ----------------------------------------------
            # PURCHASE RECORD
            # ----------------------------------------------

            purchase_data = {

                "purchase_id":
                    purchase_id,

                "raffle_id":
                    raffle_id,

                "telegram_id":
                    telegram_id,

                "quantity":
                    quantity,

                "ticket_price":
                    TICKET_PRICE,

                "total_cost":
                    total_cost,

                "first_ticket":
                    created_tickets[0],

                "last_ticket":
                    created_tickets[-1],

                "created_at":
                    now()

            }

            transaction.set(
                purchase_reference,
                purchase_data
            )

            return {
                "duplicate": False,
                "purchase":
                    purchase_data,

                "tickets":
                    created_tickets,

                "remaining_points":
                    current_points
                    - total_cost
            }

        transaction = db.transaction()

        result = process_purchase(
            transaction
        )

        if result.get(
            "duplicate"
        ):

            return jsonify({

                "success": True,

                "duplicate": True,

                "purchase":
                    serialize_value(
                        result["purchase"]
                    ),

                "message":
                    "This purchase was already processed."

            })

        return jsonify({

            "success": True,

            "duplicate": False,

            "raffle_id":
                raffle_id,

            "quantity":
                quantity,

            "ticket_price":
                TICKET_PRICE,

            "total_cost":
                quantity
                * TICKET_PRICE,

            "tickets":
                result["tickets"],

            "remaining_points":
                result[
                    "remaining_points"
                ],

            "message":
                "Tickets purchased successfully."

        })

    except ValueError as e:

        code = str(e)

        errors = {

            "RAFFLE_NOT_FOUND":
                (
                    "Raffle not found.",
                    404
                ),

            "RAFFLE_NOT_STARTED":
                (
                    "This raffle has not started yet.",
                    403
                ),

            "RAFFLE_ENDED":
                (
                    "This raffle has ended.",
                    403
                ),

            "RAFFLE_INVALID":
                (
                    "This raffle is invalid.",
                    400
                ),

            "USER_NOT_FOUND":
                (
                    "User account not found.",
                    404
                ),

            "INSUFFICIENT_POINTS":
                (
                    "You do not have enough QuizBee Points.",
                    400
                )

        }

        message, status_code = errors.get(
            code,
            (
                "Unable to process ticket purchase.",
                400
            )
        )

        return jsonify({

            "success": False,

            "error":
                message,

            "code":
                code

        }), status_code

    except Exception as e:

        print(
            "Raffle ticket purchase error:",
            repr(e)
        )

        return jsonify({

            "success": False,

            "error":
                "Unable to process ticket purchase.",

            "code":
                "RAFFLE_PURCHASE_ERROR"

        }), 500

# ============================================================
# ADMIN AUTH
# ============================================================

def get_admin_user():
    init_data = request.headers.get(
        "X-Telegram-Init-Data",
        ""
    )

    if not init_data:
        return None, "UNAUTHORIZED"

    admin_bot_token = os.getenv(
        "ADMIN_BOT_TOKEN",
        ""
    ).strip()

    if not admin_bot_token:
        return None, "ADMIN_BOT_TOKEN_MISSING"

    user = validate_telegram_init_data(
        init_data,
        bot_token=admin_bot_token
    )

    if not user:
        return None, "UNAUTHORIZED"

    telegram_id = str(user.get("id"))

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

    if telegram_id not in allowed_ids:
        return None, "FORBIDDEN"

    return user, None


def require_admin():
    admin, error = get_admin_user()

    if error:
        if error == "FORBIDDEN":
            return None, (
                jsonify({
                    "success": False,
                    "error": "Admin access required."
                }),
                403
            )

        return None, (
            jsonify({
                "success": False,
                "error": "Unauthorized admin session."
            }),
            401
        )

    return admin, None


# ============================================================
# ADMIN — CREATE RAFFLE
# ============================================================

@raffle_bp.post("/admin/create")
def admin_create_raffle():

    admin, error = require_admin()

    if error:
        return error

    try:
        body = (
            request.get_json(
                silent=True
            )
            or {}
        )

        raffle_id = str(
            body.get(
                "raffle_id",
                ""
            )
        ).strip()

        prize_name = str(
            body.get(
                "prize_name",
                ""
            )
        ).strip()

        prize_image = str(
            body.get(
                "prize_image",
                ""
            )
        ).strip()

        start_at = str(
            body.get(
                "start_at",
                ""
            )
        ).strip()

        end_at = str(
            body.get(
                "end_at",
                ""
            )
        ).strip()

        if not raffle_id:
            raffle_id = (
                datetime.now(
                    timezone.utc
                ).strftime(
                    "raffle-%Y%m%d-%H%M%S"
                )
            )

        if not prize_name:
            return jsonify({
                "success": False,
                "error":
                    "Prize name is required."
            }), 400

        if not start_at:
            return jsonify({
                "success": False,
                "error":
                    "Start date/time is required."
            }), 400

        if not end_at:
            return jsonify({
                "success": False,
                "error":
                    "End date/time is required."
            }), 400

        try:
            start_datetime = datetime.fromisoformat(
                start_at.replace(
                    "Z",
                    "+00:00"
                )
            )

            end_datetime = datetime.fromisoformat(
                end_at.replace(
                    "Z",
                    "+00:00"
                )
            )

        except ValueError:
            return jsonify({
                "success": False,
                "error":
                    "Invalid date/time format."
            }), 400

        if start_datetime.tzinfo is None:
            start_datetime = start_datetime.replace(
                tzinfo=timezone.utc
            )

        if end_datetime.tzinfo is None:
            end_datetime = end_datetime.replace(
                tzinfo=timezone.utc
            )

        if end_datetime <= start_datetime:
            return jsonify({
                "success": False,
                "error":
                    "End date/time must be after start date/time."
            }), 400

        ref = raffle_ref(
            raffle_id
        )

        if ref.get().exists:
            return jsonify({
                "success": False,
                "error":
                    "A raffle with this ID already exists."
            }), 409

        raffle_data = {
            "raffle_id":
                raffle_id,

            "prize_name":
                prize_name,

            "prize_image":
                prize_image,

            "ticket_price":
                TICKET_PRICE,

            "start_at":
                start_datetime,

            "end_at":
                end_datetime,

            "ticket_counter":
                0,

            "created_at":
                now(),

            "created_by":
                str(admin.get("id")),

            "created_by_username":
                admin.get(
                    "username",
                    ""
                ),

            "enabled":
                True
        }

        ref.set(
            raffle_data
        )

        return jsonify({
            "success": True,
            "message":
                "Raffle created successfully.",
            "raffle":
                public_raffle_data(
                    raffle_data
                )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# ADMIN — GET RAFFLE
# ============================================================

@raffle_bp.get("/admin/<raffle_id>")
def admin_get_raffle(raffle_id):

    admin, error = require_admin()

    if error:
        return error

    try:
        snap = raffle_ref(
            raffle_id
        ).get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "Raffle not found."
            }), 404

        data = snap.to_dict() or {}

        return jsonify({
            "success": True,
            "raffle":
                serialize_value(
                    data
                ),
            "status":
                get_raffle_status(
                    data
                )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# ADMIN — LIST RAFFLES
# ============================================================

@raffle_bp.get("/admin")
def admin_list_raffles():

    admin, error = require_admin()

    if error:
        return error

    try:

        docs = list(
            db.collection(
                RAFFLE_COLLECTION
            )
            .order_by(
                "start_at",
                direction=firestore.Query.DESCENDING
            )
            .limit(50)
            .stream()
        )

        raffles = []

        for doc in docs:

            data = doc.to_dict() or {}

            raffles.append({
                "id":
                    doc.id,

                "raffle":
                    serialize_value(
                        data
                    ),

                "status":
                    get_raffle_status(
                        data
                    )
            })

        return jsonify({
            "success": True,
            "raffles":
                raffles
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# ADMIN — LIST TICKETS
# ============================================================

@raffle_bp.get(
    "/admin/<raffle_id>/tickets"
)
def admin_list_tickets(raffle_id):

    admin, error = require_admin()

    if error:
        return error

    try:

        raffle_snap = raffle_ref(
            raffle_id
        ).get()

        if not raffle_snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "Raffle not found."
            }), 404

        docs = list(
            raffle_ref(
                raffle_id
            )
            .collection(
                "tickets"
            )
            .order_by(
                "ticket_number",
                direction=firestore.Query.ASCENDING
            )
            .stream()
        )

        tickets = []

        for doc in docs:

            data = doc.to_dict() or {}

            data["id"] = doc.id

            tickets.append(
                serialize_value(
                    data
                )
            )

        return jsonify({
            "success": True,

            "raffle_id":
                raffle_id,

            "count":
                len(tickets),

            "tickets":
                tickets,

            "ticket_ids":
                [
                    ticket.get(
                        "ticket_id"
                    )
                    for ticket in tickets
                    if ticket.get(
                        "ticket_id"
                    )
                ]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# ADMIN — SEARCH TICKET
# ============================================================

@raffle_bp.get(
    "/admin/<raffle_id>/tickets/search"
)
def admin_search_ticket(raffle_id):

    admin, error = require_admin()

    if error:
        return error

    try:

        ticket_id = str(
            request.args.get(
                "ticket_id",
                ""
            )
        ).strip()

        if not ticket_id:
            return jsonify({
                "success": False,
                "error":
                    "Ticket ID is required."
            }), 400

        snap = (
            raffle_ref(
                raffle_id
            )
            .collection(
                "tickets"
            )
            .document(
                ticket_id
            )
            .get()
        )

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "Ticket not found."
            }), 404

        ticket = (
            snap.to_dict()
            or {}
        )

        ticket["id"] = snap.id

        return jsonify({
            "success": True,
            "ticket":
                serialize_value(
                    ticket
                )
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# ADMIN — END RAFFLE
# ============================================================

@raffle_bp.post(
    "/admin/<raffle_id>/end"
)
def admin_end_raffle(raffle_id):

    admin, error = require_admin()

    if error:
        return error

    try:

        ref = raffle_ref(
            raffle_id
        )

        snap = ref.get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "Raffle not found."
            }), 404

        data = snap.to_dict() or {}

        end_time = now()

        ref.update({
            "end_at":
                end_time,

            "ended_by":
                str(
                    admin.get(
                        "id"
                    )
                ),

            "ended_at":
                end_time,

            "enabled":
                False
        })

        return jsonify({
            "success": True,
            "message":
                "Raffle ended successfully.",
            "raffle_id":
                raffle_id
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# ADMIN — DELETE RAFFLE
# ============================================================

@raffle_bp.delete(
    "/admin/<raffle_id>"
)
def admin_delete_raffle(raffle_id):

    admin, error = require_admin()

    if error:
        return error

    try:

        ref = raffle_ref(
            raffle_id
        )

        snap = ref.get()

        if not snap.exists:
            return jsonify({
                "success": False,
                "error":
                    "Raffle not found."
            }), 404

        # ----------------------------------------------------
        # DELETE TICKETS
        # ----------------------------------------------------

        ticket_docs = list(
            ref.collection(
                "tickets"
            ).stream()
        )

        for ticket_doc in ticket_docs:
            ticket_doc.reference.delete()

        # ----------------------------------------------------
        # DELETE PURCHASE RECORDS
        # ----------------------------------------------------

        purchase_docs = list(
            ref.collection(
                "purchases"
            ).stream()
        )

        for purchase_doc in purchase_docs:
            purchase_doc.reference.delete()

        # ----------------------------------------------------
        # DELETE RAFFLE
        # ----------------------------------------------------

        ref.delete()

        return jsonify({
            "success": True,

            "message":
                "Raffle and all associated tickets deleted.",

            "raffle_id":
                raffle_id,

            "deleted_tickets":
                len(ticket_docs),

            "deleted_purchases":
                len(purchase_docs)
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
