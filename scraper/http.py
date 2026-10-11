"""Polite HTTP client.

Uses curl_cffi to present a real-browser TLS fingerprint (several portals reject
plain python-requests), enforces a per-domain delay so we never hammer a site,
and detects bot-protection blocks so a source can stop early instead of
burning its whole request budget on 403s.
"""
import logging
import random
import threading
import time
from urllib.parse import urlparse

from curl_cffi import requests as cffi_requests

log = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
}


FALLBACK_FINGERPRINTS = ("safari", "firefox")


class Blocked(Exception):
    """The site is refusing us (bot protection / rate limit). Stop this source."""


class Http:
    def __init__(self, min_delay=2.0, max_delay=4.5, timeout=30):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self._last = {}
        self._lock = threading.Lock()
        self._session = cffi_requests.Session(impersonate="chrome")
        self._alt = {}  # host -> (fallback level, session with another browser fingerprint) after a 403
        self.request_count = 0

    def _wait_turn(self, host, min_delay, max_delay):
        with self._lock:
            now = time.time()
            nxt = self._last.get(host, 0) + random.uniform(min_delay, max_delay)
            self._last[host] = max(now, nxt)
            wait = nxt - now
        if wait > 0:
            time.sleep(wait)

    def get(self, url, *, params=None, headers=None, retries=2, delay=None, allow_404=False):
        host = urlparse(url).netloc
        lo, hi = delay if delay else (self.min_delay, self.max_delay)
        last_exc = None
        for attempt in range(retries + 1):
            self._wait_turn(host, lo, hi)
            level, session = self._alt.get(host, (0, self._session))
            try:
                self.request_count += 1
                r = session.get(url, params=params, timeout=self.timeout,
                                headers={**DEFAULT_HEADERS, **(headers or {})})
            except Exception as e:  # network error
                last_exc = e
                log.warning("GET %s failed (%s), attempt %d", url, e, attempt + 1)
                time.sleep(3 * (attempt + 1))
                continue
            if r.status_code == 200:
                return r
            if r.status_code == 404 and allow_404:
                return None
            if r.status_code == 403 and level < len(FALLBACK_FINGERPRINTS) and attempt < retries:
                # some sites block only one TLS fingerprint (e.g. from cloud IPs): try another browser
                self._alt[host] = (level + 1, cffi_requests.Session(impersonate=FALLBACK_FINGERPRINTS[level]))
                log.info("%s answered 403, retrying as %s", host, FALLBACK_FINGERPRINTS[level])
                continue
            if r.status_code in (403, 401) or (r.status_code == 429 and attempt == retries):
                raise Blocked(f"{host} answered {r.status_code}")
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(8 * (attempt + 1))
                continue
            if r.status_code == 404:
                log.info("404 %s", url)
                return None
            last_exc = RuntimeError(f"HTTP {r.status_code} for {url}")
        if last_exc:
            raise last_exc
        return None
