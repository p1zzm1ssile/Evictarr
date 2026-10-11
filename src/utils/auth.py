"""Login for the web UI.

The account lives in auth.json in CONFIG_DIR, with the password stored as a
scrypt hash. To reset a forgotten password, delete auth.json and restart: the
web UI will ask to create an account again.
"""

import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import threading
import time
import utils.config as config

AUTH_FILE = os.path.join(config.config_dir, "auth.json")
SESSION_SECONDS = 7 * 24 * 3600
MAX_FAILURES = 5
LOCKOUT_SECONDS = 5 * 60

# Headers a reverse proxy adds. A request carrying any of them never gets the LAN
# bypass, since behind a proxy every visitor appears to come from the proxy's
# own (often private) address.
PROXY_HEADERS = ("X-Forwarded-For", "X-Real-IP", "Forwarded", "X-Forwarded-Host",
                 "X-Forwarded-Proto", "CF-Connecting-IP", "True-Client-IP")

PASSWORD_RULES = [
    ("length", "At least 8 characters", lambda p: len(p) >= 8),
    ("upper", "An uppercase letter", lambda p: re.search(r"[A-Z]", p)),
    ("lower", "A lowercase letter", lambda p: re.search(r"[a-z]", p)),
    ("number", "A number", lambda p: re.search(r"[0-9]", p)),
    ("special", "A special character, like ! ? # or @", lambda p: re.search(r"[^A-Za-z0-9]", p)),
]

_lock = threading.Lock()
_sessions = {}  # token -> (username, expires)
_failures = {}  # ip -> (count, locked_until)


def password_problems(password: str) -> list:
    return [text for _, text, check in PASSWORD_RULES if not check(password or "")]


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=64)


def _load():
    try:
        with open(AUTH_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save(data):
    os.makedirs(config.config_dir, exist_ok=True)
    tmp = AUTH_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, AUTH_FILE)


def has_account() -> bool:
    return _load() is not None


def username() -> str:
    return (_load() or {}).get("username", "")


def set_password(user: str, password: str):
    """Create the account, or change its password. Raises ValueError if not allowed."""
    user = (user or "").strip()
    if not 1 <= len(user) <= 64:
        raise ValueError("Username must be 1 to 64 characters")
    problems = password_problems(password)
    if problems:
        raise ValueError("Password needs: " + ", ".join(p.lower() for p in problems))
    salt = secrets.token_bytes(16)
    _save({"username": user, "salt": salt.hex(), "hash": _hash(password, salt).hex()})
    with _lock:
        _sessions.clear()  # sign everyone out after a password change


def check_password(user: str, password: str) -> bool:
    data = _load()
    if not data:
        return False
    candidate = _hash(password or "", bytes.fromhex(data["salt"]))
    user_ok = hmac.compare_digest((user or "").strip().lower(), data["username"].lower())
    return hmac.compare_digest(candidate, bytes.fromhex(data["hash"])) and user_ok


def locked_for(ip: str) -> int:
    with _lock:
        count, until = _failures.get(ip, (0, 0))
        return max(0, int(until - time.time()))


def login(ip: str, user: str, password: str):
    """Return a session token, or None. Locks an address out after repeated failures."""
    if locked_for(ip):
        return None
    if check_password(user, password):
        with _lock:
            _failures.pop(ip, None)
            token = secrets.token_urlsafe(32)
            _sessions[token] = (username(), time.time() + SESSION_SECONDS)
            return token
    with _lock:
        count, _ = _failures.get(ip, (0, 0))
        count += 1
        until = time.time() + LOCKOUT_SECONDS if count >= MAX_FAILURES else 0
        _failures[ip] = (0 if until else count, until)
    return None


def session_user(token: str):
    if not token:
        return None
    with _lock:
        entry = _sessions.get(token)
        if entry is None:
            return None
        user, expires = entry
        if expires < time.time():
            _sessions.pop(token, None)
            return None
        return user


def logout(token: str):
    with _lock:
        _sessions.pop(token, None)


def is_proxied(headers) -> bool:
    return any(headers.get(h) for h in PROXY_HEADERS)


def is_local_address(ip: str) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if address.version == 6 and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_private or address.is_loopback or address.is_link_local


def lan_bypass(ip: str, headers) -> bool:
    return bool(config.auth_lan_bypass) and is_local_address(ip) and not is_proxied(headers)


def can_create_account(ip: str, headers) -> bool:
    """The first account can only be created from the local network, not through a proxy."""
    return not has_account() and is_local_address(ip) and not is_proxied(headers)
