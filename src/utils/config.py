from dotenv import load_dotenv
import os

load_dotenv()


def ensure_http(url):
    return url if url.startswith(("http://", "https://")) else "http://" + url


def split_labels(value):
    return [l.strip() for l in value.split(",") if l.strip()]


# Purgarr Behaviour
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
purge_stalled = os.getenv("PURGE_STALLED", "True").lower() == "true"
purge_stalled_interval = int(os.getenv("PURGE_STALLED_INTERVAL", 300))
block_stalled_torrents = os.getenv("BLOCK_STALLED_TORRENTS", "True").lower() == "true"
purge_imported = os.getenv("PURGE_IMPORTED", "True").lower() == "true"
purge_imported_interval = int(os.getenv("PURGE_IMPORTED_INTERVAL", 600))
purge_failed_imports = os.getenv("PURGE_FAILED_IMPORTS", "False").lower() == "true"
delete_files = os.getenv("DELETE_FILES", "True").lower() == "true"
ignore_other_categories = (
    os.getenv("IGNORE_OTHER_CATEGORIES", "False").lower() == "true"
)
retry_search = os.getenv("RETRY_SEARCH", "True").lower() == "true"
log_output = os.getenv("LOG_OUTPUT", "all").lower()
web_host = os.getenv("WEB_HOST", "http://localhost").lower()
web_port = int(os.getenv("WEB_PORT", 9891))
request_timeout = int(os.getenv("REQUEST_TIMEOUT", 30))

# Torrents
# DOWNLOAD_CLIENT is an alias, since SABnzbd isn't a torrent client
torrent_client = os.getenv("DOWNLOAD_CLIENT") or os.getenv("TORRENT_CLIENT", "qbittorrent")
torrent_age = os.getenv("TORRENT_AGE", 5)

# qBittorrent
qbit_url = ensure_http(os.getenv("QBIT_URL", "localhost:8080")) + "/api/v2"
qbit_user = os.getenv("QBIT_USER", "admin")
qbit_pass = os.getenv("QBIT_PASSWORD")
qbit_token_refresh_interval = int(os.getenv("QBIT_TOKEN_REFRESH_INTERVAL", 600))

# Deluge
deluge_url = ensure_http(os.getenv("DELUGE_URL", "localhost:8112"))
deluge_pass = os.getenv("DELUGE_PASSWORD", "deluge")

# Transmission
transmission_url = ensure_http(os.getenv("TRANSMISSION_URL", "localhost:9091")).rstrip("/")
if not transmission_url.endswith("/rpc"):
    transmission_url += "/transmission/rpc"
transmission_user = os.getenv("TRANSMISSION_USER")
transmission_pass = os.getenv("TRANSMISSION_PASSWORD")

# SABnzbd
sabnzbd_url = ensure_http(os.getenv("SABNZBD_URL", "localhost:8080")).rstrip("/")
sabnzbd_api_key = os.getenv("SABNZBD_API_KEY")

# Sonarr
sonarr_labels = split_labels(os.getenv("SONARR_LABELS", "tv-sonarr"))
sonarr_url = ensure_http(os.getenv("SONARR_URL", "localhost:8989")) + "/api/v3"
sonarr_api_key = os.getenv("SONARR_API_KEY")
sonarr_imported_label = os.getenv("SONARR_IMPORTED_LABEL", "sonarr-imported")

# Radarr
radarr_labels = split_labels(os.getenv("RADARR_LABELS", "radarr"))
radarr_url = ensure_http(os.getenv("RADARR_URL", "localhost:7878")) + "/api/v3"
radarr_api_key = os.getenv("RADARR_API_KEY")
radarr_imported_label = os.getenv("RADARR_IMPORTED_LABEL", "radarr-imported")

# webUI
log_lines = int(os.getenv("LOG_LINES", 100))
log_refresh_interval = int(os.getenv("LOG_REFRESH_INTERVAL", 5))

# Other
import_labels = split_labels(
    os.getenv("IMPORT_LABELS", f"{sonarr_imported_label}, {radarr_imported_label}")
)
