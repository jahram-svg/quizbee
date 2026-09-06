from backend.firebase import initialize_firebase


def get_leaderboard(limit=100):

    db = initialize_firebase()

    if db is None:
        return []

    docs = (
        db.collection("users")
        .order_by("score", direction="DESCENDING")
        .limit(limit)
        .stream()
    )

    leaderboard = []

    position = 1

    for doc in docs:

        data = doc.to_dict()

        leaderboard.append({
            "position": position,
            "username": data.get("username") or data.get("first_name", "Player"),
            "score": data.get("score", 0)
        })

        position += 1

    return leaderboard
