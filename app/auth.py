
from fastapi import APIRouter

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.get("/")
def auth_status():
    return {
        "message": "PitchPredict authentication module is ready"
    }
