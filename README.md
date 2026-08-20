# SkillSwap Three-Tier Architecture

SkillSwap is a web application for exchanging knowledge instead of money. Users
list the skills they can teach and the skills they want to learn, discover
people with a two-way skill match, and schedule a learning session.

This branch implements the **three-tier architecture**. The presentation,
application, and database tiers are separate deployable components:

```text
[ Browser ]
     |
     v
[ Nginx frontend :3000 ] -- /api --> [ Flask backend :4000 ] -- SQL --> [ MySQL :3307 ]
```

The frontend does not connect directly to MySQL. Nginx serves the browser files
and forwards `/api` requests to Flask. Flask owns authentication, business
logic, and database access. MySQL is isolated as its own database container.

## Common functionality

The application contains three user-facing functions.

### User and skills profiles

Users can create an account with a name, unique email address, and password of
at least six characters. After logging in, each user maintains two comma-
separated skill lists:

- Skills they can teach
- Skills they want to learn

Skills are trimmed, converted to lowercase, deduplicated, sorted, and stored as
JSON arrays. Passwords are stored as Werkzeug password hashes. Flask session
cookies identify the logged-in user through the same frontend origin.

### Mutual matchmaking

The Matches view compares the signed-in user with every other user. A match is
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

## Tier responsibilities

### Presentation tier: Nginx and browser frontend

The files in `three-tier/frontend/` provide the browser experience:

- `index.html` defines the authentication and application views.
- `app.js` sends JSON requests with `fetch()` and renders profile, matches, and
  scheduling data.
- `style.css` provides the user interface styling.
- Nginx serves these static files on port `3000`.
- Nginx proxies `/api/*` to the backend service, keeping the browser on one
  origin and allowing the session cookie to work across the UI.

### Application tier: Flask REST API

The files in `three-tier/backend/` provide the application layer:

- `app.py` exposes JSON API endpoints.
- Flask sessions handle login state.
- Werkzeug hashes and verifies passwords.
- Matching logic uses set intersections in Python.
- PyMySQL connects to MySQL using environment variables.
- The backend listens on port `5000` inside its container and is published as
  port `4000` for direct local inspection.

### Database tier: MySQL

The MySQL container owns persistent application data. Its schema is initialized
from `three-tier/database/init.sql`. The database is published as port `3307`
for optional local inspection, but the frontend never accesses this port.

## API endpoints

The frontend calls these backend endpoints through `/api` on the frontend
origin. Protected endpoints require the Flask session created by login.

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/api/health` | No | Checks the API and database connection |
| `POST` | `/api/auth/signup` | No | Creates an account from JSON name, email, and password |
| `POST` | `/api/auth/login` | No | Verifies credentials and creates a session cookie |
| `POST` | `/api/auth/logout` | No | Clears the current session |
| `GET` | `/api/me` | Yes | Returns the signed-in user's profile |
| `PUT` | `/api/profile` | Yes | Updates offered and wanted skill arrays |
| `GET` | `/api/matches` | Yes | Calculates and returns mutual matches |
| `GET` | `/api/users` | Yes | Returns other users for scheduling selection |
| `GET` | `/api/sessions` | Yes | Returns proposals involving the signed-in user |
| `POST` | `/api/sessions` | Yes | Creates a proposal with recipient and time |
| `POST` | `/api/sessions/<id>/accept` | Yes | Confirms a pending proposal as its recipient |

Successful API responses are JSON. Validation errors generally return `400`,
invalid credentials return `401`, duplicate email registration returns `409`,
and unauthorized session acceptance returns `403`.

## Database schema

### `users`

| Column | Purpose |
|---|---|
| `id` | Auto-incrementing primary key |
| `name` | Display name |
| `email` | Unique login email |
| `password_hash` | Werkzeug-generated password hash |
| `offered_skills` | MySQL JSON array of normalized skills |
| `wanted_skills` | MySQL JSON array of normalized skills |
| `created_at` | Account creation timestamp |

### `sessions`

| Column | Purpose |
|---|---|
| `id` | Auto-incrementing primary key |
| `proposer_id` | Foreign key to `users.id` |
| `recipient_id` | Foreign key to `users.id` |
| `proposed_time` | Submitted date/time text |
| `status` | `proposed` or `confirmed` |
| `created_at` | Proposal creation timestamp |

The database is stored in the named Docker volume
`three_tier_mysql_data`. Normal container shutdown preserves this data.

## Project structure

```text
SkillsSwap/
├── docker-compose.yml       # Starts all three tiers
├── three-tier/
│   ├── frontend/
│   │   ├── index.html       # Browser UI
│   │   ├── app.js           # API client and view rendering
│   │   ├── style.css        # Frontend styling
│   │   ├── Dockerfile       # Nginx image
│   │   └── nginx.conf       # Static server and API proxy
│   ├── backend/
│   │   ├── app.py           # Flask API and business logic
│   │   ├── requirements.txt # Flask, PyMySQL, cryptography
│   │   └── Dockerfile       # Python API image
│   └── database/
│       └── init.sql         # MySQL schema
└── README.md
```

## Run the three-tier application

Docker Desktop must be running. From the project root:

```powershell
git switch three-tier
docker compose up --build
```

The first run downloads the MySQL, Python, and Nginx images and builds the two
project images. Open [http://localhost:3000](http://localhost:3000) to use the
application.

The services are available at:

| Service | Local address | Role |
|---|---|---|
| Frontend | `http://localhost:3000` | Main browser application |
| Backend | `http://localhost:4000` | Direct API and health checks |
| MySQL | `localhost:3307` | Optional database inspection |

The recommended user flow is to create two accounts, give them complementary
skills, save both profiles, check Matches, and propose a session from Schedule.

## Stop, restart, and reset

Stop and remove containers while preserving the database volume:

```powershell
docker compose down
```

Start the existing images again:

```powershell
docker compose up -d
```

Rebuild after source or dependency changes:

```powershell
docker compose up --build -d
```

View service status and logs:

```powershell
docker compose ps
docker compose logs --tail=100
docker compose logs backend database
```

Remove containers and reset all MySQL data:

```powershell
docker compose down --volumes
```

The `--volumes` option is destructive for local database data. The schema is
recreated automatically on the next `docker compose up`.

## Configuration and checks

Development values are defined in `docker-compose.yml`:

- Database host: `database`
- Database name: `skillswap`
- Database user/password: `skillswap` / `skillswap`
- MySQL root password: development-only value in Compose
- Flask secret key: development-only value in Compose

Change these values before any non-local deployment and use environment secrets
instead of committing credentials.

Useful checks:

```powershell
docker compose config --quiet
(Invoke-WebRequest http://localhost:3000 -UseBasicParsing).StatusCode
(Invoke-WebRequest http://localhost:3000/api/health -UseBasicParsing).Content
```

The frontend should return `200`, and the health endpoint should report
`status: ok` and `database: connected`. The three-tier branch requires Docker
Desktop; it does not require system-wide Flask, PyMySQL, or MySQL installations.
