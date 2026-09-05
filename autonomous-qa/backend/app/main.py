"""FastAPI application entrypoint."""
from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import applications, discovery, health, projects, results, runs, test_cases
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="AI that adapts QA as fast as software changes.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attaches a request_id to every request/response for structured
    log correlation, and enforces a basic request-size limit."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.MAX_REQUEST_BODY_BYTES:
            return JSONResponse(status_code=413, content={"detail": "Request body too large."})

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = int((time.monotonic() - start) * 1000)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http.request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


app.add_middleware(RequestContextMiddleware)


# --- Minimal in-memory rate limiter (per-IP sliding window) ---
_request_log: dict[str, deque] = defaultdict(deque)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = _request_log[client_ip]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= settings.RATE_LIMIT_PER_MINUTE:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded."})
        window.append(now)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    # Detailed exception is already logged where raised; the client only
    # ever sees the safe, non-leaky message.
    logger.warning(
        "app_error", path=request.url.path, error_type=type(exc).__name__, detail=exc.detail
    )
    return JSONResponse(status_code=exc.http_status, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred."})


app.include_router(health.router)
app.include_router(projects.router)
app.include_router(applications.router)
app.include_router(discovery.router)
app.include_router(test_cases.router)
app.include_router(runs.router)
app.include_router(results.router)


@app.get("/")
def root() -> dict:
    return {
        "name": settings.APP_NAME,
        "tagline": "AI that adapts QA as fast as software changes.",
        "docs": "/docs",
    }
