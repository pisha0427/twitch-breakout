"""Twitch Helix API client — app access token (client credentials) flow.

Only public-data endpoints; no user OAuth needed.
"""
from __future__ import annotations

import os
import time

import requests

# local credentials support: load .env from the project directory if present
try:
    from dotenv import load_dotenv
    _ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(_ENV_PATH):
        load_dotenv(_ENV_PATH)
except ImportError:
    pass

POLL_TS_FMT = "%Y-%m-%dT%H:%M:%SZ"

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
HELIX = "https://api.twitch.tv/helix"

MAX_RETRIES = 5



class HelixClient:
    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        # strip(): secrets pasted into GitHub/UIs often carry a trailing newline,
        # which breaks the OAuth request with an unhelpful 403 — trim it here.
        self.client_id = str(client_id or os.environ.get("TWITCH_CLIENT_ID", "")).strip()
        self.client_secret = str(client_secret or os.environ.get("TWITCH_CLIENT_SECRET", "")).strip()
        if not self.client_id or not self.client_secret:
            raise SystemExit(
                "Missing TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET. "
                "Set them in the environment or a .env file (see .env.example)."
            )
        self._token: str | None = None
        self._expires_at = 0.0
        self.session = requests.Session()

    # -- auth ---------------------------------------------------------------
    def _fetch_token(self) -> None:
        resp = self.session.post(
            TOKEN_URL,
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        # refresh 2 minutes early to dodge edge-of-expiry 401s
        self._expires_at = time.time() + int(data.get("expires_in", 3600)) - 120

    def _token_valid(self) -> bool:
        return self._token is not None and time.time() < self._expires_at

    # -- core ---------------------------------------------------------------
    def get(self, endpoint: str, params: dict | None = None):
        """GET a Helix endpoint. Returns (items, cursor)."""
        params = dict(params or {})
        for attempt in range(MAX_RETRIES):
            if not self._token_valid():
                self._fetch_token()
            headers = {
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {self._token}",
            }
            try:
                resp = self.session.get(
                    f"{HELIX}/{endpoint}", headers=headers, params=params, timeout=30
                )
            except requests.RequestException:
                time.sleep(2**attempt * 2)
                continue

            if resp.status_code == 429:  # rate limited — back off and retry
                time.sleep(2**attempt * 5)
                continue
            if resp.status_code == 401:  # token revoked/expired mid-run
                self._token = None
                continue
            if resp.status_code >= 500:
                time.sleep(2**attempt * 2)
                continue

            resp.raise_for_status()
            data = resp.json()
            cursor = data.get("pagination", {}).get("cursor")
            return data.get("data", []), cursor

        raise RuntimeError(f"{endpoint}: failed after {MAX_RETRIES} retries")

    def get_paginated(self, endpoint: str, params: dict | None = None, max_pages: int = 10):
        """Collect all pages (up to max_pages) from a paginated endpoint."""
        items: list[dict] = []
        cursor = None
        for _ in range(max_pages):
            page_params = dict(params or {})
            if cursor:
                page_params["after"] = cursor
            page, cursor = self.get(endpoint, page_params)
            items.extend(page)
            if not cursor:
                break
        return items

    # -- project endpoints --------------------------------------------------
    def top_games(self, first: int = 100) -> list[dict]:
        return self.get_paginated("games/top", {"first": min(first, 100)}, max_pages=3)

    def streams_for_game(self, game_id: str, limit: int = 300) -> list[dict]:
        """Top `limit` live streams in one game category."""
        streams = self.get_paginated(
            "streams", {"game_id": game_id, "first": 100}, max_pages=(limit + 99) // 100
        )
        return streams[:limit]

    def streams_all(self, first: int = 100, max_pages: int = 5) -> list[dict]:
        """Site-wide live streams (no game filter)."""
        return self.get_paginated("streams", {"first": min(first, 100)}, max_pages=max_pages)
