"""Shared HTTP client: retries with backoff, openFDA pagination and rate-limit handling."""
import logging
import os
import time

import httpx
from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_exponential

log = logging.getLogger("ingestion")

OPENFDA = "https://api.fda.gov/drug"
PAGE_SIZE = 1000  # openFDA maximum per request
SKIP_CAP = 25000  # openFDA refuses skip values above this
# With a free key openFDA allows far more requests per minute; pace gently either way.
REQUEST_PAUSE = 0.1 if os.getenv("OPENFDA_API_KEY") else 0.5


def _retryable(exc: BaseException) -> bool:
    """Retry network errors, 429 and 5xx; fail fast on other 4xx."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return isinstance(exc, httpx.TransportError)


def client() -> httpx.Client:
    return httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 shortagewatch"})


@retry(
    retry=retry_if_exception(_retryable),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, max=60),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def get(c: httpx.Client, url: str, **params) -> httpx.Response:
    """GET with exponential backoff; honours Retry-After on 429."""
    r = c.get(url, params=params or None)
    if r.status_code == 429:
        time.sleep(float(r.headers.get("Retry-After", 5)))
    r.raise_for_status()
    return r


def fetch_openfda(c: httpx.Client, endpoint: str, search: str | None = None) -> list[dict]:
    """Page through an openFDA endpoint with limit/skip until exhausted."""
    params = {"limit": PAGE_SIZE}
    if key := os.getenv("OPENFDA_API_KEY"):
        params["api_key"] = key
    if search:
        params["search"] = search
    out, skip = [], 0
    while True:
        body = get(c, f"{OPENFDA}/{endpoint}.json", **params, skip=skip).json()
        out += body["results"]
        total = body["meta"]["results"]["total"]
        skip += PAGE_SIZE
        if skip >= total:
            return out
        if skip > SKIP_CAP:
            raise RuntimeError(f"{endpoint} has {total} records; exceeds openFDA skip cap, use a bulk download")
        time.sleep(REQUEST_PAUSE)
