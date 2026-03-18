"""
FastAPI Application Factory.

Creates and configures the Verus API application.

Middleware stack (applied bottom-up — inner first):
  1. CORSMiddleware          — allow configured origins
  2. RequestIDMiddleware     — inject X-Request-ID into every response
  3. GlobalExceptionHandler  — catch all unhandled exceptions, return 500

Error handling:
  All HTTPExceptions propagate normally (FastAPI handles them).
  All other exceptions are caught by the global handler, logged with
  full detail internally, and returned as 500 INTERNAL_ERROR with only
  a correlation_id — no stack traces or internal messages exposed.

Routes:
  All routes are registered under /v1/ via the router in routes.py.
  The /v1/health route is explicitly excluded from authentication
  requirements so load balancers can probe it without credentials.
"""
from __future__ import annotations
import os
import logging
import uuid
from datetime import datetime, timezone

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from packages.api.routes import router
from packages.api.schemas import ErrorCode, ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

API_VERSION = "1.0.0"


def create_app() -> FastAPI:
    """
    Application factory. Returns a configured FastAPI instance.

    Usage:
        app = create_app()
        # In production: uvicorn packages.api.app:app
    """
    app = FastAPI(
        title="Verus Diligence API",
        description=(
            "Verus confirmatory diligence API. "
            "Provides reasoning runs, intelligence chat, and 100-day plan stress-testing."
        ),
        version=API_VERSION,
        docs_url="/v1/docs",
        redoc_url="/v1/redoc",
        openapi_url="/v1/openapi.json",
    )

    # ── Global exception handlers ─────────────────────────────────────────────

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Convert Pydantic validation errors to structured VALIDATION_ERROR responses."""
        corr_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Extract the first field error for the response
        first_error = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(l) for l in first_error.get("loc", [])[1:])
        message = first_error.get("msg", "Validation error")

        response = ErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"Validation error on field '{field}': {message}",
                correlation_id=corr_id,
                field=field or None,
            ),
            request_id=str(uuid.uuid4()),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=response.model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """
        Catch-all for unhandled exceptions.
        Logs full detail internally. Returns only correlation_id to the caller.
        Stack traces are NEVER returned to the caller.
        """
        corr_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        logger.exception(
            "Unhandled exception: method=%s path=%s correlation_id=%s",
            request.method,
            request.url.path,
            corr_id,
        )
        response = ErrorResponse(
            error=ErrorDetail(
                code=ErrorCode.INTERNAL_ERROR,
                message=(
                    f"An internal error occurred. "
                    f"Reference correlation ID {corr_id} for support."
                ),
                correlation_id=corr_id,
            ),
            request_id=str(uuid.uuid4()),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response.model_dump(mode="json"),
        )

    # ── Routes ────────────────────────────────────────────────────────────────

    cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    app.include_router(router, prefix="/v1")

    return app


# Module-level app instance for uvicorn
app = create_app()
