from backend.firebase import initialize_firebase


def get_games():

    db = initialize_firebase()

    if db is None:
        return []

    games = []

    docs = db.collection("games").stream()

    for doc in docs:
        game = doc.to_dict()
        game["id"] = doc.id
        games.append(game)

    return games
