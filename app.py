import json
import os
import sqlite3
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "skillswap.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            offered_skills TEXT NOT NULL DEFAULT '[]',
            wanted_skills TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposer_id INTEGER NOT NULL,
            recipient_id INTEGER NOT NULL,
            proposed_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'proposed',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (proposer_id) REFERENCES users (id),
            FOREIGN KEY (recipient_id) REFERENCES users (id)
        );
        """
    )
    db.commit()


def skills_from_json(value):
    try:
        return json.loads(value or "[]")
    except json.JSONDecodeError:
        return []


def skills_from_form(value):
    return sorted({skill.strip().lower() for skill in value.split(",") if skill.strip()})


def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(**kwargs)

    return wrapped_view


@app.before_request
def load_logged_in_user():
    user_id = session.get("user_id")
    g.user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone() if user_id else None


@app.context_processor
def inject_helpers():
    return {"skills_from_json": skills_from_json}


@app.route("/")
def index():
    return redirect(url_for("profile" if g.user else "login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not name or not email or len(password) < 6:
            flash("Enter your name, a valid email, and a password of at least 6 characters.", "error")
            return render_template("signup.html")

        try:
            db = get_db()
            db.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "error")
            return render_template("signup.html")

        flash("Account created. You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (request.form["email"].strip().lower(),)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("profile"))
        flash("Email or password is incorrect.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        offered = skills_from_form(request.form.get("offered_skills", ""))
        wanted = skills_from_form(request.form.get("wanted_skills", ""))
        db = get_db()
        db.execute(
            "UPDATE users SET offered_skills = ?, wanted_skills = ? WHERE id = ?",
            (json.dumps(offered), json.dumps(wanted), g.user["id"]),
        )
        db.commit()
        flash("Your skills have been updated.", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", title="My profile")


@app.route("/matches")
@login_required
def matches():
    current_offered = set(skills_from_json(g.user["offered_skills"]))
    current_wanted = set(skills_from_json(g.user["wanted_skills"]))
    users = get_db().execute("SELECT * FROM users WHERE id != ?", (g.user["id"],)).fetchall()
    results = []

    for user in users:
        other_offered = set(skills_from_json(user["offered_skills"]))
        other_wanted = set(skills_from_json(user["wanted_skills"]))
        you_can_learn = current_offered & other_wanted
        they_can_learn = other_offered & current_wanted
        if you_can_learn and they_can_learn:
            results.append({
                "user": user,
                "you_can_learn": sorted(you_can_learn),
                "they_can_learn": sorted(they_can_learn),
                "score": len(you_can_learn) + len(they_can_learn),
            })

    results.sort(key=lambda item: item["score"], reverse=True)
    return render_template("matches.html", title="Mutual matches", matches=results)


@app.route("/sessions", methods=["GET", "POST"])
@login_required
def scheduling():
    db = get_db()
    if request.method == "POST":
        recipient_id = request.form.get("recipient_id", type=int)
        proposed_time = request.form["proposed_time"].strip()
        recipient = db.execute("SELECT id FROM users WHERE id = ?", (recipient_id,)).fetchone()
        if recipient and proposed_time:
            db.execute(
                "INSERT INTO sessions (proposer_id, recipient_id, proposed_time) VALUES (?, ?, ?)",
                (g.user["id"], recipient_id, proposed_time),
            )
            db.commit()
            flash("Session proposal sent.", "success")
        else:
            flash("Choose a match and provide a time.", "error")
        return redirect(url_for("scheduling"))

    proposals = db.execute(
        """
        SELECT sessions.*, proposer.name AS proposer_name, recipient.name AS recipient_name
        FROM sessions
        JOIN users AS proposer ON proposer.id = sessions.proposer_id
        JOIN users AS recipient ON recipient.id = sessions.recipient_id
        WHERE proposer_id = ? OR recipient_id = ?
        ORDER BY proposed_time
        """,
        (g.user["id"], g.user["id"]),
    ).fetchall()
    other_users = db.execute("SELECT id, name FROM users WHERE id != ? ORDER BY name", (g.user["id"],)).fetchall()
    return render_template("schedule.html", title="Schedule a swap", proposals=proposals, other_users=other_users)


@app.post("/sessions/<int:session_id>/accept")
@login_required
def accept_session(session_id):
    db = get_db()
    db.execute(
        "UPDATE sessions SET status = 'confirmed' WHERE id = ? AND recipient_id = ?",
        (session_id, g.user["id"]),
    )
    db.commit()
    flash("Session confirmed.", "success")
    return redirect(url_for("scheduling"))


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
