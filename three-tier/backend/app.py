import json
import os
import time
from functools import wraps

import pymysql
from flask import Flask, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "three-tier-development-secret")


def db_connection():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "skillswap"),
        password=os.environ.get("DB_PASSWORD", "skillswap"),
        database=os.environ.get("DB_NAME", "skillswap"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def with_db(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        connection = db_connection()
        try:
            return view(connection, *args, **kwargs)
        finally:
            connection.close()

    return wrapped


def current_user(connection):
    user_id = session.get("user_id")
    if not user_id:
        return None
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, name, email, offered_skills, wanted_skills FROM users WHERE id = %s",
            (user_id,),
        )
        user = cursor.fetchone()
    if user:
        user["offered_skills"] = json.loads(user["offered_skills"])
        user["wanted_skills"] = json.loads(user["wanted_skills"])
    return user


def login_required(view):
    @wraps(view)
    def wrapped(connection, *args, **kwargs):
        user = current_user(connection)
        if user is None:
            return jsonify(error="Authentication required"), 401
        return view(connection, user, *args, **kwargs)

    return wrapped


def clean_skills(value):
    return sorted({skill.strip().lower() for skill in value if skill.strip()})


@app.get("/api/health")
@with_db
def health(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return jsonify(status="ok", tier="backend", database="connected")


@app.post("/api/auth/signup")
@with_db
def signup(connection):
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not name or not email or len(password) < 6:
        return jsonify(error="Enter a name, email, and password of at least 6 characters"), 400
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (name, email, password_hash, offered_skills, wanted_skills) VALUES (%s, %s, %s, %s, %s)",
                (name, email, generate_password_hash(password), "[]", "[]"),
            )
    except pymysql.err.IntegrityError:
        return jsonify(error="That email is already registered"), 409
    return jsonify(message="Account created"), 201


@app.post("/api/auth/login")
@with_db
def login(connection):
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, password_hash FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Email or password is incorrect"), 401
    session.clear()
    session["user_id"] = user["id"]
    return jsonify(message="Logged in")


@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify(message="Logged out")


@app.get("/api/me")
@with_db
def me(connection):
    user = current_user(connection)
    if user is None:
        return jsonify(error="Authentication required"), 401
    return jsonify(user=user)


@app.put("/api/profile")
@with_db
@login_required
def update_profile(connection, user):
    payload = request.get_json(silent=True) or {}
    offered = clean_skills(payload.get("offered_skills", []))
    wanted = clean_skills(payload.get("wanted_skills", []))
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE users SET offered_skills = %s, wanted_skills = %s WHERE id = %s",
            (json.dumps(offered), json.dumps(wanted), user["id"]),
        )
    user["offered_skills"] = offered
    user["wanted_skills"] = wanted
    return jsonify(user=user)


@app.get("/api/matches")
@with_db
@login_required
def matches(connection, user):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, name, offered_skills, wanted_skills FROM users WHERE id != %s",
            (user["id"],),
        )
        candidates = cursor.fetchall()
    current_offered = set(user["offered_skills"])
    current_wanted = set(user["wanted_skills"])
    results = []
    for candidate in candidates:
        offered = set(json.loads(candidate["offered_skills"]))
        wanted = set(json.loads(candidate["wanted_skills"]))
        you_can_learn = sorted(current_offered & wanted)
        they_can_learn = sorted(offered & current_wanted)
        if you_can_learn and they_can_learn:
            results.append({
                "user": {"id": candidate["id"], "name": candidate["name"]},
                "you_can_learn": you_can_learn,
                "they_can_learn": they_can_learn,
                "score": len(you_can_learn) + len(they_can_learn),
            })
    results.sort(key=lambda item: item["score"], reverse=True)
    return jsonify(matches=results)


@app.get("/api/users")
@with_db
@login_required
def users(connection, user):
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, name FROM users WHERE id != %s ORDER BY name", (user["id"],))
        return jsonify(users=cursor.fetchall())


@app.get("/api/sessions")
@with_db
@login_required
def get_sessions(connection, user):
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT sessions.id, sessions.proposer_id, sessions.recipient_id,
                      sessions.proposed_time, sessions.status,
                      proposer.name AS proposer_name, recipient.name AS recipient_name
               FROM sessions
               JOIN users AS proposer ON proposer.id = sessions.proposer_id
               JOIN users AS recipient ON recipient.id = sessions.recipient_id
               WHERE proposer_id = %s OR recipient_id = %s
               ORDER BY proposed_time""",
            (user["id"], user["id"]),
        )
        return jsonify(sessions=cursor.fetchall())


@app.post("/api/sessions")
@with_db
@login_required
def create_session(connection, user):
    payload = request.get_json(silent=True) or {}
    recipient_id = payload.get("recipient_id")
    proposed_time = str(payload.get("proposed_time", "")).strip()
    if not recipient_id or not proposed_time:
        return jsonify(error="Choose a person and provide a time"), 400
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE id = %s", (recipient_id,))
        recipient = cursor.fetchone()
        if recipient is None or recipient["id"] == user["id"]:
            return jsonify(error="Choose another registered user"), 400
        cursor.execute(
            "INSERT INTO sessions (proposer_id, recipient_id, proposed_time) VALUES (%s, %s, %s)",
            (user["id"], recipient_id, proposed_time),
        )
    return jsonify(message="Session proposal sent"), 201


@app.post("/api/sessions/<int:session_id>/accept")
@with_db
@login_required
def accept_session(connection, user, session_id):
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE sessions SET status = 'confirmed' WHERE id = %s AND recipient_id = %s AND status = 'proposed'",
            (session_id, user["id"]),
        )
        if cursor.rowcount == 0:
            return jsonify(error="Only the recipient can accept a pending proposal"), 403
    return jsonify(message="Session confirmed")


if __name__ == "__main__":
    for attempt in range(30):
        try:
            db_connection().close()
            break
        except pymysql.MySQLError:
            if attempt == 29:
                raise
            time.sleep(2)
    app.run(host="0.0.0.0", port=5000)
