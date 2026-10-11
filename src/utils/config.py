"""Evictarr settings.

Every setting is described once in FIELDS: its tab in the web UI, its label, its
type, the environment variable it used to come from, and its default. Settings
live in settings.json in CONFIG_DIR and are edited in the web UI. On first start,
settings.json is created from the environment variables, so existing Purgarr and
Evictarr setups carry over.

The rest of Evictarr reads plain module attributes (config.sonarr_url and so on).
apply() fills those in from the saved values, so a change made in the web UI takes
effect without a restart.
"""

from dotenv import load_dotenv
import json
import os
import tempfile
import threading

load_dotenv()


def ensure_http(url):
    url = (url or "").strip()
    return url if url.startswith(("http://", "https://")) else "http://" + url


def split_labels(value):
    if isinstance(value, list):
        value = ",".join(value)
    return [l.strip() for l in (value or "").split(",") if l.strip()]


def env_bool(*names, default=False):
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value.strip().lower() == "true"
    return default


def env_str(*names, default=""):
    for name in names:
        value = os.getenv(name)
        if value is not None:
            return value
    return default


def env_int(*names, default=0):
    value = env_str(*names, default=None)
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


# Only set by environment, since they're needed before the web UI can run
config_dir = os.getenv("CONFIG_DIR") or ("/config" if os.path.isdir("/config") else "config")
settings_file = os.path.join(config_dir, "settings.json")
log_dir = os.path.join(config_dir, "logs")
log_file = os.path.join(log_dir, "evictarr.log")
log_output = os.getenv("LOG_OUTPUT", "all").lower()
web_host = os.getenv("WEB_HOST", "http://localhost").lower()
web_port = int(os.getenv("WEB_PORT", 9891))
log_refresh_interval = int(os.getenv("LOG_REFRESH_INTERVAL", 5))

# Ready-made groups that can be used in the extension settings, e.g. "@archives,@roms"
FILE_GROUPS = {
    "malware": "arj,lnk,exe,bat,cmd,com,scr,pif,vbs,ps1",
    "executables": "exe,msi,bat,cmd,com,scr,pif,vbs,ps1,jar,apk,dmg",
    "archives": "rar,zip,7z,tar,gz,bz2,xz,arj,r[0-9][0-9],[0-9][0-9][0-9]",
    "disc-images": "iso,img,bin,cue,nrg,mdf,mds",
    "roms": "rom,nes,sfc,smc,gb,gbc,gba,n64,z64,v64,nds,3ds,cia,xci,nsp,wbfs,gcm,chd,pbp",
}
unknown_file_groups = []


def parse_networks(value):
    import ipaddress

    networks = []
    for item in split_labels(value):
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            pass
    return networks


def parse_extensions(value):
    extensions = set()
    for item in split_labels(value):
        item = item.lower().lstrip(".")
        if item.startswith("@"):
            group = FILE_GROUPS.get(item[1:])
            if group is None:
                unknown_file_groups.append(item)
                continue
            extensions.update(group.split(","))
        else:
            extensions.add(item)
    return sorted(extensions)


CLIENTS = {
    "qbittorrent": "qBittorrent",
    "rdtclient": "RDTClient",
    "deluge": "Deluge",
    "transmission": "Transmission",
    "sabnzbd": "SABnzbd",
}

TABS = {
    "general": "General",
    "blocking": "Blocking",
    "sonarr": "Sonarr",
    "radarr": "Radarr",
    "clients": "Download clients",
    "indexers": "Indexers",
}


def _legacy_client():
    """The client an environment-variable setup used, or None on a brand-new install."""
    chosen = env_str("DOWNLOAD_CLIENT", "TORRENT_CLIENT", default="").strip().lower()
    if chosen:
        return chosen
    # Purgarr defaulted to qBittorrent, so an older setup may only have set QBIT_*
    if any(os.getenv(name) for name in ("QBIT_URL", "QBIT_PASSWORD", "QBIT_USER")):
        return "qbittorrent"
    return None


def F(key, tab, label, type, default, help="", section="", group=None, **extra):
    """Describe one setting. type is bool, int, text, secret, select, labels or files."""
    return dict(key=key, tab=tab, label=label, type=type, default=default, help=help,
                section=section, group=group, **extra)


FIELDS = [
    # General
    F("purge_imported", "general", "Remove imported downloads", "bool",
      env_bool("PURGE_IMPORTED", default=True), section="Imported downloads",
      help="Remove downloads once Sonarr/Radarr has imported them (their post-import category)."),
    F("purge_imported_interval", "general", "Check every (seconds)", "int",
      env_int("PURGE_IMPORTED_INTERVAL", default=600), section="Imported downloads", min=10),
    F("purge_stalled", "general", "Remove stalled downloads", "bool",
      env_bool("PURGE_STALLED", default=True), section="Stalled downloads"),
    F("block_stalled_torrents", "general", "Blocklist stalled releases", "bool",
      env_bool("BLOCK_STALLED_TORRENTS", default=True), section="Stalled downloads",
      help="Add stalled releases to the Sonarr/Radarr blocklist so a different release is grabbed."),
    F("purge_stalled_interval", "general", "Check every (seconds)", "int",
      env_int("PURGE_STALLED_INTERVAL", default=300), section="Stalled downloads", min=10),
    F("torrent_age", "general", "Grace period (minutes)", "int",
      env_int("TORRENT_AGE", default=5), section="Stalled downloads", min=0,
      help="How old a download must be before it can count as stalled."),
    F("purge_failed_imports", "general", "Remove failed imports", "bool",
      env_bool("PURGE_FAILED_IMPORTS", default=False), section="Failed imports",
      help="Remove and blocklist downloads Sonarr/Radarr couldn't import. Leave off if you import by hand."),
    F("ignore_other_categories", "general", "Only touch Sonarr/Radarr categories", "bool",
      env_bool("IGNORE_OTHER_CATEGORIES", default=False), section="Behaviour",
      help="Leave downloads in any other category alone."),
    F("delete_files", "general", "Delete files when removing", "bool",
      env_bool("DELETE_FILES", default=True), section="Behaviour"),
    F("retry_search", "general", "Search for a replacement", "bool",
      env_bool("RETRY_SEARCH", default=True), section="Behaviour",
      help="Ask Sonarr/Radarr to search again after blocklisting a release."),
    F("request_timeout", "general", "Request timeout (seconds)", "int",
      env_int("REQUEST_TIMEOUT", default=30), section="Behaviour", min=1),
    F("log_level", "general", "Log level", "select", env_str("LOG_LEVEL", default="INFO").upper(),
      section="Logs", options=["INFO", "WARNING", "ERROR"]),
    F("log_lines", "general", "Log lines shown", "int", env_int("LOG_LINES", default=500),
      section="Logs", min=50, max=10000),
    F("auth_lan_bypass", "general", "Skip login on my local network", "bool",
      env_bool("AUTH_LAN_BYPASS", default=False), section="Login",
      help="Don't ask for a password from the networks below. Never applies to requests that come through a reverse proxy."),
    F("local_networks", "general", "My local networks", "labels",
      env_str("LOCAL_NETWORKS", default="192.168.0.0/16, 10.0.0.0/8"), section="Login",
      help="Addresses that skip the login, separated by commas. 172.16.0.0/12 isn't included by default because Docker uses it, "
           "and traffic forwarded by Docker can appear to come from there."),

    # Blocking
    F("purge_extensions", "blocking", "Turn on file blocking", "bool",
      env_bool("PURGE_FILES", "PURGE_EXTENSIONS", default=False), section="File blocking",
      help="Check the files inside every download Sonarr/Radarr are tracking."),
    F("purge_extensions_interval", "blocking", "Check every (seconds)", "int",
      env_int("PURGE_EXTENSIONS_INTERVAL", default=60), section="File blocking", min=10),
    F("blocked_extensions", "blocking", "Reject downloads containing", "files",
      env_str("BLOCKED_EXTENSIONS", default="@malware"), section="Block (reject the whole download)",
      help="The release is blocklisted, removed with its files, and a replacement is searched for."),
    F("blocked_names", "blocking", "Reject downloads with file names like", "labels",
      env_str("BLOCKED_NAMES", default=""), section="Block (reject the whole download)",
      help="Wildcards, separated by commas, e.g. *password*. Use / to match folders: */extras/*"),
    F("skipped_extensions", "blocking", "Don't download these file types", "files",
      env_str("SKIPPED_EXTENSIONS", default=""), section="Skip (keep the rest of the download)"),
    F("skipped_names", "blocking", "Don't download files named like", "labels",
      env_str("SKIPPED_NAMES", default=""), section="Skip (keep the rest of the download)",
      help="e.g. *sample*. If nothing would be left, the download is rejected instead."),

    # Sonarr and Radarr
    *[
        field
        for arr, port, labels in (("sonarr", 8989, "tv-sonarr"), ("radarr", 7878, "radarr"))
        for field in (
            F(f"{arr}_enabled", arr, f"Use {arr.capitalize()}", "bool",
              env_bool(f"{arr.upper()}_ENABLED", default=bool(os.getenv(f"{arr.upper()}_API_KEY"))),
              section="Connection"),
            F(f"{arr}_url", arr, "Address", "text",
              env_str(f"{arr.upper()}_URL", default=f"localhost:{port}"), section="Connection",
              help=f"IP address or hostname with port, e.g. 192.168.1.10:{port}"),
            F(f"{arr}_api_key", arr, "API key", "secret", env_str(f"{arr.upper()}_API_KEY"),
              section="Connection", help="Settings > General > Security in " + arr.capitalize()),
            F(f"{arr}_labels", arr, "Categories", "labels",
              env_str(f"{arr.upper()}_LABELS", default=labels), section="Categories",
              help="The category (or label) set in its download client settings. Separate several with commas."),
            F(f"{arr}_imported_label", arr, "Post-import category", "labels",
              env_str("IMPORT_LABELS", f"{arr.upper()}_IMPORTED_LABEL", default=f"{arr}-imported"), section="Categories",
              help="Downloads moved to this category after import are removed."),
        )
    ],

    # Download clients
    F("client_qbittorrent", "clients", "qBittorrent", "bool", _legacy_client() == "qbittorrent",
      section="qBittorrent", group="qbittorrent", toggle=True),
    F("qbit_url", "clients", "Address", "text", env_str("QBIT_URL", default="localhost:8080"),
      section="qBittorrent", group="qbittorrent"),
    F("qbit_user", "clients", "Username", "text", env_str("QBIT_USER", default="admin"),
      section="qBittorrent", group="qbittorrent", help="Leave empty if the Web UI has no login."),
    F("qbit_pass", "clients", "Password", "secret", env_str("QBIT_PASSWORD"),
      section="qBittorrent", group="qbittorrent"),
    F("client_rdtclient", "clients", "RDTClient", "bool", _legacy_client() == "rdtclient",
      section="RDTClient", group="rdtclient", toggle=True),
    F("rdt_url", "clients", "Address", "text",
      env_str("RDT_URL", "QBIT_URL", default="localhost:6500") if _legacy_client() == "rdtclient"
      else env_str("RDT_URL", default="localhost:6500"), section="RDTClient", group="rdtclient"),
    F("rdt_user", "clients", "Username", "text",
      env_str("RDT_USER", "QBIT_USER") if _legacy_client() == "rdtclient" else env_str("RDT_USER"),
      section="RDTClient", group="rdtclient", help="Leave empty if authentication is turned off."),
    F("rdt_pass", "clients", "Password", "secret",
      env_str("RDT_PASSWORD", "QBIT_PASSWORD") if _legacy_client() == "rdtclient" else env_str("RDT_PASSWORD"),
      section="RDTClient", group="rdtclient"),
    F("client_deluge", "clients", "Deluge", "bool", _legacy_client() == "deluge",
      section="Deluge", group="deluge", toggle=True),
    F("deluge_url", "clients", "Web UI address", "text", env_str("DELUGE_URL", default="localhost:8112"),
      section="Deluge", group="deluge"),
    F("deluge_pass", "clients", "Web UI password", "secret", env_str("DELUGE_PASSWORD", default="deluge"),
      section="Deluge", group="deluge"),
    F("client_transmission", "clients", "Transmission", "bool", _legacy_client() == "transmission",
      section="Transmission", group="transmission", toggle=True),
    F("transmission_url", "clients", "Address", "text", env_str("TRANSMISSION_URL", default="localhost:9091"),
      section="Transmission", group="transmission"),
    F("transmission_user", "clients", "Username", "text", env_str("TRANSMISSION_USER"),
      section="Transmission", group="transmission", help="Leave empty if authentication is turned off."),
    F("transmission_pass", "clients", "Password", "secret", env_str("TRANSMISSION_PASSWORD"),
      section="Transmission", group="transmission"),
    F("client_sabnzbd", "clients", "SABnzbd", "bool", _legacy_client() == "sabnzbd",
      section="SABnzbd", group="sabnzbd", toggle=True),
    F("sabnzbd_url", "clients", "Address", "text", env_str("SABNZBD_URL", default="localhost:8080"),
      section="SABnzbd", group="sabnzbd"),
    F("sabnzbd_api_key", "clients", "API key", "secret", env_str("SABNZBD_API_KEY"),
      section="SABnzbd", group="sabnzbd", help="Config > General in SABnzbd"),
    F("qbit_token_refresh_interval", "clients", "Log in again every (seconds)", "int",
      env_int("QBIT_TOKEN_REFRESH_INTERVAL", default=600), section="Advanced", min=60,
      help="For qBittorrent and RDTClient."),

    # Indexers
    F("prowlarr_enabled", "indexers", "Prowlarr", "bool", env_bool("PROWLARR_ENABLED", default=False),
      section="Prowlarr", group="prowlarr", toggle=True),
    F("prowlarr_url", "indexers", "Address", "text", env_str("PROWLARR_URL", default="localhost:9696"),
      section="Prowlarr", group="prowlarr"),
    F("prowlarr_api_key", "indexers", "API key", "secret", env_str("PROWLARR_API_KEY"),
      section="Prowlarr", group="prowlarr", help="Settings > General in Prowlarr"),
    F("jackett_enabled", "indexers", "Jackett", "bool", env_bool("JACKETT_ENABLED", default=False),
      section="Jackett", group="jackett", toggle=True),
    F("jackett_url", "indexers", "Address", "text", env_str("JACKETT_URL", default="localhost:9117"),
      section="Jackett", group="jackett"),
    F("jackett_api_key", "indexers", "API key", "secret", env_str("JACKETT_API_KEY"),
      section="Jackett", group="jackett", help="Shown at the top of the Jackett dashboard"),
]

FIELDS_BY_KEY = {f["key"]: f for f in FIELDS}
SECRET_KEYS = {f["key"] for f in FIELDS if f["type"] == "secret"}

# The address each secret is sent to. A saved secret is never reused with a new
# address, or anyone with access could send it to a server of their choosing.
SECRET_URLS = {
    "qbit_pass": "qbit_url", "rdt_pass": "rdt_url", "deluge_pass": "deluge_url",
    "transmission_pass": "transmission_url", "sabnzbd_api_key": "sabnzbd_url",
    "sonarr_api_key": "sonarr_url", "radarr_api_key": "radarr_url",
    "prowlarr_api_key": "prowlarr_url", "jackett_api_key": "jackett_url",
}


def secrets_needing_reentry(changes: dict) -> dict:
    """{secret key: reason} for saved secrets whose address is being changed."""
    problems = {}
    for secret, url in SECRET_URLS.items():
        new_url = changes.get(url)
        if new_url is None or str(new_url).strip() == str(values.get(url, "")).strip():
            continue
        if changes.get(secret) is None and values.get(secret):
            label = FIELDS_BY_KEY[secret]["label"]
            problems[secret] = f"{label}: enter it again, since the address changed"
    return problems

_lock = threading.RLock()
load_error = None
values = {f["key"]: f["default"] for f in FIELDS}


def coerce(field, value):
    """Turn a submitted value into the right type, or raise ValueError with a reason."""
    t = field["type"]
    if t == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise ValueError("must be on or off")
    if t == "int":
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError("must be a whole number")
        if "min" in field and number < field["min"]:
            raise ValueError(f"must be at least {field['min']}")
        if "max" in field and number > field["max"]:
            raise ValueError(f"must be at most {field['max']}")
        return number
    if t == "select":
        if value not in field["options"]:
            raise ValueError(f"must be one of {', '.join(field['options'])}")
        return value
    value = "" if value is None else str(value).strip()
    if len(value) > 2000:
        raise ValueError("is too long")
    if t == "text" and field["key"].endswith("_url") and any(c in value for c in " <>\"'"):
        raise ValueError("isn't a valid address")
    if field["key"] == "local_networks":
        import ipaddress
        for item in split_labels(value):
            try:
                ipaddress.ip_network(item, strict=False)
            except ValueError:
                raise ValueError(f"has an invalid network: {item} (use a form like 192.168.1.0/24)")
    return value


def resolve(raw):
    """Every attribute the rest of Evictarr reads, worked out from the raw settings."""
    resolved = dict(raw)
    resolved["enabled_clients"] = [c for c in CLIENTS if raw.get(f"client_{c}")]
    resolved["torrent_client"] = ", ".join(resolved["enabled_clients"]) or "none"

    resolved["qbit_url"] = ensure_http(raw["qbit_url"]).rstrip("/") + "/api/v2"
    resolved["rdt_url"] = ensure_http(raw["rdt_url"]).rstrip("/") + "/api/v2"
    resolved["deluge_url"] = ensure_http(raw["deluge_url"]).rstrip("/")
    transmission_url = ensure_http(raw["transmission_url"]).rstrip("/")
    if not transmission_url.endswith("/rpc"):
        transmission_url += "/transmission/rpc"
    resolved["transmission_url"] = transmission_url
    resolved["sabnzbd_url"] = ensure_http(raw["sabnzbd_url"]).rstrip("/")

    for arr in ("sonarr", "radarr"):
        resolved[f"{arr}_url"] = ensure_http(raw[f"{arr}_url"]).rstrip("/") + "/api/v3"
        resolved[f"{arr}_labels"] = split_labels(raw[f"{arr}_labels"])
    resolved["import_labels"] = split_labels(
        f"{raw['sonarr_imported_label']},{raw['radarr_imported_label']}"
    )

    resolved["prowlarr_url"] = ensure_http(raw["prowlarr_url"]).rstrip("/")
    resolved["jackett_url"] = ensure_http(raw["jackett_url"]).rstrip("/")

    del unknown_file_groups[:]
    resolved["blocked_extensions"] = parse_extensions(raw["blocked_extensions"])
    resolved["skipped_extensions"] = parse_extensions(raw["skipped_extensions"])
    resolved["blocked_names"] = [n.lower() for n in split_labels(raw["blocked_names"])]
    resolved["skipped_names"] = [n.lower() for n in split_labels(raw["skipped_names"])]
    resolved["local_networks"] = parse_networks(raw["local_networks"])
    return resolved


def apply(target, raw):
    """Set the attributes the rest of Evictarr reads, on target, from raw values.

    The purge threads read them without a lock, so each attribute is only ever
    set to its final value: never, even briefly, to the raw text it comes from.
    """
    for key, value in resolve(raw).items():
        setattr(target, key, value)


def load():
    """Read settings.json, creating it from the environment on first start."""
    global values
    with _lock:
        saved = {}
        if os.path.exists(settings_file):
            try:
                with open(settings_file) as f:
                    saved = json.load(f)
            except (OSError, ValueError) as e:
                # Keep the broken file for the user to fix, rather than overwrite it later
                global load_error
                broken = f"{settings_file}.broken-{int(__import__('time').time())}"
                os.replace(settings_file, broken)
                load_error = f"settings.json couldn't be read ({e}). It was moved to {broken} and defaults are being used"
                saved = {}

        merged = {f["key"]: f["default"] for f in FIELDS}
        for key, value in saved.items():
            if key in FIELDS_BY_KEY:
                try:
                    merged[key] = coerce(FIELDS_BY_KEY[key], value)
                except ValueError:
                    pass
        values = merged
        apply(globals_namespace, values)

        if not os.path.exists(settings_file):
            _write(values)


def _write(data):
    os.makedirs(config_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=config_dir, prefix=".settings-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.chmod(tmp, 0o600)  # holds API keys and passwords
        os.replace(tmp, settings_file)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def update(changes: dict):
    """Validate and save changed settings. Returns {key: reason} for any rejected."""
    global values
    errors = {}
    clean = {}
    for key, value in changes.items():
        field = FIELDS_BY_KEY.get(key)
        if field is None:
            errors[key] = "isn't a setting"
            continue
        # Secrets are never sent to the browser; an untouched one comes back as None
        if field["type"] == "secret" and value is None:
            continue
        try:
            clean[key] = coerce(field, value)
        except ValueError as e:
            errors[key] = f"{field['label']} {e}"

    errors.update(secrets_needing_reentry(changes))
    if errors:
        return errors

    with _lock:
        new_values = {**values, **clean}
        _write(new_values)
        values = new_values
        apply(globals_namespace, values)
    return {}


def preview(changes: dict):
    """A copy of the current settings with unsaved changes applied, for testing a connection."""
    from types import SimpleNamespace

    problems = secrets_needing_reentry(changes)
    if problems:
        raise ValueError("; ".join(problems.values()))
    raw = dict(values)
    for key, value in changes.items():
        field = FIELDS_BY_KEY.get(key)
        if field is None or (field["type"] == "secret" and value is None):
            continue
        raw[key] = coerce(field, value)
    target = SimpleNamespace(**{k: v for k, v in globals().items() if not k.startswith("_")})
    apply(target, raw)
    return target


def public_values():
    """Settings safe to send to the browser: secrets are replaced by whether they're set."""
    with _lock:
        return {
            key: ({"set": bool(value)} if key in SECRET_KEYS else value)
            for key, value in values.items()
        }


class _Module:
    """Lets apply() set attributes on this module."""

    def __setattr__(self, key, value):
        globals()[key] = value

    def __getattr__(self, key):
        try:
            return globals()[key]
        except KeyError:
            raise AttributeError(key)


globals_namespace = _Module()
load()
