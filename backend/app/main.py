"""FastAPI main application entrypoint for OpsPilot."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal, engine, init_db
from app.demo_data import load_demo_data
from app.models import HealthResponse
from app.routes.audit import global_router as audit_global_router
from app.routes.audit import router as audit_router
from app.routes.data import router as data_router
from app.routes.pipeline import router as pipeline_router
from app.routes.runs import router as runs_router
from app.routes.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context for initialization and cleanup."""
    init_db()
    # Demo-first: make sure sample datasets, templates, and users exist locally.
    with SessionLocal() as db:
        load_demo_data(db)
    yield


app = FastAPI(
    title="OpsPilot Backend API",
    description="Agentic workflow dashboard for small business operations.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register sub-routers
app.include_router(audit_router)
app.include_router(audit_global_router)
app.include_router(data_router)
app.include_router(pipeline_router)
app.include_router(runs_router)
app.include_router(users_router)


# Standard Error Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle standard HTTP exceptions with unified error envelope."""
    detail: Any = exc.detail
    code = "http_error"
    message = str(detail)
    details: Any = None

    if isinstance(detail, dict):
        code = detail.get("code", "http_error")
        message = detail.get("message", "An error occurred.")
        details = detail.get("details", None)

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message, "details": details}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic schema validation errors with unified envelope."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "validation_error",
                "message": "Invalid request schema.",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler returning standard error envelope."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_server_error",
                "message": str(exc) if settings.ENV == "dev" else "An unexpected error occurred.",
                "details": None,
            }
        },
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health and liveness check",
)
def get_health() -> HealthResponse:
    """Return system liveness status, active execution mode, and database health."""
    db_status = "connected"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    return HealthResponse(
        status="ok",
        mode=settings.MODE,
        database=db_status,
        llm_configured=bool(settings.LLM_API_KEY),
    )
