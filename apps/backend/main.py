from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.core.migrations import run_migrations
from app.api.v1 import (
    health, status, conversations, chat, notes, memory, settings as settings_router, security, executive, workspaces, agent, computer, communication, knowledge, proactive, orchestrator, system, browser
)
import app.computer.permissions  # Register computer tools
import app.communication.permissions  # Register communication tools

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} backend...")
    run_migrations()
    yield
    logger.info(f"Shutting down {settings.APP_NAME} backend.")

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="MATRIOSHAI Core Local Backend API",
    lifespan=lifespan
)

# CORS Middleware (Localhost Tauri desktop access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restricted to local desktop app context
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router Registration
app.include_router(health.router, prefix="/api/v1")
app.include_router(status.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(notes.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")
app.include_router(security.router, prefix="/api/v1")
app.include_router(executive.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(computer.router, prefix="/api/v1")
app.include_router(communication.router, prefix="/api/v1")
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(proactive.router, prefix="/api/v1")
app.include_router(orchestrator.router, prefix="/api/v1")
app.include_router(system.router, prefix="/api/v1")
app.include_router(browser.router, prefix="/api/v1")

@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "status": "online",
        "docs": "/docs",
        "api_v1": "/api/v1"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=(settings.APP_ENV == "development")
    )
