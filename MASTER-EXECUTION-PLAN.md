# Master Execution Plan — Fortnite Tournament Tracker (Phase 1)

> **For the coding agent (Cursor).** This is your build plan. Work **one task at a time, top to bottom**. Do not start a task until the previous task's *Done when* checks pass. Companion reference: `phase1-build-spec.md` (contains the canonical DDL, the Osirion adapter, and the scheduler algorithm — treat it as the source of truth for those implementations).

---

## 0. Mission

Build a Fortnite **tournament** tracker (updates + stats), covering **all regions and all tiers**. Single upstream data source: the **Osirion Public API** (`https://fnapi.osirion.gg`). Free-only path — no paid replay API, no Epic OAuth in this phase.

The product serves cached, normalized data from our own Postgres. Users never trigger upstream calls.

---

## 1. Golden rules (invariants — never violate)

These are hard constraints. If a task seems to require breaking one, **stop and flag it**, don't work around it.

1. **Snapshot-first.** Every successful leaderboard poll writes to `leaderboard_snapshots` (append-only, deduped on the API's `updatedAt`). This table is load-bearing for v2 and can never be reconstructed later. Never skip or overwrite it.
2. **No upstream calls from the browser.** The Next.js client only ever calls our FastAPI. Only the backend talks to Osirion.
3. **Respect rate limits at 90% ceilings:** account 50/min → 45, leaderboard 60/min → 54, everything else 100/min → 90. All Osirion calls go through the shared `RateLimiter`.
4. **Tiered polling, never brute-force.** Poll live-window top pages frequently; deep pages lazily/on-demand; full backfill only when a window closes.
5. **Beta tolerance.** The API is slow and occasionally errors. Every call has a generous timeout + retry-with-backoff. Failures degrade gracefully; they never crash a poll cycle.
6. **No Epic/official API, no paid Osirion replay API** in Phase 1.
7. **Idempotent ingestion.** Re-running any sync must not duplicate rows. Use upserts + unique constraints.

---

## 2. Pinned stack & conventions

Do not substitute these without asking.

**Backend**
- Python **3.12**, dependency mgmt with **uv** (`pyproject.toml`). Fallback: pip + venv.
- **FastAPI** (async), **httpx** (async client), **SQLAlchemy 2.0** async ORM + **asyncpg** driver, **Alembic** migrations.
- Scheduling: **APScheduler** (`AsyncIOScheduler`). (Celery is a future phase — do not add it now.)
- Config: **pydantic-settings** from `.env`.
- Lint/format: **ruff**. Tests: **pytest** + **pytest-asyncio**, **respx** for mocking httpx.

**Database**
- **PostgreSQL 16**, run locally via Docker Compose.

**Frontend**
- **Next.js (App Router)** + **TypeScript** + **Tailwind**.
- Server Components + **ISR** for tournament/detail pages. Live leaderboards use client-side polling via **TanStack Query**.

**Conventions**
- All timestamps stored `TIMESTAMPTZ` (UTC). Parse Osirion ISO strings to UTC on ingest.
- Store raw upstream sub-objects as `JSONB` (`display_data`, `entries`, `scoring_rules`, `trackedStats`) — do not flatten what we don't query on.
- Type hints everywhere; Pydantic models for every Osirion response shape.

---

## 3. Target repository structure

```
tournament-tracker/
├── docker-compose.yml            # postgres
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── alembic.ini
│   ├── migrations/               # alembic
│   └── app/
│       ├── main.py               # FastAPI app + lifespan (starts scheduler)
│       ├── config.py             # pydantic-settings
│       ├── db.py                 # async engine/session
│       ├── models.py             # SQLAlchemy models (mirrors DDL in spec)
│       ├── schemas.py            # Pydantic: Osirion response + API response models
│       ├── osirion/
│       │   ├── client.py         # OsirionClient + RateLimiter (see spec §4)
│       │   └── ingest.py         # tournaments sync + leaderboard poll → DB
│       ├── scheduler.py          # priority poller (see spec §5)
│       └── api/
│           ├── tournaments.py
│           ├── leaderboards.py
│           └── players.py
└── frontend/
    ├── package.json
    └── src/app/
        ├── page.tsx                        # tournament list
        ├── tournaments/[eventId]/page.tsx  # detail (rendered from display_data)
        ├── leaderboard/[lbEventId]/[lbWindowId]/page.tsx
        └── players/[accountId]/page.tsx
```

---

## 4. Agent operating protocol

For **every** task below:
1. Read the task's *Goal* and *Done when*.
2. Implement only what the task asks. No scope creep.
3. Run the verification commands. Paste the output.
4. If *Done when* is fully green, commit with the task ID in the message (e.g. `M1-T2: leaderboard_snapshots migration`). Then proceed.
5. If blocked or a Golden Rule conflicts, stop and ask.
6. Never run destructive DB commands (`drop`, `truncate`) against anything but the local dev database, and only when a task explicitly says to.

---

## 5. Milestones & tasks

### M0 — Scaffold & tooling

**T0.1** Initialize repo, `backend/` with uv (`pyproject.toml`), and `frontend/` with `create-next-app` (TS + Tailwind + App Router).
**T0.2** Add `docker-compose.yml` running Postgres 16 with a named volume. Add `.env.example` (`DATABASE_URL`, `OSIRION_BASE_URL=https://fnapi.osirion.gg`, `OSIRION_API_KEY=` placeholder).
**T0.3** Wire ruff + a `make dev` / uv script to run the API.

**Done when:** `docker compose up -d` starts Postgres; `uv run uvicorn app.main:app --reload` serves a `GET /health` returning `{"ok": true}`; `npm run dev` serves the Next.js starter.

---

### M1 — Database layer

**T1.1** Create SQLAlchemy models mirroring **exactly** the 7 tables in `phase1-build-spec.md §3`: `tournaments`, `event_windows`, `score_locations`, `players`, `leaderboard_snapshots`, `leaderboard_current`, `leaderboard_entry_players`. Preserve every column, type, index, and unique constraint — especially `leaderboard_snapshots`'s `UNIQUE (leaderboard_event_id, leaderboard_event_window_id, page, source_updated_at)`.
**T1.2** Configure Alembic (async) and autogenerate the initial migration. Review it against the spec DDL before applying.
**T1.3** Apply migration.

**Done when:** `alembic upgrade head` succeeds; `\dt` lists all 7 tables; `\d leaderboard_snapshots` shows the 4-column unique constraint; `\d event_windows` shows the `(begin_time, end_time)` index.

---

### M2 — Osirion adapter

**T2.1** Implement `RateLimiter` and `OsirionClient` per `phase1-build-spec.md §4` — three rate-limiter buckets (account/leaderboard/default at 90% ceilings), 30s timeout, 3-attempt backoff. Methods: `get_tournaments`, `get_leaderboard`, `lookup_by_name`.
**T2.2** Define Pydantic response models in `schemas.py` for `TournamentsDataResponse` (incl. `displayData`, `eventWindows`, `scoreLocations`) and `TournamentLeaderboardDataResponse` (incl. `entries`, `players`, `sessionHistory`). Parse responses into these.
**T2.3** Unit-test the client with **respx**: mock a tournaments payload and a leaderboard payload; assert parsing; assert the limiter blocks past the ceiling.

**Done when:** `pytest tests/test_osirion.py` passes; the limiter test proves no more than the ceiling fires within a 60s window (use a fake clock).

> **Open item to resolve here:** `sessionHistory[].trackedStats` is an untyped object in the OpenAPI spec. Model it as `dict` for now. Add a `# TODO: inspect live payload` note — a real event response may reveal time-alive/elims we can surface without diffing.

---

### M3 — Tournament ingestion

**T3.1** In `ingest.py`, implement `sync_tournaments()`: call `get_tournaments(historic=false)` across all regions (or the global call), then **upsert** into `tournaments`, `event_windows`, and `score_locations`. Update `last_seen`. Must be idempotent (re-run = no dupes).
**T3.2** Add a one-off CLI/entrypoint to run `sync_tournaments()` manually.

**Done when:** running the sync twice leaves identical row counts; `SELECT count(*) FROM tournaments`, `event_windows`, `score_locations` are all > 0; a spot-checked `display_data` JSONB contains poster/color fields.

---

### M4 — Leaderboard poller + snapshot writer (**critical path**)

**T4.1** Implement `poll_leaderboard(lb_event_id, lb_window_id, page)`:
- call `get_leaderboard(...)`,
- **INSERT into `leaderboard_snapshots` with `ON CONFLICT DO NOTHING`** keyed on `(lb_event_id, lb_window_id, page, source_updated_at)`,
- **upsert** `leaderboard_current` (replace rows for this leaderboard/page),
- upsert `players` and `leaderboard_entry_players`.
**T4.2** Ensure a repeat poll when `updatedAt` is unchanged inserts **zero** new snapshot rows but still refreshes `current` harmlessly.

**Done when:** polling a leaderboard page writes 1 snapshot row; polling again with the same `updatedAt` writes 0 new snapshot rows (verify with a count before/after); `leaderboard_current` and `leaderboard_entry_players` are populated; `players` has the entrants.

---

### M5 — Priority scheduler

**T5.1** Implement the loop from `phase1-build-spec.md §5` in `scheduler.py` using `AsyncIOScheduler`:
- refresh tournaments list when stale (>6h),
- compute `live_windows` (`begin_time <= now <= end_time`),
- enqueue **HIGH** = top pages 0..9 of each live main score_location (target 60–90s cadence), **LOW** = deeper pages (~5m), **BACKFILL** = all pages once for windows ended in the last 10m,
- drain through the leaderboard `RateLimiter`.
**T5.2** Start the scheduler in FastAPI's lifespan; stop it cleanly on shutdown.
**T5.3** Add a `POST /admin/enqueue-deep-page` internal hook so the API can request an on-demand deep page (used in M6).

**Done when:** with a seeded/mocked live window, the scheduler polls its top pages on schedule and stays under 54 leaderboard req/min (log the per-minute count); an ended window triggers exactly one backfill sweep; scheduler starts/stops with the app.

---

### M6 — FastAPI read API

Implement, reading **only** from Postgres (except the documented lazy deep-page path):

**T6.1** `GET /tournaments?region=&live=` — list from `tournaments` (+ live flag derived from windows).
**T6.2** `GET /tournaments/{event_id}` — detail with its windows and score_locations.
**T6.3** `GET /leaderboard/{lb_event_id}/{lb_window_id}?page=0` — from `leaderboard_current`. If the page isn't cached, enqueue a HIGH deep-page fetch and return `202`/loading semantics (client re-polls).
**T6.4** `GET /players/search?name=` — `players` by name, with `lookup_by_name` fallback (rate-limited).
**T6.5** `GET /players/{account_id}/placements` — cross-tournament history via `leaderboard_entry_players` join.

**Done when:** each endpoint returns correct shapes against seeded data; the leaderboard endpoint serves cached pages instantly and gracefully enqueues uncached ones; no endpoint calls Osirion synchronously except the documented fallback paths.

---

### M7 — Next.js frontend

**T7.1** Tournament list (`/`) — cards rendered from `display_data` (poster, colors, titles). ISR revalidate ~5 min. Region/tier filter.
**T7.2** Tournament detail (`/tournaments/[eventId]`) — themed from `display_data`; lists windows with schedule + live badge.
**T7.3** Leaderboard (`/leaderboard/[lbEventId]/[lbWindowId]`) — paginated table (rank, team/players + flag, score, points, percentile). While the window is live, **TanStack Query polls every 60–90s**; show `updatedAt` as "updated X ago".
**T7.4** Player page (`/players/[accountId]`) — placement history across tournaments.

**Done when:** all four pages render from the FastAPI API; the live leaderboard visibly refreshes on its interval; no client code references `fnapi.osirion.gg`.

---

### M8 — Observability & hardening

**T8.1** Structured logging of every Osirion call: endpoint, page, latency, and running per-minute count per bucket.
**T8.2** A `/admin/metrics` (or logs) surface showing: live-window count, snapshots written last hour, rate-limit utilization, last successful tournaments sync.
**T8.3** Wrap each poll job so one failure logs and continues — a single bad leaderboard never aborts the cycle.

**Done when:** logs show rate-limit utilization staying under ceilings during simulated multi-region load; a forced upstream error is logged and the cycle keeps running.

---

## 6. Environment & secrets

- `.env` (never commit): `DATABASE_URL`, `OSIRION_BASE_URL`, `OSIRION_API_KEY` (empty during beta; wire it into the client's headers now so it's ready when keys ship).
- Frontend: `NEXT_PUBLIC_API_BASE_URL` → the FastAPI base. No upstream secrets in the frontend, ever.

---

## 7. Phase 1 definition of done

- All regions/tiers of current (non-historic) tournaments ingested and browsable.
- Live windows auto-poll on a tiered schedule, provably under rate ceilings.
- `leaderboard_snapshots` accumulating deduped time-series from day one.
- Four frontend surfaces working off cached data.
- Zero client-side upstream calls; zero paid/Epic APIs used.

## 8. Explicitly out of scope (do not build now)

Epic/official API + OAuth · paid Osirion replay API · damage/drops/movement/kill-feed stats · v2 derived analytics (risers, progression) · auth/user accounts · historical data before mid-2024. These come later; leave clean seams (e.g. the JSONB snapshot store) but don't implement them.
