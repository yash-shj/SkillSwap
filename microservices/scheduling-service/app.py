import os
import sqlite3
from functools import wraps
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "microservices-development-secret")
DATABASE = os.environ.get("DATABASE_PATH", "/data/sessions.db")
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://user-service:5001")
PUBLIC = Path(__file__).parent / "public"


def db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    Path(DATABASE).parent.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, proposer_id INTEGER NOT NULL, recipient_id INTEGER NOT NULL, proposed_time TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'proposed', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")


def required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="Authentication required"), 401
        return view(*args, **kwargs)
    return wrapped


def users():
    response = requests.get(f"{USER_SERVICE_URL}/api/users", timeout=3)
    response.raise_for_status()
    return response.json()["users"]


@app.get("/")
def home():
    return send_from_directory(PUBLIC, "index.html")


@app.get("/health")
def health():
    try:
        available_users = len(users())
        return jsonify(status="ok", service="scheduling-service", user_service="connected", users_available=available_users, database="sqlite")
    except requests.RequestException:
        return jsonify(status="degraded", service="scheduling-service", user_service="unavailable"), 503


@app.get("/api/users")
@required
def other_users():
    try:
        current_id = session["user_id"]
        return jsonify(users=[user for user in users() if user["id"] != current_id], source="User Service API")
    except requests.RequestException as error:
        return jsonify(error=str(error)), 503


@app.get("/api/sessions")
@required
def get_sessions():
    current_id = session["user_id"]
    with db() as connection:
        rows = connection.execute("SELECT * FROM sessions WHERE proposer_id = ? OR recipient_id = ? ORDER BY proposed_time", (current_id, current_id)).fetchall()
    try:
        known = {user["id"]: user["name"] for user in users()}
    except requests.RequestException as error:
        return jsonify(error=str(error)), 503
    result = []
    for row in rows:
        item = dict(row)
        item["proposer_name"] = known.get(item["proposer_id"], "Unknown")
        item["recipient_name"] = known.get(item["recipient_id"], "Unknown")
        result.append(item)
    return jsonify(sessions=result, source="Scheduling database + User Service API")


@app.post("/api/sessions")
@required
def create_session():
    payload = request.get_json(silent=True) or {}
    recipient_id = payload.get("recipient_id")
    proposed_time = str(payload.get("proposed_time", "")).strip()
    if not recipient_id or not proposed_time:
        return jsonify(error="Recipient and proposed time are required"), 400
    try:
        valid = {user["id"] for user in users()}
    except requests.RequestException as error:
        return jsonify(error=str(error)), 503
    if recipient_id not in valid or recipient_id == session["user_id"]:
        return jsonify(error="Choose another registered user"), 400
    with db() as connection:
        cursor = connection.execute("INSERT INTO sessions (proposer_id, recipient_id, proposed_time) VALUES (?, ?, ?)", (session["user_id"], recipient_id, proposed_time))
        session_id = cursor.lastrowid
    return jsonify(message="Session proposal sent", session_id=session_id), 201


@app.post("/api/sessions/<int:session_id>/accept")
@required
def accept_session(session_id):
    with db() as connection:
        cursor = connection.execute("UPDATE sessions SET status = 'confirmed' WHERE id = ? AND recipient_id = ? AND status = 'proposed'", (session_id, session["user_id"]))
    if cursor.rowcount == 0:
        return jsonify(error="Only the recipient can accept a pending proposal"), 403
    return jsonify(message="Session confirmed")


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
