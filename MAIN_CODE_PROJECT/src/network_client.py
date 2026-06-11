"""Timeout-enforced network client.

Provides connection and read timeouts for all HTTP operations.
Unresponsive services will raise ``urllib.error.URLError`` instead
of blocking indefinitely.
"""

from typing import Any, Dict, Optional
import json
import ssl
import time
import urllib.error
import urllib.request


DEFAULT_TIMEOUT = 10
USER_AGENT = "Python45-Client/1.0"


class NetworkClient:
    """HTTP client with mandatory timeouts."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout
        self._ssl_ctx = ssl.create_default_context()

    def fetch_json(
        self,
        url: str,
        params: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """GET *url* and return the JSON response as a dict.

        Raises ``urllib.error.URLError`` on timeout or connection failure.
        """
        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}"
        started = time.perf_counter()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(
            req, timeout=timeout or self._timeout, context=self._ssl_ctx
        ) as resp:
            payload = resp.read().decode("utf-8", errors="replace")
        elapsed = round(time.perf_counter() - started, 4)
        try:
            data: Dict[str, Any] = json.loads(payload)
        except json.JSONDecodeError:
            data = {"raw": payload}
        data["elapsed_seconds"] = elapsed
        data["status_code"] = getattr(resp, "status", 200)
        return data
