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
