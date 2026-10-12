from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Casa Lopez Prototype API",
    description="Demonstration API for validating the initial product flow.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
