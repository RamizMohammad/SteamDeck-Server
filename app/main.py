"""Linkium API — FastAPI drop-in replacement for the old Express server."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from . import security, store
from .config import Settings, load_settings
from .http import ApiError
from .jscompat import JSResponse, error
from .routes import activity, auth, pairing, programs
from .ws import Relay

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("linkium")


class ExpressCORSMiddleware(CORSMiddleware):
    """Same as Starlette's, but answers preflights with 204 No Content like the `cors` package."""

    def preflight_response(self, request_headers):  # type: ignore[override]
        resp = super().preflight_response(request_headers)
        if resp.status_code != 200:
            return resp
        headers = {k: v for k, v in resp.headers.items() if k.lower() not in ("content-length", "content-type")}
        return Response(status_code=204, headers=headers)


class TrailingSlashMiddleware:
    """Express treats /api/me and /api/me/ the same; do that instead of a 307 redirect."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            path: str = scope["path"]
            if len(path) > 1 and path.endswith("/"):
                scope = dict(scope)
                scope["path"] = path.rstrip("/") or "/"
                scope["raw_path"] = scope["path"].encode()
        await self.app(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    security.init(settings)
    relay = Relay(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await store.connect(settings)
        log.info("Server running on port %s | WebSocket at /ws", settings.port)
        try:
            yield
        finally:
            log.info("Shutting down...")
            await relay.close_all()
            await store.close()

    app = FastAPI(
        title="Linkium API",
        lifespan=lifespan,
        docs_url=None,  # no public API docs in production
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
    )
    app.state.settings = settings
    app.state.relay = relay

    app.add_middleware(
        ExpressCORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )
    app.add_middleware(TrailingSlashMiddleware)

    # ---- errors always come back as {"error": "..."} -----------------------------
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return error(exc.status, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        if exc.status_code in (404, 405):  # Express answers unknown routes/methods with 404
            return error(404, "Not found")
        return error(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        return error(400, "Invalid request")

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error: %s", exc)
        return error(500, "Internal server error")

    # ---- routes -------------------------------------------------------------------
    @app.get("/api/health")
    async def health():
        return JSResponse({"status": "ok", "service": "Linkium API", "websocket": settings.public_ws_url})

    for module in (auth, pairing, programs, activity):
        app.include_router(module.router, prefix="/api")

    @app.websocket("/ws")
    async def websocket(ws: WebSocket):
        await relay.handle(ws)

    return app
