import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend import database
from backend.admin_router import router as admin_router
from backend.routers import router


@asynccontextmanager
async def lifespan(application: FastAPI):
    engine = database.create_database_engine() if "DATABASE_URL" in os.environ else None
    application.state.db_engine = engine
    try:
        yield
    finally:
        if engine is not None:
            engine.dispose()


app = FastAPI(
    title="Casa Lopez Prototype API",
    description="Demonstration API for validating the initial product flow.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)
app.include_router(admin_router)


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
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "mode": "demo"}


@app.get("/api/demo/resources")
def demo_resources() -> dict[str, object]:
    return {
        "mode": "demo",
        "disclaimer": "Fictional demonstration data only. Not for real quotations or costing decisions.",
        "resources": [
            {
                "name": "Producto de demostración",
                "description": "Elemento ficticio para explorar el flujo de productos.",
            },
            {
                "name": "Material de demostración",
                "description": "Referencia ficticia; no representa un precio ni una oferta real.",
            },
            {
                "name": "Proveedor de demostración",
                "description": "Registro ilustrativo para validar el lenguaje y las relaciones.",
            },
        ],
    }
