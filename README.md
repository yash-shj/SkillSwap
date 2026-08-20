# SkillSwap Microservices Architecture

SkillSwap is a web application for exchanging knowledge instead of money. Users
list the skills they can teach and the skills they want to learn, discover
people with a two-way skill match, and schedule a learning session.

This branch implements the **microservices architecture**. The three core
functions are split into three independently deployable services. An Nginx API
gateway provides one entry point for the demonstration.

```text
                              [ Browser ]
                                   |
                                   v
                         [ Nginx API Gateway :8080 ]
                           /            |            \
                          v             v             v
                [ User Service ] [ Matchmaking ] [ Scheduling ]
                    :5001             :5002          :5003
                    SQLite            API only       SQLite
```

Each service owns its GUI, business logic, runtime process, and data boundary.
The services never read another service's database directly. When a service
needs data owned by another service, it calls that service's HTTP API.

## Common functionality

The application contains three user-facing functions.

### User and skills profiles

Users can create an account with a name, unique email address, and password of
at least six characters. After logging in, each user maintains two comma-
separated skill lists:

- Skills they can teach
- Skills they want to learn

Skills are trimmed, converted to lowercase, deduplicated, sorted, and stored as
JSON arrays. Passwords are stored as Werkzeug password hashes. A signed Flask
session cookie identifies the logged-in user across the gateway and services.

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

The Matchmaking Service does not access the User Service database. It requests
profiles from `GET /api/users` on the User Service, calculates the intersections
locally, and returns the match results.

### Session scheduling

An authenticated user can choose another registered user and propose a date and
time. Both participants can view the proposal. Only the recipient can accept a
pending proposal, changing its status from `proposed` to `confirmed`.

The Scheduling Service stores session records in its own SQLite database. It
calls User Service to validate recipients and resolve participant names. It
never reads the User Service database file.

The scope intentionally excludes payments, ratings, chat, notifications, and
calendar integration.

## Service responsibilities

### 1. User Service

Location: `microservices/user-service/`

Responsibilities:

- Signup, login, logout, and session management
- Profile creation and skill updates
- Password hashing and credential verification
- The source of truth for users and skills
- Its own browser interface at `/`
- Its own SQLite database at `/data/users.db`

The User Service is the only service allowed to access user account data. Other
services use its internal API instead.

### 2. Matchmaking Service

Location: `microservices/matchmaking-service/`

Responsibilities:

- Fetches user profiles from User Service over HTTP
- Calculates mutual skill intersections
- Sorts matches by exchange score
- Provides its own matches interface at `/`
- Has no shared database and does not persist user records

This service demonstrates the key microservices boundary: matchmaking depends on
an API contract, not a shared database connection.

### 3. Scheduling Service

Location: `microservices/scheduling-service/`

Responsibilities:

- Fetches valid users from User Service over HTTP
- Creates and lists session proposals
- Allows only the recipient to confirm a proposal
- Provides its own scheduling interface at `/`
- Stores only scheduling data in its own SQLite database at `/data/sessions.db`

### 4. API Gateway

Location: `gateway/`

The Nginx gateway is the public entry point on port `8080`:

| Public path | Destination |
|---|---|
| `/` | Gateway landing page |
| `/users/*` | User Service |
| `/matches/*` | Matchmaking Service |
| `/sessions/*` | Scheduling Service |
| `/health` | Gateway health response |

The gateway routes requests and serves the combined landing page. It does not
contain profile, matching, or scheduling business logic.

## Service APIs

The gateway prefixes each service's browser/API path. Inside the Docker network,
services call each other using their Compose service names.

### User Service API

Base URL inside Compose: `http://user-service:5001`

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/health` | No | Service and database health |
| `POST` | `/api/signup` | No | Creates an account |
| `POST` | `/api/login` | No | Verifies credentials and creates session |
| `POST` | `/api/logout` | No | Clears the session |
| `GET` | `/api/me` | Yes | Returns the current user's profile |
| `PUT` | `/api/profile` | Yes | Updates offered and wanted skills |
| `GET` | `/api/users` | No | Returns profiles for internal consumers |
| `GET` | `/api/users/<id>` | No | Returns one profile for internal consumers |

### Matchmaking Service API

Base URL inside Compose: `http://matchmaking-service:5002`

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/health` | No | Checks the service and User Service dependency |
| `GET` | `/api/matches` | Yes | Returns matches for the signed-in user |
| `GET` | `/api/matches/<user_id>` | No | Calculates matches for an internal/demo request |

A successful `/api/matches` response includes `matches` and identifies the
source as the User Service API. A `503` response indicates that User Service is
unavailable.

### Scheduling Service API

Base URL inside Compose: `http://scheduling-service:5003`

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/health` | No | Checks scheduling DB and User Service dependency |
| `GET` | `/api/users` | Yes | Lists valid recipients from User Service |
| `GET` | `/api/sessions` | Yes | Lists sessions involving the current user |
| `POST` | `/api/sessions` | Yes | Creates a session proposal |
| `POST` | `/api/sessions/<id>/accept` | Yes | Confirms a pending session as recipient |

Validation errors generally return `400`, missing authentication returns `401`,
duplicate signup emails return `409`, and unauthorized acceptance returns `403`.
Dependency failures return `503`.

## Databases and data ownership

The microservices version intentionally uses database-per-service ownership.

### User Service database: `users.db`

Stored in the `user_service_data` Docker volume.

| Column | Purpose |
|---|---|
| `id` | User primary key |
| `name` | Display name |
| `email` | Unique login email |
| `password_hash` | Werkzeug password hash |
| `offered_skills` | JSON array of normalized skills |
| `wanted_skills` | JSON array of normalized skills |
| `created_at` | Account creation timestamp |

### Scheduling Service database: `sessions.db`

Stored in the `scheduling_service_data` Docker volume.

| Column | Purpose |
|---|---|
| `id` | Session primary key |
| `proposer_id` | User ID from User Service |
| `recipient_id` | User ID from User Service |
| `proposed_time` | Submitted date/time text |
| `status` | `proposed` or `confirmed` |
| `created_at` | Proposal creation timestamp |

Matchmaking has no database in this implementation. It calculates results from
fresh User Service API data on each request. This avoids a shared database and
keeps the ownership boundary explicit.

## Project structure

```text
SkillsSwap/
├── docker-compose.yml
├── gateway/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── index.html
├── microservices/
│   ├── user-service/
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── public/index.html
│   ├── matchmaking-service/
│   │   ├── app.py
│   │   ├── requirements.txt
│   │   ├── Dockerfile
│   │   └── public/index.html
│   └── scheduling-service/
│       ├── app.py
│       ├── requirements.txt
│       ├── Dockerfile
│       └── public/index.html
└── README.md
```

## Run the microservices application

Docker Desktop must be running. From the project root:

```powershell
git switch microservices
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080) for the gateway landing
page. The services are also published individually for demonstration and
troubleshooting:

| Service | Local address | Role |
|---|---|---|
| Gateway | `http://localhost:8080` | Public entry point and service links |
| User Service | `http://localhost:5001` | Profile GUI and API |
| Matchmaking Service | `http://localhost:5002` | Matches GUI and API |
| Scheduling Service | `http://localhost:5003` | Scheduling GUI and API |

To demonstrate the complete workflow:

1. Open Users and create two accounts.
2. Give the users complementary offered and wanted skills.
3. Save both profiles and log in as one user.
4. Open Matches and verify the two-way match.
5. Open Sessions, propose a time, then log in as the recipient and accept it.

## Stop, restart, and reset

Stop and remove service containers and the gateway while preserving both service
databases:

```powershell
docker compose down
```

Start the existing images again:

```powershell
docker compose up -d
```

Rebuild after code or dependency changes:

```powershell
docker compose up --build -d
```

View status and logs:

```powershell
docker compose ps
docker compose logs --tail=100
docker compose logs user-service matchmaking-service scheduling-service
```

Remove containers and reset all User Service and Scheduling Service data:

```powershell
docker compose down --volumes
```

The `--volumes` option is destructive for local account and session data. The
SQLite files are recreated automatically on the next startup.

## Health checks and failure isolation

Check the gateway and each service directly:

```powershell
(Invoke-WebRequest http://localhost:8080/health -UseBasicParsing).Content
(Invoke-WebRequest http://localhost:5001/health -UseBasicParsing).Content
(Invoke-WebRequest http://localhost:5002/health -UseBasicParsing).Content
(Invoke-WebRequest http://localhost:5003/health -UseBasicParsing).Content
```

The gateway should report `status: ok`. The Matchmaking and Scheduling health
responses should report that User Service is connected.

The architecture also demonstrates fault isolation. For example, stopping
Scheduling does not stop User Service or Matchmaking. Users can still manage
profiles and calculate matches, although session operations are unavailable.
Matchmaking has an explicit API dependency on User Service, so stopping User
Service causes its health check and match calculation to report a dependency
failure instead of silently reading stale shared data.

## Configuration and security notes

Development configuration is in `docker-compose.yml`:

- Shared Flask session secret: development-only value
- User database path: `/data/users.db`
- Scheduling database path: `/data/sessions.db`
- User Service URL: `http://user-service:5001`

Change secrets before any non-local deployment. This educational implementation
uses development credentials, Flask's development server, and open internal
profile APIs for service-to-service calls. A production version should add
service authentication, CSRF protection, stricter authorization, TLS, secret
management, rate limiting, and a production WSGI server.

The microservices branch requires Docker Desktop, but it does not require
system-wide Flask, Requests, or SQLite installations. Dependencies are installed
inside each service image.
