from fastapi import FastAPI
from app.core.config import settings
from app.api.router import router as api_router
from app.api.endpoints import secret

def create_app() -> FastAPI:
    """
    Create FastAPI application.

    Endpoints:
        - "/" -> Root endpoint returning API information.
        - "/secret" -> Secret endpoint to test different environments
        - api_router -> API endpoint for all accessible endpoints in production.
    """
    app = FastAPI(
        title="GritFlow API",
        version="0.0.1",
        debug=settings.debug,
    )

    app.include_router(api_router, prefix="/api")

    @app.get("/")
    async def root():
        return {"name": "GritFlow API", "version": "0.0.1", "env": settings.environment}

    if settings.environment == "dev":
        app.include_router(secret.router, prefix="/api", tags=["dev"])

    return app

app = create_app()
