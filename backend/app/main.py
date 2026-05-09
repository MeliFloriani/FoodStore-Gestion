from fastapi import FastAPI

app = FastAPI(
    title="Food Store API",
    version="0.1.0",
)

# Routers de negocio se registran en changes posteriores (Change 06+)
# Ejemplo: app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Health check endpoint — responde sin dependencias de BD ni autenticación."""
    return {"status": "ok"}
