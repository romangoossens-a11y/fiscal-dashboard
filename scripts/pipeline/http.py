"""HTTP GET with retries, shared by every source."""

import time

import requests

USER_AGENT = "fiscal-dashboard/2 (+https://github.com/romangoossens-a11y/fiscal-dashboard)"


def get(url, params=None, timeout=60, retries=3, backoff=2.0):
    """GET a URL, retrying on network errors and 5xx or 429 responses.

    Raises the last error once the retries are used up. Query parameters are
    never logged, because the FRED API key travels in them.
    """
    last = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout,
                                headers={"User-Agent": USER_AGENT})
            if resp.status_code == 429 or resp.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resp.status_code} from {url}")
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last = exc
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
    raise last
