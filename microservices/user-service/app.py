import json
import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, redirect, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "microservices-development-secret")
DATABASE = os.environ.get("DATABASE_PATH", "/data/users.db")
PUBLIC = Path(__file__).parent / "public"


def db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    Path(DATABASE).parent.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            offered_skills TEXT NOT NULL DEFAULT '[]',
            wanted_skills TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)


def user_json(user):
    if not user:
        return None
    result = dict(user)
    result["offered_skills"] = json.loads(result["offered_skills"])
    result["wanted_skills"] = json.loads(result["wanted_skills"])
    result.pop("password_hash", None)
    return result


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    with db() as connection:
        return connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return jsonify(error="Authentication required"), 401
        return view(user, *args, **kwargs)
    return wrapped


def skills(value):
    return sorted({str(item).strip().lower() for item in (value or []) if str(item).strip()})


@app.get("/")
def home():
    return send_from_directory(PUBLIC, "index.html")


@app.get("/health")
def health():
    return jsonify(status="ok", service="user-service", database="sqlite")


@app.post("/api/signup")
def signup():
    payload = request.get_json(silent=True) or {}
    name, email, password = str(payload.get("name", "")).strip(), str(payload.get("email", "")).strip().lower(), str(payload.get("password", ""))
    if not name or not email or len(password) < 6:
        return jsonify(error="Name, email, and a password of at least 6 characters are required"), 400
    try:
        with db() as connection:
            connection.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)", (name, email, generate_password_hash(password)))
    except sqlite3.IntegrityError:
        return jsonify(error="That email is already registered"), 409
    return jsonify(message="Account created"), 201


@app.post("/api/login")
def login():
    payload = request.get_json(silent=True) or {}
    with db() as connection:
        user = connection.execute("SELECT * FROM users WHERE email = ?", (str(payload.get("email", "")).strip().lower(),)).fetchone()
    if not user or not check_password_hash(user["password_hash"], str(payload.get("password", ""))):
        return jsonify(error="Email or password is incorrect"), 401
    session.clear()
    session["user_id"] = user["id"]
    return jsonify(user=user_json(user))


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(message="Logged out")


@app.get("/api/me")
@required
def me(user):
    return jsonify(user=user_json(user))


@app.put("/api/profile")
@required
def profile(user):
    payload = request.get_json(silent=True) or {}
    offered, wanted = skills(payload.get("offered_skills")), skills(payload.get("wanted_skills"))
    with db() as connection:
        connection.execute("UPDATE users SET offered_skills = ?, wanted_skills = ? WHERE id = ?", (json.dumps(offered), json.dumps(wanted), user["id"]))
        updated = connection.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return jsonify(user=user_json(updated))


@app.get("/api/users")
def all_users():
    with db() as connection:
        rows = connection.execute("SELECT id, name, email, offered_skills, wanted_skills FROM users ORDER BY name").fetchall()
    return jsonify(users=[user_json(row) for row in rows])


@app.get("/api/users/<int:user_id>")
def one_user(user_id):
    with db() as connection:
        user = connection.execute("SELECT id, name, email, offered_skills, wanted_skills FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify(error="User not found"), 404
    return jsonify(user=user_json(user))


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
