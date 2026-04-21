"""
A client to access the unofficial DUPR API.
This API seems to be mostly a backend for front end type of API that
does not necessarily fit other use.

There is a automatically generated swagger doc that helps a little
but check the data return and project readme for more tips to
use this effectively

https://api.dupr.gg/swagger-ui/index.html

"""

import os
import requests
from requests import Response
from loguru import logger
import json
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


def _resolve_tls_verify() -> "bool | str":
    """
    Return the value to pass as `requests.*(verify=...)`.

    Controlled by `DUPR_TLS_VERIFY`:
      - unset / "1" / "true" / "yes" → True (default, verify normally)
      - "0" / "false" / "no" / "off"  → False (skip verification — dev only)
      - any other value               → treated as a path to a CA bundle

    Rationale: some local environments (corporate VPN, Zscaler, Little Snitch,
    stale certifi bundles) intercept HTTPS with their own CA and break the
    trust chain for `api.dupr.gg`. When that happens every `requests` call
    raises `SSLCertVerificationError` *before* any bytes go out, which the
    outer error handlers in `dupr_live.search` then swallow — the user sees
    "no results" with zero diagnostic signal. This flag is a documented
    escape hatch; production should leave it default.
    """
    raw = os.environ.get("DUPR_TLS_VERIFY")
    if raw is None:
        return True
    lowered = raw.strip().lower()
    if lowered in ("", "1", "true", "yes", "on"):
        return True
    if lowered in ("0", "false", "no", "off"):
        return False
    return raw  # treat as a CA bundle path


class DuprClient(object):

    def __init__(
        self, api_url: str = None, api_version: str = None, verbose: bool = False
    ):
        self.env_path = os.path.expanduser("~/.duprly_config")
        logger.debug(self.env_path)
        if api_url:
            self.env_url = api_url
        else:
            self.env_url = "https://api.dupr.gg"
        if api_version:
            self.version = api_version
        else:
            self.version = "v1.0"
        self.access_token = None
        self.refresh_token = None  # from login
        self.failed = False  # Strange way to return error, for now TBD
        self.verbose = verbose
        # TLS verify behavior is env-driven so we can flip it without a code
        # change when a machine's trust store is broken. See
        # `_resolve_tls_verify` for the accepted values.
        self._tls_verify = _resolve_tls_verify()
        if self._tls_verify is False:
            logger.warning(
                "DuprClient: TLS verification DISABLED via DUPR_TLS_VERIFY — "
                "dev-only escape hatch; do not use in production."
            )
            # Silence the noisy InsecureRequestWarning since the user opted in.
            try:
                import urllib3  # type: ignore
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass
        self.load_token()

    def load_token(self):
        """Load access token stored locally if available"""
        try:
            with open(self.env_path, "r") as f:
                data = json.load(f)
                logger.debug(f"{data['access_token'][:10]}...")
                self.access_token = data["access_token"]
        except FileNotFoundError:
            pass

    def save_token(self):
        """Save  access token to disk, in plain json text"""
        try:
            with open(self.env_path, "w") as f:
                data = {"access_token": self.access_token}
                json.dump(data, f)
        except FileNotFoundError:
            logger.debug(f"Cannot save token to {self.env_path}")

    def u(self, parts):
        """Helper function to construct URL"""
        url = f"{self.env_url}{parts}"
        return url

    def ppj(self, data):
        """Pretty Print Json for debug"""
        if self.verbose:
            logger.debug(json.dumps(data, indent=4))

    def save_json_to_file(self, name: str, data: dict):
        """Save raw json to file for later use"""
        with open(f"{name}.json", "w") as f:
            json.dump(data, f)

    def load_json_from_file(self, name: str) -> dict:
        """
        Load previously saved json from file.
        """
        with open(f"{name}.json", "r") as f:
            data = json.load(f)
            return data

    def auth_user(self, username: str, password: str) -> int:
        """This is the external callable auth method.
        It handles a saved access token, no need to re-login, or
        login and save token for next time.

        This API currently just uses an access token (no refresh-token OAuth
        dance). JWTs from `/auth/v1.0/login/` expire after ~30 days and DUPR
        returns `401 {"status":"FAILURE","message":"Session expired"}` once
        they lapse — at which point every subsequent request fails until we
        re-login. We stash the creds so `dupr_get`/`dupr_post` can re-login
        transparently when they see a 401, instead of surfacing the error
        all the way up to the UI.
        """
        self._username = username
        self._password = password
        if self.access_token:
            return 0
        else:
            rc = self.login_user(username, password)
            return rc

    def _relogin(self) -> int:
        """Discard the cached token and re-run the login flow.

        Returns the HTTP status code from the login call (200 = ok). Callers
        typically invoke this after observing a 401 on an authed request.
        Safe no-op returning 0 when we don't have stored creds (e.g. the
        client was constructed manually without going through `auth_user`).
        """
        username = getattr(self, "_username", None)
        password = getattr(self, "_password", None)
        if not username or not password:
            return 0
        self.access_token = None
        rc = self.login_user(username, password)
        return rc

    def login_user(self, username: str, password: str) -> int:
        """Low level just do login (will need refresh after)"""
        body = {
            "email": username,
            "password": password,
        }
        logger.debug(f"login user: {username}")
        try:
            r = requests.post(
                self.u("/auth/v1.0/login/"), json=body, verify=self._tls_verify
            )
        except requests.exceptions.SSLError as exc:
            logger.error(
                f"login_user: TLS verification failed talking to DUPR ({exc}). "
                f"Set DUPR_TLS_VERIFY=0 in your .env to bypass (dev only) or "
                f"upgrade certifi / fix your trust store."
            )
            return 0
        logger.debug(f"login user: {r.status_code}")
        logger.debug(f"login user: {r.request.url}")
        if r.status_code == 200:
            data = r.json()
            self.ppj(data)
            self.access_token = data.get("result").get("accessToken")
            logger.debug(f"access token: {self.access_token[:10]}...")
            self.save_token()
        return r.status_code

    def headers(self):
        return {"Authorization": f"Bearer {self.access_token}"}

    def dupr_get(self, url, name: str = "") -> Response:
        logger.debug(f"GET: {name} : {url}")
        r = requests.get(self.u(url), headers=self.headers(), verify=self._tls_verify)
        logger.debug(f"return: {r.status_code}")
        # 401 = "Session expired" (DUPR's signal to re-login). 403 = forbidden
        # (keep the legacy refresh path). Both should trigger a fresh login
        # against the stored creds and a single retry.
        if r.status_code in (401, 403):
            rc = self._relogin() if r.status_code == 401 else self.refresh_user()
            if rc == 200:
                logger.debug(f"retry GET after relogin: {url}")
                r = requests.get(
                    self.u(url), headers=self.headers(), verify=self._tls_verify
                )
                logger.debug(f"return: {r.status_code}")
        self.failed = r.status_code != 200
        return r

    def dupr_post(self, url, json_data=None, name: str = "") -> Response:
        logger.debug(f"POST: {name} : {url}")
        headers = self.headers()
        r = requests.post(
            self.u(url), headers=headers, json=json_data, verify=self._tls_verify
        )
        logger.debug(f"return: {r.status_code}")
        # See dupr_get for the 401/403 rationale — re-login on 401 ("Session
        # expired") and retry the POST once with the same json body.
        if r.status_code in (401, 403):
            rc = self._relogin() if r.status_code == 401 else self.refresh_user()
            if rc == 200:
                logger.debug(f"retry POST after relogin: {url}")
                r = requests.post(
                    self.u(url),
                    headers=self.headers(),
                    json=json_data,
                    verify=self._tls_verify,
                )
                logger.debug(f"return: {r.status_code}")
        self.failed = r.status_code != 200
        return r

    def dupr_put(self, url, json_data=None, name: str = "") -> Response:
        logger.debug(f"PUT: {name} : {url}")
        headers = self.headers()
        r = requests.put(
            self.u(url), headers=headers, json=json_data, verify=self._tls_verify
        )
        logger.debug(f"return: {r.status_code}")
        if r.status_code == 403:
            rc = self.refresh_user()
            if rc == 200:
                logger.debug(f"PUT: {url}")
                r = requests.put(
                    self.u(url),
                    headers=self.headers(),
                    json=json_data,
                    verify=self._tls_verify,
                )
                logger.debug(f"return: {r.status_code}")
        self.failed = r.status_code != 200
        return r

    def get_profile(self) -> tuple[int, dict]:
        r = self.dupr_get(f"/user/{self.version}/profile/", "get_profile")
        if r.status_code == 200:
            self.ppj(r.json())
            return r.status_code, r.json()["result"]
        return r.status_code, None

    def _is_short_dupr_id(self, player_id: str) -> bool:
        """True if this looks like a short duprId (e.g. L2PLVZ) not a numeric id."""
        if not player_id or not isinstance(player_id, str):
            return False
        s = player_id.strip()
        return 4 <= len(s) <= 12 and not s.isdigit()

    def get_player(self, player_id: str) -> tuple[int, Optional[dict]]:
        """Get player by numeric id or short duprId. Falls back to search when short id returns 4xx."""
        player_id = str(player_id).strip()
        r = self.dupr_get(f"/player/{self.version}/{player_id}", "get_player")
        if r.status_code == 200:
            self.ppj(r.json())
            return r.status_code, r.json()["result"]
        # API returns 400/404 for short duprId; resolve via search (search accepts short id as query)
        if 400 <= r.status_code < 500 and self._is_short_dupr_id(player_id):
            rc, result = self.search_players(player_id, limit=10)
            if rc == 200 and result:
                hits = result.get("hits") if isinstance(result, dict) else (result if isinstance(result, list) else [])
                if not isinstance(hits, list):
                    hits = []
                for hit in hits:
                    if hit and (hit.get("duprId") or "").strip().upper() == player_id.upper():
                        return 200, hit
        return r.status_code, None

    def enrich_members_with_ratings(
        self,
        members: list[dict],
        limit: int = 500,
        delay_sec: float = 0.05,
        max_workers: int = 0,
    ) -> list[dict]:
        """
        For each member (up to limit), call get_player(id or duprId) and merge ratings into member.
        Use when club members API returns no ratings.
        - delay_sec: used only when max_workers=0 to avoid rate limits.
        - max_workers: if > 0, fetch in parallel (e.g. 10) instead of one-by-one; no delay between calls.
        DUPR has no batch player API, so we "batch" by concurrency (many get_player calls in parallel).
        """
        import time
        to_fetch = []
        for i, member in enumerate(members):
            if i >= limit:
                break
            player_id = member.get("id") or member.get("duprId")
            if player_id is not None:
                to_fetch.append((i, member, str(player_id)))

        if max_workers and max_workers > 0:
            def fetch_one(item):
                idx, member, pid = item
                rc, player = self.get_player(pid)
                if rc == 200 and player and isinstance(player.get("ratings"), dict):
                    member["ratings"] = player["ratings"]
                return idx

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(fetch_one, item): item for item in to_fetch}
                for f in as_completed(futures):
                    f.result()
            return members
        else:
            for _, member, player_id in to_fetch:
                rc, player = self.get_player(player_id)
                if rc == 200 and player and isinstance(player.get("ratings"), dict):
                    member["ratings"] = player["ratings"]
                if delay_sec > 0:
                    time.sleep(delay_sec)
            return members

    def get_club(self, club_id: str):
        r = self.dupr_get(f"/club/{self.version}/{club_id}", "get_club")
        if r.status_code == 200:
            self.ppj(r.json())
        return r.status_code

    def get_member_match_history_p(self, member_id: str) -> tuple[int, list]:
        page_data = {
            "filters": {},
            "sort": {
                "order": "DESC",
                "parameter": "MATCH_DATE",
            },
            "limit": 10,
            "offset": 0,
        }
        offset = 0
        hit_data = []
        while offset is not None:
            r = self.dupr_post(
                f"/player/{self.version}/{member_id}/history",
                page_data,
                name="get_member_match_history",
            )
            if r.status_code == 200:
                offset, hits = self.handle_paging(r.json())
                hit_data.extend(hits)
                page_data["offset"] = offset
        self.ppj(page_data)
        return r.status_code, hit_data

    def get_member_match_history(self, member_id: str) -> tuple[int, list]:
        offset = 0
        hit_data = []
        while offset is not None:
            r = self.dupr_get(
                f"/player/{self.version}/{member_id}/history?limit=100&offset={offset}",
                name="get_member_match_history",
            )
            if r.status_code == 200:
                offset, hits = self.handle_paging(r.json())
                hit_data.extend(hits)
        self.ppj(hit_data)
        return r.status_code, hit_data

    def handle_paging(self, json_data):
        """
        Handle results that are paged.
        use like this:

            while offset is not None:
                dupr_get
                offset, hits = handle_paging(response.json())

        """
        result = json_data["result"]
        total = result["total"]
        offset = result["offset"]
        limit = result["limit"]
        hits = result["hits"]
        if offset + limit < total:
            # there is more
            return offset + limit, hits
        else:
            return None, hits

    def _member_rating_value(self, member: dict, kind: str = "doubles") -> str:
        """Get rating string from member using multiple possible API key paths. Returns 'NR' if missing."""
        for ratings in (member.get("ratings"), member.get("rating")):
            if not isinstance(ratings, dict):
                continue
            # Try common key variants (API may use different casing or naming)
            keys = (
                ["doubles", "Doubles", "DOUBLES", "doublesRating", "doubles_rating"]
                if kind == "doubles"
                else ["singles", "Singles", "SINGLES", "singlesRating", "singles_rating"]
            )
            for key in keys:
                val = ratings.get(key)
                if val is not None and str(val).strip() and str(val).upper() != "NR":
                    return str(val).strip()
        # Top-level fallback (some APIs put rating at member root)
        val = member.get("doubles" if kind == "doubles" else "singles")
        if val is not None and str(val).strip() and str(val).upper() != "NR":
            return str(val).strip()
        return "NR"

    def _member_doubles_sort_key(self, member: dict) -> float:
        """Sort key for member by doubles rating (highest first). NR/empty → -1 so they sort last."""
        raw = self._member_rating_value(member, "doubles")
        if raw == "NR":
            return -1.0
        try:
            return float(raw)
        except (TypeError, ValueError):
            return -1.0

    def get_members_by_club(
        self,
        club_id: str,
        sort_by_recent: bool = False,
        sort_by_rating: bool = False,
    ):
        """
        this call is a post call because it supports query and filter.
        If sort_by_recent True, request sort by join date descending (API may support).
        If sort_by_rating True, sort members client-side by doubles rating (highest first).
        """
        data = {"exclude": [], "limit": 20, "offset": 0, "query": "*"}
        if sort_by_recent:
            data["sort"] = {"parameter": "JOIN_DATE", "order": "DESC"}
        offset = 0
        pdata = []
        while offset is not None:
            data["offset"] = offset
            r = self.dupr_post(
                f"/club/{club_id}/members/v1.0/all",
                json_data=data,
                name="get_member_by_club",
            )
            if r.status_code == 200:
                self.ppj(r.json())
                offset, hits = self.handle_paging(r.json())
                pdata.extend(hits)

        if sort_by_rating and pdata:
            pdata = sorted(pdata, key=self._member_doubles_sort_key, reverse=True)

        return r.status_code, pdata

    def search_players(
        self,
        query: str,
        lat: float = 39.977763,
        lng: float = -105.1319296,
        radius_meters: int = 0,  # deprecated/ignored — kept for backward compat
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[int, dict]:
        """
        Search for players by name and location.

        Body matches DUPR's own dashboard (dashboard.dupr.com) request shape.
        Previously we sent `filter.radiusInMeters` with a 10k-mile radius and
        a top-level `address` field — DUPR's server treated these as hard
        location filters and silently dropped out-of-area hits (e.g. searching
        "bryan sullivan" returned nothing even though the dashboard found him).
        The dashboard uses `filter.locationText: ""` to bias ranking by the
        requester's coords without enforcing a radius, so we do the same.

        Args:
            query: Player name (or DUPR id / short DUPR id) to search for.
            lat / lng: Coords used for location-based *ranking* (not filtering).
            radius_meters: deprecated — ignored. Kept as a kwarg so existing
                callers that pass it don't break.
            limit: Max number of results.
            offset: Pagination offset.

        Returns:
            tuple: (status_code, search_results)
        """
        del radius_meters  # intentionally unused — see docstring above.
        search_data = {
            "limit": limit,
            "offset": offset,
            "query": query,
            "exclude": [],
            "includeUnclaimedPlayers": True,
            "filter": {
                "lat": lat,
                "lng": lng,
                "rating": {"maxRating": None, "minRating": None},
                "locationText": "",
            },
        }

        r = self.dupr_post(
            f"/player/{self.version}/search",
            json_data=search_data,
            name="search_players",
        )
        if r.status_code == 200:
            self.ppj(r.json())
            return r.status_code, r.json()["result"]
        else:
            return r.status_code, None

    def add_members(
        self, club_id: str, user_ids: list[int]
    ) -> tuple[int, Optional[dict]]:
        """Add existing DUPR users to a club by numeric user ids.

        Args:
            club_id: Club id (numeric string)
            user_ids: List of numeric DUPR user ids (not duprId short codes)

        Returns:
            (status_code, parsed_json or None)
        """
        payload = {"userIds": user_ids}
        r = self.dupr_put(
            f"/club/{club_id}/members/v1.0/add", json_data=payload, name="add_members"
        )
        try:
            data = r.json()
        except Exception:
            data = None
        return r.status_code, data

    def add_members_bulk(
        self, club_id: str, add_members: list[dict]
    ) -> tuple[int, Optional[dict]]:
        """Bulk add members by name/email.

        Args:
            club_id: Club id (numeric string)
            add_members: List of dicts with keys like {"fullName": str, "email": str}

        Returns:
            (status_code, parsed_json or None)
        """
        payload = {"addMembers": add_members}
        r = self.dupr_put(
            f"/club/{club_id}/members/v1.0/multiple/add",
            json_data=payload,
            name="add_members_bulk",
        )
        try:
            data = r.json()
        except Exception:
            data = None
        return r.status_code, data

    def refresh_user(self) -> int:
        """Refresh access token if needed"""
        # This would need to be implemented based on DUPR's refresh mechanism
        # For now, just return 200 as a placeholder
        return 200

    def get_expected_score(
        self,
        teams,
        event_format="DOUBLES",
        match_source="CLUB",
        game_count=1,
        winning_score=11,
        match_type="SIDE_ONLY",
    ) -> tuple[int, dict]:
        """
        Get expected scores for a match between teams

        Args:
            teams: List of teams, each team is a dict with player1Id and player2Id
            event_format: "DOUBLES" or "SINGLES"
            match_source: "CLUB", "TOURNAMENT", etc.
            game_count: Number of games (default 1)
            winning_score: Winning score (default 11)
            match_type: "SIDE_ONLY", "SIDE_AND_SERVE", etc.

        Returns:
            tuple: (status_code, expected_scores)
        """
        request_data = {
            "teams": teams,
            "eventFormat": event_format,
            "matchSource": match_source,
            "gameCount": game_count,
            "winningScore": winning_score,
            "matchType": match_type,
        }

        r = self.dupr_post(
            f"/match/{self.version}/expected-score",
            json_data=request_data,
            name="get_expected_score",
        )
        if r.status_code == 200:
            self.ppj(r.json())
            return r.status_code, r.json()
        else:
            return r.status_code, None

    def get_forecast(
        self,
        teams,
        event_format: str = "DOUBLES",
        match_source: str = "CLUB",
        game_count: int = 1,
        winning_score: int = 11,
        match_type: str = "SIDE_ONLY",
    ) -> tuple[int, dict]:
        """
        Call DUPR's official match forecaster.

        Same request shape as `/expected-score` but the response carries the
        full rating-impact curves (`winningRatingImpacts`, `winProbabilityPercentage`)
        that power the "DUPR Forecaster" view in the iOS / web app.

        See `tests/fixtures/dupr_api/07-forecast-to-11.*` for a canonical
        request / response pair.

        Args:
            teams: List of teams, each a dict with player1Id and player2Id
                   (use player2Id == player1Id — or drop it — for singles).
            event_format: "DOUBLES" or "SINGLES"
            match_source: "CLUB" | "TOURNAMENT" | ...
            game_count:   Number of games played in the match (usually 1).
            winning_score: Target game score (11 / 15 / 21).
            match_type:   "SIDE_ONLY" | "SIDE_AND_SERVE" | ...

        Returns:
            (status_code, parsed response dict) — response shape documented
            in tests/fixtures/dupr_api/README.md.
        """
        request_data = {
            "teams": teams,
            "eventFormat": event_format,
            "matchSource": match_source,
            "gameCount": game_count,
            "winningScore": winning_score,
            "matchType": match_type,
        }
        r = self.dupr_post(
            f"/match/{self.version}/forecast",
            json_data=request_data,
            name="get_forecast",
        )
        if r.status_code == 200:
            self.ppj(r.json())
            return r.status_code, r.json()
        return r.status_code, None
