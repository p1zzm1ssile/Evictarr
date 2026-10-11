import requests
import threading
import time
import utils.config as config
from utils.logger import *


class SABnzbdClient:
    """SABnzbd API client (Usenet).

    Usenet downloads have no stalled state and SABnzbd doesn't report when a
    queue item was added, so Evictarr tracks progress itself: an active download
    whose remaining size hasn't changed for longer than TORRENT_AGE is stalled.
    """

    ACTIVE = {"Downloading", "Grabbing", "Fetching"}

    def __init__(self, cfg=None):
        self.cfg = cfg or config
        self.session = requests.Session()
        self.progress = {}  # nzo_id -> (first_seen, mbleft, last_progress)
        self.lock = threading.Lock()

    def call(self, mode: str, **params) -> dict:
        response = self.session.get(
            f"{self.cfg.sabnzbd_url}/api",
            params={"mode": mode, "output": "json", "apikey": self.cfg.sabnzbd_api_key, **params},
            timeout=self.cfg.request_timeout,
        )
        # Don't use raise_for_status, its message includes the URL and so the API key
        if response.status_code == 403:
            raise Exception("API key rejected, check SABNZBD_API_KEY")
        if not response.ok:
            raise Exception(f"{mode} failed | HTTP {response.status_code}")

        body = response.json()

        if isinstance(body, dict) and body.get("status") is False:
            raise Exception(f"{mode} failed | {body.get('error')}")

        return body

    def get_torrents(self) -> list:
        queue = self.call("queue")["queue"]
        now = time.time()
        results = []

        with self.lock:
            seen = {}

            for slot in queue.get("slots", []):
                nzo_id = slot["nzo_id"]
                mbleft = slot.get("mbleft")
                first_seen, last_mbleft, last_progress = self.progress.get(
                    nzo_id, (now, mbleft, now)
                )

                if mbleft != last_mbleft:
                    last_progress = now

                # Nothing moves while the whole queue is paused, so don't count it
                if queue.get("paused"):
                    last_progress = now

                seen[nzo_id] = (first_seen, mbleft, last_progress)
                stuck_minutes = (now - last_progress) / 60

                match slot.get("status"):
                    case "Failed":
                        state = "error"
                    case "Paused":
                        state = "paused"
                    case "Queued":
                        state = "queued"
                    case s if s in self.ACTIVE and stuck_minutes > int(self.cfg.torrent_age):
                        state = "stalled"
                    case s if s in self.ACTIVE or s in {"Checking", "Propagating"}:
                        state = "processing"
                    case _:
                        state = "unknown"

                results.append(
                    {
                        "age": (now - first_seen) / 60,
                        "category": slot.get("cat") or "",
                        "id": nzo_id,
                        "name": slot.get("filename", nzo_id),
                        "state": state,
                    }
                )

            self.progress = seen

        return results

    def get_files(self, torrent_id: str) -> list:
        return [
            {"index": f.get("nzf_id"), "name": f.get("filename", ""), "wanted": True}
            for f in self.call("get_files", value=torrent_id).get("files", [])
        ]

    def skip_files(self, torrent_id: str, files: list):
        # Usenet files can't be paused individually, so they are dropped from the job
        for f in files:
            self.call("queue", name="delete_nzf", value=torrent_id, value2=f["index"])

    def remove_torrents(self, ids: list, delete_files: bool = None):
        if delete_files is None:
            delete_files = self.cfg.delete_files

        self.call("queue", name="delete", value=",".join(ids), del_files=int(delete_files))

    def version(self) -> str:
        # The version call works without an API key, so check the key separately
        self.call("queue", limit=0)
        return self.call("version").get("version", "unknown")
