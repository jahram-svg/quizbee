import os
import time
import hmac
import hashlib
import json

from urllib.parse import parse_qsl


def validate_telegram_init_data(
    init_data: str,
    max_age: int = 86400,
    bot_token: str = None
): 
    """
    Validate Telegram Mini App initData.

    Returns the Telegram user dictionary if valid.
    Returns None if invalid or expired.
    """

    if not init_data:
        return None

    if bot_token is None:
        bot_token = os.getenv("BOT_TOKEN")

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is missing.")

    try:
        parsed = dict(
            parse_qsl(
                init_data,
                keep_blank_values=True
            )
        )

        received_hash = parsed.pop("hash", None)

        if not received_hash:
            return None

        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(parsed.items())
        )

        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode("utf-8"),
            digestmod=hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(
            calculated_hash,
            received_hash
        ):
            return None

        auth_date = parsed.get("auth_date")

        if not auth_date:
            return None

        try:
            auth_timestamp = int(auth_date)
        except (TypeError, ValueError):
            return None

        current_time = int(time.time())

        if current_time - auth_timestamp > max_age:
            return None

        if auth_timestamp > current_time + 60:
            return None

        user_data = parsed.get("user")

        if not user_data:
            return None

        user = json.loads(user_data)

        if not user.get("id"):
            return None

        return user

    except Exception:
        return None
