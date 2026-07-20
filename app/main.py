"""
app/main.py
============
FastAPI application factory.

Responsibilities:
- Create the FastAPI app instance
- Register middleware (CORS)
- Register global exception handlers
- Attach the API router
- Manage the application lifespan (engine warm-up, startup/shutdown logging)

This file should remain thin. Business logic lives in the application/ and
services/ layers. Infrastructure concerns live in infrastructure/.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import combined_router as v1_router
from app.core.config import settings
from app.core.exceptions import (
    DocumentNotFoundError,
    FileTooLargeError,
    ImageReadError,
    OCRProcessingError,
    PDFConversionError,
    UnsupportedFileTypeError,
    AIServiceUnavailableError,
    AIRequestTimeoutError,
    AIAuthorizationError,
    AIForbiddenError,
    AIInvalidResponseError,
)
from app.core.logging import configure_logging


# ── Lifespan ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.

    Startup: configure logging, optionally warm up OCR engines.
    Shutdown: log graceful exit.
    """
    configure_logging()

    import logging
    startup_log = logging.getLogger(__name__)
    startup_log.info(
        f"Starting {settings.app_title} v{settings.app_version} | "
        f"debug={settings.debug}"
    )

    if settings.ocr_warmup_on_startup:
        from app.infrastructure.ocr.engine import warmup_engines
        startup_log.info("OCR warm-up requested — initializing engines at startup...")
        warmup_engines()

    yield

    startup_log.info("Shutting down OCR service. Goodbye.")


# ── App Factory ────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_title,
    description=settings.app_description,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Middleware ─────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# ── Global Exception Handlers ──────────────────────────────────────────────

@app.exception_handler(UnsupportedFileTypeError)
async def unsupported_file_type_handler(request: Request, exc: UnsupportedFileTypeError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(FileTooLargeError)
async def file_too_large_handler(request: Request, exc: FileTooLargeError):
    return JSONResponse(status_code=413, content={"detail": str(exc)})


@app.exception_handler(DocumentNotFoundError)
async def document_not_found_handler(request: Request, exc: DocumentNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ImageReadError)
async def image_read_error_handler(request: Request, exc: ImageReadError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(OCRProcessingError)
async def ocr_error_handler(request: Request, exc: OCRProcessingError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(PDFConversionError)
async def pdf_error_handler(request: Request, exc: PDFConversionError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# ── AI Vision Exception Handlers ───────────────────────────────────────────

@app.exception_handler(AIAuthorizationError)
async def ai_auth_error_handler(request: Request, exc: AIAuthorizationError):
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(AIForbiddenError)
async def ai_forbidden_error_handler(request: Request, exc: AIForbiddenError):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(AIInvalidResponseError)
async def ai_invalid_response_handler(request: Request, exc: AIInvalidResponseError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(AIServiceUnavailableError)
async def ai_unavailable_handler(request: Request, exc: AIServiceUnavailableError):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(AIRequestTimeoutError)
async def ai_timeout_handler(request: Request, exc: AIRequestTimeoutError):
    return JSONResponse(status_code=504, content={"detail": str(exc)})


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    """Health check — returns service name and version."""
    return {
        "message": "Welcome to Document Report OCR Service API (PaddleOCR Engine)",
        "version": settings.app_version,
        "docs": "/docs",
    }


app.include_router(v1_router)
