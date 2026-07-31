import asyncio
import random

import httpx

from ghunt import globals as gb

# ghunt-fixed addition: transient failures (see upstream issues #469
# RemoteProtocolError, #464 ConnectTimeout) currently crash the whole
# lookup on the first blip. These are retried with exponential backoff
# instead. Redirect-based throttling (e.g. #540, Maps returning a "sorry"
# page) isn't covered here - that needs response-content inspection, not
# just status/exception, so it's left to the calling code.
RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
)
RETRYABLE_STATUS_CODES = {429, 502, 503, 504}
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0

class AsyncClient(httpx.AsyncClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _merge_cookies(self, cookies: dict):
        """Don't save the cookies in the client."""
        return cookies

    async def send(self, request: httpx.Request, **kwargs) -> httpx.Response:
        attempt = 0
        while True:
            try:
                response = await super().send(request, **kwargs)
            except RETRYABLE_EXCEPTIONS as e:
                if attempt >= MAX_RETRIES:
                    raise
                delay = BASE_DELAY_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                gb.rc.print(
                    f"[!] {type(e).__name__} on {request.url}, retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})...",
                    style="italic yellow"
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_RETRIES:
                delay = BASE_DELAY_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
                gb.rc.print(
                    f"[!] HTTP {response.status_code} on {request.url}, retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{MAX_RETRIES})...",
                    style="italic yellow"
                )
                await response.aclose()
                await asyncio.sleep(delay)
                attempt += 1
                continue

            return response