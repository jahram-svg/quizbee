from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import validate_telegram_init_data


wallet_bp = Blueprint(
    "wallet",
    __name__,
    url_prefix="/api/wallet"
)


# ============================================================
# HELPERS
# ============================================================

def now():
    return datetime.now(timezone.utc)


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


def require_user():
    user = get_authenticated_telegram_user()

    if not user:
        return None

    return user


def user_ref(telegram_id):
    return (
        db.collection("users")
        .document(str(telegram_id))
    )


def get_user(telegram_id):
    ref = user_ref(telegram_id)
    snap = ref.get()

    if not snap.exists:
        return None

    data = snap.to_dict()
    data["telegram_id"] = str(telegram_id)

    return data


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_money(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None

    if amount < 0:
        return None

    return amount.quantize(
        Decimal("0.01")
    )


def transaction(
    telegram_id,
    tx_type,
    amount,
    currency,
    balance_type,
    status="completed",
    provider="internal",
    provider_reference=None,
    description="",
    extra=None
):
    data = {
        "telegram_id": str(telegram_id),
        "type": tx_type,
        "amount": amount,
        "currency": currency,
        "balance_type": balance_type,
        "status": status,
        "provider": provider,
        "provider_reference": (
            provider_reference
        ),
        "description": description,
        "created_at": now(),
        "updated_at": now()
    }

    if extra:
        data.update(extra)

    ref = (
        db.collection("transactions")
        .document()
    )

    ref.set(data)

    return ref.id


def serialize_doc(doc):
    data = doc.to_dict() or {}

    data["id"] = doc.id

    for key, value in list(data.items()):
        if isinstance(value, datetime):
            data[key] = value.isoformat()

    return data


# ============================================================
# WALLET OVERVIEW
# ============================================================

@wallet_bp.get("")
def wallet_overview():

    user = require_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    data = get_user(
        user["telegram_id"]
    )

    if not data:
        return jsonify({
            "success": False,
            "error": "User account not found."
        }), 404

    return jsonify({
        "success": True,
        "wallet": {
            "quizbee_points": safe_int(
                data.get(
                    "quizbee_points",
                    0
                )
            ),
            "prize_balance": float(
                data.get(
                    "prize_balance",
                    0
                )
            )
        }
    })


# ============================================================
# TRANSACTION HISTORY
# ============================================================

@wallet_bp.get("/transactions")
def wallet_transactions():

    user = require_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    telegram_id = user["telegram_id"]

    docs = (
        db.collection("transactions")
        .where(
            "telegram_id",
            "==",
            telegram_id
        )
        .order_by(
            "created_at",
            direction=firestore.Query.DESCENDING
        )
        .limit(100)
        .stream()
    )

    results = [
        serialize_doc(doc)
        for doc in docs
    ]

    return jsonify({
        "success": True,
        "transactions": results
    })


# ============================================================
# POINT PURCHASE OPTIONS
# ============================================================

@wallet_bp.get("/purchase-options")
def purchase_options():

    return jsonify({
        "success": True,
        "options": [
            {
                "id": "nigeria_manual",
                "name": "Nigeria",
                "icon": "🇳🇬",
                "price": 100,
                "currency": "NGN",
                "points": 50,
                "method": "manual"
            },
            {
                "id": "crypto_manual",
                "name": "Crypto",
                "icon": "🌎",
                "price": 1,
                "currency": "USD",
                "points": 1000,
                "method": "manual"
            },
            {
                "id": "telegram_stars",
                "name": "Telegram Stars",
                "icon": "⭐",
                "price": 0,
                "currency": "XTR",
                "points": 0,
                "method": "telegram_stars"
            }
        ]
    })


# ============================================================
# CREATE MANUAL POINT PURCHASE ORDER
# ============================================================

@wallet_bp.post("/point-order")
def create_point_order():

    user = require_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )

    package_id = str(
        body.get(
            "package_id",
            ""
        )
    ).strip()

    packages = {
        "nigeria_manual": {
            "amount": 100,
            "currency": "NGN",
            "points": 50,
            "provider": "manual_paystack"
        },
        "crypto_manual": {
            "amount": 1,
            "currency": "USD",
            "points": 1000,
            "provider": "manual_crypto"
        }
    }

    package = packages.get(
        package_id
    )

    if not package:
        return jsonify({
            "success": False,
            "error": "Invalid purchase option."
        }), 400

    telegram_id = user[
        "telegram_id"
    ]

    order_ref = (
        db.collection(
            "point_orders"
        ).document()
    )

    order_ref.set({
        "telegram_id": telegram_id,
        "package_id": package_id,
        "points": package["points"],
        "amount": package["amount"],
        "currency": package["currency"],
        "provider": package["provider"],
        "provider_reference": None,
        "status": "pending",
        "created_at": now(),
        "updated_at": now(),
        "paid_at": None,
        "approved_at": None,
        "admin_note": ""
    })

    transaction(
        telegram_id=telegram_id,
        tx_type="point_purchase",
        amount=package["points"],
        currency="quizbee_points",
        balance_type="quizbee_points",
        status="pending",
        provider=package["provider"],
        provider_reference=order_ref.id,
        description=(
            f"Pending purchase: "
            f"{package['points']} QuizBee Points"
        ),
        extra={
            "order_id": order_ref.id,
            "purchase_amount": package["amount"],
            "purchase_currency": package["currency"]
        }
    )

    return jsonify({
        "success": True,
        "order": {
            "id": order_ref.id,
            "package_id": package_id,
            "points": package["points"],
            "amount": package["amount"],
            "currency": package["currency"],
            "status": "pending"
        },
        "message": (
            "Purchase request created. "
            "Complete payment and wait for approval."
        )
    })


# ============================================================
# POINT PURCHASE HISTORY
# ============================================================

@wallet_bp.get("/point-orders")
def point_orders():

    user = require_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    docs = (
        db.collection(
            "point_orders"
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

    results = [
        serialize_doc(doc)
        for doc in docs
    ]

    return jsonify({
        "success": True,
        "orders": results
    })


# ============================================================
# WITHDRAWAL
# ============================================================

@wallet_bp.post("/withdraw")
def create_withdrawal():

    user = require_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )

    amount = safe_money(
        body.get("amount")
    )

    if amount is None:
        return jsonify({
            "success": False,
            "error": "Enter a valid withdrawal amount."
        }), 400

    if amount <= 0:
        return jsonify({
            "success": False,
            "error": "Withdrawal amount must be greater than $0."
        }), 400

    method = str(
        body.get(
            "method",
            ""
        )
    ).strip().lower()

    if method not in [
        "nigerian_bank",
        "usdt_bep20"
    ]:
        return jsonify({
            "success": False,
            "error": "Select a valid withdrawal method."
        }), 400

    telegram_id = user[
        "telegram_id"
    ]

    user_document = user_ref(
        telegram_id
    )

    current_user = get_user(
        telegram_id
    )

    if not current_user:
        return jsonify({
            "success": False,
            "error": "User account not found."
        }), 404

    current_balance = Decimal(
        str(
            current_user.get(
                "prize_balance",
                0
            )
        )
    )

    if amount > current_balance:
        return jsonify({
            "success": False,
            "error": (
                "You cannot withdraw more "
                "than your available Prize Balance."
            )
        }), 400

    if method == "nigerian_bank":

        bank_name = str(
            body.get(
                "bank_name",
                ""
            )
        ).strip()

        account_number = str(
            body.get(
                "account_number",
                ""
            )
        ).strip()

        account_name = str(
            body.get(
                "account_name",
                ""
            )
        ).strip()

        if not bank_name:
            return jsonify({
                "success": False,
                "error": "Enter your bank name."
            }), 400

        if not account_number:
            return jsonify({
                "success": False,
                "error": "Enter your account number."
            }), 400

        if not account_name:
            return jsonify({
                "success": False,
                "error": "Enter your account name."
            }), 400

        network = "NGN_BANK"

        destination = account_number

    else:

        wallet_address = str(
            body.get(
                "wallet_address",
                ""
            )
        ).strip()

        if not wallet_address:
            return jsonify({
                "success": False,
                "error": (
                    "Enter your USDT BEP20 wallet address."
                )
            }), 400

        network = "BEP20"

        destination = wallet_address

        bank_name = ""
        account_number = ""
        account_name = ""

    withdrawal_ref = (
        db.collection(
            "withdrawals"
        ).document()
    )

    withdrawal_data = {
        "telegram_id": telegram_id,
        "amount": float(amount),
        "currency": "USD",
        "method": method,
        "network": network,
        "destination": destination,
        "account_name": account_name,
        "bank_name": bank_name,
        "account_number": (
            account_number
            if method == "nigerian_bank"
            else ""
        ),
        "status": "pending",
        "created_at": now(),
        "updated_at": now(),
        "approved_at": None,
        "paid_at": None,
        "rejected_at": None,
        "admin_note": "",
        "payment_reference": None
    }

    withdrawal_ref.set(
        withdrawal_data
    )

    # Reserve the prize money immediately.
    user_document.update({
        "prize_balance":
            firestore.Increment(
                -float(amount)
            ),
        "updated_at":
            now()
    })

    transaction(
        telegram_id=telegram_id,
        tx_type="withdrawal",
        amount=-float(amount),
        currency="USD",
        balance_type="prize_balance",
        status="pending",
        provider=method,
        provider_reference=withdrawal_ref.id,
        description=(
            f"Prize withdrawal request: "
            f"${amount:.2f}"
        ),
        extra={
            "withdrawal_id":
                withdrawal_ref.id
        }
    )

    return jsonify({
        "success": True,
        "withdrawal": {
            "id":
                withdrawal_ref.id,
            "amount":
                float(amount),
            "currency":
                "USD",
            "method":
                method,
            "network":
                network,
            "status":
                "pending"
        },
        "message": (
            "Withdrawal request submitted. "
            "Your prize will be manually reviewed "
            "and paid by QuizBee."
        )
    })


# ============================================================
# WITHDRAWAL HISTORY
# ============================================================

@wallet_bp.get("/withdrawals")
def withdrawals():

    user = require_user()

    if not user:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    docs = (
        db.collection(
            "withdrawals"
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

    results = [
        serialize_doc(doc)
        for doc in docs
    ]

    return jsonify({
        "success": True,
        "withdrawals": results
    })


# ============================================================
# ADMIN AUTH
# ============================================================

def is_admin(telegram_id):

    import os

    admin_id = os.getenv(
        "ADMIN_TELEGRAM_ID",
        ""
    ).strip()

    return (
        admin_id
        and str(telegram_id) == admin_id
    )


def require_admin():

    user = require_user()

    if not user:
        return None

    if not is_admin(
        user["telegram_id"]
    ):
        return "FORBIDDEN"

    return user


# ============================================================
# ADMIN: LIST WITHDRAWALS
# ============================================================

@wallet_bp.get("/admin/withdrawals")
def admin_withdrawals():

    admin = require_admin()

    if admin == "FORBIDDEN":
        return jsonify({
            "success": False,
            "error": "Admin access required."
        }), 403

    if not admin:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    status = request.args.get(
        "status",
        "pending"
    )

    query = (
        db.collection(
            "withdrawals"
        )
    )

    if status:
        query = query.where(
            "status",
            "==",
            status
        )

    docs = (
        query.order_by(
            "created_at",
            direction=firestore.Query.DESCENDING
        )
        .limit(100)
        .stream()
    )

    results = [
        serialize_doc(doc)
        for doc in docs
    ]

    return jsonify({
        "success": True,
        "withdrawals": results
    })


# ============================================================
# ADMIN: APPROVE WITHDRAWAL
# ============================================================

@wallet_bp.post(
    "/admin/withdrawals/<withdrawal_id>/approve"
)
def approve_withdrawal(
    withdrawal_id
):

    admin = require_admin()

    if admin == "FORBIDDEN":
        return jsonify({
            "success": False,
            "error": "Admin access required."
        }), 403

    if not admin:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    ref = (
        db.collection(
            "withdrawals"
        )
        .document(
            withdrawal_id
        )
    )

    snap = ref.get()

    if not snap.exists:
        return jsonify({
            "success": False,
            "error": "Withdrawal not found."
        }), 404

    data = snap.to_dict()

    if data.get("status") != "pending":
        return jsonify({
            "success": False,
            "error": (
                "Only pending withdrawals "
                "can be approved."
            )
        }), 400

    ref.update({
        "status": "approved",
        "approved_at": now(),
        "updated_at": now()
    })

    return jsonify({
        "success": True,
        "message": "Withdrawal approved."
    })


# ============================================================
# ADMIN: REJECT WITHDRAWAL
# ============================================================

@wallet_bp.post(
    "/admin/withdrawals/<withdrawal_id>/reject"
)
def reject_withdrawal(
    withdrawal_id
):

    admin = require_admin()

    if admin == "FORBIDDEN":
        return jsonify({
            "success": False,
            "error": "Admin access required."
        }), 403

    if not admin:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )

    note = str(
        body.get(
            "admin_note",
            ""
        )
    ).strip()

    ref = (
        db.collection(
            "withdrawals"
        )
        .document(
            withdrawal_id
        )
    )

    snap = ref.get()

    if not snap.exists:
        return jsonify({
            "success": False,
            "error": "Withdrawal not found."
        }), 404

    data = snap.to_dict()

    if data.get("status") != "pending":
        return jsonify({
            "success": False,
            "error": (
                "Only pending withdrawals "
                "can be rejected."
            )
        }), 400

    amount = float(
        data.get(
            "amount",
            0
        )
    )

    telegram_id = str(
        data.get(
            "telegram_id"
        )
    )

    ref.update({
        "status": "rejected",
        "rejected_at": now(),
        "updated_at": now(),
        "admin_note": note
    })

    # Return the reserved prize money.
    user_ref(
        telegram_id
    ).update({
        "prize_balance":
            firestore.Increment(
                amount
            ),
        "updated_at":
            now()
    })

    transaction(
        telegram_id=telegram_id,
        tx_type="withdrawal_refund",
        amount=amount,
        currency="USD",
        balance_type="prize_balance",
        status="completed",
        provider="internal",
        provider_reference=withdrawal_id,
        description=(
            f"Refund for rejected "
            f"withdrawal ${amount:.2f}"
        ),
        extra={
            "withdrawal_id":
                withdrawal_id
        }
    )

    return jsonify({
        "success": True,
        "message": (
            "Withdrawal rejected and "
            "Prize Balance restored."
        )
    })


# ============================================================
# ADMIN: MARK WITHDRAWAL PAID
# ============================================================

@wallet_bp.post(
    "/admin/withdrawals/<withdrawal_id>/mark-paid"
)
def mark_withdrawal_paid(
    withdrawal_id
):

    admin = require_admin()

    if admin == "FORBIDDEN":
        return jsonify({
            "success": False,
            "error": "Admin access required."
        }), 403

    if not admin:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )

    payment_reference = str(
        body.get(
            "payment_reference",
            ""
        )
    ).strip()

    admin_note = str(
        body.get(
            "admin_note",
            ""
        )
    ).strip()

    if not payment_reference:
        return jsonify({
            "success": False,
            "error": (
                "Enter the payment reference "
                "before marking as paid."
            )
        }), 400

    ref = (
        db.collection(
            "withdrawals"
        )
        .document(
            withdrawal_id
        )
    )

    snap = ref.get()

    if not snap.exists:
        return jsonify({
            "success": False,
            "error": "Withdrawal not found."
        }), 404

    data = snap.to_dict()

    if data.get("status") not in [
        "approved",
        "processing"
    ]:
        return jsonify({
            "success": False,
            "error": (
                "Withdrawal must be approved "
                "before it can be marked paid."
            )
        }), 400

    ref.update({
        "status": "paid",
        "paid_at": now(),
        "updated_at": now(),
        "payment_reference":
            payment_reference,
        "admin_note":
            admin_note
    })

    # Update the original transaction status.
    tx_query = (
        db.collection(
            "transactions"
        )
        .where(
            "provider_reference",
            "==",
            withdrawal_id
        )
        .where(
            "type",
            "==",
            "withdrawal"
        )
        .limit(1)
    )

    tx_docs = list(
        tx_query.stream()
    )

    for tx_doc in tx_docs:
        tx_doc.reference.update({
            "status": "paid",
            "updated_at": now()
        })

    return jsonify({
        "success": True,
        "message": (
            "Withdrawal marked as paid."
        )
    })


# ============================================================
# ADMIN: POINT PURCHASES
# ============================================================

@wallet_bp.get("/admin/point-orders")
def admin_point_orders():

    admin = require_admin()

    if admin == "FORBIDDEN":
        return jsonify({
            "success": False,
            "error": "Admin access required."
        }), 403

    if not admin:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    status = request.args.get(
        "status",
        "pending"
    )

    docs = (
        db.collection(
            "point_orders"
        )
        .where(
            "status",
            "==",
            status
        )
        .order_by(
            "created_at",
            direction=firestore.Query.DESCENDING
        )
        .limit(100)
        .stream()
    )

    results = [
        serialize_doc(doc)
        for doc in docs
    ]

    return jsonify({
        "success": True,
        "orders": results
    })


# ============================================================
# ADMIN: APPROVE POINT PURCHASE
# ============================================================

@wallet_bp.post(
    "/admin/point-orders/<order_id>/approve"
)
def approve_point_order(
    order_id
):

    admin = require_admin()

    if admin == "FORBIDDEN":
        return jsonify({
            "success": False,
            "error": "Admin access required."
        }), 403

    if not admin:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    ref = (
        db.collection(
            "point_orders"
        )
        .document(
            order_id
        )
    )

    snap = ref.get()

    if not snap.exists:
        return jsonify({
            "success": False,
            "error": "Point order not found."
        }), 404

    order = snap.to_dict()

    if order.get("status") != "pending":
        return jsonify({
            "success": False,
            "error": (
                "This order has already "
                "been processed."
            )
        }), 400

    telegram_id = str(
        order.get(
            "telegram_id"
        )
    )

    points = safe_int(
        order.get(
            "points",
            0
        )
    )

    if points <= 0:
        return jsonify({
            "success": False,
            "error": "Invalid point amount."
        }), 400

    # Credit points.
    user_ref(
        telegram_id
    ).update({
        "quizbee_points":
            firestore.Increment(
                points
            ),
        "updated_at":
            now()
    })

    ref.update({
        "status": "paid",
        "paid_at": now(),
        "approved_at": now(),
        "updated_at": now()
    })

    # Update the pending transaction.
    tx_query = (
        db.collection(
            "transactions"
        )
        .where(
            "provider_reference",
            "==",
            order_id
        )
        .where(
            "type",
            "==",
            "point_purchase"
        )
        .limit(1)
    )

    tx_docs = list(
        tx_query.stream()
    )

    for tx_doc in tx_docs:
        tx_doc.reference.update({
            "status": "completed",
            "updated_at": now()
        })

    transaction(
        telegram_id=telegram_id,
        tx_type="point_purchase_credit",
        amount=points,
        currency="quizbee_points",
        balance_type="quizbee_points",
        status="completed",
        provider=order.get(
            "provider",
            "manual"
        ),
        provider_reference=order_id,
        description=(
            f"Approved purchase: "
            f"{points} QuizBee Points"
        ),
        extra={
            "order_id": order_id
        }
    )

    return jsonify({
        "success": True,
        "points_added": points,
        "message": (
            f"{points} QuizBee Points "
            "added successfully."
        )
    })


# ============================================================
# ADMIN: REJECT POINT PURCHASE
# ============================================================

@wallet_bp.post(
    "/admin/point-orders/<order_id>/reject"
)
def reject_point_order(
    order_id
):

    admin = require_admin()

    if admin == "FORBIDDEN":
        return jsonify({
            "success": False,
            "error": "Admin access required."
        }), 403

    if not admin:
        return jsonify({
            "success": False,
            "error": "Unauthorized Telegram session."
        }), 401

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )

    note = str(
        body.get(
            "admin_note",
            ""
        )
    ).strip()

    ref = (
        db.collection(
            "point_orders"
        )
        .document(
            order_id
        )
    )

    snap = ref.get()

    if not snap.exists:
        return jsonify({
            "success": False,
            "error": "Point order not found."
        }), 404

    order = snap.to_dict()

    if order.get("status") != "pending":
        return jsonify({
            "success": False,
            "error": (
                "This order has already "
                "been processed."
            )
        }), 400

    ref.update({
        "status": "rejected",
        "updated_at": now(),
        "admin_note": note
    })

    tx_query = (
        db.collection(
            "transactions"
        )
        .where(
            "provider_reference",
            "==",
            order_id
        )
        .where(
            "type",
            "==",
            "point_purchase"
        )
        .limit(1)
    )

    tx_docs = list(
        tx_query.stream()
    )

    for tx_doc in tx_docs:
        tx_doc.reference.update({
            "status": "rejected",
            "updated_at": now()
        })

    return jsonify({
        "success": True,
        "message": "Point purchase rejected."
    })
