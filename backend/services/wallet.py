from backend.firebase import initialize_firebase


def get_wallet(telegram_id):

    db = initialize_firebase()

    if db is None:
        return {
            "quizbee_points": 0,
            "prize_balance": 0
        }

    doc = (
        db.collection("users")
        .document(str(telegram_id))
        .get()
    )

    if not doc.exists:
        return {
            "quizbee_points": 0,
            "prize_balance": 0
        }

    data = doc.to_dict()

    return {
        "quizbee_points": data.get("quizbee_points", 0),
        "prize_balance": data.get("prize_balance", 0)
  }
