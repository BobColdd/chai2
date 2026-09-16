"""
Token-based auth for the mobile app. The web app uses Flask-Login cookie
sessions, which don't translate to a native client. The mobile app logs in
once, gets a signed token back (itsdangerous — already a Flask dependency),
and sends it as `Authorization: Bearer <token>` on every request after that.
"""

from functools import wraps
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import request, jsonify, g, current_app

TOKEN_SALT = "chai-yako-mobile-token"
TOKEN_MAX_AGE = 60 * 60 * 24 * 60  # 60 days


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=TOKEN_SALT)


def generate_token(farmer_id):
    return _serializer().dumps({"id": farmer_id})


def _decode_token(token):
    try:
        return _serializer().loads(token, max_age=TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def _bearer_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def farmer_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        from app.models import Farmer

        token = _bearer_token()
        data = _decode_token(token) if token else None
        if not data:
            return jsonify({"error": "Unauthorized. Please log in again."}), 401

        farmer = Farmer.query.get(data["id"])
        if not farmer:
            return jsonify({"error": "Unauthorized. Please log in again."}), 401

        g.current_farmer = farmer
        return f(*args, **kwargs)
    return wrapped
