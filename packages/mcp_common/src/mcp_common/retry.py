from collections.abc import Awaitable, Callable

import httpx


async def with_retry[T](fn: Callable[[], Awaitable[T]], *, attempts: int = 3) -> T:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return await fn()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            last_error = exc
    if last_error is None:
        raise RuntimeError("Retry called without attempts")
    raise last_error
