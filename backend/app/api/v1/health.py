from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"data": {"status": "ok"}}


@router.get("/ready")
async def ready():
    return {"data": {"status": "ok"}}
