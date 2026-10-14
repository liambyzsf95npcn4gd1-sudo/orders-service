"""Upstream HTTP client for retrieving raw orders."""

from typing import Any, List
import httpx

from app.config import settings


class UpstreamError(Exception):
    """Base class for upstream service failures."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class UpstreamTimeoutError(UpstreamError):
    def __init__(self, message: str = "Upstream request timed out"):
        super().__init__(message=message, status_code=504)


class UpstreamDataError(UpstreamError):
    def __init__(self, message: str = "Upstream returned invalid data structure"):
        super().__init__(message=message, status_code=502)


async def fetch_upstream_orders(
    url: str = settings.UPSTREAM_URL,
    timeout: float = settings.UPSTREAM_TIMEOUT_SECONDS,
    trust_env: bool = settings.HTTP_TRUST_ENV,
) -> List[Any]:
    """Fetch raw order records from upstream API with finite timeout and strict validation."""
    headers = {
        "User-Agent": "Orders-Normalizer-Service/1.0",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=trust_env) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()

            try:
                data = resp.json()
            except Exception as json_err:
                raise UpstreamDataError(f"Failed to parse upstream response as JSON: {json_err}") from json_err

            if not isinstance(data, list):
                raise UpstreamDataError(
                    f"Upstream JSON root must be an array of orders, received: {type(data).__name__}"
                )

            return data

    except httpx.TimeoutException as exc:
        raise UpstreamTimeoutError(f"Connection/read timeout to upstream {url} after {timeout}s: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        raise UpstreamError(
            f"Upstream returned HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            status_code=502,
        ) from exc
    except httpx.RequestError as exc:
        raise UpstreamError(f"Network error contacting upstream {url}: {exc}", status_code=502) from exc
