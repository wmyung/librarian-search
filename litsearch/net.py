"""HTTP helpers with polite rate limiting and retries (stdlib only)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "litsearch/0.1 (systematic literature search helper)"
_last_call: dict[str, float] = {}


def _throttle(host: str, min_interval: float) -> None:
    now = time.monotonic()
    wait = _last_call.get(host, 0) + min_interval - now
    if wait > 0:
        time.sleep(wait)
    _last_call[host] = time.monotonic()


def request(url: str, params: dict | None = None, data: dict | None = None,
            min_interval: float = 0.34, retries: int = 4, timeout: int = 60) -> bytes:
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params, doseq=True)
    body = urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None
    host = urllib.parse.urlparse(url).netloc
    for attempt in range(retries + 1):
        _throttle(host, min_interval)
        req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 ** attempt * 1.5)
                continue
            detail = e.read()[:500].decode("utf-8", "replace")
            raise RuntimeError(f"HTTP {e.code} for {url[:200]}: {detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries:
                time.sleep(2 ** attempt * 1.5)
                continue
            raise RuntimeError(f"Network error for {url[:200]}: {e}") from e
    raise RuntimeError("unreachable")


def get_json(url: str, params: dict | None = None, **kw):
    return json.loads(request(url, params, **kw), strict=False)


def post_json(url: str, data: dict, **kw):
    return json.loads(request(url, data=data, **kw), strict=False)
