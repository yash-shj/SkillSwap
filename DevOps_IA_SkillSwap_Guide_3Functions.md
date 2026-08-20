# DevOps IA Project: SkillSwap (Scoped to 3 Core Functions)

## 1. Project Idea — Simplified Scope

**SkillSwap** lets users trade skills instead of money. To keep the build manageable, the app is scoped to exactly **3 functions**, which map 1:1 onto 3 microservices later — this makes the architecture story very clean to present.

| # | Function | What it does |
|---|---|---|
| 1 | **User & Skills Profile** | Sign up, log in, list skills you offer and skills you want |
| 2 | **Matchmaking** | View mutual matches — users whose offered skills match your wanted skills, and vice versa |
| 3 | **Session Scheduling** | Propose a swap session time with a match, and accept/confirm it |

That's the entire app. No ratings, no notifications, no payments — every extra feature was cut so the 3 functions map exactly to 3 tiers/services with nothing left over.

---

## 2. Recommended Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | HTML/CSS/JS (or React) | Easy to split into per-service pages later |
| Backend | Node.js + Express (or Python Flask) | Fast to scaffold, easy to explain in a viva |
| Database | MySQL for users; MongoDB for match results | Shows polyglot persistence in the microservices phase without overcomplicating |
| Containerization | Docker + Docker Compose | Lets you run and demo isolated services |
| Gateway | Simple Express reverse-proxy or Nginx | Single entry point for the 3 microservices |

---

## 3. The Matching Algorithm (unique technical highlight)

**Rule:** Users A and B are a mutual match if A offers something B wants, *and* B offers something A wants.

```
function findMatches(user):
    candidates = allUsersExcept(user)
    matches = []
    for other in candidates:
        a_to_b = intersect(user.offeredSkills, other.wantedSkills)
        b_to_a = intersect(other.offeredSkills, user.wantedSkills)
        if a_to_b is not empty AND b_to_a is not empty:
            score = len(a_to_b) + len(b_to_a)
            matches.append({ user: other, score, skillsExchanged: [a_to_b, b_to_a] })
    return sortByScoreDescending(matches)
```

This is pure logic with no UI/DB concerns — which is exactly why it becomes its own isolated Matchmaking Service in Stage 3.

---

## 4. Stage 1 — Monolithic Application

**Definition:** One deployable unit where UI rendering, business logic (auth, matching, scheduling), and database access all live in one codebase and one process.

### Folder structure
```
skillswap-monolith/
├── views/            # profile.ejs, matches.ejs, schedule.ejs
├── routes/           # auth, matching, scheduling — all mixed here
├── models/
├── app.js            # single entry point
├── package.json
└── skillswap.db
```

### Implementation steps
1. `npm init -y && npm install express ejs mysql2 body-parser bcrypt`
2. One `users` table holding offered/wanted skills (JSON column is fine).
3. Each of the 3 functions gets one route file, but all three run in the same process:
```js
// routes/profile.js — Function 1
app.post('/signup', ...);
app.post('/skills', ...);

// routes/matches.js — Function 2
app.get('/matches', async (req, res) => {
  const matches = findMatches(currentUser, allUsers);
  res.render('matches', { matches });
});

// routes/schedule.js — Function 3
app.post('/sessions', ...);
app.post('/sessions/:id/accept', ...);
```
4. Run as a single process on one port (e.g., `node app.js` on :3000).

### What to highlight
- All 3 functions ship, scale, and can fail together — a bug in scheduling can crash matchmaking too.
- Simple and fast to build for a 3-function MVP, but that simplicity is the exact thing you're about to trade away for isolation.

---

## 5. Stage 2 — Three-Tier Architecture

**Definition:** Split into presentation, application, and database tiers, each independently deployable.

### Architecture diagram
```
[ Browser/Frontend ]  --HTTP-->  [ Express API Server ]  --SQL-->  [ MySQL DB Server ]
   (Presentation)                (Application: all 3               (Database)
                                   functions' logic)
```

### Folder structure
```
skillswap-3tier/
├── frontend/          # calls REST API only, no logic
│   └── src/
├── backend/           # all 3 functions' logic, still one server
│   ├── routes/
│   │   ├── profile.js
│   │   ├── matches.js
│   │   └── sessions.js
│   └── server.js
└── database/
    └── init.sql       # users, skills, sessions tables
```

### Implementation steps
1. **Frontend**: rebuild the 3 pages (profile, matches, schedule) as pure client-side views calling `fetch('/api/matches')`, `fetch('/api/sessions')`, etc.
2. **Backend**: expose 3 REST route groups, one per function, but still a single deployable server:
```js
app.get('/api/matches', authMiddleware, async (req, res) => {
  res.json(await getMatchesFor(req.user.id));
});
```
3. **Database**: MySQL runs as its own container, reachable only by the backend.
4. `docker-compose.yml`:
```yaml
services:
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
  backend:
    build: ./backend
    ports: ["4000:4000"]
    depends_on: [database]
  database:
    image: mysql:8
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: skillswap
```

### What to highlight
- Presentation, application, and database now scale/redeploy independently.
- All 3 functions' logic is centralized in one application tier — easier to secure and test than the monolith, but a bug in one function's route can still crash the whole API server.

---

## 6. Stage 3 — Microservices Architecture

**Definition:** Each of the 3 functions becomes its own independently deployable service with its **own GUI, own logic, and own database**.

### Service mapping (clean 1:1 with the 3 functions)

| Function | Service | Own GUI | Own Database |
|---|---|---|---|
| 1. User & Skills Profile | **User Service** | Signup/login/profile page | MySQL (users + skills) |
| 2. Matchmaking | **Matchmaking Service** | Matches browsing page | MongoDB (cached match results) |
| 3. Session Scheduling | **Scheduling Service** | Propose/accept session page | MySQL or SQLite (sessions) |

### Architecture diagram
```
                     ┌────────────────────┐
                     │   API Gateway /     │
                     │   Nginx             │
                     └─────────┬───────────┘
              ┌───────────────┼───────────────┐
              ▼                ▼               ▼
       [User Service]   [Matchmaking]   [Scheduling]
         own GUI           own GUI        own GUI
         own logic         own logic      own logic
         MySQL             MongoDB        MySQL/SQLite
```

### Folder structure
```
skillswap-microservices/
├── gateway/
├── user-service/
│   ├── public/ (signup/profile page)
│   ├── routes/, models/
│   └── Dockerfile
├── matchmaking-service/
│   ├── public/ (matches page)
│   ├── routes/, matchController.js
│   └── Dockerfile
├── scheduling-service/
│   ├── public/ (schedule page)
│   ├── routes/, models/
│   └── Dockerfile
└── docker-compose.yml
```

### Implementation steps
1. Move `findMatches()` into its own **Matchmaking Service**. It cannot query User Service's MySQL directly — it calls `GET /users/:id/skills` on User Service's API instead. This is the core microservices lesson: **no shared databases.**
2. Each service serves its own small frontend page from its own port — User:5001, Matchmaking:5002, Scheduling:5003 — satisfying the "own GUI" requirement.
3. **Gateway** routes `/users/*` → User Service, `/matches/*` → Matchmaking Service, `/sessions/*` → Scheduling Service, and also serves one combined landing page linking to all 3 for your demo.
4. Scheduling Service, when confirming a session, calls Matchmaking/User Service APIs only if it needs data — never their databases.
5. `docker-compose.yml`:
```yaml
services:
  gateway:
    build: ./gateway
    ports: ["8080:8080"]
  user-service:
    build: ./user-service
    ports: ["5001:5001"]
  matchmaking-service:
    build: ./matchmaking-service
    ports: ["5002:5002"]
  scheduling-service:
    build: ./scheduling-service
    ports: ["5003:5003"]
```

### What to highlight
- 3 functions → 3 services, each independently deployable, scalable, and replaceable.
- If Scheduling Service goes down, users can still sign up and view matches — fault isolation.
- Trade-off for depth: Matchmaking Service now needs a network call to User Service to fetch skills, which didn't exist in the monolith — added latency and a new failure mode in exchange for isolation.

---

## 7. Comparison Table

| Aspect | Monolithic | Three-Tier | Microservices |
|---|---|---|---|
| Deployment unit | 1 | 3 | 3 (one per function) |
| Database | 1 shared | 1 shared, isolated from UI | 1 per service (polyglot) |
| Function isolation | None | Logical only | Physical (separate processes) |
| Scaling | Whole app at once | Per tier | Per service |
| Fault isolation | None | Partial | Strong |
| Complexity | Low | Medium | Medium-High |

---

## 8. Presentation Tips (Individual Performance marks)

- Tell it as one story across 3 stages: "Same 3 functions — profile, matching, scheduling — rebuilt 3 times. Watch: monolith crashes as one unit; three-tier lets me restart the API without losing data; microservices lets me kill Scheduling and Matchmaking keeps working."
- Be ready to explain the matching algorithm from memory — your strongest differentiator.
- Have one precise definition per stage ready in case you're asked cold.
- Volunteer the trade-off (added latency/complexity in microservices) — shows depth beyond just praising the "better" architecture.

---

## 9. Submission Checklist

- [ ] Monolith code (all 3 functions) + demo screenshot
- [ ] Three-tier code (3 containers: frontend/backend/DB) + docker-compose
- [ ] Microservices code (3 services + gateway) + docker-compose
- [ ] Architecture diagrams for all three stages
- [ ] Comparison table/write-up
- [ ] Submitted on the allocated day
