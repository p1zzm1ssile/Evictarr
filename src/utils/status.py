import json
import threading
import time

STATUS_FILE = "evictarr-status.json"

# A check is overdue when it hasn't finished within two of its intervals
GRACE_SECONDS = 60

_lock = threading.Lock()
_status = {"started": time.time(), "client": None, "checks": {}}


def _write():
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(_status, f)
    except OSError:
        pass


def set_client(name: str, version: str):
    with _lock:
        _status["client"] = {"name": name, "version": version}
        _write()


def register(check: str, interval: int):
    with _lock:
        _status["checks"][check] = {
            "interval": interval,
            "last_run": None,
            "ok": None,
            "summary": "Waiting for first run",
        }
        _write()


def record(check: str, ok: bool, summary: str, interval: int = None):
    with _lock:
        entry = _status["checks"][check]
        entry.update(last_run=time.time(), ok=ok, summary=summary)
        if interval is not None:
            entry["interval"] = interval
        _write()


def evaluate(status: dict, now: float = None) -> dict:
    """Work out whether Evictarr is healthy from a status snapshot."""
    now = now or time.time()
    problems = []

    for name, check in status["checks"].items():
        since = check["last_run"] or status["started"]
        if now - since > check["interval"] * 2 + GRACE_SECONDS:
            problems.append(f"{name} check is overdue")
        elif check["ok"] is False:
            problems.append(f"{name} check failed: {check['summary']}")

    return {
        "healthy": not problems,
        "problems": problems,
        "client": status["client"],
        "checks": status["checks"],
        "uptime_seconds": int(now - status["started"]),
    }


def health() -> dict:
    with _lock:
        return evaluate(json.loads(json.dumps(_status)))


def health_from_file(path: str = STATUS_FILE) -> dict:
    with open(path) as f:
        return evaluate(json.load(f))
