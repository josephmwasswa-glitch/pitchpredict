
from fastapi import FastAPI

app = FastAPI(
    title="PitchPredict API",
    description="Worldwide AI-powered football predictions platform",
    version="1.0.0"
)

@app.get("/")
def home():
    return {
        "message": "Welcome to PitchPredict",
        "status": "Running"
    }

@app.get("/health")
def health():
    return {"status": "healthy"}
