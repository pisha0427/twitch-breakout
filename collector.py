#!/usr/bin/env python3
"""Poll Twitch every run and append a snapshot to data/twitch.db.

Designed to run every 10 minutes (locally via cron, or on GitHub Actions).
Idempotent per poll: re-running the same minute overwrites via INSERT OR REPLACE.

Usage:
    python collector.py                 # top 30 games, ~300 streams per game
    python collector.py --games 20      # fewer games = faster, fewer API calls
"""
import argparse
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from schema import init_db  # noqa: E402
from twitch_client import HelixClient, POLL_TS_FMT  # noqa: E402

DB_PATH = Path(__file__).resolve().parent / "data" / "twitch.db"


def upsert_rows(conn, table: str, columns: list[str], rows: list[tuple]) -> None:
    if not rows:
        return
    placeholders = ", ".join(["?"] * len(columns))
    col_list = ", ".join(columns)
    sql = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"
    conn.executemany(sql, rows)


def poll(conn: sqlite3.Connection, client: HelixClient, n_games: int) -> dict:
    poll_ts = datetime.now(timezone.utc).strftime(POLL_TS_FMT)

    games = client.top_games(first=100)
    games_by_id = {g["id"]: g for g in games}
    top = games[:n_games]

    stream_rows: list[tuple] = []
    viewers_by_game: dict[str, int] = {}
    for g in top:
        try:
            streams = client.streams_for_game(g["id"], limit=300)
        except RuntimeError as exc:
            print(f"[warn] streams failed for game {g['name']}: {exc}", file=sys.stderr)
            continue
        viewers_by_game[g["id"]] = sum(
            int(s.get("viewer_count", 0) or 0) for s in streams
        )
        for s in streams:
            stream_rows.append(
                (
                    poll_ts,
                    s.get("game_id", g["id"]),
                    s["user_id"],
                    s.get("user_login"),
                    int(s.get("viewer_count", 0) or 0),
                    s.get("language"),
                    s.get("started_at"),
                )
            )
        time.sleep(0.6)  # stay well under the rate limit

    # NOTE: Helix's games/top does not expose viewer counts, so category viewers
    # = sum of the top ~300 live streams we polled. A consistent undercount for
    # huge categories, which is fine for trend analysis — document in the memo.
    game_rows = [
        (poll_ts, g["id"], g["name"], i + 1, viewers_by_game.get(g["id"], 0))
        for i, g in enumerate(top)
    ]
    upsert_rows(conn, "snapshots", ["poll_ts", "game_id", "game_name", "rank", "viewers"], game_rows)

    upsert_rows(
        conn,
        "streams",
        ["poll_ts", "game_id", "user_id", "user_login", "viewers", "language", "started_at"],
        stream_rows,
    )

    # dedupe: a stream may be returned under a game_id we also poll separately
    conn.execute(
        """
        DELETE FROM streams
        WHERE poll_ts = ? AND user_id IN (
            SELECT user_id FROM (
                SELECT user_id, ROW_NUMBER() OVER (
                    PARTITION BY user_id ORDER BY viewers DESC
                ) AS rn
                FROM streams WHERE poll_ts = ?
            ) WHERE rn > 1
        )
        """,
        (poll_ts, poll_ts),
    )

    counts = {
        "games": len(game_rows),
        "streams": conn.execute(
            "SELECT COUNT(*) FROM streams WHERE poll_ts = ?", (poll_ts,)
        ).fetchone()[0],
        "total_streamers_seen": conn.execute("SELECT COUNT(DISTINCT user_id) FROM streams").fetchone()[0],
    }

    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
        (f"last_poll:{poll_ts}", str(counts)),
    )
    conn.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=30, help="top N game categories to poll")
    args = parser.parse_args()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    client = HelixClient()
    counts = poll(conn, client, args.games)
    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] poll ok: {counts}")
    conn.close()


if __name__ == "__main__":
    main()
