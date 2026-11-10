import threading
import time
import utils.config as config
from services.qbittorrent import QBittorrentClient
from services.deluge import DelugeClient
from services.transmission import TransmissionClient
from services.sabnzbd import SABnzbdClient


def make_client(name: str, cfg=None):
    match name:
        case "qbittorrent":
            return QBittorrentClient(cfg, prefix="qbit")
        case "rdtclient":
            return QBittorrentClient(cfg, prefix="rdt")
        case "deluge":
            return DelugeClient(cfg)
        case "transmission":
            return TransmissionClient(cfg)
        case "sabnzbd":
            return SABnzbdClient(cfg)
    raise ValueError(f"Unknown download client: {name}")


class MultiClient:
    """All enabled download clients behind the interface of one.

    Each download is tagged with the client it came from, and removals and file
    changes go back to that client. A client that can't be reached doesn't stop
    the others: its error is kept in errors for the check to report.
    """

    # How long a file list is reused before it's read again. A download's files
    # don't change, but someone may change which ones are wanted in the client.
    FILES_MAX_AGE = 3600

    def __init__(self, names=None, clients=None):
        names = config.enabled_clients if names is None else names
        self.clients = clients if clients is not None else {name: make_client(name) for name in names}
        self.owner = {}  # download id -> client name
        self.errors = {}  # client name -> last error
        self.lock = threading.Lock()
        # The checks run side by side, so one torrent list is shared between
        # them for a few seconds rather than each asking the client for its own
        self.fetch_lock = threading.Lock()
        self.listed = None  # (when, downloads, errors)
        self.files = {}  # download id -> (when, files)

    def __bool__(self):
        return bool(self.clients)

    def get_torrents(self, max_age: float = 0) -> list:
        """Every download from every client.

        max_age reuses a list read up to that many seconds ago, so checks that run
        at the same moment share one request. 0 always reads a fresh list.
        """
        with self.fetch_lock:
            listed = self.listed
            if not (max_age and listed and time.time() - listed[0] <= max_age):
                listed = self._read_torrents()
            when, downloads, errors = listed
        with self.lock:
            self.errors = dict(errors)
        return [dict(t) for t in downloads]

    def _read_torrents(self):
        started = time.time()
        results = []
        errors = {}
        owner = {}

        for name, client in self.clients.items():
            try:
                for t in client.get_torrents():
                    t["client"] = name
                    owner[t["id"].lower()] = name
                    results.append(t)
            except Exception as e:
                errors[name] = e

        with self.lock:
            self.owner.update(owner)
            # Forget the file lists of downloads that are gone
            if not errors:
                for torrent_id in list(self.files):
                    if torrent_id not in owner:
                        self.files.pop(torrent_id, None)
        self.listed = (started, results, errors)
        return self.listed

    def _owner(self, torrent_id: str):
        name = self.owner.get(torrent_id.lower())
        if name is None:
            # Not seen yet: refresh the list once to find out who owns it
            self.get_torrents()
            name = self.owner.get(torrent_id.lower())
        return name

    def _client_for(self, torrent_id: str):
        name = self._owner(torrent_id)
        if name is None:
            raise Exception(f"no download client has download {torrent_id}")
        return self.clients[name]

    def remove_torrents(self, ids: list, delete_files: bool = None):
        """Remove downloads from whichever clients hold them.

        A download that's already gone is skipped, and one client failing doesn't
        stop the removals from the others. Any failures are raised at the end.
        """
        by_client = {}
        for torrent_id in ids:
            name = self.owner.get(torrent_id.lower())
            if name is None:
                continue  # already removed, e.g. by hand
            by_client.setdefault(name, []).append(torrent_id)

        failures = []
        for name, client_ids in by_client.items():
            try:
                self.clients[name].remove_torrents(client_ids, delete_files=delete_files)
                with self.lock:
                    for torrent_id in client_ids:
                        self.owner.pop(torrent_id.lower(), None)
                        self.files.pop(torrent_id.lower(), None)
            except Exception as e:
                from utils.daemons import describe_error  # here, as daemons imports this module
                failures.append(f"{config.CLIENTS[name]}: {describe_error(e)}")
        # A shared list would still show the removed downloads
        self.listed = None
        if failures:
            raise Exception("; ".join(failures))

    def get_files(self, torrent_id: str, cached: bool = True) -> list:
        """A download's files, read from the client at most once an hour unless cached is False."""
        key = torrent_id.lower()
        hit = self.files.get(key) if cached else None
        if hit and time.time() - hit[0] < self.FILES_MAX_AGE:
            return [dict(f) for f in hit[1]]
        files = self._client_for(torrent_id).get_files(torrent_id)
        # A magnet link has no files until its metadata arrives, so ask again next time
        if files:
            self.files[key] = (time.time(), [dict(f) for f in files])
        return files

    def skip_files(self, torrent_id: str, files: list):
        result = self._client_for(torrent_id).skip_files(torrent_id, files)
        cached = self.files.get(torrent_id.lower())
        if cached:
            skipped = {f["name"] for f in files}
            for f in cached[1]:
                if f["name"] in skipped:
                    f["wanted"] = False
        return result

    def versions(self) -> dict:
        found = {}
        for name, client in self.clients.items():
            try:
                found[name] = client.version()
            except Exception as e:
                found[name] = e
        return found
