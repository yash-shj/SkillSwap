# SkillSwap Monolith

SkillSwap is a web application for exchanging knowledge instead of money. Users
list the skills they can teach and the skills they want to learn, discover
people with a two-way skill match, and schedule a learning session.

This branch documents and runs the **monolithic architecture**. The browser,
Flask routes, business logic, HTML rendering, and SQLite access are part of one
Python application and one deployable process.

## Common functionality

The application contains three user-facing functions.

### User and skills profiles

Users can create an account with a name, unique email address, and password of
at least six characters. After logging in, each user maintains two comma-
separated skill lists:

- Skills they can teach
- Skills they want to learn

Skills are trimmed, converted to lowercase, deduplicated, sorted, and stored as
JSON arrays. Passwords are stored as Werkzeug password hashes, never as plain
text. Flask sessions keep track of the authenticated user.

### Mutual matchmaking

The Matches page compares the signed-in user with every other user. A match is
shown only when both exchanges are possible:

```text
you can learn = your offered skills intersect their wanted skills
they can learn = their offered skills intersect your wanted skills
```

Both intersections must be non-empty. Each result includes the two skill groups
and an exchange score equal to the total number of matching skills. Results are
sorted by score in descending order.

### Session scheduling

An authenticated user can choose another registered user and propose a date and
time. Both participants can view the proposal. Only the recipient can accept a
pending proposal, changing its status from `proposed` to `confirmed`.

The scope intentionally excludes payments, ratings, chat, notifications, and
calendar integration.

## Monolith architecture

```text
[ Browser ]
	 |
	 v
[ Flask application :5000 ]
  routes + auth + matching + scheduling + Jinja templates
	 |
	 v
[ SQLite: skillswap.db ]
```

All requests are handled by `app.py`. Flask renders the HTML templates directly
and reads or writes the SQLite database in the same process. This architecture
is simple to run and understand, but all three functions share one deployment
unit: a failure or restart of the process affects the whole application.

### Project structure

```text
SkillsSwap/
├── app.py                 # Flask routes, logic, authentication, DB access
├── requirements.txt       # Flask dependency
├── static/style.css       # Shared application styles
└── templates/
	├── base.html          # Shared layout and navigation
	├── auth.html          # Authentication layout
	├── login.html         # Login form
	├── signup.html        # Registration form
	├── profile.html       # Skill profile form
	├── matches.html       # Match results
	└── schedule.html      # Session proposals
```

## Web routes

These are server-rendered Flask routes, not separate REST services. Routes marked
as protected require a logged-in user; unauthenticated requests redirect to
`/login`.

| Method | Path | Auth | Behavior |
|---|---|---|---|
| `GET` | `/` | No | Redirects to `/profile` when signed in, otherwise `/login` |
| `GET`, `POST` | `/signup` | No | Displays registration and creates a user |
| `GET`, `POST` | `/login` | No | Displays login and creates the Flask session |
| `GET` | `/logout` | No | Clears the current session |
| `GET`, `POST` | `/profile` | Yes | Displays or updates the signed-in user's skills |
| `GET` | `/matches` | Yes | Calculates and displays mutual matches |
| `GET`, `POST` | `/sessions` | Yes | Displays proposals or creates a new proposal |
| `POST` | `/sessions/<session_id>/accept` | Yes | Confirms a proposal for its recipient |

## Database

SQLite is built into Python, so no database server installation is required.
When `app.py` is imported, `init_db()` creates `skillswap.db` and the required
tables if they do not already exist.

### `users`

| Column | Purpose |
|---|---|
| `id` | Auto-incrementing primary key |
| `name` | Display name |
| `email` | Unique login email |
| `password_hash` | Werkzeug-generated password hash |
| `offered_skills` | JSON array of normalized skills |
| `wanted_skills` | JSON array of normalized skills |
| `created_at` | Account creation timestamp |

### `sessions`

| Column | Purpose |
|---|---|
| `id` | Auto-incrementing primary key |
| `proposer_id` | Foreign key to the proposing user |
| `recipient_id` | Foreign key to the receiving user |
| `proposed_time` | Submitted date/time text |
| `status` | `proposed` or `confirmed` |
| `created_at` | Proposal creation timestamp |

The application uses parameterized SQLite queries and joins the `sessions` table
to `users` to display participant names. To reset local data, stop the server
and delete `skillswap.db`; it will be recreated on the next startup.

## Run locally

From the project root, create the virtual environment once and install the
project dependency:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On later runs, only activation is needed:

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The monolith runs with
Flask debug mode enabled by the `app.py` entry point.

To stop the server, press `Ctrl+C` in the terminal where it is running.

If PowerShell blocks activation, run this once for your Windows user and then
activate the environment again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Configuration and checks

The secret key is read from `SECRET_KEY`. The fallback is suitable only for
local development:

```powershell
$env:SECRET_KEY = "replace-with-a-long-random-value"
python app.py
```

Useful checks, run with the virtual environment active:

```powershell
python -m py_compile app.py
(Invoke-WebRequest http://127.0.0.1:5000/ -UseBasicParsing).StatusCode
```

The second command should return `200` while the server is running. The Flask
development server and debug mode should not be used for production deployment.
For production, use a WSGI server, a managed database, CSRF protection, and
stronger validation and authorization controls.

Do not commit `.venv/`, `skillswap.db`, `__pycache__/`, or secrets.
