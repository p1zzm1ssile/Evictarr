"""Check whether Evictarr is working. Exits 0 when healthy, 1 when not.

Run it inside the container with: docker exec evictarr python healthcheck.py
"""

import sys
import time
from utils.status import STATUS_FILE, health_from_file


def main():
    try:
        result = health_from_file()
    except FileNotFoundError:
        print(f"UNHEALTHY: {STATUS_FILE} not found, Evictarr has not started")
        return 1

    client = result["client"] or {}
    print(f"{'HEALTHY' if result['healthy'] else 'UNHEALTHY'}", end="")
    print(f" | {client.get('name', 'unknown client')} {client.get('version', '')}".rstrip())

    for name, check in result["checks"].items():
        if check["last_run"]:
            ago = f"{int(time.time() - check['last_run'])}s ago"
        else:
            ago = "not run yet"
        mark = "FAIL" if check["ok"] is False else "OK"
        print(f"  [{mark}] {name} ({ago}): {check['summary']}")

    for problem in result["problems"]:
        print(f"  ! {problem}")

    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
