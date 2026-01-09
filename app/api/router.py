from fastapi import APIRouter
from app.api.endpoints import health, auth_google

router = APIRouter()

# /health router for testing
router.include_router(health.router)

# /start and /callback routes for Google OAuth
router.include_router(auth_google.router, prefix="/auth/google")