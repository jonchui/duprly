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

        This API curently just use an access token.
        Not oauth style access/refresh token set.
        """
        if self.access_token:
            return 0
        else:
            rc = self.login_user(username, password)
            return rc

    def login_user(self, username: str, password: str) -> int:
        """Low level just do login (will need refresh after)"""
        body = {
            "email": username,
            "password": password,
        }
        logger.debug(f"login user: {username}")
        r = requests.post(self.u("/auth/v1.0/login/"), json=body)
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
        r = requests.get(self.u(url), headers=self.headers())
        logger.debug(f"return: {r.status_code}")
        if r.status_code == 403:
            rc = self.refresh_user()
            if rc == 200:
                logger.debug(f"GET: {url}")
                r = requests.get(self.u(url), headers=self.headers())
                logger.debug(f"return: {r.status_code}")
        self.failed = r.status_code != 200
        return r

    def dupr_post(self, url, json_data=None, name: str = "") -> Response:
        logger.debug(f"POST: {name} : {url}")
        headers = self.headers()
        r = requests.post(self.u(url), headers=headers, json=json_data)
        logger.debug(f"return: {r.status_code}")
        if r.status_code == 403:
            rc = self.refresh_user()
            if rc == 200:
                logger.debug(f"POST: {url}")
                r = requests.post(self.u(url), headers=self.headers())
                logger.debug(f"return: {r.status_code}")
        self.failed = r.status_code != 200
        return r

    def dupr_put(self, url, json_data=None, name: str = "") -> Response:
        logger.debug(f"PUT: {name} : {url}")
        headers = self.headers()
        r = requests.put(self.u(url), headers=headers, json=json_data)
        logger.debug(f"return: {r.status_code}")
        if r.status_code == 403:
            rc = self.refresh_user()
            if rc == 200:
                logger.debug(f"PUT: {url}")
                r = requests.put(self.u(url), headers=self.headers(), json=json_data)
                logger.debug(f"return: {r.status_code}")
        self.failed = r.status_code != 200
        return r

    def get_profile(self) -> tuple[int, dict]:
        r = self.dupr_get(f"/user/{self.version}/profile/", "get_profile")
        if r.status_code == 200:
            self.ppj(r.json())
            return r.status_code, r.json()["result"]
        return r.status_code, None

    def get_player(self, player_id: str) -> tuple[int, Optional[dict]]:
        r = self.dupr_get(f"/player/{self.version}/{player_id}", "get_player")
        if r.status_code == 200:
            self.ppj(r.json())
            return r.status_code, r.json()["result"]
        else:
            return r.status_code, None

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

    def get_members_by_club(self, club_id: str):
        """
        this call is a post call because it supports query and filter.
        """
        data = {"exclude": [], "limit": 20, "offset": 0, "query": "*"}
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

        return r.status_code, pdata

    def search_players(
        self,
        query: str,
        lat: float = 39.977763,
        lng: float = -105.1319296,
        radius_meters: int = 16093400000,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[int, dict]:
        """
        Search for players by name and location

        Args:
            query: Player name to search for
            lat: Latitude for location-based search
            lng: Longitude for location-based search
            radius_meters: Search radius in meters (default ~10,000 miles)
            limit: Maximum number of results to return
            offset: Offset for pagination

        Returns:
            tuple: (status_code, search_results)
        """
        search_data = {
            "filter": {"radiusInMeters": radius_meters, "lat": lat, "lng": lng},
            "includeUnclaimedPlayers": True,
            "address": {"latitude": lat, "longitude": lng},
            "offset": offset,
            "limit": limit,
            "query": query,
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
