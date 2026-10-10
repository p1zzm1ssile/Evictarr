import posixpath
import requests
import utils.config as config
from datetime import datetime
from utils.logger import *


class TransmissionClient:
    """Transmission RPC client."""

    SESSION_HEADER = "X-Transmission-Session-Id"

    def __init__(self):
        self.session = requests.Session()
        if config.transmission_user:
            self.session.auth = (config.transmission_user, config.transmission_pass or "")

    def call(self, method: str, arguments: dict = None) -> dict:
        payload = {"method": method, "arguments": arguments or {}}
        response = self.session.post(
            config.transmission_url, json=payload, timeout=config.request_timeout
        )

        # Transmission answers 409 with a fresh session id that has to be sent back
        if response.status_code == 409:
            self.session.headers[self.SESSION_HEADER] = response.headers[self.SESSION_HEADER]
            response = self.session.post(
                config.transmission_url, json=payload, timeout=config.request_timeout
            )

        if response.status_code == 401:
            raise Exception("authentication failed, check TRANSMISSION_USER and TRANSMISSION_PASSWORD")

        response.raise_for_status()
        body = response.json()

        if body.get("result") != "success":
            raise Exception(f"{method} failed | {body.get('result')}")

        return body.get("arguments", {})

    def get_torrents(self) -> list:
        fields = [
            "hashString",
            "name",
            "status",
            "error",
            "addedDate",
            "percentDone",
            "rateDownload",
            "peersSendingToUs",
            "downloadDir",
            "labels",
        ]
        torrents = self.call("torrent-get", {"fields": fields}).get("torrents", [])
        results = []

        for t in torrents:
            added = datetime.fromtimestamp(int(t["addedDate"]))
            now = datetime.now()
            age = (now - added).total_seconds() / 60

            # Transmission has no stalled state of its own. Treat a downloading
            # torrent with no peers sending anything as stalled.
            match t["status"]:
                case _ if t["error"] == 3:  # local error, e.g. disk or permissions
                    state = "error"
                case 0 if t["percentDone"] >= 1:
                    state = "finished"
                case 0:
                    state = "paused"
                case 1 | 2:
                    state = "processing"
                case 3:
                    state = "queued"
                case 4 if t["rateDownload"] == 0 and t["peersSendingToUs"] == 0:
                    state = "stalled"
                case 4:
                    state = "processing"
                case 5 | 6:
                    state = "finished"
                case _:
                    state = "unknown"

            # Sonarr and Radarr put the category in a label on Transmission 4.0+,
            # and in a subfolder of the download folder on older versions
            folder = posixpath.basename((t.get("downloadDir") or "").replace("\\", "/").rstrip("/"))
            categories = [*(t.get("labels") or []), folder]

            results.append(
                {
                    "age": age,
                    "category": categories[0],
                    "categories": categories,
                    "id": t["hashString"],
                    "name": t["name"],
                    "state": state,
                }
            )

        return results

    def get_files(self, torrent_id: str) -> list:
        torrents = self.call(
            "torrent-get", {"ids": [torrent_id], "fields": ["files", "fileStats"]}
        ).get("torrents", [])
        return [
            {"index": i, "name": f["name"], "wanted": stats.get("wanted", True)}
            for t in torrents
            for i, (f, stats) in enumerate(zip(t.get("files", []), t.get("fileStats", [])))
        ]

    def skip_files(self, torrent_id: str, files: list):
        self.call(
            "torrent-set",
            {"ids": [torrent_id], "files-unwanted": [f["index"] for f in files]},
        )

    def remove_torrents(self, hashes: list, delete_files: bool = None):
        if delete_files is None:
            delete_files = config.delete_files

        self.call(
            "torrent-remove",
            {"ids": hashes, "delete-local-data": delete_files},
        )

    def version(self) -> str:
        return self.call("session-get", {"fields": ["version"]}).get("version", "unknown")
