from __future__ import annotations

import json
from typing import Any
from urllib import error, parse, request


class HttpError(RuntimeError):
    pass


def get_json(
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
) -> Any:
    if params:
        query = parse.urlencode({k: v for k, v in params.items() if v is not None})
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{query}"
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "PortfolioDailyReporter/0.1",
        **(headers or {}),
    }
    req = request.Request(url, headers=request_headers, method="GET")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            data = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HttpError(f"GET {url} failed with HTTP {exc.code}: {body}") from exc
    except error.URLError as exc:
        raise HttpError(f"GET {url} failed: {exc.reason}") from exc
    if not data:
        return None
    return json.loads(data)
