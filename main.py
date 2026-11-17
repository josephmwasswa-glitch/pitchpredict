
from fastapi import FastAPI
from app.auth import router as auth_router
from app.users import router as users_router

app = FastAPI(
    title="PitchPredict API",
    description="Worldwide AI-powered football predictions platform",
    version="1.0.0"
)

app.include_router(auth_router)
app.include_router(users_router)

@app.get("/")
def home():
    return {
        "message": "Welcome to PitchPredict",
        "status": "Running"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}
