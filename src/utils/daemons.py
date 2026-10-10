import requests
import time
import utils.config as config
import utils.status as status
import sys
from utils.logger import *
from utils.webui import *
from services.sonarr import Sonarr
from services.radarr import Radarr
from services.qbittorrent import QBittorrentClient
from services.deluge import DelugeClient
from services.transmission import TransmissionClient
from services.sabnzbd import SABnzbdClient

# Sonarr/Radarr queue states for a finished download they couldn't import
FAILED_IMPORT_STATES = {"importPending", "importBlocked", "importFailed"}


def describe_error(e: Exception) -> str:
    """A short reason for an error, without the long request details."""
    request = getattr(e, "request", None)
    host = request.url.split("/")[2] if request is not None and request.url else "server"

    if isinstance(e, requests.ConnectionError):
        return f"can't connect to {host}"
    if isinstance(e, requests.Timeout):
        return f"{host} didn't respond within {config.request_timeout} seconds"
    if isinstance(e, requests.HTTPError) and e.response is not None:
        code = e.response.status_code
        hint = " (check the API key)" if code == 401 else ""
        return f"{host} answered HTTP {code}{hint}"
    return str(e)


def in_labels(torrent: dict, labels: list) -> bool:
    return any(c in labels for c in torrent.get("categories") or [torrent["category"]])


class Daemons:
    def __init__(self):
        self.sonarr = Sonarr()
        self.radarr = Radarr()
        self.file_cache = {}  # download id -> file names, which don't change once known

        match config.torrent_client.lower():
            case "qbittorrent" | "rdtclient":
                self.torrent_client = QBittorrentClient()
            case "deluge":
                self.torrent_client = DelugeClient()
            case "transmission":
                self.torrent_client = TransmissionClient()
            case "sabnzbd":
                self.torrent_client = SABnzbdClient()
            case _:
                logger.critical(f"Unsupported download client: {config.torrent_client}")
                sys.exit(1)

        try:
            self.torrent_client_version = self.torrent_client.version()
            logger.info(f"Found {config.torrent_client} {self.torrent_client_version}")
            status.set_client(config.torrent_client, self.torrent_client_version)
        except Exception as e:
            logger.error(f"Failed to communicate with {config.torrent_client} | {describe_error(e)}")
            sys.exit(1)

    def remove_log(self, type: str, torrents):
        n = 0
        for t in torrents:
            n += 1
            logger.log(
                "ACTION", f"({n}/{len(torrents)}) Purging {type} download: {t['name']}"
            )

    def run_forever(self, check: str, interval: int, cycle):
        """Run one check every interval, recording how each run went.

        An error in one run is logged and recorded, and the next run still happens.
        """
        status.register(check, interval)

        while True:
            try:
                ok, summary = cycle()
            except Exception as e:
                ok, summary = False, f"Failed: {describe_error(e)}"

            status.record(check, ok, summary)
            log = logger.info if ok else logger.error
            log(f"{check.capitalize()} check: {summary} (next check in {interval}s)")

            time.sleep(interval)

    def imported_evictarr(self):
        self.run_forever("imported", config.purge_imported_interval, self.purge_imported)

    def purge_imported(self):
        torrents = [
            t
            for t in self.torrent_client.get_torrents()
            if in_labels(t, config.import_labels)
        ]

        if not torrents:
            return True, "nothing to purge"

        self.remove_log("imported", torrents)
        self.torrent_client.remove_torrents([t["id"] for t in torrents])
        return True, f"purged {len(torrents)} imported download(s)"

    def stalled_evictarr(self, service: str, url: str):
        self.run_forever(
            service.lower(),
            config.purge_stalled_interval,
            lambda: self.purge_service(service.lower()),
        )

    def purge_service(self, service: str):
        match service:
            case "sonarr":
                arr = self.sonarr
                labels = config.sonarr_labels
            case "radarr":
                arr = self.radarr
                labels = config.radarr_labels

        results = []
        errors = []

        try:
            queue = [q for page in arr.get_queue() for q in page]
        except Exception as e:
            queue = None
            errors.append(f"couldn't read the {service} queue ({describe_error(e)})")

        if config.purge_stalled:
            try:
                results.append(self.purge_stalled(service, arr, labels, queue))
            except Exception as e:
                errors.append(f"stalled purge failed ({describe_error(e)})")

        if config.purge_failed_imports and queue is not None:
            try:
                results.append(self.purge_failed_imports(arr, queue))
            except Exception as e:
                errors.append(f"failed-import purge failed ({describe_error(e)})")

        return not errors, "; ".join(results + errors)

    def purge_stalled(self, service: str, arr, labels: list, queue):
        stalled_torrents = [
            t
            for t in self.torrent_client.get_torrents()
            if t["state"] == "stalled"
            and t["age"] > int(config.torrent_age)
            and (not config.ignore_other_categories or in_labels(t, labels))
        ]

        if not stalled_torrents:
            return "no stalled downloads"

        # Without the queue nothing can be blocklisted, so leave the downloads
        # for the next run rather than removing them without a replacement search
        if config.block_stalled_torrents and queue is None:
            return f"{len(stalled_torrents)} stalled download(s) left for next run"

        # Blocklist before removing the torrent, while the release is still in
        # the Arr queue, so the Arr can find it and search for a replacement
        blocked = 0
        if config.block_stalled_torrents:
            for st in stalled_torrents:
                match = next(
                    (
                        q
                        for q in queue
                        if (q.get("downloadId") or "").lower() == st["id"].lower()
                        or q.get("title") == st["name"]
                    ),
                    None,
                )
                if match and arr.block_release(match["title"], match["id"]):
                    blocked += 1

        self.remove_log("stalled", stalled_torrents)
        self.torrent_client.remove_torrents([t["id"] for t in stalled_torrents])

        summary = f"purged {len(stalled_torrents)} stalled download(s)"
        if config.block_stalled_torrents:
            summary += f", blocklisted {blocked} in {service.capitalize()}"
        return summary

    def purge_failed_imports(self, arr, queue: list):
        failed = [
            q
            for q in queue
            if q.get("status") == "completed"
            and q.get("trackedDownloadStatus") == "warning"
            and q.get("trackedDownloadState") in FAILED_IMPORT_STATES
        ]

        if not failed:
            return "no failed imports"

        removed = 0
        for n, q in enumerate(failed, start=1):
            reasons = "; ".join(
                m
                for sm in q.get("statusMessages") or []
                for m in sm.get("messages") or []
            )
            logger.log(
                "ACTION",
                f"({n}/{len(failed)}) Purging failed import: {q['title']}"
                + (f" ({reasons})" if reasons else ""),
            )
            if arr.remove_failed_import(q["title"], q["id"]):
                removed += 1

        return f"purged and blocklisted {removed} failed import(s)"

    def extension_evictarr(self):
        self.run_forever(
            "extensions", config.purge_extensions_interval, self.purge_extensions
        )

    def purge_extensions(self):
        results = []
        errors = []

        for service, arr in (("sonarr", self.sonarr), ("radarr", self.radarr)):
            try:
                queue = [q for page in arr.get_queue() for q in page]
                results.append(self.purge_blocked_files(service, arr, queue))
            except Exception as e:
                errors.append(f"{service} failed ({describe_error(e)})")

        return not errors, "; ".join(results + errors)

    def purge_blocked_files(self, service: str, arr, queue: list):
        """Remove downloads containing blocked file types, such as .arj or .lnk.

        Only downloads Sonarr/Radarr are tracking are checked. A season pack has
        one queue item per episode, all sharing the same download id.
        """
        tracked = {}
        for q in queue:
            download_id = (q.get("downloadId") or "").lower()
            if download_id:
                tracked.setdefault(download_id, q)

        downloads = {t["id"].lower(): t for t in self.torrent_client.get_torrents()}
        blocked = []

        for download_id, q in tracked.items():
            t = downloads.get(download_id)
            if t is None:
                continue

            # A magnet link has no file list until its metadata arrives
            files = self.file_cache.get(download_id) or self.torrent_client.get_files(t["id"])
            if files:
                self.file_cache[download_id] = files

            matches = sorted(
                {
                    ext
                    for f in files
                    for ext in config.blocked_extensions
                    if f.lower().endswith(f".{ext}")
                }
            )
            if matches:
                blocked.append((t, q, matches))

        if not blocked:
            return f"no blocked file types in {service.capitalize()} downloads"

        blocklisted = 0
        for n, (t, q, matches) in enumerate(blocked, start=1):
            found = ", ".join(f".{m}" for m in matches)
            logger.log(
                "ACTION",
                f"({n}/{len(blocked)}) Purging download with blocked file type(s) {found}: {t['name']}",
            )
            # Blocklist first, while the release is still in the queue, so the
            # Arr searches for another release instead of treating this one as done
            if arr.block_release(q["title"], q["id"]):
                blocklisted += 1

        # Always delete the data: these files may be malware
        self.torrent_client.remove_torrents([t["id"] for t, _, _ in blocked], delete_files=True)
        for t, _, _ in blocked:
            self.file_cache.pop(t["id"].lower(), None)

        return (
            f"purged {len(blocked)} download(s) with blocked file types, "
            f"blocklisted {blocklisted} in {service.capitalize()}"
        )

    def webui(self):
        server_address = ("", config.web_port)
        httpd = HTTPServer(server_address, LogHandler)
        logger.info(f"Starting web UI at {config.web_host}:{config.web_port}")
        httpd.serve_forever()
