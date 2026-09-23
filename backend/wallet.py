import io
import os
import requests

from flask import (
    Blueprint,
    jsonify,
    request,
    send_file
) 
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import validate_telegram_init_data
from backend.notifications import create_notification
from backend.admin import (
    require_admin as admin_require_admin
)


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

    try:

        snap = (
            user_ref(
                user["telegram_id"]
            ).get()
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
            "error":
                "Unauthorized Telegram session."
        }), 401

    telegram_id = str(
        user["telegram_id"]
    )

    try:

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

        results = []

        for doc in docs:

            data = serialize_doc(doc)

            # ------------------------------------------------
            # NORMALIZE AMOUNT
            # ------------------------------------------------

            try:
                data["amount"] = float(
                    data.get(
                        "amount",
                        0
                    ) or 0
                )
            except (
                TypeError,
                ValueError
            ):
                data["amount"] = 0

            # ------------------------------------------------
            # NORMALIZE CURRENCY
            # ------------------------------------------------

            currency = str(
                data.get(
                    "currency",
                    ""
                )
                or ""
            )

            if currency == "quizbee_points":
                data["currency"] = "Points"

            elif currency.upper() in [
                "USD",
                "$"
            ]:
                data["currency"] = "USD"

            # ------------------------------------------------
            # NORMALIZE DIRECTION
            # ------------------------------------------------

            if (
                data.get("direction")
                not in [
                    "credit",
                    "debit"
                ]
            ):

                amount = data["amount"]

                data["direction"] = (
                    "credit"
                    if amount >= 0
                    else "debit"
                )

            # ------------------------------------------------
            # DISPLAY AMOUNT
            # ------------------------------------------------

            if data["direction"] == "debit":
                data["display_amount"] = -abs(
                    data["amount"]
                )
            else:
                data["display_amount"] = abs(
                    data["amount"]
                )

            results.append(data)

        # ----------------------------------------------------
        # LOCAL SORT
        # ----------------------------------------------------

        results.sort(
            key=lambda item:
                item.get(
                    "created_at",
                    ""
                ) or "",
            reverse=True
        )

        return jsonify({
            "success":
                True,

            "transactions":
                results[:150]
        })

    except Exception as exc:

        print(
            "Wallet transactions error:",
            repr(exc)
        )

        return jsonify({
            "success":
                False,

            "error":
                "Unable to load transaction history."
        }), 500


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
                "points": 500,
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
            "provider": "quizbee_funding_bot" 
        },
        "crypto_manual": {
        "amount": 1,
        "currency": "USD",
        "points": 500,
        "provider": "quizbee_funding_bot"
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
            "error":
                "Withdrawal amount must be greater than $0."
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
            "error":
                "Select a valid withdrawal method."
        }), 400

    telegram_id = user["telegram_id"]

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
                "error":
                    "Enter your bank name."
            }), 400

        if not account_number:
            return jsonify({
                "success": False,
                "error":
                    "Enter your account number."
            }), 400

        if not account_name:
            return jsonify({
                "success": False,
                "error":
                    "Enter your account name."
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
                "error":
                    "Enter your USDT BEP20 wallet address."
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

    withdrawal_id = withdrawal_ref.id

    transaction_ref = (
        db.collection(
            "transactions"
        )
        .document(
            f"withdrawal_{withdrawal_id}"
        )
    )

    user_document = user_ref(
        telegram_id
    )

    firestore_transaction = db.transaction()

    @firestore.transactional
    def create_withdrawal_transaction(tx):

        user_snapshot = user_document.get(
            transaction=tx
        )

        if not user_snapshot.exists:
            raise ValueError(
                "User account not found."
            )

        user_data = (
            user_snapshot.to_dict()
            or {}
        )

        try:
            current_balance = Decimal(
                str(
                    user_data.get(
                        "prize_balance",
                        0
                    )
                )
            )
        except Exception:
            current_balance = Decimal("0")

        if amount > current_balance:
            raise ValueError(
                "You cannot withdraw more "
                "than your available Prize Balance."
            )

        withdrawal_data = {
            "telegram_id":
                telegram_id,

            "amount":
                float(amount),

            "currency":
                "USD",

            "method":
                method,

            "network":
                network,

            "destination":
                destination,

            "account_name":
                account_name,

            "bank_name":
                bank_name,

            "account_number":
                (
                    account_number
                    if method == "nigerian_bank"
                    else ""
                ),

            "status":
                "pending",

            "created_at":
                firestore.SERVER_TIMESTAMP,

            "updated_at":
                firestore.SERVER_TIMESTAMP,

            "approved_at":
                None,

            "paid_at":
                None,

            "rejected_at":
                None,

            "admin_note":
                "",

            "payment_reference":
                None
        }

        tx.set(
            withdrawal_ref,
            withdrawal_data
        )

        tx.update(
            user_document,
            {
                "prize_balance":
                    firestore.Increment(
                        -float(amount)
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
                    "withdrawal",

                "amount":
                    -float(amount),

                "currency":
                    "USD",

                "balance_type":
                    "prize_balance",

                "status":
                    "pending",

                "provider":
                    method,

                "provider_reference":
                    withdrawal_id,

                "withdrawal_id":
                    withdrawal_id,

                "description":
                    (
                        f"Prize withdrawal request: "
                        f"${amount:.2f}"
                    ),

                "created_at":
                    firestore.SERVER_TIMESTAMP,

                "updated_at":
                    firestore.SERVER_TIMESTAMP
            }
        )

        return True

    try:

        create_withdrawal_transaction(
            firestore_transaction
        )

    except ValueError as exc:

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400

    except Exception as exc:

        print(
            "Withdrawal transaction error:",
            repr(exc)
        )

        return jsonify({
            "success": False,
            "error":
                "Unable to submit withdrawal."
        }), 500

    create_notification(
        user_id=telegram_id,

        title="💸 Withdrawal Submitted",

        message=(
            f"Your withdrawal request for "
            f"${float(amount):.2f} has been submitted "
            f"and is pending review."
        ),

        notification_type="general",

        action_url="",

        button_text="",

        dedupe_key=(
            f"withdrawal-submitted:"
            f"{withdrawal_id}"
        ),

        send_telegram=True
    )

    return jsonify({
        "success": True,

        "withdrawal": {
            "id":
                withdrawal_id,

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

def require_admin():

    admin, error = admin_require_admin()

    if error == "FORBIDDEN":

        return "FORBIDDEN"

    if error:

        return None

    return admin


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

    try:

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

        # ----------------------------------------------------
        # Do NOT use Firestore order_by here.
        #
        # Filtering by status + ordering by created_at
        # can require a composite Firestore index.
        # We sort locally instead.
        # ----------------------------------------------------

        docs = list(
            query
            .limit(100)
            .stream()
        )

        results = [
            serialize_doc(doc)
            for doc in docs
        ]

        results.sort(
            key=lambda item:
                item.get(
                    "created_at",
                    ""
                ) or "",
            reverse=True
        )

        return jsonify({
            "success": True,
            "withdrawals": results
        })

    except Exception as e:

        print(
            "Admin withdrawals error:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error":
                "Unable to load withdrawals."
        }), 500


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
            "error":
                "Unauthorized Telegram session."
        }), 401

    withdrawal_ref = (
        db.collection(
            "withdrawals"
        )
        .document(
            withdrawal_id
        )
    )

    firestore_transaction = db.transaction()

    @firestore.transactional
    def approve_transaction(tx):

        snapshot = withdrawal_ref.get(
            transaction=tx
        )

        if not snapshot.exists:
            raise ValueError(
                "Withdrawal not found."
            )

        data = (
            snapshot.to_dict()
            or {}
        )

        if data.get("status") != "pending":
            raise ValueError(
                "Only pending withdrawals "
                "can be approved."
            )

        tx.update(
            withdrawal_ref,
            {
                "status":
                    "approved",

                "approved_at":
                    firestore.SERVER_TIMESTAMP,

                "updated_at":
                    firestore.SERVER_TIMESTAMP
            }
        )

        return {
            "telegram_id":
                str(
                    data.get(
                        "telegram_id",
                        ""
                    )
                ),

            "amount":
                float(
                    data.get(
                        "amount",
                        0
                    )
                )
        }

    try:

        result = approve_transaction(
            firestore_transaction
        )

    except ValueError as exc:

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400

    except Exception as exc:

        print(
            "Withdrawal approval transaction error:",
            repr(exc)
        )

        return jsonify({
            "success": False,
            "error":
                "Unable to approve withdrawal."
        }), 500

    create_notification(
        user_id=result["telegram_id"],

        title="✅ Withdrawal Approved",

        message=(
            f"Your withdrawal of "
            f"${result['amount']:.2f} "
            "has been approved and is now "
            "ready for payment."
        ),

        notification_type="general",

        action_url="",

        button_text="",

        dedupe_key=(
            f"withdrawal-approved:"
            f"{withdrawal_id}"
        ),

        send_telegram=True
    )

    return jsonify({
        "success": True,
        "message":
            "Withdrawal approved."
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
            "error":
                "Unauthorized Telegram session."
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

    withdrawal_ref = (
        db.collection(
            "withdrawals"
        )
        .document(
            withdrawal_id
        )
    )

    refund_transaction_ref = (
        db.collection(
            "transactions"
        )
        .document(
            f"withdrawal_refund_{withdrawal_id}"
        )
    )

    firestore_transaction = db.transaction()

    @firestore.transactional
    def reject_transaction(tx):

        snapshot = withdrawal_ref.get(
            transaction=tx
        )

        if not snapshot.exists:
            raise ValueError(
                "Withdrawal not found."
            )

        data = (
            snapshot.to_dict()
            or {}
        )

        if data.get("status") != "pending":
            raise ValueError(
                "Only pending withdrawals "
                "can be rejected."
            )

        telegram_id = str(
            data.get(
                "telegram_id",
                ""
            )
        ).strip()

        if not telegram_id:
            raise ValueError(
                "Withdrawal has no Telegram user."
            )

        amount = float(
            data.get(
                "amount",
                0
            )
        )

        if amount <= 0:
            raise ValueError(
                "Invalid withdrawal amount."
            )

        user_reference = user_ref(
            telegram_id
        )

        user_snapshot = user_reference.get(
            transaction=tx
        )

        if not user_snapshot.exists:
            raise ValueError(
                "User account not found."
            )

        refund_snapshot = (
            refund_transaction_ref.get(
                transaction=tx
            )
        )

        if refund_snapshot.exists:
            raise ValueError(
                "This withdrawal has already been refunded."
            )

        tx.update(
            withdrawal_ref,
            {
                "status":
                    "rejected",

                "rejected_at":
                    firestore.SERVER_TIMESTAMP,

                "updated_at":
                    firestore.SERVER_TIMESTAMP,

                "admin_note":
                    note
            }
        )

        tx.update(
            user_reference,
            {
                "prize_balance":
                    firestore.Increment(
                        amount
                    ),

                "updated_at":
                    firestore.SERVER_TIMESTAMP
            }
        )

        tx.set(
            refund_transaction_ref,
            {
                "telegram_id":
                    telegram_id,

                "type":
                    "withdrawal_refund",

                "amount":
                    amount,

                "currency":
                    "USD",

                "balance_type":
                    "prize_balance",

                "status":
                    "completed",

                "provider":
                    "internal",

                "provider_reference":
                    withdrawal_id,

                "withdrawal_id":
                    withdrawal_id,

                "description":
                    (
                        f"Refund for rejected "
                        f"withdrawal ${amount:.2f}"
                    ),

                "created_at":
                    firestore.SERVER_TIMESTAMP,

                "updated_at":
                    firestore.SERVER_TIMESTAMP
            }
        )

        return {
            "telegram_id":
                telegram_id,

            "amount":
                amount
        }

    try:

        result = reject_transaction(
            firestore_transaction
        )

    except ValueError as exc:

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400

    except Exception as exc:

        print(
            "Withdrawal rejection transaction error:",
            repr(exc)
        )

        return jsonify({
            "success": False,
            "error":
                "Unable to reject withdrawal."
        }), 500

    telegram_id = result["telegram_id"]
    amount = result["amount"]

    create_notification(
        user_id=telegram_id,

        title="❌ Withdrawal Rejected",

        message=(
            f"Your withdrawal of "
            f"${amount:.2f} was rejected. "
            f"The amount has been returned to "
            f"your Prize Balance."
            + (
                f"\n\nAdmin note: {note}"
                if note
                else ""
            )
        ),

        notification_type="warning",

        action_url="",

        button_text="",

        dedupe_key=(
            f"withdrawal-rejected:"
            f"{withdrawal_id}"
        ),

        send_telegram=True
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
            "error":
                "Unauthorized Telegram session."
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
            "error":
                "Enter the payment reference "
                "before marking as paid."
        }), 400

    withdrawal_ref = (
        db.collection(
            "withdrawals"
        )
        .document(
            withdrawal_id
        )
    )

    firestore_transaction = db.transaction()

    @firestore.transactional
    def mark_paid_transaction(tx):

        snapshot = withdrawal_ref.get(
            transaction=tx
        )

        if not snapshot.exists:
            raise ValueError(
                "Withdrawal not found."
            )

        data = (
            snapshot.to_dict()
            or {}
        )

        if data.get("status") not in [
            "approved",
            "processing"
        ]:
            if data.get("status") == "paid":
                raise ValueError(
                    "This withdrawal has already been marked as paid."
                )

            raise ValueError(
                "Withdrawal must be approved "
                "before it can be marked paid."
            )

        tx.update(
            withdrawal_ref,
            {
                "status":
                    "paid",

                "paid_at":
                    firestore.SERVER_TIMESTAMP,

                "updated_at":
                    firestore.SERVER_TIMESTAMP,

                "payment_reference":
                    payment_reference,

                "admin_note":
                    admin_note
            }
        )

        return {
            "telegram_id":
                str(
                    data.get(
                        "telegram_id",
                        ""
                    )
                ),

            "amount":
                float(
                    data.get(
                        "amount",
                        0
                    )
                )
        }

    try:

        result = mark_paid_transaction(
            firestore_transaction
        )

    except ValueError as exc:

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400

    except Exception as exc:

        print(
            "Mark withdrawal paid transaction error:",
            repr(exc)
        )

        return jsonify({
            "success": False,
            "error":
                "Unable to mark withdrawal as paid."
        }), 500

    # Update original withdrawal transaction.
    try:

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
                "status":
                    "completed",

                "updated_at":
                    now(),

                "payment_reference":
                    payment_reference
            })

    except Exception as exc:

        print(
            "Withdrawal transaction status update error:",
            repr(exc)
        )

    create_notification(
        user_id=result["telegram_id"],

        title="💸 Withdrawal Paid",

        message=(
            f"Your withdrawal of "
            f"${result['amount']:.2f} "
            "has been marked as paid."
        ),

        notification_type="wallet",

        action_url="",

        button_text="",

        dedupe_key=(
            f"withdrawal-paid:"
            f"{withdrawal_id}"
        ),

        send_telegram=True
    )

    return jsonify({
        "success": True,
        "message":
            "Withdrawal marked as paid."
    })


# ============================================================
# ADMIN: VIEW POINT PURCHASE RECEIPT
# ============================================================

@wallet_bp.get(
    "/admin/point-orders/<order_id>/receipt"
)
def point_order_receipt(
    order_id
):

    admin = require_admin()

    if admin == "FORBIDDEN":

        return jsonify({
            "success": False,
            "error":
                "Admin access required."
        }), 403

    if not admin:

        return jsonify({
            "success": False,
            "error":
                "Unauthorized Telegram session."
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
            "error":
                "Point order not found."
        }), 404

    order = (
        snap.to_dict()
        or {}
    )

    file_id = order.get(
        "receipt_file_id"
    )

    if not file_id:

        return jsonify({
            "success": False,
            "error":
                "No receipt attached."
        }), 404

    token = os.getenv(
        "FUNDING_BOT_TOKEN",
        ""
    ).strip()

    if not token:

        return jsonify({
            "success": False,
            "error":
                "Funding bot token is not configured."
        }), 500

    try:

        get_file_response = requests.get(
            "https://api.telegram.org/bot"
            f"{token}/getFile",
            params={
                "file_id":
                    file_id
            },
            timeout=20
        )

        get_file_response.raise_for_status()

        file_data = (
            get_file_response
            .json()
        )

        if not file_data.get(
            "ok"
        ):

            return jsonify({
                "success": False,
                "error":
                    "Unable to retrieve receipt."
            }), 502

        file_path = (
            file_data
            .get("result", {})
            .get("file_path")
        )

        if not file_path:

            return jsonify({
                "success": False,
                "error":
                    "Receipt file path unavailable."
            }), 502

        download_url = (
            "https://api.telegram.org/file/bot"
            f"{token}/{file_path}"
        )

        file_response = requests.get(
            download_url,
            timeout=30
        )

        file_response.raise_for_status()

        content_type = (
            file_response
            .headers
            .get(
                "Content-Type",
                "application/octet-stream"
            )
        )

        return send_file(
            io.BytesIO(
                file_response.content
            ),
            mimetype=content_type,
            as_attachment=False
        )

    except Exception as e:

        return jsonify({
            "success": False,
            "error":
                f"Unable to load receipt: {e}"
        }), 500


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

    try:

        query = (
            db.collection(
                "point_orders"
            )
        )

        if status:
            query = query.where(
                "status",
                "==",
                status
            )

        # ----------------------------------------------------
        # Do NOT use Firestore order_by here.
        #
        # The status filter + created_at ordering can require
        # a composite Firestore index.
        # Sort the returned documents locally instead.
        # ----------------------------------------------------

        docs = list(
            query
            .limit(100)
            .stream()
        )

        results = [
            serialize_doc(doc)
            for doc in docs
        ]

        results.sort(
            key=lambda item:
                item.get(
                    "created_at",
                    ""
                ) or "",
            reverse=True
        )

        return jsonify({
            "success": True,
            "orders": results
        })

    except Exception as e:

        print(
            "Admin point orders error:",
            repr(e)
        )

        return jsonify({
            "success": False,
            "error":
                "Unable to load point purchases."
        }), 500


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

    order_ref = (
        db.collection(
            "point_orders"
        )
        .document(
            order_id
        )
    )

    credit_transaction_ref = (
        db.collection(
            "transactions"
        )
        .document(
            f"point_purchase_credit_{order_id}"
        )
    )

    firestore_transaction = db.transaction()

    @firestore.transactional
    def approve_transaction(tx):

        order_snapshot = order_ref.get(
            transaction=tx
        )

        if not order_snapshot.exists:
            raise ValueError(
                "Point order not found."
            )

        order = (
            order_snapshot.to_dict()
            or {}
        )

        # ----------------------------------------------------
        # IDEMPOTENCY
        #
        # Only a PENDING order can be approved.
        # This prevents a second approval from crediting
        # the same purchase again.
        # ----------------------------------------------------

        if order.get("status") != "pending":
            raise ValueError(
                "This order has already been processed."
            )

        telegram_id = str(
            order.get(
                "telegram_id",
                ""
            )
        ).strip()

        if not telegram_id:
            raise ValueError(
                "Point order has no Telegram user."
            )

        points = safe_int(
            order.get(
                "points",
                0
            )
        )

        if points <= 0:
            raise ValueError(
                "Invalid point amount."
            )

        user_reference = user_ref(
            telegram_id
        )

        user_snapshot = user_reference.get(
            transaction=tx
        )

        if not user_snapshot.exists:
            raise ValueError(
                "User account not found."
            )

        # ----------------------------------------------------
        # PERMANENT CREDIT MARKER
        #
        # If this document already exists, this purchase
        # has already been credited.
        # ----------------------------------------------------

        credit_snapshot = (
            credit_transaction_ref.get(
                transaction=tx
            )
        )

        if credit_snapshot.exists:
            raise ValueError(
                "This purchase has already been credited."
            )

        # ----------------------------------------------------
        # CREDIT POINTS + CLOSE ORDER + CREATE CREDIT
        # IN ONE FIRESTORE TRANSACTION
        # ----------------------------------------------------

        tx.update(
            user_reference,
            {
                "quizbee_points":
                    firestore.Increment(
                        points
                    ),

                "updated_at":
                    firestore.SERVER_TIMESTAMP
            }
        )

        tx.update(
            order_ref,
            {
                "status":
                    "paid",

                "paid_at":
                    firestore.SERVER_TIMESTAMP,

                "approved_at":
                    firestore.SERVER_TIMESTAMP,

                "updated_at":
                    firestore.SERVER_TIMESTAMP
            }
        )

        tx.set(
            credit_transaction_ref,
            {
                "telegram_id":
                    telegram_id,

                "type":
                    "point_purchase_credit",

                "direction":
                     "credit",

                "amount":
                    points,

                "currency":
                    "quizbee_points",

                "balance_type":
                    "quizbee_points",

                "status":
                    "completed",

                "provider":
                    order.get(
                        "provider",
                        "manual"
                    ),

                "provider_reference":
                    order_id,

                "description":
                    (
                        f"Approved purchase: "
                        f"{points} QuizBee Points"
                    ),

                "order_id":
                    order_id,

                "created_at":
                    firestore.SERVER_TIMESTAMP,

                "updated_at":
                    firestore.SERVER_TIMESTAMP
            }
        )

        return {
            "telegram_id":
                telegram_id,

            "points":
                points
        }

    try:

        result = approve_transaction(
            firestore_transaction
        )

    except ValueError as exc:

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 400

    except Exception as exc:

        print(
            "Point purchase approval transaction error:",
            repr(exc)
        )

        return jsonify({
            "success": False,
            "error":
                "Unable to approve point purchase."
        }), 500

    telegram_id = result["telegram_id"]
    points = result["points"]

    # --------------------------------------------------------
    # UPDATE THE ORIGINAL PENDING TRANSACTION
    # --------------------------------------------------------

    try:

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
                "status":
                    "completed",

                "updated_at":
                    now()
            })

    except Exception as exc:

        print(
            "Pending point purchase transaction update error:",
            repr(exc)
        )

    # --------------------------------------------------------
    # NOTIFICATION
    # --------------------------------------------------------

    create_notification(
        user_id=telegram_id,

        title="💰 Points Added!",

        message=(
            f"Your payment has been approved.\n\n"
            f"🪙 {points:,} QuizBee Points "
            f"have been added to your wallet."
        ),

        notification_type="wallet",

        action_url="",

        button_text="",

        dedupe_key=(
            f"point-purchase-approved:"
            f"{order_id}"
        ),

        send_telegram=True
    )

    return jsonify({
        "success": True,

        "points_added":
            points,

        "message":
            (
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

    telegram_id = str(
        order.get(
            "telegram_id",
            ""
        )
    )

    create_notification(
        user_id=telegram_id,
        title="❌ Payment Rejected",
        message=(
            "Your QuizBee funding request "
            "was rejected."
            + (
                f"\n\nAdmin note: {note}"
                if note
                else ""
            )
        ),
        notification_type="warning",
        action_url="",
        button_text="",
        dedupe_key=(
            f"point-purchase-rejected:"
            f"{order_id}"
        ),
        send_telegram=True
    )

    return jsonify({
        "success": True,
        "message": "Point purchase rejected."
    })
