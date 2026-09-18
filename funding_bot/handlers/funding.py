from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from firebase_admin import firestore

from backend.firebase import db
from backend.notifications import create_notification

from funding_bot.config import (
    get_admin_ids
)


router = Router()


# ============================================================
# CONSTANTS
# ============================================================

NGN_RATE_AMOUNT = Decimal("100")
NGN_RATE_POINTS = 50

USDT_RATE_AMOUNT = Decimal("1")
USDT_RATE_POINTS = 500


# ============================================================
# STATES
# ============================================================

class FundingStates(StatesGroup):

    choosing_currency = State()

    entering_amount = State()

    awaiting_receipt = State()

    awaiting_approval = State()


# ============================================================
# HELPERS
# ============================================================

def now():

    return datetime.now(
        timezone.utc
    )


def user_ref(
    telegram_id
):

    return (
        db.collection("users")
        .document(
            str(telegram_id)
        )
    )


def get_quizbee_user(
    telegram_id
):

    snap = user_ref(
        telegram_id
    ).get()

    if not snap.exists:

        return None

    data = (
        snap.to_dict()
        or {}
    )

    data["telegram_id"] = str(
        telegram_id
    )

    return data


def settings_ref():

    return (
        db.collection("settings")
        .document("app")
    )


def get_funding_settings():

    snap = settings_ref().get()

    data = (
        snap.to_dict()
        or {}
    )

    return data


def currency_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="🇳🇬 NGN",
                    callback_data="fund_currency:NGN"
                )
            ],

            [
                InlineKeyboardButton(
                    text="💵 USDT",
                    callback_data="fund_currency:USDT"
                )
            ],

            [
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data="fund_cancel"
                )
            ]

        ]
    )


def receipt_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="✅ Approve Payment",
                    callback_data="fund_submit"
                )
            ],

            [
                InlineKeyboardButton(
                    text="❌ Cancel Payment",
                    callback_data="fund_cancel"
                )
            ]

        ]
    )


def parse_amount(
    value
):

    try:

        amount = Decimal(
            str(value).strip()
        )

    except (
        InvalidOperation,
        ValueError,
        TypeError
    ):

        return None

    if amount <= 0:

        return None

    return amount


def calculate_points(
    currency,
    amount
):

    if currency == "NGN":

        if (
            amount < NGN_RATE_AMOUNT
            or amount % NGN_RATE_AMOUNT != 0
        ):

            return None

        multiplier = (
            amount /
            NGN_RATE_AMOUNT
        )

        return int(
            multiplier *
            NGN_RATE_POINTS
        )

    if currency == "USDT":

        if (
            amount < USDT_RATE_AMOUNT
            or amount % USDT_RATE_AMOUNT != 0
        ):

            return None

        multiplier = (
            amount /
            USDT_RATE_AMOUNT
        )

        return int(
            multiplier *
            USDT_RATE_POINTS
        )

    return None


def money_text(
    currency,
    amount
):

    if currency == "NGN":

        return (
            f"₦{amount:,.0f}"
        )

    return (
        f"${amount:,.2f}"
    )


# ============================================================
# ADMIN ALERT
# ============================================================

async def notify_admins(
    order_id,
    order,
    receipt_type=None
):

    from aiogram import Bot

    from funding_bot.config import (
        ADMIN_BOT_TOKEN
    )

    if not ADMIN_BOT_TOKEN:

        return

    admin_ids = get_admin_ids()

    if not admin_ids:

        return

    username = (
        order.get(
            "username"
        )
        or "no_username"
    )

    currency = order.get(
        "currency",
        ""
    )

    amount = order.get(
        "amount",
        0
    )

    points = order.get(
        "points",
        0
    )

    text = (
        "💰 <b>New QuizBee Funding Request</b>\n\n"
        f"👤 User: @{username}\n"
        f"🆔 Telegram ID: "
        f"<code>{order.get('telegram_id', '')}</code>\n"
        f"💱 Currency: {currency}\n"
        f"💵 Amount: {amount}\n"
        f"🪙 Points: {points:,}\n"
        f"🆔 Order: <code>{order_id}</code>\n"
        f"📌 Status: Pending Review"
    )

    if receipt_type:

        text += (
            f"\n🧾 Receipt: {receipt_type}"
        )

    bot = Bot(
        token=ADMIN_BOT_TOKEN
    )

    try:

        for admin_id in admin_ids:

            try:

                await bot.send_message(
                    chat_id=int(
                        admin_id
                    ),
                    text=text
                )

            except Exception as e:

                print(
                    "Admin notification error:",
                    e
                )

    finally:

        await bot.session.close()


# ============================================================
# START
# ============================================================

@router.message(
    CommandStart()
)
async def start_funding(
    message: Message,
    state: FSMContext
):

    await state.clear()

    telegram_id = (
        message.from_user.id
    )

    user = get_quizbee_user(
        telegram_id
    )

    if not user:

        await message.answer(
            "❌ <b>QuizBee account not found.</b>\n\n"
            "Please open QuizBee first and "
            "complete registration before funding "
            "your wallet."
        )

        return

    await state.set_state(
        FundingStates.choosing_currency
    )

    await message.answer(
        "🐝 <b>QuizBee Funding</b>\n\n"
        "Welcome! Let's fund your QuizBee wallet.\n\n"
        "Choose your payment currency:",
        reply_markup=currency_keyboard()
    )


# ============================================================
# HELP
# ============================================================

@router.message(
    Command("fund")
)
async def fund_command(
    message: Message,
    state: FSMContext
):

    await state.clear()

    await state.set_state(
        FundingStates.choosing_currency
    )

    await message.answer(
        "💰 <b>Fund QuizBee Wallet</b>\n\n"
        "Choose your payment currency:",
        reply_markup=currency_keyboard()
    )


# ============================================================
# CURRENCY
# ============================================================

@router.callback_query(
    F.data.startswith(
        "fund_currency:"
    )
)
async def choose_currency(
    callback: CallbackQuery,
    state: FSMContext
):

    currency = (
        callback.data.split(
            ":",
            1
        )[1]
    )

    if currency not in (
        "NGN",
        "USDT"
    ):

        await callback.answer(
            "Invalid currency.",
            show_alert=True
        )

        return

    await state.update_data(
        currency=currency
    )

    await state.set_state(
        FundingStates.entering_amount
    )

    if currency == "NGN":

        text = (
            "🇳🇬 <b>NGN Funding</b>\n\n"
            "Rate:\n"
            "<b>₦100 = 50 QuizBee Points</b>\n\n"
            "Enter the amount you want to pay.\n\n"
            "Example:\n"
            "<code>1000</code> = "
            "<b>500 Points</b>\n\n"
            "Minimum: ₦100\n"
            "Amount must be in multiples of ₦100."
        )

    else:

        text = (
            "💵 <b>USDT Funding</b>\n\n"
            "Network: <b>BEP20</b>\n\n"
            "Rate:\n"
            "<b>$1 = 500 QuizBee Points</b>\n\n"
            "Enter the amount you want to pay.\n\n"
            "Example:\n"
            "<code>10</code> = "
            "<b>5,000 Points</b>\n\n"
            "Minimum: $1."
        )

    await callback.message.edit_text(
        text
    )

    await callback.answer()


# ============================================================
# AMOUNT
# ============================================================

@router.message(
    FundingStates.entering_amount,
    F.text
)
async def receive_amount(
    message: Message,
    state: FSMContext
):

    data = await state.get_data()

    currency = data.get(
        "currency"
    )

    amount = parse_amount(
        message.text
    )

    if amount is None:

        await message.answer(
            "❌ Enter a valid amount."
        )

        return

    points = calculate_points(
        currency,
        amount
    )

    if points is None:

        if currency == "NGN":

            await message.answer(
                "❌ NGN amount must be at least "
                "₦100 and a multiple of ₦100.\n\n"
                "Example: ₦500, ₦1,000, ₦5,000."
            )

        else:

            await message.answer(
                "❌ USDT amount must be at least "
                "$1.\n\n"
                "Example: $1, $5, $10."
            )

        return

    user = get_quizbee_user(
        message.from_user.id
    )

    if not user:

        await message.answer(
            "❌ QuizBee account not found."
        )

        await state.clear()

        return

    settings = (
        get_funding_settings()
    )

    if currency == "NGN":

        bank_name = settings.get(
            "funding_ngn_bank_name",
            ""
        )

        account_name = settings.get(
            "funding_ngn_account_name",
            ""
        )

        account_number = settings.get(
            "funding_ngn_account_number",
            ""
        )

        instructions = settings.get(
            "funding_ngn_instructions",
            ""
        )

        if not (
            bank_name
            and account_name
            and account_number
        ):

            await message.answer(
                "⚠️ <b>NGN payment details are "
                "not configured yet.</b>\n\n"
                "Please contact QuizBee Admin."
            )

            await state.clear()

            return

        payment_text = (
            "🇳🇬 <b>NGN PAYMENT DETAILS</b>\n\n"
            f"🏦 Bank: <b>{bank_name}</b>\n"
            f"👤 Account Name: "
            f"<b>{account_name}</b>\n"
            f"🔢 Account Number: "
            f"<code>{account_number}</code>\n\n"
        )

        if instructions:

            payment_text += (
                f"📝 {instructions}\n\n"
            )

    else:

        usdt_network = settings.get(
            "funding_usdt_network",
            "BEP20"
        )

        usdt_address = settings.get(
            "funding_usdt_address",
            ""
        )

        instructions = settings.get(
            "funding_usdt_instructions",
            ""
        )

        if not usdt_address:

            await message.answer(
                "⚠️ <b>USDT payment details are "
                "not configured yet.</b>\n\n"
                "Please contact QuizBee Admin."
            )

            await state.clear()

            return

        payment_text = (
            "💵 <b>USDT PAYMENT DETAILS</b>\n\n"
            f"🌐 Network: <b>{usdt_network}</b>\n"
            f"📍 Address:\n"
            f"<code>{usdt_address}</code>\n\n"
        )

        if instructions:

            payment_text += (
                f"📝 {instructions}\n\n"
            )

    order_ref = (
        db.collection(
            "point_orders"
        ).document()
    )

    order_data = {

        "telegram_id":
            str(
                message.from_user.id
            ),

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

        "currency":
            currency,

        "amount":
            float(amount),

        "points":
            points,

        "provider":
            "quizbee_funding_bot",

        "provider_reference":
            None,

        "status":
            "awaiting_payment",

        "receipt_type":
            None,

        "receipt_file_id":
            None,

        "receipt_file_name":
            None,

        "created_at":
            now(),

        "updated_at":
            now(),

        "paid_at":
            None,

        "approved_at":
            None,

        "submitted_at":
            None,

        "rejected_at":
            None,

        "cancelled_at":
            None,

        "admin_note":
            ""

    }

    order_ref.set(
        order_data
    )

    await state.update_data(
        order_id=order_ref.id
    )

    await state.set_state(
        FundingStates.awaiting_receipt
    )

    summary = (
        f"💰 <b>Funding Summary</b>\n\n"
        f"💱 Currency: <b>{currency}</b>\n"
        f"💵 Amount: "
        f"<b>{money_text(currency, amount)}</b>\n"
        f"🪙 Points: <b>{points:,}</b>\n\n"
    )

    await message.answer(
        summary +
        payment_text +
        "━━━━━━━━━━━━━━\n\n"
        "After making the payment, "
        "<b>send your payment receipt here.</b>\n\n"
        "📸 You can send a screenshot/photo "
        "or payment document."
    )


# ============================================================
# RECEIPT PHOTO
# ============================================================

@router.message(
    FundingStates.awaiting_receipt,
    F.photo
)
async def receive_receipt_photo(
    message: Message,
    state: FSMContext
):

    data = await state.get_data()

    order_id = data.get(
        "order_id"
    )

    if not order_id:

        await message.answer(
            "❌ Funding session expired. "
            "Please send /start again."
        )

        await state.clear()

        return

    order_ref = (
        db.collection(
            "point_orders"
        )
        .document(order_id)
    )

    snap = order_ref.get()

    if not snap.exists:

        await message.answer(
            "❌ Funding order not found."
        )

        await state.clear()

        return

    order = snap.to_dict() or {}

    if order.get("status") != "awaiting_payment":

        await message.answer(
            "This funding order is no longer "
            "waiting for a receipt."
        )

        await state.clear()

        return

    photo = (
        message.photo[-1]
    )

    order_ref.update({

        "receipt_type":
            "photo",

        "receipt_file_id":
            photo.file_id,

        "receipt_file_name":
            None,

        "updated_at":
            now()

    })

    await state.set_state(
        FundingStates.awaiting_approval
    )

    await message.answer(
        "🧾 <b>Receipt received.</b>\n\n"
        "Please review your payment details below.\n\n"
        f"💱 Currency: <b>{order.get('currency')}</b>\n"
        f"💵 Amount: <b>{order.get('amount')}</b>\n"
        f"🪙 Points: <b>{int(order.get('points', 0)):,}</b>\n\n"
        "When you are sure the payment has been made, "
        "tap <b>Approve Payment</b> below.\n\n"
        "⚠️ This does <b>not</b> instantly credit your "
        "account. It submits the payment for Admin review.",
        reply_markup=receipt_keyboard()
    )


# ============================================================
# RECEIPT DOCUMENT
# ============================================================

@router.message(
    FundingStates.awaiting_receipt,
    F.document
)
async def receive_receipt_document(
    message: Message,
    state: FSMContext
):

    data = await state.get_data()

    order_id = data.get(
        "order_id"
    )

    if not order_id:

        await message.answer(
            "❌ Funding session expired. "
            "Please send /start again."
        )

        await state.clear()

        return

    order_ref = (
        db.collection(
            "point_orders"
        )
        .document(order_id)
    )

    snap = order_ref.get()

    if not snap.exists:

        await message.answer(
            "❌ Funding order not found."
        )

        await state.clear()

        return

    order = snap.to_dict() or {}

    if order.get("status") != "awaiting_payment":

        await message.answer(
            "This funding order is no longer "
            "waiting for a receipt."
        )

        await state.clear()

        return

    document = (
        message.document
    )

    order_ref.update({

        "receipt_type":
            "document",

        "receipt_file_id":
            document.file_id,

        "receipt_file_name":
            document.file_name,

        "updated_at":
            now()

    })

    await state.set_state(
        FundingStates.awaiting_approval
    )

    await message.answer(
        "🧾 <b>Payment receipt received.</b>\n\n"
        "Tap <b>Approve Payment</b> to submit it "
        "for Admin review.\n\n"
        "⚠️ Your QuizBee Points are only credited "
        "after Admin approval.",
        reply_markup=receipt_keyboard()
    )


# ============================================================
# SUBMIT PAYMENT
# ============================================================

@router.callback_query(
    F.data == "fund_submit"
)
async def submit_payment(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    order_id = data.get(
        "order_id"
    )

    if not order_id:

        await callback.answer(
            "Funding session expired.",
            show_alert=True
        )

        await state.clear()

        return

    ref = (
        db.collection(
            "point_orders"
        )
        .document(order_id)
    )

    snap = ref.get()

    if not snap.exists:

        await callback.answer(
            "Order not found.",
            show_alert=True
        )

        await state.clear()

        return

    order = snap.to_dict() or {}

    if order.get("status") != "awaiting_payment":

        if order.get("status") == "pending":

            await callback.answer(
                "Already submitted.",
                show_alert=True
            )

        else:

            await callback.answer(
                "This order is no longer active.",
                show_alert=True
            )

        await state.clear()

        return

    if not order.get(
        "receipt_file_id"
    ):

        await callback.answer(
            "Please send your receipt first.",
            show_alert=True
        )

        return

    ref.update({

        "status":
            "pending",

        "submitted_at":
            now(),

        "updated_at":
            now()

    })

    # --------------------------------------------------------
    # TRANSACTION
    # --------------------------------------------------------

    db.collection(
        "transactions"
    ).document().set({

        "telegram_id":
            str(
                order.get(
                    "telegram_id"
                )
            ),

        "type":
            "point_purchase",

        "amount":
            order.get(
                "points",
                0
            ),

        "currency":
            "quizbee_points",

        "balance_type":
            "quizbee_points",

        "status":
            "pending",

        "provider":
            "quizbee_funding_bot",

        "provider_reference":
            order_id,

        "description":
            (
                "Pending QuizBee Funding "
                f"purchase: "
                f"{int(order.get('points', 0)):,} "
                "Points"
            ),

        "purchase_amount":
            order.get(
                "amount",
                0
            ),

        "purchase_currency":
            order.get(
                "currency",
                ""
            ),

        "created_at":
            now(),

        "updated_at":
            now()

    })

    await callback.message.edit_text(
        "⏳ <b>Payment under review.</b>\n\n"
        "Your payment has been submitted to "
        "QuizBee Admin.\n\n"
        f"🪙 Allocated Points: "
        f"<b>{int(order.get('points', 0)):,}</b>\n\n"
        "Your account would be credited soon "
        "after the payment is verified.\n\n"
        f"🆔 Order ID:\n"
        f"<code>{order_id}</code>"
    )

    await callback.answer(
        "Payment submitted for review."
    )

    await notify_admins(
        order_id,
        {
            **order,
            "status": "pending"
        },
        receipt_type=order.get(
            "receipt_type"
        )
    )

    await state.clear()


# ============================================================
# CANCEL
# ============================================================

@router.callback_query(
    F.data == "fund_cancel"
)
async def cancel_funding(
    callback: CallbackQuery,
    state: FSMContext
):

    data = await state.get_data()

    order_id = data.get(
        "order_id"
    )

    if order_id:

        ref = (
            db.collection(
                "point_orders"
            )
            .document(order_id)
        )

        snap = ref.get()

        if snap.exists:

            order = (
                snap.to_dict()
                or {}
            )

            if order.get(
                "status"
            ) in (
                "awaiting_payment",
                "pending"
            ):

                ref.update({

                    "status":
                        "cancelled",

                    "cancelled_at":
                        now(),

                    "updated_at":
                        now()

                })

    await state.clear()

    await callback.message.edit_text(
        "❌ <b>Funding cancelled.</b>\n\n"
        "No points were added to your account."
    )

    await callback.answer(
        "Funding cancelled."
    )


# ============================================================
# TEXT WHILE WAITING FOR RECEIPT
# ============================================================

@router.message(
    FundingStates.awaiting_receipt
)
async def waiting_for_receipt(
    message: Message
):

    await message.answer(
        "🧾 Please send your payment receipt "
        "as a photo or document.\n\n"
        "Example: a screenshot of your bank "
        "transfer or USDT transaction."
    )


# ============================================================
# TEXT AFTER RECEIPT
# ============================================================

@router.message(
    FundingStates.awaiting_approval
)
async def waiting_for_approval(
    message: Message
):

    await message.answer(
        "Your receipt has already been received.\n\n"
        "Please use the <b>Approve Payment</b> "
        "button on the receipt message to submit "
        "your payment for Admin review."
  )
