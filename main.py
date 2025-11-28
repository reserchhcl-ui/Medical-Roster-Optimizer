from fastapi import FastAPI
from app.core.config import settings

app = FastAPI(
    title="Medical Roster Optimizer",
    description="API de Otimização de Escalas Médicas com OR-Tools",
    version="1.0.0"
)

@app.get("/health")
def health_check():
    return {"status": "active", "system": "medical-roster"}
