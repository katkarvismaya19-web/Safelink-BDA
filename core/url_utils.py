"""URL normalisation so that small variations of the same link map to the same key."""
from urllib.parse import urlsplit


def normalize_url(raw):
    raw = raw.strip()
    if not raw:
        return "", ""
    if "://" not in raw:
        raw = "http://" + raw
    parts = urlsplit(raw)
    host = (parts.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/")
    full = host + path
    if parts.query:
        full += "?" + parts.query
    return full, host


def keys_for(raw):
    """A link is checked both as the full URL and as its domain."""
    full, host = normalize_url(raw)
    keys = []
    if full:
        keys.append(full)
    if host and host != full:
        keys.append(host)
    return keys
