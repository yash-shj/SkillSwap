import os
from functools import wraps
from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "microservices-development-secret")
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://user-service:5001")
PUBLIC = Path(__file__).parent / "public"


def required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify(error="Authentication required"), 401
        return view(*args, **kwargs)
    return wrapped


def fetch_users():
    response = requests.get(f"{USER_SERVICE_URL}/api/users", timeout=3)
    response.raise_for_status()
    return response.json()["users"]


@app.get("/")
def home():
    return send_from_directory(PUBLIC, "index.html")


@app.get("/health")
def health():
    try:
        users = fetch_users()
        return jsonify(status="ok", service="matchmaking-service", user_service="connected", users_available=len(users))
    except requests.RequestException:
        return jsonify(status="degraded", service="matchmaking-service", user_service="unavailable"), 503


@app.get("/api/matches")
@required
def matches():
    current_id = session["user_id"]
    try:
        users = fetch_users()
    except requests.RequestException as error:
        return jsonify(error=f"User Service unavailable: {error}"), 503
    current = next((user for user in users if user["id"] == current_id), None)
    if current is None:
        return jsonify(error="Current user not found"), 404
    current_offered, current_wanted = set(current["offered_skills"]), set(current["wanted_skills"])
    results = []
    for other in users:
        if other["id"] == current_id:
            continue
        you_can_learn = sorted(current_offered & set(other["wanted_skills"]))
        they_can_learn = sorted(set(other["offered_skills"]) & current_wanted)
        if you_can_learn and they_can_learn:
            results.append({"user": {"id": other["id"], "name": other["name"]}, "you_can_learn": you_can_learn, "they_can_learn": they_can_learn, "score": len(you_can_learn) + len(they_can_learn)})
    results.sort(key=lambda result: result["score"], reverse=True)
    return jsonify(matches=results, source="User Service API")


@app.get("/api/matches/<int:user_id>")
def matches_for_user(user_id):
    with app.test_request_context():
        pass
    try:
        users = fetch_users()
    except requests.RequestException as error:
        return jsonify(error=str(error)), 503
    current = next((user for user in users if user["id"] == user_id), None)
    if not current:
        return jsonify(error="User not found"), 404
    current_offered, current_wanted = set(current["offered_skills"]), set(current["wanted_skills"])
    results = []
    for other in users:
        if other["id"] != user_id:
            learn = sorted(current_offered & set(other["wanted_skills"]))
            teach = sorted(set(other["offered_skills"]) & current_wanted)
            if learn and teach:
                results.append({"user_id": other["id"], "score": len(learn) + len(teach), "you_can_learn": learn, "they_can_learn": teach})
    return jsonify(matches=sorted(results, key=lambda item: item["score"], reverse=True))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
