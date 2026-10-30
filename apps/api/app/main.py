import logging
import hashlib
import ipaddress
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.store import InMemoryStore, PostgresStore, StoreUnavailable, get_store, store_holder
from app.routers import alerts, investigations, memories, wallets
from app.services.memory import memory_service

logger = logging.getLogger("trace.api")
MAX_ANALYSIS_BODY_BYTES = 16_384

ERROR_CODES = {
    400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed",
    409: "conflict", 413: "payload_too_large", 422: "validation_failed", 429: "rate_limited",
    500: "internal_error", 501: "not_implemented", 502: "upstream_error", 503: "unavailable", 504: "upstream_timeout",
}


def error_response(status_code: int, message: str, request_id: str | None, extra: dict[str, Any] | None = None) -> JSONResponse:
    """One error shape everywhere. `detail` stays for existing clients; `error` is the structured form."""
    body: dict[str, Any] = {
        "detail": message,
        "error": {
            "code": ERROR_CODES.get(status_code, "error"),
            "message": message,
            "request_id": request_id,
            "retryable": status_code in (429, 502, 503, 504),
        },
    }
    if extra:
        body["error"].update(extra)
    return JSONResponse(status_code=status_code, content=body)


def is_limited_route(method: str | None, path: str | None) -> bool:
    """Routes that call paid providers (Tatum reads, Walrus writes/deletes) share one rate limit and body cap."""
    prefix = settings.API_V1_STR
    if method == "POST" and path in (f"{prefix}/wallets/analyze", f"{prefix}/memories"):
        return True
    if method == "DELETE" and path in (f"{prefix}/memories", f"{prefix}/investigations"):
        return True
    return method == "POST" and bool(path) and path.startswith(f"{prefix}/alerts/") and path.endswith("/feedback")


class AnalysisBodySizeMiddleware:
    """Bound JSON bodies even when Content-Length is absent or inaccurate."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not is_limited_route(scope.get("method"), scope.get("path")):
            await self.app(scope, receive, send)
            return

        messages = []
        body_size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                messages.append(message)
                break
            body_size += len(message.get("body", b""))
            if body_size > self.max_bytes:
                request_id = str(uuid.uuid4())
                response = error_response(413, "Request body is too large.", request_id)
                response.headers.update({
                    "X-Request-ID": request_id,
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                    "X-Frame-Options": "DENY",
                    "Referrer-Policy": "strict-origin-when-cross-origin",
                })
                await response(scope, receive, send)
                return
            messages.append(message)
            if not message.get("more_body", False):
                break

        async def replay_receive():
            if messages:
                return messages.pop(0)
            return {"type": "http.disconnect"}

        await self.app(scope, replay_receive, send)

configure_logging()

if settings.env not in {"development", "demo", "production"}:
    raise RuntimeError("TRACE_ENV must be set to development, demo, or production.")
_problems = settings.configuration_problems()
if _problems:
    raise RuntimeError("TRACE production configuration is incomplete:\n- " + "\n- ".join(_problems))


class HealthCheckAwareTrustedHost(TrustedHostMiddleware):
    """Platform health probes may use an internal Host header; /health exposes no sensitive data."""

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") == "/health":
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


@asynccontextmanager
async def lifespan(application: FastAPI):
    redis_client = None
    if settings.REDIS_URL and settings.RATE_LIMIT_STORE == "redis":
        redis_client = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
        try:
            await redis_client.ping()
        except (RedisError, OSError) as exc:
            await redis_client.aclose()
            if settings.is_production:
                raise RuntimeError("Production rate-limit store is unavailable") from exc
            # Development/demo only: an unreachable REDIS_URL would otherwise make
            # every analysis fail with 503. Fall back to the process-local limiter.
            logger.warning("REDIS_URL is unreachable; using the process-local rate limiter for %s", settings.TRACE_ENV)
            redis_client = None
    elif settings.is_production and settings.RATE_LIMIT_STORE == "redis":
        raise RuntimeError("Production requires REDIS_URL for shared rate limiting")
    elif settings.is_production:
        logger.warning("Using the in-process rate limiter (RATE_LIMIT_STORE=memory); run a single instance")
    application.state.redis = redis_client

    if settings.DATABASE_URL:
        candidate = PostgresStore(settings.database_dsn, max_size=settings.DATABASE_POOL_MAX)
        try:
            await candidate.startup()
            store_holder.current = candidate
            logger.info("persistence: postgresql (migrations up to date)")
        except StoreUnavailable as exc:
            if settings.is_production:
                if redis_client is not None:
                    await redis_client.aclose()
                raise RuntimeError(f"Production database is unavailable: {exc}") from None
            logger.warning("DATABASE_URL is unreachable; using the process-local store for %s", settings.TRACE_ENV)
            store_holder.current = InMemoryStore()
    else:
        store_holder.current = InMemoryStore()
        if settings.is_production:
            logger.warning("DATABASE_URL is not set: investigation history is process-local and lost on restart")
    try:
        yield
    finally:
        # Graceful shutdown: release connections after in-flight requests finish.
        await store_holder.current.close()
        if redis_client is not None:
            await redis_client.aclose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="TRACE API: read-only Sui wallet intelligence with Walrus Memory",
    version="1.1.0",
    docs_url="/docs" if (settings.ENABLE_API_DOCS or not settings.is_production) else None,
    openapi_url="/openapi.json" if (settings.ENABLE_API_DOCS or not settings.is_production) else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Trace-Workspace", "Idempotency-Key"],
    expose_headers=["X-Request-ID"],
)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    message = exc.detail if isinstance(exc.detail, str) else "Request failed."
    response = error_response(exc.status_code, message, getattr(request.state, "request_id", None))
    if exc.headers:
        response.headers.update(exc.headers)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Field locations and messages only. Submitted values are never echoed back,
    # so a rejected label or reason cannot leak into responses or client logs.
    fields = [{"field": ".".join(str(p) for p in err.get("loc", ()) if p != "body"), "message": err.get("msg", "invalid")} for err in exc.errors()]
    return error_response(422, "Request validation failed.", getattr(request.state, "request_id", None), {"fields": fields[:20]})


app.add_middleware(HealthCheckAwareTrustedHost, allowed_hosts=settings.allowed_hosts)
app.add_middleware(AnalysisBodySizeMiddleware, max_bytes=MAX_ANALYSIS_BODY_BYTES)

# In-memory fallback is only for local development. Production startup requires
# Redis and uses the shared atomic rate limiter below.
_analysis_requests: dict[str, deque[float]] = defaultdict(deque)


def secure_response(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


@app.middleware("http")
async def request_controls(request: Request, call_next: Any):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    if is_limited_route(request.method, request.url.path):
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            content_length = 17_000
        if content_length > MAX_ANALYSIS_BODY_BYTES:
            response = error_response(413, "Request body is too large.", request_id)
            response.headers["X-Request-ID"] = request_id
            return secure_response(response)
        client_ip = request.client.host if request.client else "unknown"
        if settings.is_production:
            forwarded_for = request.headers.get("x-forwarded-for", "")
            if forwarded_for:
                # The platform proxy appends the real client IP last; earlier entries are client-controlled.
                client_ip = forwarded_for.rsplit(",", 1)[-1].strip()
        try:
            client_ip = str(ipaddress.ip_address(client_ip))
        except ValueError:
            client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        redis_client = getattr(request.app.state, "redis", None)
        if redis_client is not None:
            client_key = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()
            window_seconds = settings.ANALYSIS_RATE_WINDOW_SECONDS
            window = int(time.time() // window_seconds)
            redis_key = f"trace:analysis:{client_key}:{window}"
            increment_script = (
                "local count = redis.call('INCR', KEYS[1]); "
                "if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]); end; "
                "return count"
            )
            try:
                count = int(await redis_client.eval(increment_script, 1, redis_key, window_seconds + 1))
            except RedisError:
                logger.exception("rate limit store unavailable request_id=%s", request_id)
                response = error_response(503, "Analysis is temporarily unavailable.", request_id)
                response.headers["Retry-After"] = "10"
                response.headers["X-Request-ID"] = request_id
                return secure_response(response)
            if count > settings.ANALYSIS_RATE_LIMIT:
                response = error_response(429, "Request limit reached. Try again in a minute.", request_id)
                response.headers["Retry-After"] = str(window_seconds)
                response.headers["X-Request-ID"] = request_id
                return secure_response(response)
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("unhandled request failure request_id=%s", request_id)
                response = error_response(500, f"Unexpected server error. Reference: {request_id}", request_id)
            response.headers["X-Request-ID"] = request_id
            return secure_response(response)
        for ip, old_bucket in list(_analysis_requests.items()):
            while old_bucket and now - old_bucket[0] >= 60:
                old_bucket.popleft()
            if not old_bucket:
                _analysis_requests.pop(ip, None)
        if client_ip not in _analysis_requests and len(_analysis_requests) >= 10_000:
            response = error_response(429, "Demo request capacity reached.", request_id)
            response.headers["Retry-After"] = "60"
            response.headers["X-Request-ID"] = request_id
            return secure_response(response)
        bucket = _analysis_requests[client_ip]
        if len(bucket) >= settings.ANALYSIS_RATE_LIMIT:
            response = error_response(429, "Request limit reached. Try again in a minute.", request_id)
            response.headers["Retry-After"] = "60"
            response.headers["X-Request-ID"] = request_id
            return secure_response(response)
        bucket.append(now)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled request failure request_id=%s", request_id)
        response = error_response(500, f"Unexpected server error. Reference: {request_id}", request_id)
    response.headers["X-Request-ID"] = request_id
    return secure_response(response)


app.include_router(wallets.router, prefix=settings.API_V1_STR, tags=["wallets"])
app.include_router(alerts.router, prefix=settings.API_V1_STR, tags=["alerts"])
app.include_router(memories.router, prefix=settings.API_V1_STR, tags=["memories"])
app.include_router(investigations.router, prefix=settings.API_V1_STR, tags=["investigations"])


@app.get("/health")
@app.get(f"{settings.API_V1_STR}/health")
async def health(request: Request):
    """Liveness plus a capability summary. Never includes secrets or topology."""
    return {
        "status": "ok",
        "service": "trace-api",
        "version": app.version,
        "environment": settings.env,
        "capabilities": {
            "wallet_data_source": "tatum_sui_grpc",
            "tatum_credentials_present": bool(settings.TATUM_MAINNET_API_KEY),
            "walrus_memory": "configured" if memory_service.configured else "not_configured",
            "memory_isolation": "per-browser workspace (no user accounts)",
            "authentication": "not_implemented",
            "persistence": get_store().backend,
            "distributed_rate_limiting": "redis" if getattr(request.app.state, "redis", None) is not None else "process_local",
        },
    }


@app.get("/ready")
@app.get(f"{settings.API_V1_STR}/ready")
async def ready(request: Request):
    """Readiness: configuration and the rate-limit store. Returns 503 when not ready."""
    checks = {"configuration": not settings.configuration_problems(), "tatum_credentials": bool(settings.TATUM_MAINNET_API_KEY)}
    redis_client = getattr(request.app.state, "redis", None)
    if settings.RATE_LIMIT_STORE == "redis" and (settings.is_production or redis_client is not None):
        try:
            checks["rate_limit_store"] = bool(redis_client is not None and await redis_client.ping())
        except (RedisError, OSError):
            checks["rate_limit_store"] = False
    if settings.DATABASE_URL:
        checks["database"] = isinstance(get_store(), PostgresStore) and await get_store().ping()
    ready_now = all(checks.values())
    return JSONResponse(status_code=200 if ready_now else 503, content={"ready": ready_now, "environment": settings.env, "checks": checks})


@app.get(f"{settings.API_V1_STR}/me")
async def get_me():
    raise HTTPException(status_code=501, detail="Authentication is not implemented; this demo has no user identity")
