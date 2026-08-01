# Phase 1 Build Spec

Canonical reference for DDL (section 3), the Osirion adapter (section 4), and the scheduler (section 5).

---

## 3. Database DDL

```sql
-- 1. tournaments
CREATE TABLE tournaments (
    event_id        TEXT PRIMARY KEY,
    event_group     TEXT,
    regions         TEXT[]      NOT NULL DEFAULT '{}',
    platforms       TEXT[]      NOT NULL DEFAULT '{}',
    display_data    JSONB       NOT NULL,
    metadata        JSONB,
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tournaments_regions ON tournaments USING GIN (regions);

-- 2. event_windows
CREATE TABLE event_windows (
    event_window_id     TEXT PRIMARY KEY,
    event_id            TEXT NOT NULL REFERENCES tournaments(event_id) ON DELETE CASCADE,
    round               INT,
    begin_time          TIMESTAMPTZ NOT NULL,
    end_time            TIMESTAMPTZ NOT NULL,
    playlist_id         TEXT,
    match_cap           INT,
    require_all_tokens  TEXT[] DEFAULT '{}',
    require_any_tokens  TEXT[] DEFAULT '{}',
    metadata            JSONB,
    last_seen           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_windows_live ON event_windows (begin_time, end_time);

-- 3. score_locations
CREATE TABLE score_locations (
    id                          BIGSERIAL PRIMARY KEY,
    event_window_id             TEXT NOT NULL REFERENCES event_windows(event_window_id) ON DELETE CASCADE,
    leaderboard_event_id        TEXT NOT NULL,
    leaderboard_event_window_id TEXT NOT NULL,
    is_main                     BOOLEAN NOT NULL DEFAULT false,
    payout_tables               JSONB,
    scoring_rules               JSONB,
    UNIQUE (leaderboard_event_id, leaderboard_event_window_id)
);

-- 4. players
CREATE TABLE players (
    account_id  TEXT PRIMARY KEY,
    username    TEXT,
    flag_token  TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_players_username ON players (lower(username));

-- 5. leaderboard_snapshots
CREATE TABLE leaderboard_snapshots (
    id                          BIGSERIAL PRIMARY KEY,
    leaderboard_event_id        TEXT NOT NULL,
    leaderboard_event_window_id TEXT NOT NULL,
    page                        INT  NOT NULL,
    total_pages                 INT,
    source_updated_at           TIMESTAMPTZ NOT NULL,
    captured_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    entries                     JSONB NOT NULL,
    UNIQUE (leaderboard_event_id, leaderboard_event_window_id, page, source_updated_at)
);

-- 6. leaderboard_current
CREATE TABLE leaderboard_current (
    leaderboard_event_id        TEXT NOT NULL,
    leaderboard_event_window_id TEXT NOT NULL,
    team_id                     TEXT NOT NULL,
    rank                        INT,
    score                       NUMERIC,
    points_earned               NUMERIC,
    percentile                  NUMERIC,
    players                     JSONB,
    session_history             JSONB,
    source_updated_at           TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (leaderboard_event_id, leaderboard_event_window_id, team_id)
);
CREATE INDEX idx_current_rank
    ON leaderboard_current (leaderboard_event_id, leaderboard_event_window_id, rank);

-- 7. leaderboard_entry_players
CREATE TABLE leaderboard_entry_players (
    leaderboard_event_id        TEXT NOT NULL,
    leaderboard_event_window_id TEXT NOT NULL,
    team_id                     TEXT NOT NULL,
    account_id                  TEXT NOT NULL,
    rank                        INT,
    PRIMARY KEY (leaderboard_event_id, leaderboard_event_window_id, account_id)
);
CREATE INDEX idx_entry_players_account ON leaderboard_entry_players (account_id);
```

---

## 4. Osirion adapter

Reference implementation for `app/osirion/client.py`. All upstream calls go through this module.

```python
# app/osirion/client.py
import asyncio, time, httpx
from app.config import settings

class RateLimiter:
    """Sliding 60s window, blocks until a slot is free under the ceiling."""
    def __init__(self, max_per_min: int):
        self.capacity = int(max_per_min * 0.9)   # 90% ceiling
        self._hits: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            while True:
                now = time.monotonic()
                self._hits = [t for t in self._hits if now - t < 60]
                if len(self._hits) < self.capacity:
                    self._hits.append(now)
                    return
                await asyncio.sleep(60 - (now - self._hits[0]) + 0.05)

class OsirionClient:
    def __init__(self):
        headers = {}
        if settings.osirion_api_key:
            headers["Authorization"] = f"Bearer {settings.osirion_api_key}"
        self._c = httpx.AsyncClient(base_url=settings.osirion_base_url,
                                    timeout=30.0, headers=headers)
        self._rl = {
            "account":     RateLimiter(50),
            "leaderboard": RateLimiter(60),
            "default":     RateLimiter(100),
        }

    async def _get(self, path, cls, params=None):
        await self._rl[cls].acquire()
        for attempt in range(3):
            try:
                r = await self._c.get(path, params=params)
                r.raise_for_status()
                return r.json()
            except (httpx.TimeoutException, httpx.HTTPStatusError):
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

    async def get_tournaments(self, region=None, historic=False, lang=None):
        params = {"includeHistoricData": str(historic).lower()}
        if region: params["region"] = region
        if lang:   params["lang"] = lang
        return await self._get("/v1/tournaments", "default", params)

    async def get_leaderboard(self, lb_event_id, lb_window_id, page=0):
        return await self._get("/v1/tournaments/leaderboard", "leaderboard", {
            "leaderboardEventId": lb_event_id,
            "leaderboardEventWindowId": lb_window_id,
            "page": page,
        })

    async def lookup_by_name(self, display_name, platform=None):
        params = {"displayName": display_name}
        if platform: params["platform"] = platform
        return await self._get("/v1/accounts/lookup-by-display-name", "account", params)
```

---

## 5. Priority scheduler

Reference implementation for `app/scheduler.py`. Orchestrates tiered leaderboard polling via P4 `poll_leaderboard`.

### Loop (every 15s)

1. Refresh tournament catalog when stale (>6h) via `sync_tournaments`.
2. Query live windows (`begin_time <= now <= end_time`) and recently ended windows (`end_time` within last 10 minutes).
3. Enqueue due jobs by tier:
   - **HIGH** (priority 0): pages 0-9 of each live main score location, target 60-90s cadence (base 75s, stretches under queue pressure).
   - **LOW** (priority 1): pages >= 10 when `total_pages` is known, every 5 minutes.
   - **BACKFILL** (priority 2): all pages once per recently closed main window, then never again.
4. Drain the priority queue: each job calls `poll_leaderboard` through the shared `OsirionClient` (leaderboard limiter at 54/min). One failure logs and the cycle continues.

### On-demand

`enqueue_deep_page(lb_event_id, lb_window_id, page)` inserts a HIGH-priority job for API-driven deep fetches (P6).

### Rate logging

Every 60s, log leaderboard request count in the rolling window (must stay at or under 54).

---

## 6. Read API

FastAPI endpoints reading from Postgres. Response JSON uses camelCase field names.

### `GET /tournaments?region=&live=`

List tournaments with optional filters. `isLive` is true when any window has `begin_time <= now <= end_time`.

### `GET /tournaments/{event_id}`

Tournament detail with nested `eventWindows` and `scoreLocations`. Returns 404 when missing.

### `GET /leaderboard/{lb_event_id}/{lb_window_id}?page=0`

Serves rows from `leaderboard_current` for the requested page (100 ranks per page).

- **Cached** (snapshot exists for this page): **200** with `status: "ready"` and entries.
- **Uncached**: enqueue via `enqueue_deep_page` (P5), return **202** with `status: "loading"`. Never call Osirion inline.

### `GET /players/search?name=`

Search `players` by username prefix. Falls back to `lookup_by_name` through the adapter when the DB has no match.

### `GET /players/{account_id}/placements`

Cross-tournament placement history from `leaderboard_entry_players`.
