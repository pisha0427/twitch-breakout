"""SQLite schema for the Twitch breakout-category collector."""

DDL = """
CREATE TABLE IF NOT EXISTS snapshots (
    poll_ts   TEXT NOT NULL,
    game_id   TEXT NOT NULL,
    game_name TEXT,
    rank      INTEGER,
    viewers   INTEGER,
    PRIMARY KEY (poll_ts, game_id)
);

CREATE TABLE IF NOT EXISTS streams (
    poll_ts    TEXT NOT NULL,
    game_id    TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    user_login TEXT,
    viewers    INTEGER,
    language   TEXT,
    started_at TEXT,
    PRIMARY KEY (poll_ts, user_id)
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def init_db(conn) -> None:
    conn.executescript(DDL)
