"""Basic in-process sliding-window rate limiter.

Good enough for a single API instance. For several instances, back SlidingWindow with Redis
(same interface: hit(key, limit) -> allowed)."""
import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings


class SlidingWindow:
    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.window = SlidingWindow()

    async def dispatch(self, request: Request, call_next):
        if settings.environment == "test":
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        is_upload = request.method == "POST" and request.url.path.endswith("/floor-plan")
        bucket, limit = ("upload", settings.upload_rate_limit_per_minute) if is_upload else (
            "api", settings.rate_limit_per_minute)
        if not self.window.hit(f"{ip}:{bucket}", limit):
            return JSONResponse(
                {"error": {"code": "rate_limited", "message": "Too many requests. Wait a minute and try again."}},
                status_code=429,
            )
        return await call_next(request)
