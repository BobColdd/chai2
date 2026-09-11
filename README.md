# Chai Yako

Digital farm record-keeping for small- and large-scale tea farmers in Kenya. Farmers
self-register, register one or more farm numbers, and log plucking kilos, pruning activity,
tool/equipment condition, and free-text notes — through a tea-green dashboard with a live
30-day trend chart, a tea-market news feed, a Kericho weather card, and a rule-based farm
assistant chatbot.

This document describes the project **as it currently stands**, including the admin-layer
groundwork (`is_admin`, `LoginActivity`) added on top of the original self-service build, and
the demo-data seed scripts that populate it for testing/demoing.

---

## Table of contents

1. [What this project is](#what-this-project-is)
2. [Architecture overview](#architecture-overview)
3. [Tech stack](#tech-stack)
4. [Data model](#data-model)
5. [Application structure](#application-structure)
6. [Routes / URL map](#routes--url-map)
7. [Authentication & the login-activity log](#authentication--the-login-activity-log)
8. [Local setup](#local-setup)
9. [Environment variables](#environment-variables)
10. [Deploying to Render](#deploying-to-render)
11. [Connecting a custom domain](#connecting-a-custom-domain)
12. [Demo data & seed scripts](#demo-data--seed-scripts)
13. [The admin interface — current state and what's still needed](#the-admin-interface--current-state-and-whats-still-needed)
14. [Known gaps / things intentionally not built yet](#known-gaps--things-intentionally-not-built-yet)
15. [Project structure (file tree)](#project-structure-file-tree)
16. [Glossary of farm terms used in the code](#glossary-of-farm-terms-used-in-the-code)

---

## What this project is

This is **version 1** of Chai Yako: fully self-service. A farmer creates their own account, adds
their own farm(s), and logs their own activity — no factory involvement is required for any of
it. A separate, factory-owned version (farmers registered by an actual tea factory, tallyboys
recording purchases live, official receipts, a factory notice board, a complaints channel to a
manager) is planned as **version 2**, and will only make sense once a real factory is ready to
come on board and operate it. Nothing in this codebase blocks building that later — the two
could even run as separate deployments sharing nothing but the general approach.

## Architecture overview

Chai Yako is a monolithic **Flask** application using the **application factory** pattern
(`create_app()` in `app/__init__.py`), with functionality split into **Blueprints** — one per
concern — rather than one giant routes file:

```
                        ┌─────────────────────┐
                        │      run.py         │   entrypoint (dev + gunicorn)
                        └──────────┬───────────┘
                                   │
                        ┌──────────▼───────────┐
                        │   create_app()       │   app/__init__.py
                        │   - loads Config      │
                        │   - inits db, login   │
                        │   - registers         │
                        │     blueprints        │
                        │   - db.create_all()   │
                        └──────────┬───────────┘
             ┌─────────────┬───────┼───────────┬─────────────┐
             ▼             ▼       ▼           ▼             ▼
        auth_bp        main_bp  chatbot_bp   news_bp     (static/templates)
     register/login/   dashboard  /chatbot/ask  /news      Jinja2 + one
     logout            + all      rule-based    tea-market  stylesheet,
                        record     Q&A over      RSS feed    no JS framework
                        CRUD +     the logged-
                        CSV        in farmer's
                        export     own records
```

Data flows one way in normal operation: a logged-in farmer's browser submits a form → a
blueprint route validates and writes to Postgres/SQLite via SQLAlchemy → the dashboard re-queries
and re-renders. There is no API layer, no JS build step, and no background job runner — every
request is synchronous, which is intentional for this project's scale (an individual smallholder
farmer logging a handful of records a day, not a high-throughput system).

**Database-agnostic by design.** `config.py` reads `DATABASE_URL` from the environment. If it's
unset, it falls back to a local SQLite file (`chaiyako.db`) — so the whole app runs with zero
external dependencies for local development, but points at real Postgres in production (Render
supplies `DATABASE_URL` automatically — see [Deploying to Render](#deploying-to-render)). One
small but important detail: SQLAlchemy expects the `postgresql://` scheme, but some providers
(including Render, historically) hand out `postgres://` — `config.py` rewrites that prefix
automatically so this never causes a silent connection failure.

## Tech stack

| Layer | Choice | Why it's here |
|---|---|---|
| Web framework | Flask 3.0.3 | Lightweight, blueprint-based, matches the app's modest scale |
| ORM | Flask-SQLAlchemy 3.1.1 | Maps `Farmer` / `Farm` / records to tables without hand-written SQL for normal CRUD |
| Auth | Flask-Login 0.6.3 | Session-based login (`UserMixin` on `Farmer`), `@login_required` guards on all farm-data routes |
| Forms | Flask-WTF 1.2.1 + WTForms 3.1.2 | CSRF protection + server-side validation on register/login |
| DB driver | psycopg2-binary 2.9.9 | Postgres driver for production; SQLite needs no driver (stdlib) |
| Password hashing | Werkzeug security (`generate_password_hash` / `check_password_hash`) | Salted hashing — passwords are never stored in plaintext, see [Authentication](#authentication--the-login-activity-log) |
| Env config | python-dotenv 1.0.1 | Loads `.env` locally; irrelevant in production where Render injects env vars directly |
| WSGI server | gunicorn 22.0.0 | Production server, invoked via `Procfile` / `render.yaml`'s `startCommand` |
| News feed | feedparser 6.0.11 + requests 2.32.3 | Pulls and parses live Kenyan tea-market RSS headlines for `/news` |
| Email validation | email-validator 2.2.0 | Backs WTForms' email field validator at registration |
| Frontend | Server-rendered Jinja2 templates + one hand-written stylesheet | No React/Vue, no build step, no npm — deliberately simple to keep deploys and debugging trivial |

## Data model

Six tables, all defined in `app/models.py`. `is_admin` and the entire `LoginActivity` table were
added after the original v1 build, to support an in-progress admin interface (see
[that section](#the-admin-interface--current-state-and-whats-still-needed)).

### `farmers` (the `Farmer` model)

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, PK | |
| `full_name` | String(150), required | |
| `email` | String(150), **unique**, indexed, required | Login identifier |
| `phone` | String(30) | Optional |
| `password_hash` | String(255), required | Never the raw password — see [Authentication](#authentication--the-login-activity-log) |
| `scale` | String(20), default `"small"` | `"small"` or `"large"` — free-text field, not an enum, so validate on the form side |
| `is_admin` | Boolean, default `False`, required | Gates access to the (in-progress) admin interface |
| `created_at` | DateTime, default now | |

Relationships: one `Farmer` has many `farms`, `tools`, and `notes` (all cascade-deleted if the
farmer is deleted). `total_bushes` is a computed property (not a stored column) summing
`approx_bushes` across every farm the farmer owns.

### `farms` (the `Farm` model)

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, PK | |
| `farmer_id` | Integer, FK → `farmers.id`, required | |
| `farm_number` | String(50), required | **Unique per farmer** (see constraint below) — a farm's own identifying code, e.g. `ML083` |
| `location` | String(150) | Free-text label, e.g. `"Home Farm"`, `"Cherire Farm A"` |
| `approx_bushes` | Integer, default `0` | |
| `acreage` | Float | |
| `created_at` | DateTime, default now | |

**Important constraint:** `UniqueConstraint("farmer_id", "farm_number")`. A given farmer cannot
register the same `farm_number` twice. This is exactly what forced a real modeling decision
during demo-data import: the source data had *two different physical locations* ("home" and
"cherire") both reporting activity under code `ML083`. Since one farmer can't have two farms
both numbered `ML083`, the resolution taken was to split into **three** `Farm` rows for that
farmer — Home Farm (`ML083`), Cherire Farm A (`ML051`), and Cherire Farm B (renamed to
`ML083-C` to stay unique) — rather than losing data or violating the constraint. If your own
farm-numbering scheme can genuinely collide across locations like this, keep that constraint and
this resolution pattern in mind.

`total_kilos` is a computed property summing all `PluckingRecord.kilos` for that farm.

### `plucking_records` (the `PluckingRecord` model)

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, PK | |
| `farm_id` | Integer, FK → `farms.id`, required | |
| `date` | Date, required, default today | |
| `kilos` | Float, required | |
| `pluckers_count` | Integer | Optional — how many people plucked that day |
| `notes` | String(300) | Optional |
| `created_at` | DateTime, default now | |

### `pruning_records` (the `PruningRecord` model)

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, PK | |
| `farm_id` | Integer, FK → `farms.id`, required | |
| `date` | Date, required, default today | |
| `bushes_pruned` | Integer, required | |
| `prune_type` | String(50) | Free text, e.g. `"light"`, `"medium"` |
| `notes` | String(300) | Optional |
| `created_at` | DateTime, default now | |

### `tools` (the `Tool` model)

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, PK | |
| `farmer_id` | Integer, FK → `farmers.id`, required | |
| `name` | String(120), required | |
| `quantity` | Integer, default `1` | |
| `cost` | Float | Optional |
| `purchase_date` | Date, default today | |
| `status` | String(30), default `"good"` | Free text: `"good"` / `"needs_repair"` / `"damaged"` / `"lost"` |
| `notes` | String(300) | Optional |

### `notes` (the `Note` model)

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, PK | |
| `farmer_id` | Integer, FK → `farmers.id`, required | |
| `farm_id` | Integer, FK → `farms.id`, **nullable** | A note can be tied to a specific farm, or left farm-agnostic (e.g. the demo-seed marker notes use `farm_id = NULL`) |
| `title` | String(150) | Optional |
| `content` | Text, required | |
| `created_at` | DateTime, default now | |

There's no dedicated table for a "weeding" activity, or any activity type beyond plucking and
pruning. When demo data included weeding events, they were stored as `Note` rows rather than
invented as a new record type — worth knowing if you plan to formalize weeding (or fertilizing,
spraying, etc.) as first-class tracked activities later; right now they'd need their own table
following the same `farm_id` FK pattern as `PluckingRecord`/`PruningRecord`.

### `login_activities` (the `LoginActivity` model — added for the admin interface)

| Column | Type | Notes |
|---|---|---|
| `id` | Integer, PK | |
| `farmer_id` | Integer, FK → `farmers.id`, required | |
| `login_at` | DateTime, default now | |
| `ip_address` | String(45) | From `request.remote_addr` — sized for IPv6 |
| `user_agent` | String(255) | From the `User-Agent` header, truncated to fit |
| `success` | Boolean, default `True`, required | **Every** login attempt is logged, successful or not (see next section) |

`farmer.login_activities` gives you the reverse relationship (all login attempts for a given
farmer) via the `backref` on this model.

### Entity relationship summary

```
Farmer 1───* Farm 1───* PluckingRecord
   │             └────* PruningRecord
   ├───* Tool
   ├───* Note ──── (optionally) ──── Farm
   └───* LoginActivity
```

## Application structure

- **`app/__init__.py`** — the application factory. Creates the Flask app, loads `Config`,
  initializes `db` (SQLAlchemy) and `login_manager` (Flask-Login), registers all four
  blueprints, and calls `db.create_all()` on startup so new tables appear automatically. Note
  that `db.create_all()` only creates tables that don't exist yet — it does **not** alter
  existing tables to add new columns. That's why adding `is_admin` to the already-deployed
  `farmers` table required an explicit `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (handled inside
  `seed_demo_data_v2.py` — see [Demo data & seed scripts](#demo-data--seed-scripts)) rather than
  relying on `create_all()` alone.

- **`app/auth.py`** — `register`, `login`, `logout`. Registration takes a full name, email,
  phone, password, and scale, hashes the password immediately (`Farmer.set_password`), and logs
  the farmer straight in. Login now records a `LoginActivity` row for **every** attempt — whether
  or not the email/password matched — before deciding whether to actually log the user in. This
  means failed login attempts (wrong password, unknown email) are auditable, not just successes.

- **`app/main.py`** — the largest file. The `/dashboard` route (all farm data for the logged-in
  farmer, chart-ready plucking totals, tool/note lists) plus every CRUD action: adding/updating
  farms, adding/deleting plucking and pruning records, adding tools and updating their status,
  adding/deleting notes, a JSON endpoint feeding the dashboard's chart (`/api/chart-data`), and a
  CSV export of full plucking history (`/export/plucking.csv`).

- **`app/chatbot.py`** — a rule-based (not LLM-based) assistant reachable at
  `/chatbot/ask` (POST). Matches keywords in the farmer's question against canned responses,
  including a personalized "overview" mode that pulls the logged-in farmer's own totals
  (total kilos, farm count, etc.) into the reply.

- **`app/news.py`** — `/news`. Fetches and parses live Kenyan tea-market RSS headlines via
  `feedparser`, with basic categorization and search.

- **`app/static/` / `app/templates/`** — one hand-written stylesheet (`style.css`, tea-green
  theme) and five Jinja2 templates: `base.html` (shared layout/nav), `landing.html`,
  `register.html`, `login.html`, `dashboard.html`, `news.html`.

- **`config.py`** — reads `SECRET_KEY` and `DATABASE_URL` from the environment; see
  [Environment variables](#environment-variables).

- **`run.py`** — the entrypoint. `python run.py` for local dev; `gunicorn run:app` in production
  (see `Procfile` and `render.yaml`).

- **`seed_demo_data.py` / `seed_demo_data_v2.py`** — standalone scripts (not blueprints, not
  imported by the app) for populating demo data directly against whichever database
  `DATABASE_URL` points at. Covered in detail below.

## Routes / URL map

| Method(s) | Path | Blueprint | Auth required? | Purpose |
|---|---|---|---|---|
| GET | `/` | main | No | Landing page |
| GET, POST | `/register` | auth | No | Farmer self-registration |
| GET, POST | `/login` | auth | No | Login — now logs every attempt to `login_activities` |
| GET | `/logout` | auth | Yes | Logout |
| GET | `/dashboard` | main | Yes | The farmer's own dashboard — farms, records, tools, notes, chart |
| POST | `/farms/add` | main | Yes | Add a new farm |
| POST | `/farms/<int:farm_id>/update` | main | Yes | Edit an existing farm |
| POST | `/plucking/add` | main | Yes | Log a plucking record |
| POST | `/plucking/<int:record_id>/delete` | main | Yes | Delete a plucking record |
| POST | `/pruning/add` | main | Yes | Log a pruning record |
| POST | `/tools/add` | main | Yes | Add a tool/equipment item |
| POST | `/tools/<int:tool_id>/status` | main | Yes | Update a tool's condition status |
| POST | `/notes/add` | main | Yes | Add a farm note |
| POST | `/notes/<int:note_id>/delete` | main | Yes | Delete a note |
| GET | `/api/chart-data` | main | Yes | JSON feed for the dashboard's 30-day trend chart |
| GET | `/export/plucking.csv` | main | Yes | CSV export of the farmer's full plucking history |
| POST | `/chatbot/ask` | chatbot | Yes | Rule-based Q&A against the farmer's own data |
| GET | `/news` | news | No | Tea-market news feed |

Every `main` route scopes queries to `current_user` (the logged-in farmer) — there is currently
**no route that lets one farmer see another farmer's data**, which is expected for v1's
self-service model, and is exactly the gap the admin interface (below) is meant to fill in a
controlled way.

## Authentication & the login-activity log

Passwords are hashed with Werkzeug's `generate_password_hash` (`Farmer.set_password`) and
verified with `check_password_hash` (`Farmer.check_password`) — the raw password is never
persisted anywhere, in the database or in `LoginActivity`.

As of the admin-interface groundwork, `/login` records a `LoginActivity` row on **every**
attempt:

```python
success = bool(farmer and farmer.check_password(password))
if farmer:
    db.session.add(LoginActivity(
        farmer_id=farmer.id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:255],
        success=success,
    ))
    db.session.commit()

if success:
    login_user(farmer)
    ...
```

Note the `if farmer:` guard — an attempt against an email that doesn't exist at all isn't logged
(there's no `farmer_id` to attach it to), only attempts where the email matched a real account
but the password was wrong. Something to be aware of if you're relying on this table for a
complete brute-force/enumeration audit trail later — right now it only catches "right email,
wrong password," not "email doesn't exist."

## Local setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # edit SECRET_KEY if you like
python run.py
```

Visit `http://127.0.0.1:5000`. With no `DATABASE_URL` set, it uses a local SQLite file
(`chaiyako.db`) created automatically — no Postgres setup needed for local development.

## Environment variables

| Variable | Required? | Default (if unset) | Purpose |
|---|---|---|---|
| `SECRET_KEY` | Recommended | `"dev-secret-change-me"` | Flask session signing key — **must** be set to a real random value in production; the default is intentionally insecure so it's obvious if you forgot |
| `DATABASE_URL` | No | Local SQLite file | Full connection string. Render supplies this automatically when using `render.yaml`. Accepts either `postgres://` or `postgresql://` — the former is rewritten to the latter automatically in `config.py` since SQLAlchemy requires it |

## Deploying to Render

1. Push this project to a GitHub repo.
2. On Render: **New +** → **Blueprint**, point it at the repo. `render.yaml` provisions both the
   web service and a free Postgres database automatically, and wires `DATABASE_URL` from the
   database to the web service's environment for you — no manual copy-pasting of connection
   strings required.
3. Render builds with `pip install -r requirements.txt` and starts with `gunicorn run:app`
   (defined in both `Procfile` and `render.yaml`'s `startCommand` — the `Procfile` is there for
   platforms that read it directly, `render.yaml` is authoritative on Render itself).
4. `SECRET_KEY` is set to `generateValue: true` in `render.yaml`, so Render generates a secure
   random value for you automatically — you don't need to set this by hand.

### The "External Database URL" — for running scripts against production data

Render's Postgres dashboard exposes two connection strings: an **Internal Database URL** (only
reachable from other Render services in the same region) and an **External Database URL**
(reachable from your own machine). The seed scripts in this project are meant to be run with the
**External** one, from your local machine, since they're not part of the deployed web service:

```bash
DATABASE_URL="<external database url from Render>" python seed_demo_data.py
```

## Connecting a custom domain

1. In the Render dashboard, open your web service → **Settings → Custom Domains → Add Custom
   Domain**.
2. Enter your domain (e.g. `chaiyako.co.ke` or `app.chaiyako.co.ke`).
3. Render shows you a DNS record to add — typically a **CNAME** for a subdomain, or an **A
   record** if you're pointing a bare/apex domain (apex domains can't use CNAMEs under the DNS
   standard, which is why Render recommends a subdomain like `app.yourdomain.com` where possible).
4. Add that record with whoever you registered the domain through (your registrar's DNS
   management page — not Render).
5. DNS propagation can take anywhere from a few minutes to a few hours. Render marks the domain
   "Verified" once it detects the record.
6. Render issues a free SSL certificate automatically once the domain is verified — no separate
   HTTPS setup needed.

## Demo data & seed scripts

Two standalone scripts live in the project root, meant to be run manually (not imported by the
app itself), against whichever `DATABASE_URL` you point them at:

### `seed_demo_data.py` — batch 1

Creates one demo farmer, **Jeff Chelule** (`jeff.chelule@example.com` /
`ChaiYako2026!`), with three farms — Home Farm (`ML083`), Cherire Farm A (`ML051`), Cherire
Farm B (`ML083-C`) — and 65 real plucking/weeding records spanning June–July 2026 (64 plucking
records as `PluckingRecord` rows; the single weeding record stored as a `Note`, since there's no
dedicated weeding table). Safe to re-run: it checks a marker `Note`
(`__demo_seed_v1__`) tied to the farmer before inserting anything, so running it twice won't
duplicate data.

```bash
DATABASE_URL="<your postgres url>" python seed_demo_data.py
```

### `seed_demo_data_v2.py` — batch 2 (August data + admin/multi-farmer setup)

Requires the `is_admin` column and `LoginActivity` table to exist — this script creates them
itself before touching any data:

```python
db.session.execute(text(
    "ALTER TABLE farmers ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"
))
db.session.commit()
db.create_all()  # creates login_activities if missing
```

This matters because `db.create_all()` alone only creates brand-new tables — it will not add a
column to an already-existing `farmers` table, which is why the explicit `ALTER TABLE` runs
first.

After patching the schema, it:

- Adds **30 synthetic August 2026 plucking records** for Jeff Chelule across his existing three
  farms, plus 2 pruning records for variety. *(These August figures are generated for demo/UI
  purposes — real numbers weren't supplied for this month, unlike the June–July batch.)*
- Creates **Grace Naliaka** (`grace.naliaka@example.com` / `ChaiYako2026!`, small scale, one farm,
  14 synthetic August plucking records) — a second demo farmer, entirely synthetic.
- Creates **Kennedy Rotich** (`kennedy.rotich@example.com` / `ChaiYako2026!`, large scale, two
  farms, 24 synthetic August plucking records) — a third demo farmer, entirely synthetic.
- Creates **Wanjiru Admin** (`admin@chaiyako.demo` / `ChaiYakoAdmin2026!`, `is_admin=True`, no
  farms of their own) — the admin demo account.
- Seeds **5 `LoginActivity` rows per account** (all four: Jeff, Grace, Kennedy, admin), timestamped
  across mid-August to early-September 2026, with the first entry per farmer deliberately marked
  as a failed attempt, so an admin login-history view has realistic mixed data to render rather
  than an unbroken string of successes.

```bash
DATABASE_URL="<your postgres url>" python seed_demo_data_v2.py
```

Also guarded by a per-farmer marker `Note` (`__demo_seed_v2__`) — safe to re-run.

### All demo logins after running both scripts

| Role | Email | Password |
|---|---|---|
| Admin | `admin@chaiyako.demo` | `ChaiYakoAdmin2026!` |
| Farmer | `jeff.chelule@example.com` | `ChaiYako2026!` |
| Farmer | `grace.naliaka@example.com` | `ChaiYako2026!` |
| Farmer | `kennedy.rotich@example.com` | `ChaiYako2026!` |

## The admin interface — current state and what's still needed

**Built so far (schema + data only, no UI yet):**
- `Farmer.is_admin` — the flag that will gate access.
- `LoginActivity` — per-attempt login history, auto-recorded from `/login` going forward.
- Demo data across 3 farmers + 1 admin account, so an admin view has more than one farmer's data
  to actually demonstrate.

**Not yet built:**
- Any actual admin **routes/blueprint** — there is currently no `/admin` anything. `is_admin`
  exists on the model but nothing checks it yet.
- Any **template/UI** for an admin to browse farmers, view their records, or view login history.
- Any **authorization guard** (e.g. an `@admin_required` decorator) to protect future admin
  routes — building the routes without this would leave farmer data readable by any logged-in
  user, admin or not.

## Known gaps / things intentionally not built yet

These were flagged during planning and deliberately deferred rather than overlooked:

- **No account status field.** There's currently no way for an admin to suspend/disable a
  farmer's account — `Farmer` has no `is_active` or equivalent column.
- **No audit trail for admin actions themselves.** `LoginActivity` covers *logging in*, not what
  an admin does once inside the system (e.g. viewing or editing another farmer's records). If
  admins will be able to modify farmer data, an action-level audit log is worth adding before
  that ships.
- **`LoginActivity` doesn't catch unknown-email attempts** — see
  [Authentication](#authentication--the-login-activity-log) above.
- **No dedicated "weeding" (or fertilizing/spraying) activity table** — currently modeled as a
  generic `Note`, which works for demo purposes but won't support structured queries (e.g. "total
  weeding events this month") the way `PluckingRecord`/`PruningRecord` do for their activities.
- **`scale`, `prune_type`, and `Tool.status` are free-text strings, not enums** — fine for a
  single-developer project at this size, but worth constraining (either at the DB level or with
  WTForms `SelectField` choices) before multiple people are entering data, to avoid inconsistent
  values like `"Small"` vs `"small"` vs `"SMALL"` accumulating.

## Project structure (file tree)

```
chai_yako/
├── app/
│   ├── __init__.py        # application factory: create_app()
│   ├── models.py           # Farmer, Farm, PluckingRecord, PruningRecord, Tool, Note, LoginActivity
│   ├── auth.py              # register / login (now logs LoginActivity) / logout
│   ├── main.py               # dashboard + all farm-data CRUD + chart API + CSV export
│   ├── chatbot.py             # rule-based farm assistant
│   ├── news.py                # tea market news feed (RSS)
│   ├── static/
│   │   └── css/style.css
│   └── templates/
│       ├── base.html
│       ├── landing.html
│       ├── register.html
│       ├── login.html
│       ├── dashboard.html
│       └── news.html
├── config.py                # env-driven config, postgres:// → postgresql:// rewrite
├── run.py                    # entrypoint
├── seed_demo_data.py          # batch 1: Jeff Chelule, 3 farms, June–July demo data
├── seed_demo_data_v2.py         # batch 2: August data + Grace/Kennedy/admin + login activity
├── requirements.txt
├── Procfile                     # gunicorn run:app
├── render.yaml                   # Render blueprint: web service + free Postgres
├── .env.example
└── README.md                      # this file
```

## Glossary of farm terms used in the code

For anyone reading this codebase without tea-farming context:

- **Plucking** — the harvesting of tea leaves, typically done by hand on a rotating cycle
  (roughly every 1–2 weeks per section). Recorded as `kilos` per day in `PluckingRecord`.
- **Pruning** — periodically cutting back tea bushes to control height and stimulate new growth.
  Recorded in `PruningRecord` with a `prune_type` (e.g. light/medium/hard) and how many bushes
  were pruned.
- **Weeding** — clearing unwanted plants from around the tea bushes. Not (yet) a structured
  record type in this schema — currently logged as free-text `Note` entries.
- **Farm number** — a farmer's own identifying code for a specific plot (e.g. `ML083`). Distinct
  from the farm's `location` label (e.g. `"Home Farm"`) — two different fields that can, and in
  this project's demo data did, need careful disambiguation when the same code appeared under
  more than one location for the same farmer.
