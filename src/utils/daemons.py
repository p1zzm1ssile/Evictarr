import requests
import threading
import utils.config as config
import utils.status as status
from utils.logger import *
from utils.files import match_file
from services.sonarr import Sonarr
from services.radarr import Radarr
from services.clients import MultiClient

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
        self.wake = threading.Condition()
        self.generation = 0
        self.reload()

    def reload(self):
        """Rebuild the connections from the current settings and run every check now."""
        self.sonarr = Sonarr()
        self.radarr = Radarr()
        self.torrent_client = MultiClient()

        if config.unknown_file_groups:
            logger.warning(
                f"Unknown file group(s) {', '.join(config.unknown_file_groups)}, "
                f"choose from {', '.join('@' + g for g in config.FILE_GROUPS)}"
            )

        if not self.torrent_client:
            logger.warning("No download client is set up yet. Choose one in Settings > Download clients")
            status.set_client("none", "")
        else:
            found = []
            for name, version in self.torrent_client.versions().items():
                if isinstance(version, Exception):
                    logger.error(f"Can't reach {config.CLIENTS[name]} | {describe_error(version)}")
                    found.append(f"{config.CLIENTS[name]} (unreachable)")
                else:
                    logger.info(f"Found {config.CLIENTS[name]} {version}")
                    found.append(f"{config.CLIENTS[name]} {version}")
            status.set_client(", ".join(found), "")

        with self.wake:
            self.generation += 1
            self.wake.notify_all()

    def sleep(self, seconds: float):
        """Wait for the next run, or until the settings are saved."""
        with self.wake:
            generation = self.generation
            self.wake.wait_for(lambda: self.generation != generation, timeout=seconds)

    def remove_log(self, type: str, torrents):
        n = 0
        for t in torrents:
            n += 1
            logger.log(
                "ACTION", f"({n}/{len(torrents)}) Purging {type} download: {t['name']}"
            )

    def run_forever(self, check: str, interval, cycle):
        """Run one check every interval, recording how each run went.

        interval is read before every wait, so a change in the web UI applies at
        once. An error in one run is logged and recorded, and the next run still
        happens. A download client that couldn't be reached fails the run too.
        """
        status.register(check, interval())

        while True:
            client = self.torrent_client
            try:
                ok, summary = cycle()
            except Exception as e:
                ok, summary = False, f"Failed: {describe_error(e)}"

            problems = [
                f"{config.CLIENTS[name]}: {describe_error(e)}"
                for name, e in getattr(client, "errors", {}).items()
            ]
            if problems and ok is not None:
                ok = False
                summary = "; ".join([summary, *problems])

            seconds = interval()
            if ok is None:
                # Turned off or not set up: nothing to report on
                status.record(check, True, summary, seconds)
            else:
                status.record(check, ok, summary, seconds)
                log = logger.info if ok else logger.error
                log(f"{check.capitalize()} check: {summary} (next check in {seconds}s)")

            self.sleep(seconds)

    def no_client(self):
        if not self.torrent_client:
            return False, "no download client set up"
        return None

    def imported_evictarr(self):
        self.run_forever(
            "imported", lambda: config.purge_imported_interval, self.purge_imported
        )

    def purge_imported(self):
        if not config.purge_imported:
            return None, "turned off"
        if missing := self.no_client():
            return missing

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

    def stalled_evictarr(self, service: str, url: str = ""):
        self.run_forever(
            service.lower(),
            lambda: config.purge_stalled_interval,
            lambda: self.purge_service(service.lower()),
        )

    def purge_service(self, service: str):
        if not getattr(config, f"{service}_enabled"):
            return None, f"{service.capitalize()} turned off"
        if not (config.purge_stalled or config.purge_failed_imports):
            return None, "stalled and failed-import purges turned off"
        if not getattr(config, f"{service}_api_key"):
            return False, f"no {service.capitalize()} API key set"
        if missing := self.no_client():
            return missing

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
            "files", lambda: config.purge_extensions_interval, self.purge_extensions
        )

    def purge_extensions(self):
        if not config.purge_extensions:
            return None, "turned off"
        if missing := self.no_client():
            return missing

        results = []
        errors = []

        for service, arr in (("sonarr", self.sonarr), ("radarr", self.radarr)):
            if not getattr(config, f"{service}_enabled") or not getattr(config, f"{service}_api_key"):
                continue
            try:
                queue = [q for page in arr.get_queue() for q in page]
                results.append(self.purge_blocked_files(service, arr, queue))
            except Exception as e:
                errors.append(f"{service} failed ({describe_error(e)})")

        if not results and not errors:
            return False, "Sonarr and Radarr aren't set up"
        return not errors, "; ".join(results + errors)

    def purge_blocked_files(self, service: str, arr, queue: list):
        """Reject or trim downloads containing blocked or skipped files.

        Only downloads Sonarr/Radarr are tracking are checked. A season pack has
        one queue item per episode, all sharing the same download id.

        Blocked files (e.g. .arj, .lnk) get the whole download rejected: it is
        blocklisted, removed with its files, and a replacement is searched for.
        Skipped files (e.g. samples) are just not downloaded. If nothing would be
        left after skipping, the download is rejected instead.
        """
        tracked = {}
        for q in queue:
            download_id = (q.get("downloadId") or "").lower()
            if download_id:
                tracked.setdefault(download_id, q)

        downloads = {t["id"].lower(): t for t in self.torrent_client.get_torrents()}
        rejected = []
        skipped = 0

        for download_id, q in tracked.items():
            t = downloads.get(download_id)
            if t is None:
                continue

            # A magnet link has no file list until its metadata arrives
            files = self.torrent_client.get_files(t["id"])
            if not files:
                continue

            # Checked whether or not a file is set to download: the client may
            # already be skipping a bad file while the Arr sees a finished download
            blocked = sorted(
                {
                    m
                    for f in files
                    if (m := match_file(f["name"], config.blocked_extensions, config.blocked_names))
                }
            )
            if blocked:
                rejected.append((t, q, f"blocked file(s) {', '.join(blocked)}"))
                continue

            to_skip = [
                f
                for f in files
                if f["wanted"]
                and match_file(f["name"], config.skipped_extensions, config.skipped_names)
            ]
            if not to_skip:
                continue

            if all(not f["wanted"] or f in to_skip for f in files):
                rejected.append((t, q, "nothing left to download after skipping files"))
                continue

            names = ", ".join(f["name"].replace("\\", "/").rsplit("/", 1)[-1] for f in to_skip)
            logger.log("ACTION", f"Skipping {len(to_skip)} file(s) in {t['name']}: {names}")
            self.torrent_client.skip_files(t["id"], to_skip)
            skipped += len(to_skip)

        results = []
        if skipped:
            results.append(f"skipped {skipped} file(s)")

        if rejected:
            blocklisted = 0
            for n, (t, q, reason) in enumerate(rejected, start=1):
                indexer = f" from {q['indexer']}" if q.get("indexer") else ""
                logger.log(
                    "ACTION",
                    f"({n}/{len(rejected)}) Rejecting download{indexer} ({reason}): {t['name']}",
                )
                # Blocklist first, while the release is still in the queue, so the
                # Arr searches for another release instead of treating this one as done
                if arr.block_release(q["title"], q["id"]):
                    blocklisted += 1

            # Always delete the data: blocked files may be malware
            self.torrent_client.remove_torrents(
                [t["id"] for t, _, _ in rejected], delete_files=True
            )
            results.append(
                f"rejected {len(rejected)} download(s), blocklisted {blocklisted} in {service.capitalize()}"
            )

        return "; ".join(results) or f"no blocked files in {service.capitalize()} downloads"
