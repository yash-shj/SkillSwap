# SkillSwap

SkillSwap is a small web application where people exchange knowledge instead of
money. A user describes the skills they can teach and the skills they want to
learn. The application finds compatible users and lets them propose and confirm
skill-swap sessions.

The project deliberately implements three core functions:

1. **User and skills profiles**: create an account, sign in, and maintain lists
	of offered and wanted skills.
2. **Mutual matchmaking**: find users where both sides can teach something the
	other person wants to learn.
3. **Session scheduling**: send a proposed session time to another user and
	accept the proposal to confirm the session.

There are no payments, ratings, notifications, chat, or calendar integrations.
Keeping the scope small makes the three core functions easy to demonstrate and
provides a clear starting point for a future service-oriented version.

## Technology

- **Backend**: Python and Flask 3.1
- **Frontend**: server-rendered Jinja templates with HTML and CSS
- **Database**: SQLite, created automatically as `skillswap.db`
- **Authentication**: Flask sessions and Werkzeug password hashing
- **Runtime**: Python 3.13 or another supported Python 3 version

The application is currently a monolith: routes, business logic, templates, and
database access run in one Flask process. This is appropriate for the current
MVP and keeps the complete workflow straightforward to run locally.

## Project structure

```text
SkillsSwap/
├── app.py                              # Flask application and route logic
├── requirements.txt                    # Python dependencies
├── README.md                           # Project documentation
├── DevOps_IA_SkillSwap_Guide_3Functions.md
├── static/
│   └── style.css                       # Application styles
└── templates/
	 ├── base.html                       # Shared layout and navigation
	 ├── auth.html                       # Shared authentication layout
	 ├── login.html                      # Sign-in form
	 ├── signup.html                     # Registration form
	 ├── profile.html                    # Offered and wanted skills
	 ├── matches.html                    # Mutual match results
	 └── schedule.html                   # Session proposals
```

## Run locally

From the project directory, create or activate the virtual environment and
install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Start the development server:

```powershell
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser. The server
runs with Flask debug mode enabled by the `app.py` entry point.

To stop it, press `Ctrl+C` in the terminal running the server.

### PowerShell execution policy

If PowerShell prevents the activation script from running, either activate the
environment in another shell or allow locally created scripts for your user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then run the activation command again.

## Using the application

### 1. Create an account

Open **Sign up** and provide a name, email address, and password of at least six
characters. Email addresses are stored in lowercase and must be unique.

### 2. Complete your profile

After signing in, enter comma-separated values for:

- **Skills I can teach**
- **Skills I want to learn**

Skills are trimmed, converted to lowercase, deduplicated, and stored as JSON in
the user record. For example:

```text
Skills I can teach: Python, public speaking
Skills I want to learn: graphic design, guitar
```

### 3. Find a mutual match

The **Matches** page compares your profile with every other user. A person is a
match only when both conditions are true:

```text
your offered skills ∩ their wanted skills is not empty
their offered skills ∩ your wanted skills is not empty
```

The results show the skills you can learn, the skills they can learn, and a
score. The score is the total number of shared skills in both directions, and
matches are sorted from highest score to lowest.

For a useful demonstration, create two accounts with complementary profiles.
For example, one user can offer Python and want guitar, while the other offers
guitar and wants Python.

### 4. Propose and confirm a session

On **Schedule**, choose another user, enter a proposed time, and submit the
proposal. Both participants can see the proposal. Only the recipient can use
the confirmation action, which changes its status from `proposed` to
`confirmed`.

## Application routes

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Redirect to the profile when signed in, otherwise to login |
| `GET`, `POST` | `/signup` | Display registration and create a user |
| `GET`, `POST` | `/login` | Display login and authenticate a user |
| `GET` | `/logout` | End the current session |
| `GET`, `POST` | `/profile` | View and update offered and wanted skills |
| `GET` | `/matches` | Display mutual matches |
| `GET`, `POST` | `/sessions` | View and create session proposals |
| `POST` | `/sessions/<session_id>/accept` | Confirm a received proposal |

Profile, match, and scheduling routes require an authenticated user. Unauthenticated
requests are redirected to `/login` with an explanatory message.

## Database

The first application import initializes the SQLite database if it does not yet
exist. The database contains two tables:

### `users`

Stores the account identity and skill profile. `offered_skills` and
`wanted_skills` contain JSON arrays such as `["python", "public speaking"]`.

### `sessions`

Stores a proposer, recipient, proposed time, status, and creation timestamp.
The default status is `proposed`; accepting a proposal changes it to
`confirmed`.

To start over with an empty local database, stop the server and delete
`skillswap.db`. It will be recreated automatically the next time the app starts.

## Development checks

Check that the application has no Python syntax errors:

```powershell
python -m py_compile app.py
```

You can also verify that Flask responds while the server is running:

```powershell
(Invoke-WebRequest http://127.0.0.1:5000/ -UseBasicParsing).StatusCode
```

The expected response is `200`.

## Configuration and security notes

The Flask secret key is read from the `SECRET_KEY` environment variable. If it
is not set, the app uses a development-only fallback. Set a strong secret key
before deploying anywhere beyond local development:

```powershell
$env:SECRET_KEY = "replace-with-a-long-random-value"
python app.py
```

The built-in Flask server and debug mode are for development only. A production
deployment should use a production WSGI server, disable debug mode, use a
managed database, and add CSRF protection, stronger input validation, and
appropriate authorization and privacy controls.

Do not commit `.venv/`, `skillswap.db`, or secrets to version control.

## Future architecture direction

The accompanying `DevOps_IA_SkillSwap_Guide_3Functions.md` describes how this
MVP can evolve from a monolith into a three-tier application and eventually
three isolated services:

- Profile service for accounts and skills
- Matchmaking service for compatibility calculations
- Scheduling service for session proposals

The current implementation keeps these responsibilities in `app.py`, while
the route boundaries and the pure set-intersection matching rule provide clear
boundaries for a later decomposition.
