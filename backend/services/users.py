from backend.firebase import initialize_firebase


def get_user(telegram_id):

    db = initialize_firebase()

    if db is None:
        return None

    doc = db.collection("users").document(str(telegram_id)).get()

    if doc.exists:
        return doc.to_dict()

    return None


def create_user(telegram_user):

    db = initialize_firebase()

    if db is None:
        return None

    user_id = str(telegram_user["id"])

    user_ref = db.collection("users").document(user_id)

    existing = user_ref.get()

    if existing.exists:
        return existing.to_dict()

    user_data = {
        "telegram_id": telegram_user["id"],
        "username": telegram_user.get("username"),
        "first_name": telegram_user.get("first_name"),
        "quizbee_points": 0,
        "prize_balance": 0,
        "streak": 0,
        "referrals": 0,
        "score": 0
    }

    user_ref.set(user_data)

    return user_data
