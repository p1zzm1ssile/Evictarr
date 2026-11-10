import requests
import threading
import time
import utils.config as config
from datetime import datetime
from utils.logger import *


class QBittorrentClient:
    """qBittorrent Web API client. Also works with RDTClient, which copies this API."""

    def __init__(self, cfg=None, prefix="qbit"):
        # prefix picks the settings: "qbit" for qBittorrent, "rdt" for RDTClient
        self.cfg = cfg or config
        self.prefix = prefix
        self.name = "RDTClient" if prefix == "rdt" else "qBittorrent"
        self.session = requests.Session()
        self.last_sid_refresh = 0
        self.warned_no_cookie = False
        # Every check shares this login. Logging in clears the cookies, so two
        # checks logging in at once would knock out each other's session.
        self.login_lock = threading.Lock()

    @property
    def url(self):
        return getattr(self.cfg, f"{self.prefix}_url")

    @property
    def user(self):
        return getattr(self.cfg, f"{self.prefix}_user") or ""

    @property
    def password(self):
        return getattr(self.cfg, f"{self.prefix}_pass") or ""

    def authenticate(self, force: bool = False, seen: float = None):
        """Log in if the login is due for a refresh, or if force is set.

        seen is when the login was last refreshed as of a request that was turned
        away: if another check has logged in again since, that login is used.
        """
        if not force and time.time() - self.last_sid_refresh < self.cfg.qbit_token_refresh_interval:
            return
        with self.login_lock:
            now = time.time()
            if force and seen is not None and self.last_sid_refresh != seen:
                return
            if not force and now - self.last_sid_refresh < self.cfg.qbit_token_refresh_interval:
                return
            self._login(now)

    def _login(self, now: float):
        logger.info(f"Refreshing {self.name} auth token")
        headers = {"Referer": self.url}
        data = {"username": self.user, "password": self.password}

        try:
            self.session.cookies.clear()
            response = self.session.post(
                f"{self.url}/auth/login",
                headers=headers,
                data=data,
                timeout=self.cfg.request_timeout,
            )
            response.raise_for_status()
        except Exception:
            # Not logged here: the request that follows fails too, and the check
            # reports a short reason ("can't connect to ...")
            return

        if response.text.strip() == "Fails.":
            logger.error(f"{self.name} authentication failed, check the username and password")
            return

        # The session keeps whatever cookie the client sets: SID on older qBittorrent,
        # QBT_SID_<port> on qBittorrent 5.2+, and none at all on RDTClient when its
        # authentication is turned off.
        if not self.session.cookies and not self.warned_no_cookie:
            logger.info("Logged in without a session cookie (authentication disabled)")
            self.warned_no_cookie = True

        self.last_sid_refresh = now

    # Wait before the one retry after a timeout or a dropped connection
    RETRY_DELAY = 2

    def send(self, method: str, endpoint: str, **kwargs):
        """Send a request, trying once more if it times out or the connection drops."""
        try:
            return self.session.request(method, f"{self.url}/{endpoint}", **kwargs)
        except (requests.Timeout, requests.ConnectionError):
            time.sleep(self.RETRY_DELAY)
            return self.session.request(method, f"{self.url}/{endpoint}", **kwargs)

    def request(self, method: str, endpoint: str, **kwargs):
        kwargs.setdefault("timeout", self.cfg.request_timeout)
        self.authenticate()
        seen = self.last_sid_refresh
        response = self.send(method, endpoint, **kwargs)

        # The session expired before the refresh interval was up, log in again
        if response.status_code in (401, 403):
            self.authenticate(force=True, seen=seen)
            response = self.send(method, endpoint, **kwargs)

        response.raise_for_status()
        return response

    def get_torrents(self) -> list:
        response = self.request("GET", "torrents/info")
        results = []

        for t in response.json():
            added = datetime.fromtimestamp(int(t["added_on"]))
            now = datetime.now()
            age = (now - added).total_seconds() / 60

            match t["state"]:
                case "error" | "missingFiles":
                    state = "error"
                case "pausedUP" | "queuedUP" | "uploading" | "stalledUP" | "stoppedUP" | "forcedUP":
                    state = "finished"
                case "downloading" | "forcedDL" | "checkingUP" | "checkingDL" | "moving":
                    state = "processing"
                case "pausedDL" | "stoppedDL":
                    state = "paused"
                case "queuedDL":
                    state = "queued"
                case "stalledDL" | "metaDL":
                    state = "stalled"
                case "checkingResumeData":
                    # qBittorrent is still starting up and loading its torrents
                    state = "loading"
                case _:
                    state = "unknown"

            results.append(
                {
                    "age": age,
                    "category": t["category"],
                    "id": t["hash"],
                    "name": t["name"],
                    "state": state,
                }
            )

        return results

    def get_files(self, torrent_id: str) -> list:
        response = self.request("GET", "torrents/files", params={"hash": torrent_id})
        return [
            {"index": f.get("index", i), "name": f["name"], "wanted": f.get("priority", 1) != 0}
            for i, f in enumerate(response.json())
        ]

    def skip_files(self, torrent_id: str, files: list):
        self.request(
            "POST",
            "torrents/filePrio",
            data={
                "hash": torrent_id,
                "id": "|".join(str(f["index"]) for f in files),
                "priority": 0,
            },
        )

    def remove_torrents(self, hashes: list, delete_files: bool = None):
        if delete_files is None:
            delete_files = self.cfg.delete_files

        self.request(
            "POST",
            "torrents/delete",
            data={
                "hashes": "|".join(hashes),
                "deleteFiles": str(delete_files).lower(),
            },
        )

    def version(self) -> str:
        return self.request("GET", "app/version").text
