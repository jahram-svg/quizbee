import os
import random
import re
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from firebase_admin import firestore

from backend.firebase import db
from backend.telegram_auth import validate_telegram_init_data
from backend.admin import require_admin, admin_error

competition_bp = Blueprint("competition", __name__)

STAGED_GAMES = {"guess_it", "survivor", "dead_number"}
OPEN_GAMES = {"impossible_question", "crowd_trap", "impossible_choice"}
ALL_GAMES = STAGED_GAMES | OPEN_GAMES
DEFAULT_FEES = [10, 10, 10, 10, 10, 10, 30]


def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat() if isinstance(dt, datetime) else dt


def parse_time(value, default=None):
    if not value:
        return default
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return default


def norm(value):
    value = "" if value is None else str(value)
    value = value.strip().lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\s-]", "", value)
    return value


def serialize(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialize(v) for v in value]
    return value


def user_auth():
    raw = request.headers.get("X-Telegram-Init-Data", "")
    if not raw:
        return None
    user = validate_telegram_init_data(raw)
    if not user:
        return None
    return {
        "telegram_id": str(user["id"]),
        "username": user.get("username", ""),
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
        "photo_url": user.get("photo_url", ""),
    }


def user_ref(tid):
    return db.collection("users").document(str(tid))


def get_user(tid, telegram_user=None):
    ref = user_ref(tid)
    snap = ref.get()
    if not snap.exists:
        if not telegram_user:
            raise PermissionError("User not found.")
        data = {
            "telegram_id": str(tid),
            "username": telegram_user.get("username", ""),
            "first_name": telegram_user.get("first_name", ""),
            "last_name": telegram_user.get("last_name", ""),
            "photo_url": telegram_user.get("photo_url", ""),
            "quizbee_points": 100,
            "prize_balance": 0,
            "total_earned": 0,
            "total_spent": 0,
            "created_at": now(),
            "updated_at": now(),
        }
        ref.set(data)
        return data
    return snap.to_dict() or {}


def game_ref(game_id):
    return db.collection("games").document(game_id)


def round_ref(round_id):
    return db.collection("game_rounds").document(round_id)


def stage_ref(round_id, stage_no):
    return round_ref(round_id).collection("stages").document(str(stage_no))


def participant_id(round_id, tid):
    return f"{round_id}_{tid}"


def entry_id(round_id, stage_no, tid):
    return f"{round_id}_{stage_no}_{tid}"


def participant_ref(round_id, tid):
    return db.collection("game_participants").document(participant_id(round_id, tid))


def entry_ref(round_id, stage_no, tid):
    return db.collection("game_stage_entries").document(entry_id(round_id, stage_no, tid))


def get_round(round_id):
    snap = round_ref(round_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    data["id"] = round_id
    return data


def get_stage(round_id, stage_no):
    snap = stage_ref(round_id, stage_no).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    data["id"] = str(stage_no)
    data["stage_no"] = int(stage_no)
    return data


def public_stage(stage):
    if not stage:
        return None
    out = dict(stage)
    for key in (
        "correct_answer", "accepted_answers", "safe_option",
        "dead_numbers", "generation_mode", "secret_approved"
    ):
        out.pop(key, None)
    return serialize(out)


def game_is_staged(game_id):
    return game_id in STAGED_GAMES


def fee_for(stage):
    return max(0, int(stage.get("entry_fee", 10)))


def current_live_stage(round_id):
    r = get_round(round_id)
    if not r:
        return None
    stage_no = int(r.get("current_stage", 1))
    s = get_stage(round_id, stage_no)
    if not s:
        return None
    t = now()
    if s.get("status") == "scheduled" and parse_time(s.get("start_at")) and parse_time(s.get("start_at")) <= t:
        # Activation is deliberately manual; scheduled does not become public/live automatically.
        return None
    if s.get("status") != "live":
        return None
    if parse_time(s.get("end_at")) and parse_time(s.get("end_at")) <= t:
        finalize_stage(round_id, stage_no)
        return None
    return get_stage(round_id, stage_no)


def count_entries(round_id, stage_no):
    docs = db.collection("game_stage_entries").where("round_id", "==", round_id).where("stage_no", "==", int(stage_no)).stream()
    return len(list(docs))


def option_counts(entries):
    counts = {}
    for e in entries:
        if e.get("status") != "submitted":
            continue
        answer = str(e.get("answer", ""))
        counts[answer] = counts.get(answer, 0) + 1
    return counts


def add_prize(tid, amount, round_id, stage_no, reason="competition_prize"):
    if amount <= 0:
        return
    user_ref(tid).update({
        "prize_balance": firestore.Increment(amount),
        "total_earned": firestore.Increment(amount),
        "updated_at": now(),
    })
    db.collection("transactions").document().set({
        "telegram_id": str(tid),
        "type": reason,
        "game_round_id": round_id,
        "stage_no": int(stage_no),
        "amount": amount,
        "currency": "usd_prize_balance",
        "created_at": now(),
    })


def final_winners(game_id, stage, entries):
    submitted = [e for e in entries if e.get("status") == "submitted"]
    if game_id == "guess_it" or game_id == "impossible_question":
        correct = norm(stage.get("correct_answer"))
        accepted = {norm(x) for x in stage.get("accepted_answers", [])}
        accepted.add(correct)
        return [e["telegram_id"] for e in submitted if norm(e.get("answer")) in accepted]

    if game_id == "survivor":
        safe = norm(stage.get("safe_option"))
        return [e["telegram_id"] for e in submitted if norm(e.get("answer")) == safe]

    if game_id == "dead_number":
        dead = {norm(x) for x in stage.get("dead_numbers", [])}
        return [e["telegram_id"] for e in submitted if norm(e.get("answer")) not in dead]

    counts = option_counts(submitted)
    if not counts:
        return []

    if game_id == "crowd_trap":
        return [e["telegram_id"] for e in submitted if counts.get(str(e.get("answer")), 0) == 1]

    mechanic = stage.get("mechanic", "minority")
    total = len(submitted)
    winners = []
    if mechanic in ("majority", "minority"):
        values = list(counts.values())
        target_count = max(values) if mechanic == "majority" else min(values)
        winning_options = {k for k, v in counts.items() if v == target_count}
        winners = [e["telegram_id"] for e in submitted if str(e.get("answer")) in winning_options]
    elif mechanic == "closest_target":
        target = float(stage.get("target_percentage", 50))
        distances = {k: abs((v / total * 100) - target) for k, v in counts.items()}
        best = min(distances.values())
        winners = [e["telegram_id"] for e in submitted if distances.get(str(e.get("answer")), 999999) == best]
    elif mechanic == "within_range":
        low = float(stage.get("target_min_percentage", 40))
        high = float(stage.get("target_max_percentage", 60))
        good = {k for k, v in counts.items() if low <= (v / total * 100) <= high}
        winners = [e["telegram_id"] for e in submitted if str(e.get("answer")) in good]
    return winners


def finalize_stage(round_id, stage_no):
    r = get_round(round_id)
    s = get_stage(round_id, stage_no)
    if not r or not s:
        return {"success": False, "error": "Round or stage not found."}
    if s.get("status") == "closed":
        return {"success": True, "already_closed": True}
    end_at = parse_time(s.get("end_at"))
    if s.get("status") == "live" and end_at and end_at > now():
        return {"success": False, "error": "Stage is still live."}
    if s.get("status") not in ("live", "scheduled"):
        return {"success": False, "error": "Stage is not active."}

    docs = list(db.collection("game_stage_entries").where("round_id", "==", round_id).where("stage_no", "==", int(stage_no)).stream())
    entries = []
    for d in docs:
        data = d.to_dict() or {}
        data["id"] = d.id
        entries.append(data)

    game_id = r["game_id"]
    winners = set(final_winners(game_id, s, entries))
    qualified = set()

    # Everyone who paid but never submitted forfeits the stage.
    for entry in entries:
        tid = str(entry.get("telegram_id"))
        if entry.get("status") != "submitted":
            entry_ref(round_id, stage_no, tid).update({"status": "forfeited", "updated_at": now()})
            participant_ref(round_id, tid).set({"status": "eliminated", "eliminated_stage": int(stage_no), "updated_at": now()}, merge=True)
            continue

        if tid in winners:
            if game_is_staged(game_id) and int(stage_no) < int(r.get("total_stages", 1)):
                participant_ref(round_id, tid).set({
                    "status": "qualified",
                    "qualified_stage": int(stage_no),
                    "updated_at": now(),
                }, merge=True)
                qualified.add(tid)
            else:
                participant_ref(round_id, tid).set({
                    "status": "winner",
                    "qualified_stage": int(stage_no),
                    "updated_at": now(),
                }, merge=True)
        else:
            participant_ref(round_id, tid).set({
                "status": "eliminated",
                "eliminated_stage": int(stage_no),
                "updated_at": now(),
            }, merge=True)

    # Mark the stage closed first so retries cannot pay/submit into it.
    stage_ref(round_id, stage_no).update({
        "status": "closed",
        "closed_at": now(),
        "winner_count": len(winners),
        "qualified_count": len(qualified),
        "updated_at": now(),
    })

    is_final = (not game_is_staged(game_id)) or int(stage_no) >= int(r.get("total_stages", 1))
    prize = float(r.get("prize_pool_usd", 0) or 0)
    paid_each = 0.0
    if is_final:
        if winners and prize > 0:
            paid_each = round(prize / len(winners), 8)
            for tid in winners:
                result_ref = db.collection("game_results").document(f"{round_id}_{tid}")
                if not result_ref.get().exists:
                    add_prize(tid, paid_each, round_id, stage_no)
                    result_ref.set({
                        "round_id": round_id,
                        "game_id": game_id,
                        "stage_no": int(stage_no),
                        "telegram_id": tid,
                        "amount_usd": paid_each,
                        "created_at": now(),
                    })
        round_ref(round_id).update({
            "status": "settled",
            "settled_at": now(),
            "winner_count": len(winners),
            "updated_at": now(),
        })
    else:
        round_ref(round_id).update({
            "status": "waiting_next_stage",
            "updated_at": now(),
        })

    return {"success": True, "winner_count": len(winners), "qualified_count": len(qualified), "paid_each": paid_each}


def ensure_round_open_for_next_stage(round_id):
    r = get_round(round_id)
    if not r:
        return False, "Round not found."
    if r.get("status") == "settled":
        return False, "Round already settled."
    return True, None


def state_for_user(game_id, tid, telegram_user=None):
    game_snap = game_ref(game_id).get()
    if not game_snap.exists:
        return {"success": False, "error": "Game not found."}, 404
    game = game_snap.to_dict() or {}
    if not game.get("active", False):
        return {"success": False, "error": "This game is coming soon."}, 403

    rounds = list(db.collection("game_rounds").where("game_id", "==", game_id).where("status", "in", ["active", "waiting_next_stage"]).stream())
    rounds += list(db.collection("game_rounds").where("game_id", "==", game_id).where("status", "==", "settled").stream())
    rounds.sort(key=lambda d: d.to_dict().get("created_at", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    if not rounds:
        return {"success": True, "status": "no_round", "game": {**game, "id": game_id}}, 200
    rdoc = rounds[0]
    r = rdoc.to_dict() or {}
    r["id"] = rdoc.id

    stage_no = int(r.get("current_stage", 1))
    s = get_stage(rdoc.id, stage_no)
    if s and s.get("status") == "live" and parse_time(s.get("end_at")) and parse_time(s.get("end_at")) <= now():
        finalize_stage(rdoc.id, stage_no)
        r = get_round(rdoc.id)
        s = get_stage(rdoc.id, stage_no)

    participant = participant_ref(rdoc.id, tid).get().to_dict() or {}
    if r.get("status") == "settled":
        return {
            "success": True, "status": "finished", "game": {**game, "id": game_id},
            "round": public_round(r), "participant": serialize(participant)
        }, 200

    live = current_live_stage(rdoc.id)
    if not live:
        return {
            "success": True, "status": "round_not_started", "message": "Round not started yet.",
            "game": {**game, "id": game_id}, "round": public_round(r),
            "participant": serialize(participant)
        }, 200

    if game_is_staged(game_id) and stage_no > 1 and participant.get("status") != "qualified":
        return {
            "success": True, "status": "eliminated", "message": "You did not qualify for this stage.",
            "game": {**game, "id": game_id}, "round": public_round(r),
            "stage": public_stage(live), "participant": serialize(participant)
        }, 200

    entry = entry_ref(rdoc.id, stage_no, tid).get().to_dict() or {}
    if not entry:
        return {
            "success": True, "status": "needs_entry", "entry_fee": fee_for(live),
            "message": f"Pay {fee_for(live)} QuizBee Points to enter this stage.",
            "game": {**game, "id": game_id}, "round": public_round(r),
            "stage": public_stage(live), "participant": serialize(participant),
        }, 200

    if entry.get("status") == "submitted":
        return {
            "success": True, "status": "submitted", "message": "Answer submitted. Wait for the round to finish.",
            "game": {**game, "id": game_id}, "round": public_round(r),
            "stage": public_stage(live), "participant": serialize(participant),
        }, 200

    return {
        "success": True, "status": "ready", "entry_fee": fee_for(live),
        "game": {**game, "id": game_id}, "round": public_round(r),
        "stage": public_stage(live), "participant": serialize(participant),
    }, 200


def public_round(r):
    out = dict(r)
    out.pop("admin_note", None)
    return serialize(out)


@competition_bp.get("/api/competition/<game_id>/state")
def competition_state(game_id):
    try:
        user = user_auth()
        if not user:
            return jsonify({"success": False, "error": "Unauthorized Telegram session."}), 401
        payload, status = state_for_user(game_id, user["telegram_id"], user)
        return jsonify(payload), status
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@competition_bp.post("/api/competition/<game_id>/enter")
def competition_enter(game_id):
    try:
        telegram_user = user_auth()
        if not telegram_user:
            return jsonify({"success": False, "error": "Unauthorized Telegram session."}), 401
        tid = telegram_user["telegram_id"]
        game_snap = game_ref(game_id).get()
        if not game_snap.exists:
            return jsonify({"success": False, "error": "Game not found."}), 404
        game = game_snap.to_dict() or {}
        if not game.get("active", False):
            return jsonify({"success": False, "error": "This game is coming soon."}), 403

        rounds = list(db.collection("game_rounds").where("game_id", "==", game_id).where("status", "in", ["active", "waiting_next_stage"]).stream())
        if not rounds:
            return jsonify({"success": False, "error": "No active round."}), 404
        rdoc = sorted(rounds, key=lambda d: d.to_dict().get("created_at", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)[0]
        r = rdoc.to_dict() or {}
        rid = rdoc.id
        stage_no = int(r.get("current_stage", 1))
        s = get_stage(rid, stage_no)
        if not s or s.get("status") != "live":
            return jsonify({"success": False, "error": "Round not started yet."}), 409
        if parse_time(s.get("end_at")) and parse_time(s.get("end_at")) <= now():
            finalize_stage(rid, stage_no)
            return jsonify({"success": False, "error": "This stage has ended."}), 409

        participant = participant_ref(rid, tid).get().to_dict() or {}
        if game_is_staged(game_id) and stage_no > 1 and participant.get("status") != "qualified":
            return jsonify({"success": False, "error": "You did not qualify for this stage."}), 403
        if participant.get("status") in ("eliminated", "winner"):
            return jsonify({"success": False, "error": "You are not eligible for this stage."}), 403

        er = entry_ref(rid, stage_no, tid)
        if er.get().exists:
            return jsonify({"success": True, "already_entered": True, "entry_fee": fee_for(s), "user": get_user(tid, telegram_user)}), 200

        fee = fee_for(s)
        ur = user_ref(tid)
        tx = db.transaction()
        user_snap = ur.get(transaction=tx)
        if not user_snap.exists:
            return jsonify({"success": False, "error": "User account not found."}), 404
        u = user_snap.to_dict() or {}
        points = int(u.get("quizbee_points", 0) or 0)
        if points < fee:
            return jsonify({"success": False, "error": f"You need {fee} QuizBee Points to enter this stage."}), 400
        tx.update(ur, {
            "quizbee_points": points - fee,
            "total_spent": firestore.Increment(fee),
            "updated_at": now(),
        })
        tx.set(er, {
            "round_id": rid, "game_id": game_id, "stage_no": stage_no,
            "telegram_id": tid, "entry_fee": fee, "status": "paid",
            "created_at": now(), "updated_at": now(),
        })
        tx.set(participant_ref(rid, tid), {
            "round_id": rid, "game_id": game_id, "telegram_id": tid,
            "status": "active", "last_paid_stage": stage_no,
            "updated_at": now(),
        }, merge=True)
        tx.set(db.collection("transactions").document(), {
            "telegram_id": tid, "type": "competition_entry", "game_id": game_id,
            "game_round_id": rid, "stage_no": stage_no,
            "amount": -fee, "currency": "quizbee_points", "created_at": now(),
        })
        updated = dict(u)
        updated["quizbee_points"] = points - fee
        return jsonify({"success": True, "already_entered": False, "user": serialize(updated), "state": "ready"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@competition_bp.post("/api/competition/<game_id>/submit")
def competition_submit(game_id):
    try:
        telegram_user = user_auth()
        if not telegram_user:
            return jsonify({"success": False, "error": "Unauthorized Telegram session."}), 401
        tid = telegram_user["telegram_id"]
        body = request.get_json(silent=True) or {}
        answer = body.get("answer")
        if answer is None or str(answer).strip() == "":
            return jsonify({"success": False, "error": "An answer is required."}), 400

        rounds = list(db.collection("game_rounds").where("game_id", "==", game_id).where("status", "in", ["active", "waiting_next_stage"]).stream())
        if not rounds:
            return jsonify({"success": False, "error": "No active round."}), 404
        rdoc = sorted(rounds, key=lambda d: d.to_dict().get("created_at", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)[0]
        rid = rdoc.id
        r = rdoc.to_dict() or {}
        stage_no = int(r.get("current_stage", 1))
        s = get_stage(rid, stage_no)
        if not s or s.get("status") != "live":
            return jsonify({"success": False, "error": "Round not started yet."}), 409
        if parse_time(s.get("end_at")) and parse_time(s.get("end_at")) <= now():
            finalize_stage(rid, stage_no)
            return jsonify({"success": False, "error": "This stage has ended."}), 409
        participant = participant_ref(rid, tid).get().to_dict() or {}
        if game_is_staged(game_id) and stage_no > 1 and participant.get("status") != "qualified":
            return jsonify({"success": False, "error": "You are not qualified for this stage."}), 403
        er = entry_ref(rid, stage_no, tid)
        es = er.get()
        if not es.exists:
            return jsonify({"success": False, "error": "Pay the stage entry fee first."}), 403
        entry = es.to_dict() or {}
        if entry.get("status") == "submitted":
            return jsonify({"success": False, "error": "You have already submitted your answer."}), 409
        er.update({"answer": str(answer), "status": "submitted", "submitted_at": now(), "updated_at": now()})

        # Guess It can immediately tell a player who failed; it does not reveal secrets for the other games.
        if game_id == "guess_it":
            accepted = {norm(s.get("correct_answer"))} | {norm(x) for x in s.get("accepted_answers", [])}
            if norm(answer) not in accepted:
                participant_ref(rid, tid).set({"status": "eliminated", "eliminated_stage": stage_no, "updated_at": now()}, merge=True)
                return jsonify({"success": True, "result": "failed", "message": "You failed, wait for the round to finish to rejoin.", "user": serialize(get_user(tid, telegram_user))})
            return jsonify({"success": True, "result": "submitted", "message": "Correct submission recorded. You have advanced if the stage remains valid."})

        return jsonify({"success": True, "result": "submitted", "message": "Answer locked. Results will be determined when the stage ends."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------- ADMIN ----------------

@competition_bp.get("/api/admin/competition/games")
def admin_games():
    admin, error = require_admin()
    if error:
        return admin_error(error)
    docs = list(db.collection("games").stream())
    return jsonify({"success": True, "games": [{"id": d.id, **(d.to_dict() or {})} for d in docs if d.id in ALL_GAMES]})


@competition_bp.post("/api/admin/competition/setup-games")
def setup_games():
    admin, error = require_admin()
    if error:
        return admin_error(error)
    defaults = [
        ("guess_it", "Guess It", "🎯", "7-day survival: identify the answer each day and survive.", True, 1),
        ("impossible_question", "Impossible Question", "💀", "One brutal question. One answer only. Open for up to seven days.", True, 2),
        ("crowd_trap", "The Crowd Trap", "🧠", "Pick a number nobody else picks.", False, 3),
        ("survivor", "The Survivor", "🏆", "Survive every stage by choosing the safe option.", False, 4),
        ("dead_number", "Dead Number", "☠️", "Avoid the numbers QuizBee marks as dead.", False, 5),
        ("impossible_choice", "Impossible Choice", "🤔", "Predict human behaviour under pressure.", False, 6),
    ]
    for gid, name, icon, desc, active, order in defaults:
        game_ref(gid).set({
            "name": name, "icon": icon, "description": desc,
            "active": active, "entry_fee": 10, "sort_order": order,
            "competition_enabled": True, "updated_at": now(),
        }, merge=True)
    return jsonify({"success": True, "message": "Competition game settings initialized."})


@competition_bp.get("/api/admin/competition/rounds")
def admin_rounds():
    admin, error = require_admin()
    if error:
        return admin_error(error)
    game_id = request.args.get("game_id", "").strip()
    docs = list(db.collection("game_rounds").stream())
    rows = []
    for d in docs:
        data = d.to_dict() or {}
        if game_id and data.get("game_id") != game_id:
            continue
        data["id"] = d.id
        rows.append(serialize(data))
    rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return jsonify({"success": True, "rounds": rows})


@competition_bp.get("/api/admin/competition/rounds/<round_id>")
def admin_round_detail(round_id):
    admin, error = require_admin()
    if error:
        return admin_error(error)
    r = get_round(round_id)
    if not r:
        return jsonify({"success": False, "error": "Round not found."}), 404
    stages = []
    for d in round_ref(round_id).collection("stages").stream():
        data = d.to_dict() or {}
        data["id"] = d.id
        # Admin is allowed to see secrets; this endpoint is admin-only.
        stages.append(serialize(data))
    stages.sort(key=lambda x: int(x.get("stage_no", 0)))
    entries = []
    for d in db.collection("game_stage_entries").where("round_id", "==", round_id).stream():
        data = d.to_dict() or {}
        data["id"] = d.id
        entries.append(serialize(data))
    results = [serialize({"id": d.id, **(d.to_dict() or {})}) for d in db.collection("game_results").where("round_id", "==", round_id).stream()]
    return jsonify({"success": True, "round": serialize(r), "stages": stages, "entries": entries, "results": results})


@competition_bp.post("/api/admin/competition/rounds/create")
def admin_create_round():
    admin, error = require_admin()
    if error:
        return admin_error(error)
    body = request.get_json(silent=True) or {}
    game_id = str(body.get("game_id", "")).strip()
    if game_id not in ALL_GAMES:
        return jsonify({"success": False, "error": "Invalid competition game."}), 400
    if not game_ref(game_id).get().exists:
        return jsonify({"success": False, "error": "Game has not been initialized."}), 404

    staged = game_is_staged(game_id)
    total_stages = int(body.get("total_stages", 7 if staged else 1))
    if staged:
        total_stages = 7
    else:
        total_stages = 1
    fees = body.get("entry_fees", DEFAULT_FEES if staged else [int(body.get("entry_fee", 10))])
    if not isinstance(fees, list):
        fees = DEFAULT_FEES if staged else [int(body.get("entry_fee", 10))]
    fees = [max(0, int(x)) for x in fees[:total_stages]]
    while len(fees) < total_stages:
        fees.append(30 if len(fees) == total_stages - 1 else 10)

    start_at = parse_time(body.get("start_at"), now())
    rref = db.collection("game_rounds").document()
    rref.set({
        "game_id": game_id,
        "title": str(body.get("title", f"{game_id} Round")),
        "status": "active",
        "total_stages": total_stages,
        "current_stage": 1,
        "entry_fees": fees,
        "prize_pool_usd": float(body.get("prize_pool_usd", 0) or 0),
        "start_at": start_at,
        "created_by": admin["telegram_id"],
        "created_at": now(),
        "updated_at": now(),
    })
    return jsonify({"success": True, "round_id": rref.id, "entry_fees": fees})


@competition_bp.post("/api/admin/competition/rounds/<round_id>/stages/create")
def admin_create_stage(round_id):
    admin, error = require_admin()
    if error:
        return admin_error(error)
    r = get_round(round_id)
    if not r:
        return jsonify({"success": False, "error": "Round not found."}), 404
    if r.get("status") == "settled":
        return jsonify({"success": False, "error": "Round is already settled."}), 400
    body = request.get_json(silent=True) or {}
    stage_no = int(body.get("stage_no", int(r.get("current_stage", 1))))
    if stage_no < 1 or stage_no > int(r.get("total_stages", 1)):
        return jsonify({"success": False, "error": "Invalid stage number."}), 400
    sref = stage_ref(round_id, stage_no)
    if sref.get().exists:
        return jsonify({"success": False, "error": "That stage already exists."}), 409

    game_id = r["game_id"]
    fee = int(body.get("entry_fee", r.get("entry_fees", [10])[stage_no - 1]))
    start_at = parse_time(body.get("start_at"), now())
    end_at = parse_time(body.get("end_at"))
    if not end_at or end_at <= start_at:
        return jsonify({"success": False, "error": "End time must be after start time."}), 400

    options = body.get("options", [])
    if isinstance(options, str):
        options = [x.strip() for x in options.split(",") if x.strip()]
    options = list(options or [])

    data = {
        "round_id": round_id,
        "game_id": game_id,
        "stage_no": stage_no,
        "title": str(body.get("title", f"Day {stage_no}")),
        "question": str(body.get("question", "")),
        "type": str(body.get("type", "text")),
        "options": options,
        "min_number": int(body.get("min_number", 1)),
        "max_number": int(body.get("max_number", 20)),
        "entry_fee": fee,
        "start_at": start_at,
        "end_at": end_at,
        "clue": str(body.get("clue", "")),
        "mechanic": str(body.get("mechanic", "minority")),
        "target_percentage": float(body.get("target_percentage", 50) or 50),
        "target_min_percentage": float(body.get("target_min_percentage", 40) or 40),
        "target_max_percentage": float(body.get("target_max_percentage", 60) or 60),
        "generation_mode": str(body.get("generation_mode", "admin")),
        "secret_approved": False,
        "status": "draft",
        "created_by": admin["telegram_id"],
        "created_at": now(),
        "updated_at": now(),
    }

    # Admin or random generation. The secret is never returned to the user API.
    if game_id in ("guess_it", "impossible_question"):
        data["correct_answer"] = str(body.get("correct_answer", "")).strip()
        accepted = body.get("accepted_answers", [])
        if isinstance(accepted, str):
            accepted = [x.strip() for x in accepted.split(",") if x.strip()]
        data["accepted_answers"] = accepted
        if data["generation_mode"] == "admin" and not data["correct_answer"]:
            return jsonify({"success": False, "error": "Admin must provide the correct answer."}), 400
    elif game_id == "survivor":
        if not options or len(options) < 2:
            return jsonify({"success": False, "error": "Survivor needs at least two options."}), 400
        safe = str(body.get("safe_option", "")).strip()
        if data["generation_mode"] == "random" and not safe:
            safe = random.choice(options)
        if safe not in options:
            return jsonify({"success": False, "error": "Safe option must be one of the supplied options."}), 400
        data["safe_option"] = safe
    elif game_id == "dead_number":
        mn, mx = data["min_number"], data["max_number"]
        if mx <= mn:
            return jsonify({"success": False, "error": "Maximum number must be greater than minimum."}), 400
        raw_dead = body.get("dead_numbers", [])
        if isinstance(raw_dead, str):
            raw_dead = [x.strip() for x in raw_dead.split(",") if x.strip()]
        dead = [str(x) for x in raw_dead]
        count = int(body.get("dead_count", len(dead) or 1))
        available = [str(x) for x in range(mn, mx + 1)]
        if data["generation_mode"] == "random":
            if count >= len(available):
                return jsonify({"success": False, "error": "Dead count must leave at least one survivor."}), 400
            dead = random.sample(available, count)
        if not dead or any(x not in available for x in dead) or len(set(dead)) != len(dead):
            return jsonify({"success": False, "error": "Invalid dead numbers."}), 400
        data["dead_numbers"] = dead
        data["dead_count"] = len(dead)
    elif game_id == "crowd_trap":
        if data["max_number"] <= data["min_number"]:
            return jsonify({"success": False, "error": "Invalid number range."}), 400
        data["type"] = "number"
    elif game_id == "impossible_choice":
        if len(options) < 2:
            return jsonify({"success": False, "error": "Impossible Choice needs at least two options."}), 400
        if data["mechanic"] not in ("majority", "minority", "closest_target", "within_range"):
            return jsonify({"success": False, "error": "Invalid Impossible Choice mechanic."}), 400

    sref.set(data)
    return jsonify({"success": True, "stage": serialize({**data, "id": str(stage_no)})})


@competition_bp.post("/api/admin/competition/rounds/<round_id>/stages/<int:stage_no>/approve")
def admin_approve_stage(round_id, stage_no):
    admin, error = require_admin()
    if error:
        return admin_error(error)
    s = get_stage(round_id, stage_no)
    if not s:
        return jsonify({"success": False, "error": "Stage not found."}), 404
    gid = s.get("game_id")
    if gid in ("guess_it", "impossible_question") and not s.get("correct_answer"):
        return jsonify({"success": False, "error": "Correct answer is required."}), 400
    if gid == "survivor" and not s.get("safe_option"):
        return jsonify({"success": False, "error": "Safe option is required."}), 400
    if gid == "dead_number" and not s.get("dead_numbers"):
        return jsonify({"success": False, "error": "Dead number(s) are required."}), 400
    stage_ref(round_id, stage_no).update({
        "secret_approved": True,
        "approved_by": admin["telegram_id"],
        "approved_at": now(),
        "updated_at": now(),
    })
    return jsonify({"success": True, "message": "Secret approved."})


@competition_bp.post("/api/admin/competition/rounds/<round_id>/stages/<int:stage_no>/start")
def admin_start_stage(round_id, stage_no):
    admin, error = require_admin()
    if error:
        return admin_error(error)
    r = get_round(round_id)
    s = get_stage(round_id, stage_no)
    if not r or not s:
        return jsonify({"success": False, "error": "Round or stage not found."}), 404
    if not s.get("secret_approved", False) and r["game_id"] in ("guess_it", "impossible_question", "survivor", "dead_number"):
        return jsonify({"success": False, "error": "Approve the actual answer/safe/dead numbers before starting."}), 400
    if parse_time(s.get("start_at")) and parse_time(s.get("start_at")) > now():
        return jsonify({"success": False, "error": "Scheduled start time has not arrived yet."}), 400
    if s.get("status") == "live":
        return jsonify({"success": True, "message": "Stage already live."})
    stage_ref(round_id, stage_no).update({"status": "live", "live_at": now(), "updated_at": now()})
    round_ref(round_id).update({"current_stage": stage_no, "status": "active", "updated_at": now()})
    return jsonify({"success": True, "message": "Stage started."})


@competition_bp.post("/api/admin/competition/rounds/<round_id>/stages/<int:stage_no>/end")
def admin_end_stage(round_id, stage_no):
    admin, error = require_admin()
    if error:
        return admin_error(error)
    s = get_stage(round_id, stage_no)
    if not s:
        return jsonify({"success": False, "error": "Stage not found."}), 404
    stage_ref(round_id, stage_no).update({"end_at": now(), "updated_at": now()})
    result = finalize_stage(round_id, stage_no)
    return jsonify(result)


@competition_bp.post("/api/admin/competition/rounds/<round_id>/next-stage")
def admin_next_stage(round_id):
    admin, error = require_admin()
    if error:
        return admin_error(error)
    r = get_round(round_id)
    if not r:
        return jsonify({"success": False, "error": "Round not found."}), 404
    current = int(r.get("current_stage", 1))
    current_stage = get_stage(round_id, current)
    if current_stage and current_stage.get("status") == "live":
        return jsonify({"success": False, "error": "End the current stage first."}), 400
    next_no = current + 1
    if next_no > int(r.get("total_stages", 1)):
        return jsonify({"success": False, "error": "There is no next stage."}), 400
    round_ref(round_id).update({"current_stage": next_no, "status": "waiting_next_stage", "updated_at": now()})
    return jsonify({"success": True, "next_stage": next_no})
