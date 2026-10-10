import requests
import time
import utils.config as config
from datetime import datetime
from utils.logger import *


class QBittorrentClient:
    """qBittorrent Web API client. Also works with RDTClient, which copies this API."""

    def __init__(self):
        self.session = requests.Session()
        self.last_sid_refresh = 0
        self.warned_no_cookie = False

    def authenticate(self, force: bool = False):
        now = time.time()
        if not force and now - self.last_sid_refresh < config.qbit_token_refresh_interval:
            return

        logger.info("Refreshing qBittorrent auth token")
        headers = {"Referer": config.qbit_url}
        data = {"username": config.qbit_user, "password": config.qbit_pass}

        try:
            self.session.cookies.clear()
            response = self.session.post(
                f"{config.qbit_url}/auth/login",
                headers=headers,
                data=data,
                timeout=config.request_timeout,
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"qBittorrent authentication failed | {e}")
            return

        if response.text.strip() == "Fails.":
            logger.error("qBittorrent authentication failed, check QBIT_USER and QBIT_PASSWORD")
            return

        # The session keeps whatever cookie the client sets: SID on older qBittorrent,
        # QBT_SID_<port> on qBittorrent 5.2+, and none at all on RDTClient when its
        # authentication is turned off.
        if not self.session.cookies and not self.warned_no_cookie:
            logger.info("Logged in without a session cookie (authentication disabled)")
            self.warned_no_cookie = True

        self.last_sid_refresh = now

    def request(self, method: str, endpoint: str, **kwargs):
        kwargs.setdefault("timeout", config.request_timeout)
        self.authenticate()
        response = self.session.request(method, f"{config.qbit_url}/{endpoint}", **kwargs)

        # The session expired before the refresh interval was up, log in again
        if response.status_code in (401, 403):
            self.authenticate(force=True)
            response = self.session.request(
                method, f"{config.qbit_url}/{endpoint}", **kwargs
            )

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
        return [f["name"] for f in response.json()]

    def remove_torrents(self, hashes: list, delete_files: bool = None):
        if delete_files is None:
            delete_files = config.delete_files

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
