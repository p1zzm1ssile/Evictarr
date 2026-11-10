import time


class RepeatedFailures:
    """Keeps a check that fails the same way run after run from filling the log.

    The first failure is logged in full. While the same failure repeats it isn't
    logged again, except for a reminder once an hour with how many runs have
    failed, and a line when the check starts working again.
    """

    REMIND_EVERY = 3600

    def __init__(self):
        self.failing = {}  # check -> {"summary", "count", "since", "reminded"}

    def failed(self, check: str, summary: str, now: float = None):
        """What to log for a failed run, or None to log nothing."""
        now = time.time() if now is None else now
        entry = self.failing.get(check)
        if entry is None or entry["summary"] != summary:
            self.failing[check] = {"summary": summary, "count": 1, "since": now, "reminded": now}
            return summary
        entry["count"] += 1
        if now - entry["reminded"] < self.REMIND_EVERY:
            return None
        entry["reminded"] = now
        return f"still failing, {entry['count']} runs in a row since {_clock(entry['since'])}: {summary}"

    def succeeded(self, check: str):
        """What to log about a recovery, or None if the check wasn't failing over and over."""
        entry = self.failing.pop(check, None)
        if entry is None or entry["count"] < 2:
            return None
        return f"working again after {entry['count']} failed runs since {_clock(entry['since'])}"


def _clock(when: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(when))
