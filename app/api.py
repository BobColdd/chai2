from datetime import date, timedelta

import requests
from flask import Blueprint, request, jsonify, g
from app import db
from app.models import Farmer, Farm, PluckingRecord, PruningRecord, Tool, Note
from app.api_auth import generate_token, farmer_required
from app.chatbot import get_bot_reply

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _farmer_json(farmer):
    return {"id": farmer.id, "full_name": farmer.full_name, "email": farmer.email, "phone": farmer.phone}


def _farm_json(farm):
    return {
        "id": farm.id, "farm_number": farm.farm_number, "location": farm.location,
        "approx_bushes": farm.approx_bushes, "acreage": farm.acreage, "total_kilos": farm.total_kilos,
    }


# ---------- Auth ----------

@api_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    scale = data.get("scale", "small")
    password = data.get("password") or ""
    farm_numbers = [f.strip() for f in (data.get("farm_numbers") or "").split(",") if f.strip()]

    if not full_name or not email or not password:
        return jsonify({"error": "Full name, email, and password are required."}), 400
    if Farmer.query.filter_by(email=email).first():
        return jsonify({"error": "An account with that email already exists."}), 409
    if not farm_numbers:
        return jsonify({"error": "Add at least one farm number."}), 400

    farmer = Farmer(full_name=full_name, email=email, phone=phone, scale=scale)
    farmer.set_password(password)
    db.session.add(farmer)
    db.session.flush()

    for fn in farm_numbers:
        db.session.add(Farm(farmer_id=farmer.id, farm_number=fn))
    db.session.commit()

    return jsonify({"token": generate_token(farmer.id), "farmer": _farmer_json(farmer)}), 201


@api_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    farmer = Farmer.query.filter_by(email=email).first()
    if not farmer or not farmer.check_password(password):
        return jsonify({"error": "Invalid email or password."}), 401

    return jsonify({"token": generate_token(farmer.id), "farmer": _farmer_json(farmer)})


# ---------- Dashboard ----------

def _weather():
    try:
        resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": -0.3676, "longitude": 35.2836, "current": "temperature_2m,precipitation",
                    "daily": "precipitation_sum", "timezone": "Africa/Nairobi", "forecast_days": 2},
            timeout=4,
        )
        if resp.ok:
            j = resp.json()
            return {"temp": j["current"]["temperature_2m"], "rain_today": j["daily"]["precipitation_sum"][0]}
    except requests.RequestException:
        pass
    return None


@api_bp.route("/dashboard")
@farmer_required
def dashboard():
    farmer = g.current_farmer
    farm_id = request.args.get("farm_id", type=int)
    farms = farmer.farms

    farm = None
    if farms:
        farm = next((f for f in farms if f.id == farm_id), farms[0])

    chart_labels, chart_values = [], []
    plucking_records, pruning_records = [], []
    total_kilos, last_30_kilos, avg_daily = 0, 0, 0

    if farm:
        total_kilos = farm.total_kilos
        cutoff = date.today() - timedelta(days=30)
        last_30 = (
            PluckingRecord.query.filter(PluckingRecord.farm_id == farm.id, PluckingRecord.date >= cutoff)
            .order_by(PluckingRecord.date.asc()).all()
        )
        last_30_kilos = sum(r.kilos for r in last_30)
        days_with_records = len({r.date for r in last_30}) or 1
        avg_daily = round(last_30_kilos / days_with_records, 1)
        chart_labels = [r.date.strftime("%d %b") for r in last_30]
        chart_values = [r.kilos for r in last_30]

        plucking_records = [
            {"id": r.id, "date": r.date.isoformat(), "kilos": r.kilos, "pluckers_count": r.pluckers_count, "notes": r.notes}
            for r in PluckingRecord.query.filter_by(farm_id=farm.id).order_by(PluckingRecord.date.desc()).limit(10).all()
        ]
        pruning_records = [
            {"id": r.id, "date": r.date.isoformat(), "bushes_pruned": r.bushes_pruned, "prune_type": r.prune_type}
            for r in PruningRecord.query.filter_by(farm_id=farm.id).order_by(PruningRecord.date.desc()).limit(5).all()
        ]

    return jsonify({
        "farmer": _farmer_json(farmer),
        "farms": [_farm_json(f) for f in farms],
        "selected_farm_id": farm.id if farm else None,
        "total_kilos": total_kilos,
        "last_30_kilos": last_30_kilos,
        "avg_daily": avg_daily,
        "chart_labels": chart_labels,
        "chart_values": chart_values,
        "plucking_records": plucking_records,
        "pruning_records": pruning_records,
        "total_bushes": farmer.total_bushes,
        "weather": _weather(),
    })


# ---------- Farms ----------

@api_bp.route("/farms", methods=["POST"])
@farmer_required
def add_farm():
    farmer = g.current_farmer
    data = request.get_json(silent=True) or {}
    farm_number = (data.get("farm_number") or "").strip()

    if not farm_number:
        return jsonify({"error": "Farm number is required."}), 400
    if Farm.query.filter_by(farmer_id=farmer.id, farm_number=farm_number).first():
        return jsonify({"error": "You already have a farm with that number."}), 409

    farm = Farm(
        farmer_id=farmer.id, farm_number=farm_number,
        location=data.get("location"), approx_bushes=data.get("approx_bushes"), acreage=data.get("acreage"),
    )
    db.session.add(farm)
    db.session.commit()
    return jsonify({"farm": _farm_json(farm)}), 201


@api_bp.route("/farms/<int:farm_id>", methods=["PUT", "POST"])
@farmer_required
def update_farm(farm_id):
    farm = Farm.query.filter_by(id=farm_id, farmer_id=g.current_farmer.id).first_or_404()
    data = request.get_json(silent=True) or {}
    if "location" in data:
        farm.location = data["location"]
    if "approx_bushes" in data:
        farm.approx_bushes = data["approx_bushes"]
    if "acreage" in data:
        farm.acreage = data["acreage"]
    db.session.commit()
    return jsonify({"farm": _farm_json(farm)})


# ---------- Plucking ----------

@api_bp.route("/plucking", methods=["POST"])
@farmer_required
def add_plucking():
    farmer = g.current_farmer
    data = request.get_json(silent=True) or {}
    farm = Farm.query.filter_by(id=data.get("farm_id"), farmer_id=farmer.id).first()

    if not farm:
        return jsonify({"error": "Select a valid farm."}), 400
    try:
        kilos = float(data.get("kilos"))
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a valid number of kilos."}), 400
    if kilos <= 0:
        return jsonify({"error": "Enter a valid number of kilos."}), 400

    rec_date = data.get("date") or date.today().isoformat()
    record = PluckingRecord(
        farm_id=farm.id, date=date.fromisoformat(rec_date), kilos=kilos,
        pluckers_count=data.get("pluckers_count"), notes=data.get("notes"),
    )
    db.session.add(record)
    db.session.commit()
    return jsonify({"message": "Plucking record saved."}), 201


@api_bp.route("/plucking/<int:record_id>", methods=["DELETE", "POST"])
@farmer_required
def delete_plucking(record_id):
    record = PluckingRecord.query.join(Farm).filter(
        PluckingRecord.id == record_id, Farm.farmer_id == g.current_farmer.id
    ).first_or_404()
    db.session.delete(record)
    db.session.commit()
    return jsonify({"message": "Deleted."})


# ---------- Pruning ----------

@api_bp.route("/pruning", methods=["POST"])
@farmer_required
def add_pruning():
    farmer = g.current_farmer
    data = request.get_json(silent=True) or {}
    farm = Farm.query.filter_by(id=data.get("farm_id"), farmer_id=farmer.id).first()

    if not farm:
        return jsonify({"error": "Select a valid farm."}), 400
    try:
        bushes_pruned = int(data.get("bushes_pruned"))
    except (TypeError, ValueError):
        return jsonify({"error": "Enter a valid number of bushes."}), 400
    if bushes_pruned <= 0:
        return jsonify({"error": "Enter a valid number of bushes."}), 400

    rec_date = data.get("date") or date.today().isoformat()
    record = PruningRecord(
        farm_id=farm.id, date=date.fromisoformat(rec_date), bushes_pruned=bushes_pruned,
        prune_type=data.get("prune_type"), notes=data.get("notes"),
    )
    db.session.add(record)
    db.session.commit()
    return jsonify({"message": "Pruning record saved."}), 201


# ---------- Tools ----------

@api_bp.route("/tools", methods=["GET", "POST"])
@farmer_required
def tools():
    farmer = g.current_farmer

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Tool name is required."}), 400

        purchase_date = data.get("purchase_date") or date.today().isoformat()
        tool = Tool(
            farmer_id=farmer.id, name=name, quantity=data.get("quantity", 1), cost=data.get("cost"),
            purchase_date=date.fromisoformat(purchase_date), status=data.get("status", "good"), notes=data.get("notes"),
        )
        db.session.add(tool)
        db.session.commit()
        return jsonify({"message": "Tool added."}), 201

    all_tools = Tool.query.filter_by(farmer_id=farmer.id).order_by(Tool.purchase_date.desc()).all()
    return jsonify({"tools": [
        {"id": t.id, "name": t.name, "quantity": t.quantity, "cost": t.cost, "status": t.status,
         "purchase_date": t.purchase_date.isoformat() if t.purchase_date else None}
        for t in all_tools
    ]})


@api_bp.route("/tools/<int:tool_id>/status", methods=["POST"])
@farmer_required
def update_tool_status(tool_id):
    tool = Tool.query.filter_by(id=tool_id, farmer_id=g.current_farmer.id).first_or_404()
    data = request.get_json(silent=True) or {}
    tool.status = data.get("status", tool.status)
    db.session.commit()
    return jsonify({"message": "Updated."})


# ---------- Notes ----------

@api_bp.route("/notes", methods=["GET", "POST"])
@farmer_required
def notes():
    farmer = g.current_farmer

    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        content = (data.get("content") or "").strip()
        if not content:
            return jsonify({"error": "Note cannot be empty."}), 400

        note = Note(farmer_id=farmer.id, farm_id=data.get("farm_id"), title=data.get("title") or "Untitled note", content=content)
        db.session.add(note)
        db.session.commit()
        return jsonify({"message": "Note saved."}), 201

    all_notes = Note.query.filter_by(farmer_id=farmer.id).order_by(Note.created_at.desc()).all()
    return jsonify({"notes": [
        {"id": n.id, "title": n.title, "content": n.content, "created_at": n.created_at.isoformat()}
        for n in all_notes
    ]})


@api_bp.route("/notes/<int:note_id>", methods=["DELETE", "POST"])
@farmer_required
def delete_note(note_id):
    note = Note.query.filter_by(id=note_id, farmer_id=g.current_farmer.id).first_or_404()
    db.session.delete(note)
    db.session.commit()
    return jsonify({"message": "Deleted."})


# ---------- Chatbot ----------

@api_bp.route("/chatbot/ask", methods=["POST"])
@farmer_required
def chatbot_ask():
    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    if not message.strip():
        return jsonify({"reply": "Please type a question."})
    return jsonify({"reply": get_bot_reply(message, farmer=g.current_farmer)})
