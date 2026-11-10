import threading
import time

import requests

from services.clients import MultiClient
from services.qbittorrent import QBittorrentClient


class FakeClient:
    def __init__(self, downloads):
        self.downloads = downloads
        self.list_calls = 0
        self.file_calls = 0
        self.fail = None

    def get_torrents(self):
        self.list_calls += 1
        if self.fail:
            raise self.fail
        return [dict(t) for t in self.downloads]

    def get_files(self, torrent_id):
        self.file_calls += 1
        return [{"index": 0, "name": "a.mkv", "wanted": True}, {"index": 1, "name": "b.nfo", "wanted": True}]

    def skip_files(self, torrent_id, files):
        pass

    def remove_torrents(self, ids, delete_files=None):
        self.downloads = [t for t in self.downloads if t["id"] not in ids]


def multi(fake):
    return MultiClient(clients={"qbittorrent": fake})


DOWNLOADS = [{"id": "AAA", "name": "One", "state": "stalled"}, {"id": "BBB", "name": "Two", "state": "finished"}]


def test_list_is_shared_within_max_age_and_fresh_by_default():
    fake = FakeClient(DOWNLOADS)
    m = multi(fake)
    m.get_torrents(max_age=15)
    m.get_torrents(max_age=15)
    assert fake.list_calls == 1
    m.get_torrents()
    assert fake.list_calls == 2


def test_removing_drops_the_shared_list():
    fake = FakeClient(DOWNLOADS)
    m = multi(fake)
    m.get_torrents(max_age=15)
    m.remove_torrents(["AAA"])
    assert [t["id"] for t in m.get_torrents(max_age=15)] == ["BBB"]


def test_shared_list_keeps_its_errors():
    fake = FakeClient(DOWNLOADS)
    fake.fail = requests.Timeout()
    m = multi(fake)
    assert m.get_torrents(max_age=15) == []
    m.errors = {}
    m.get_torrents(max_age=15)
    assert "qbittorrent" in m.errors


def test_callers_cannot_change_the_shared_list():
    m = multi(FakeClient(DOWNLOADS))
    m.get_torrents(max_age=15)[0]["state"] = "changed"
    assert m.get_torrents(max_age=15)[0]["state"] == "stalled"


def test_file_lists_are_cached_and_follow_skips():
    fake = FakeClient(DOWNLOADS)
    m = multi(fake)
    m.get_torrents()
    files = m.get_files("AAA")
    m.skip_files("AAA", [files[1]])
    again = m.get_files("aaa")
    assert fake.file_calls == 1
    assert [f["wanted"] for f in again] == [True, False]


def test_file_lists_expire_and_are_forgotten_with_their_download():
    fake = FakeClient(DOWNLOADS)
    m = multi(fake)
    m.get_torrents()
    m.get_files("AAA")
    m.files["aaa"] = (time.time() - MultiClient.FILES_MAX_AGE - 1, m.files["aaa"][1])
    m.get_files("AAA")
    assert fake.file_calls == 2

    fake.downloads = [DOWNLOADS[1]]
    m.get_torrents()
    assert "aaa" not in m.files


def test_empty_file_lists_are_not_cached():
    fake = FakeClient(DOWNLOADS)
    fake.get_files = lambda torrent_id: (setattr(fake, "file_calls", fake.file_calls + 1), [])[1]
    m = multi(fake)
    m.get_torrents()
    m.get_files("AAA")
    m.get_files("AAA")
    assert fake.file_calls == 2


class Settings:
    qbit_url = "http://qbit"
    qbit_user = "admin"
    qbit_pass = "secret"
    qbit_token_refresh_interval = 600
    request_timeout = 5


class FakeResponse:
    def __init__(self, status=200, text="Ok."):
        self.status_code = status
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


def test_turned_away_requests_share_one_new_login(monkeypatch):
    q = QBittorrentClient(Settings())
    q.last_sid_refresh = time.time()
    logins = []

    def post(url, **kwargs):
        logins.append(url)
        time.sleep(0.05)
        return FakeResponse()

    def request(method, url, **kwargs):
        # Turned away until someone has logged in again
        return FakeResponse(200 if logins else 403)

    monkeypatch.setattr(q.session, "post", post)
    monkeypatch.setattr(q.session, "request", request)

    threads = [threading.Thread(target=q.request, args=("GET", "torrents/info")) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(logins) == 1


def test_a_timeout_is_tried_once_more(monkeypatch):
    q = QBittorrentClient(Settings())
    q.last_sid_refresh = time.time()
    q.RETRY_DELAY = 0
    calls = []

    def request(method, url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            raise requests.Timeout()
        return FakeResponse()

    monkeypatch.setattr(q.session, "request", request)
    assert q.request("GET", "torrents/info").status_code == 200
    assert len(calls) == 2


def test_a_second_timeout_fails(monkeypatch):
    q = QBittorrentClient(Settings())
    q.last_sid_refresh = time.time()
    q.RETRY_DELAY = 0

    def request(method, url, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr(q.session, "request", request)
    try:
        q.request("GET", "torrents/info")
    except requests.Timeout:
        return
    raise AssertionError("expected a timeout")
