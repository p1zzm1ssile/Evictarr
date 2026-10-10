import requests
import utils.config as config
from datetime import datetime
from utils.logger import *


class DelugeClient:
    """Talks to the Deluge Web UI JSON-RPC API (Deluge 1.3 and 2.x)."""

    NOT_AUTHENTICATED = 1

    def __init__(self):
        self.session = requests.Session()
        self.request_id = 0

    def call(self, method: str, params: list, retry: bool = True):
        self.request_id += 1
        response = self.session.post(
            f"{config.deluge_url}/json",
            json={"method": method, "params": params, "id": self.request_id},
            timeout=config.request_timeout,
        )
        response.raise_for_status()
        body = response.json()
        error = body.get("error")

        if error:
            if retry and error.get("code") == self.NOT_AUTHENTICATED:
                self.authenticate()
                return self.call(method, params, retry=False)
            raise Exception(f"{method} failed | {error.get('message')}")

        return body.get("result")

    def authenticate(self):
        logger.info("Logging in to Deluge")
        self.session.cookies.clear()

        if not self.call("auth.login", [config.deluge_pass], retry=False):
            logger.error("Deluge authentication failed, check DELUGE_PASSWORD")
            return

        # The Web UI has to be connected to a Deluge daemon before core.* calls work
        if self.call("web.connected", [], retry=False):
            return

        hosts = self.call("web.get_hosts", [], retry=False) or []
        if not hosts:
            logger.error("Deluge Web UI has no daemon configured to connect to")
            return

        self.call("web.connect", [hosts[0][0]], retry=False)
        logger.info(f"Connected Deluge Web UI to daemon {hosts[0][1]}:{hosts[0][2]}")

    def get_torrents(self) -> list:
        keys = [
            "name",
            "state",
            "label",
            "time_added",
            "progress",
            "download_payload_rate",
            "num_seeds",
        ]

        torrents = self.call("core.get_torrents_status", [{}, keys])
        results = []

        for torrent_hash, t in (torrents or {}).items():
            added = datetime.fromtimestamp(int(t["time_added"]))
            now = datetime.now()
            age = (now - added).total_seconds() / 60

            # Deluge has no stalled state of its own. Treat a downloading torrent
            # with no seeds connected and nothing coming in as stalled.
            match t["state"]:
                case "Error":
                    state = "error"
                case "Seeding":
                    state = "finished"
                case "Paused" if t["progress"] >= 100:
                    state = "finished"
                case "Paused":
                    state = "paused"
                case "Queued":
                    state = "queued"
                case "Downloading" if (
                    t["download_payload_rate"] == 0 and t["num_seeds"] == 0
                ):
                    state = "stalled"
                case "Downloading" | "Checking" | "Allocating" | "Moving":
                    state = "processing"
                case _:
                    state = "unknown"

            results.append(
                {
                    "age": age,
                    # Categories in Deluge come from the Label plugin
                    "category": t.get("label") or "",
                    "id": torrent_hash,
                    "name": t["name"],
                    "state": state,
                }
            )

        return results

    def remove_torrents(self, hashes: list):
        try:
            self.call("core.remove_torrents", [hashes, config.delete_files])
        except Exception:
            # Deluge 1.3 has no bulk remove, so remove one at a time
            for h in hashes:
                self.call("core.remove_torrent", [h, config.delete_files])

    def version(self) -> str:
        return self.call("daemon.get_version", [])
