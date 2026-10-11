import threading
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

    def __init__(self, names=None):
        names = config.enabled_clients if names is None else names
        self.clients = {name: make_client(name) for name in names}
        self.owner = {}  # download id -> client name
        self.errors = {}  # client name -> last error
        self.lock = threading.Lock()

    def __bool__(self):
        return bool(self.clients)

    def get_torrents(self) -> list:
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
            self.errors = errors
        return results

    def _client_for(self, torrent_id: str):
        name = self.owner.get(torrent_id.lower())
        if name is None:
            # Not seen yet: refresh the list once to find out who owns it
            self.get_torrents()
            name = self.owner.get(torrent_id.lower())
        if name is None:
            raise Exception(f"no download client has download {torrent_id}")
        return self.clients[name]

    def remove_torrents(self, ids: list, delete_files: bool = None):
        by_client = {}
        for torrent_id in ids:
            by_client.setdefault(self._client_for(torrent_id), []).append(torrent_id)
        for client, client_ids in by_client.items():
            client.remove_torrents(client_ids, delete_files=delete_files)

    def get_files(self, torrent_id: str) -> list:
        return self._client_for(torrent_id).get_files(torrent_id)

    def skip_files(self, torrent_id: str, files: list):
        return self._client_for(torrent_id).skip_files(torrent_id, files)

    def versions(self) -> dict:
        found = {}
        for name, client in self.clients.items():
            try:
                found[name] = client.version()
            except Exception as e:
                found[name] = e
        return found
