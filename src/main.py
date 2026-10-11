from utils.daemons import Daemons
from utils.logger import logger
import utils.config as config
import utils.web as web
import signal
import sys
import threading
import time

__version__ = "0.4.0"

def main():
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    d = Daemons()

    # Always on: settings are made in the web UI
    logger.log("STARTUP", "Starting Evictarr web UI")
    threading.Thread(target=web.serve, args=(d,), daemon=True).start()

    # Every check always runs, and skips itself while turned off, so turning a
    # feature on in the web UI takes effect without a restart
    checks = [
        ("imported", d.imported_evictarr, {}),
        ("blocked file", d.extension_evictarr, {}),
        ("sonarr", d.stalled_evictarr, {"service": "sonarr"}),
        ("radarr", d.stalled_evictarr, {"service": "radarr"}),
    ]
    for name, target, kwargs in checks:
        logger.log("STARTUP", f"Starting {name} check")
        threading.Thread(target=target, kwargs=kwargs, daemon=True).start()

    logger.log("STARTUP", f"Evictarr is running. Open the web UI on port {config.web_port}")

    while True:
        time.sleep(1)


def handle_sigint(signum, frame):
    sys.exit(0)


if __name__ == "__main__":
    logger.info(f"Evictarr version {__version__} starting")
    main()
