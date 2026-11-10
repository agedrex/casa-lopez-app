import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend import api, database, db_check
from backend.routers import router


@asynccontextmanager
async def lifespan(application: FastAPI):
    engine = database.create_database_engine() if "DATABASE_URL" in os.environ else None
    application.state.db_engine = engine
    try:
        yield
    finally:
        application.state.db_engine = None  # a disposed engine must not keep answering health checks
        if engine is not None:
            engine.dispose()


app = FastAPI(
    title="Casa Lopez Prototype API",
    description="Demonstration API for validating the initial product flow.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(api.router)
api.registrar_errores(app)


@app.exception_handler(database.DatabaseConfigurationError)
async def database_configuration_error(request: Request, error: database.DatabaseConfigurationError):
    return JSONResponse(status_code=503, content={"detail": "Database unavailable."})

cors_origins = ["http://localhost:3000"]
cors_origins.extend(
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip() and origin.strip() != "*"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check(request: Request) -> JSONResponse:
    # Public on purpose (Railway healthcheck): the body says nothing about the revision, tables, hosts or errors.
    if db_check.database_responds(getattr(request.app.state, "db_engine", None)):
        return JSONResponse(status_code=200, content={"status": "ok"})
    return JSONResponse(status_code=503, content={"status": "unavailable"})
