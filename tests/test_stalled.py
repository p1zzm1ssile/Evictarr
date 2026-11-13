import utils.config as config
from services.clients import MultiClient
from utils.daemons import Daemons


class FakeClient:
    def __init__(self, downloads):
        self.downloads = downloads
        self.removed = []

    def get_torrents(self):
        return [dict(t) for t in self.downloads]

    def remove_torrents(self, ids, delete_files=None):
        self.removed += ids
        self.downloads = [t for t in self.downloads if t["id"] not in ids]


class FakeArr:
    def __init__(self):
        self.blocked = []

    def block_release(self, title, release_id):
        self.blocked.append(title)
        return True


def test_stalled_download_is_removed_only_after_the_grace_period(monkeypatch):
    monkeypatch.setattr(config, "torrent_age", 60)
    monkeypatch.setattr(config, "block_stalled_torrents", True)
    clock = [1000.0]
    monkeypatch.setattr("utils.daemons.time.time", lambda: clock[0])

    fake = FakeClient([{"id": "AAA", "name": "Show.S01E01", "category": "tv-sonarr", "state": "stalled"}])
    d = Daemons()
    d.torrent_client = MultiClient(clients={"qbittorrent": fake})
    arr = FakeArr()
    queue = [{"id": 1, "downloadId": "aaa", "title": "Show.S01E01"}]

    assert d.purge_stalled("sonarr", arr, ["tv-sonarr"], queue) == "no stalled downloads"
    clock[0] += 59 * 60
    assert d.purge_stalled("sonarr", arr, ["tv-sonarr"], queue) == "no stalled downloads"
    clock[0] += 60
    assert d.purge_stalled("sonarr", arr, ["tv-sonarr"], queue).startswith("purged 1 stalled download(s)")
    assert fake.removed == ["AAA"]
    assert arr.blocked == ["Show.S01E01"]


class TimeoutClient(FakeClient):
    def get_files(self, torrent_id):
        import requests

        raise requests.Timeout()


class QueueArr(FakeArr):
    def __init__(self, queue=None, fail=None):
        super().__init__()
        self.queue = queue or []
        self.fail = fail

    def get_queue(self):
        if self.fail:
            raise self.fail
        return [self.queue]


def files_check(monkeypatch, client, sonarr, radarr=None):
    monkeypatch.setattr(config, "purge_extensions", True)
    monkeypatch.setattr(config, "sonarr_enabled", True)
    monkeypatch.setattr(config, "sonarr_api_key", "key")
    monkeypatch.setattr(config, "radarr_enabled", radarr is not None)
    monkeypatch.setattr(config, "radarr_api_key", "key")
    d = Daemons()
    d.torrent_client = MultiClient(clients={"qbittorrent": client})
    d.sonarr, d.radarr = sonarr, radarr
    return d.purge_extensions()


def test_files_check_blames_the_download_client_not_sonarr(monkeypatch):
    fake = TimeoutClient([{"id": "AAA", "name": "Show.S01E01", "category": "tv-sonarr", "state": "downloading"}])
    sonarr = QueueArr([{"id": 1, "downloadId": "aaa", "title": "Show.S01E01"}])
    ok, summary = files_check(monkeypatch, fake, sonarr)
    assert ok is False
    assert "sonarr failed" not in summary
    assert summary.startswith("Sonarr downloads not checked (qBittorrent: ")


def test_files_check_names_sonarr_when_its_queue_fails(monkeypatch):
    import requests

    ok, summary = files_check(monkeypatch, FakeClient([]), QueueArr(fail=requests.ConnectionError()))
    assert ok is False
    assert summary.startswith("couldn't read the Sonarr queue (")


def test_files_check_skips_a_download_removed_meanwhile(monkeypatch):
    import time

    fake = FakeClient([])  # already removed from the client...
    sonarr = QueueArr([{"id": 1, "downloadId": "aaa", "title": "Show.S01E01"}])
    monkeypatch.setattr(config, "purge_extensions", True)
    monkeypatch.setattr(config, "sonarr_enabled", True)
    monkeypatch.setattr(config, "sonarr_api_key", "key")
    monkeypatch.setattr(config, "radarr_enabled", False)
    d = Daemons()
    d.torrent_client = MultiClient(clients={"qbittorrent": fake})
    # ...but still in the list another check read a few seconds ago
    d.torrent_client.listed = (time.time(), [{"id": "AAA", "name": "Show.S01E01", "state": "downloading"}], {})
    d.sonarr, d.radarr = sonarr, None
    assert d.purge_extensions() == (True, "no blocked files in Sonarr downloads")
