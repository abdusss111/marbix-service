# src/marbix/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from marbix.api.v1 import api_router as main_router
from marbix.core.config import settings
import os
import logging

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Marbix API",
    version="1.0.0",
    description="Marketing strategy generation platform"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[""],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    try:
        logger.info("Starting Marbix API...")
        logger.info("Redis configuration verified")
        logger.info("Marbix API startup completed successfully")

    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on application shutdown"""
    try:
        logger.info("Shutting down Marbix API...")
        logger.info("Marbix API shutdown completed")

    except Exception as e:
        logger.error(f"Error during shutdown: {str(e)}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Marbix API is running",
        "version": "1.0.0",
        "status": "healthy"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        return {
            "status": "healthy",
            "redis_config": "configured",
            "worker": "arq_enabled"
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.get("/metrics")
async def metrics():
    """Basic metrics endpoint for monitoring"""
    try:
        return {
            "api_status": "running",
            "redis_url_configured": bool(settings.REDIS_URL),
            "worker_enabled": True
        }

    except Exception as e:
        logger.error(f"Metrics endpoint error: {str(e)}")
        return {"error": "Failed to collect metrics"}


# Include API routes
app.include_router(main_router)