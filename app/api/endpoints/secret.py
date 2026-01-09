from fastapi import APIRouter

router = APIRouter()

@router.get("/secret")
async def secret_message():
    return {"secret-message": "abyss"}