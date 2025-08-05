# src/marbix/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from marbix.api.v1 import api_router as main_router
from marbix.core.config import settings
from arq import create_pool
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
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Redis pool storage
redis_pool = None


@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup"""
    global redis_pool

    try:
        logger.info("Starting Marbix API...")

        # Initialize Redis connection pool
        logger.info("Connecting to Redis...")
        redis_pool = await create_pool(settings.redis_settings)

        # Test Redis connection
        await redis_pool.ping()
        logger.info("Redis connection established successfully")

        # Store pool in app state for access in routes
        app.state.redis_pool = redis_pool

        logger.info("Marbix API startup completed successfully")

    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on application shutdown"""
    global redis_pool

    try:
        logger.info("Shutting down Marbix API...")

        # Close Redis connection pool
        if redis_pool:
            logger.info("Closing Redis connection pool...")
            redis_pool.close()
            await redis_pool.wait_closed()
            logger.info("Redis connection pool closed")

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
    """Health check endpoint with Redis connectivity test"""
    try:
        # Test Redis connection if available
        if hasattr(app.state, 'redis_pool') and app.state.redis_pool:
            await app.state.redis_pool.ping()
            redis_status = "connected"
        else:
            redis_status = "not_connected"

        return {
            "status": "healthy",
            "redis": redis_status,
            "timestamp": "2025-08-04T00:00:00Z"  # Add current timestamp in production
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "redis": "error",
            "error": str(e)
        }


@app.get("/metrics")
async def metrics():
    """Basic metrics endpoint for monitoring"""
    try:
        # You can add more metrics here
        metrics_data = {
            "redis_pool_status": "unknown",
            "active_connections": 0
        }

        if hasattr(app.state, 'redis_pool') and app.state.redis_pool:
            try:
                await app.state.redis_pool.ping()
                metrics_data["redis_pool_status"] = "healthy"
                # Add connection pool metrics if available
            except Exception:
                metrics_data["redis_pool_status"] = "unhealthy"

        return metrics_data

    except Exception as e:
        logger.error(f"Metrics endpoint error: {str(e)}")
        return {"error": "Failed to collect metrics"}


# Include API routes
app.include_router(main_router)


# Helper function to get Redis pool from anywhere in the app
def get_redis_pool():
    """Get Redis pool from app state"""
    if hasattr(app.state, 'redis_pool'):
        return app.state.redis_pool
    return None