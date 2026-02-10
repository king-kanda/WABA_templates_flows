"""FastAPI application - main entry point."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import create_tables, close_db
from app.routers import webhook, admin
from app.routers.conversations_ui import router as ui_router
from app.services.reminders import reminder_loop

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup
    logger.info("Starting DriveEasy WhatsApp AI Agent...")
    await create_tables()
    os.makedirs(settings.uploads_dir, exist_ok=True)
    os.makedirs("data", exist_ok=True)

    # Start reminder background task
    reminder_task = asyncio.create_task(reminder_loop())
    logger.info("Application started successfully")

    yield

    # Shutdown
    logger.info("Shutting down...")
    reminder_task.cancel()
    try:
        await reminder_task
    except asyncio.CancelledError:
        pass
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="DriveEasy WhatsApp AI Agent",
    description="WhatsApp-based car rental booking agent powered by Groq AI",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(webhook.router)
app.include_router(admin.router)
app.include_router(ui_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "DriveEasy WhatsApp AI Agent",
        "version": "1.0.0",
    }
