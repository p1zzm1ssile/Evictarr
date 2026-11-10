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
