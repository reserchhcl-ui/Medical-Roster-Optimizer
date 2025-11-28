from fastapi import APIRouter
from app.api.v1.endpoints import doctors, roster

api_router = APIRouter()

api_router.include_router(doctors.router, prefix="/doctors", tags=["Doctors"])
api_router.include_router(roster.router, prefix="/roster", tags=["Roster Optimization"])