from utils.repeats import RepeatedFailures


def test_same_failure_is_logged_once_then_hourly():
    r = RepeatedFailures()
    assert r.failed("files", "qBittorrent timed out", now=0) == "qBittorrent timed out"
    assert r.failed("files", "qBittorrent timed out", now=60) is None
    assert r.failed("files", "qBittorrent timed out", now=120) is None
    reminder = r.failed("files", "qBittorrent timed out", now=3600)
    assert reminder.startswith("still failing, 4 runs in a row since")
    assert r.failed("files", "qBittorrent timed out", now=3660) is None


def test_a_different_failure_is_logged_straight_away():
    r = RepeatedFailures()
    r.failed("files", "timed out", now=0)
    assert r.failed("files", "HTTP 500", now=10) == "HTTP 500"


def test_recovery_is_logged_only_after_repeated_failures():
    r = RepeatedFailures()
    r.failed("files", "timed out", now=0)
    assert r.succeeded("files") is None
    r.failed("files", "timed out", now=0)
    r.failed("files", "timed out", now=60)
    assert r.succeeded("files").startswith("working again after 2 failed runs")
    assert r.succeeded("files") is None


def test_checks_are_tracked_separately():
    r = RepeatedFailures()
    r.failed("files", "timed out", now=0)
    assert r.failed("sonarr", "timed out", now=1) == "timed out"
