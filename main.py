from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import asyncio

from app.api import auth, users, vpn, referrals, shiba, admin
from app.core.config import settings
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="ShibaVPN API",
    description="Бесплатный VPN-сервис с Шиба-Ину",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(vpn.router, prefix="/api/vpn", tags=["VPN"])
app.include_router(referrals.router, prefix="/api/referrals", tags=["Referrals"])
app.include_router(shiba.router, prefix="/api/shiba", tags=["Shiba"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

# Static files (frontend)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


@app.get("/")
async def root():
    return FileResponse("frontend/index.html")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "ShibaVPN"}
