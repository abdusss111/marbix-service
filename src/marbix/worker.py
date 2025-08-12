# src/marbix/worker.py

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime
from arq.connections import RedisSettings

from marbix.core.config import settings
from marbix.core.deps import get_db
from marbix.services.make_service import make_service
from marbix.agents.researcher.researcher_agent import conduct_research_async
from marbix.agents.strategy_generator import generate_strategy_async

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# No API prompt strings here — agents will read prompts from DB


async def generate_strategy(ctx, request_id: str, user_id: str, request_data: Dict[str, Any], **kwargs):
    """
    Complete strategy generation workflow: Research → Strategy
    **kwargs accepts ARQ internal parameters like _job_timeout, _max_tries, etc.
    """

    db = None
    try:
        logger.info(f"Starting strategy generation for request {request_id}, user {user_id}")

        # Validate inputs
        if not request_id or not user_id or not request_data:
            raise ValueError("Missing required parameters: request_id, user_id, or request_data")

        # Get database session with error handling
        try:
            db = next(get_db())
        except Exception as db_error:
            logger.error(f"Database connection failed: {str(db_error)}")
            raise Exception("Database connection failed")

        # Step 1: Initial notification
        await safe_notify_user(
            request_id=request_id,
            status="processing",
            message="Starting deep market research..."
        )

        # Step 2: Deep research via Researcher Agent (DB prompt: perplexity-prompt)
        logger.info(f"Starting deep research for {request_id}")
        research_result = await conduct_research_async(
            db=db,
            request_data=request_data,
            request_id=request_id,
            prompt_name="perplexity-prompt",
        )

        if not research_result.get("success"):
            error_msg = research_result.get("error", "Unknown research error")
            raise Exception(f"Research failed: {error_msg}")

        # Step 3: Update sources and notify progress
        sources_text = ""
        if research_result.get("sources"):
            sources_text = "\n".join(research_result["sources"][:50])  # Limit sources
            try:
                await make_service.update_request_sources(
                    request_id=request_id,
                    sources=sources_text,
                    db=db
                )
            except Exception as sources_error:
                logger.warning(f"Failed to update sources: {str(sources_error)}")

        await safe_notify_user(
            request_id=request_id,
            status="processing",
            message="Research completed. Generating comprehensive marketing strategy...",
            sources=sources_text if sources_text else None
        )

        # Step 4: Generate strategy via Strategy Agent (DB prompt: claude-prompt)
        logger.info(f"Starting strategy generation for {request_id}")
        strategy_result = await generate_strategy_async(
            db=db,
            request_data=request_data,
            research_output=research_result,
            request_id=request_id,
            prompt_name="claude-prompt",
        )

        if not strategy_result.get("success"):
            error_msg = strategy_result.get("error", "Unknown strategy error")
            raise Exception(f"Strategy generation failed: {error_msg}")

        # Step 5: Final database update
        try:
            make_service.update_request_status(
                request_id=request_id,
                status="completed",
                result=strategy_result["strategy"],
                db=db
            )
        except Exception as db_error:
            logger.error(f"Failed to update database: {str(db_error)}")
            raise Exception("Failed to save results")

        # Step 6: Stream strategy via WebSocket and send final completion
        try:
            await make_service.send_strategy_result(
                request_id=request_id,
                strategy_text=strategy_result["strategy"],
                sources=sources_text if sources_text else None,
            )
        except Exception as ws_err:
            logger.warning(f"WS streaming failed, falling back to single message: {ws_err}")
            await safe_notify_user(
                request_id=request_id,
                status="completed",
                message="Complete marketing strategy generated successfully!",
                result=strategy_result["strategy"],
                sources=sources_text if sources_text else None
            )

        logger.info(f"Strategy generation completed successfully for {request_id}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Strategy generation failed for {request_id}: {error_msg}")

        # Update database with error
        if db:
            try:
                make_service.update_request_status(
                    request_id=request_id,
                    status="error",
                    error=error_msg,
                    db=db
                )
            except Exception as db_error:
                logger.error(f"Failed to update error status: {str(db_error)}")

        # Notify user of error
        await safe_notify_user(
            request_id=request_id,
            status="error",
            message="Strategy generation failed. Please try again.",
            error=error_msg
        )

        # Re-raise for ARQ retry logic
        raise

    finally:
        # Always close database connection
        if db:
            try:
                db.close()
            except Exception as close_error:
                logger.warning(f"Failed to close database connection: {str(close_error)}")
        


async def safe_notify_user(
        request_id: str,
        status: str,
        message: str = None,
        result: str = None,
        error: str = None,
        sources: str = None
):
    """Safely notify user with error handling"""
    try:
        await make_service.notify_user_status(
            request_id=request_id,
            status=status,
            message=message,
            result=result,
            error=error,
            sources=sources
        )
    except Exception as notify_error:
        logger.warning(f"Failed to notify user for {request_id}: {str(notify_error)}")


# ARQ Worker Settings
class WorkerSettings:
    functions = [generate_strategy]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    job_timeout = settings.ARQ_JOB_TIMEOUT
    max_tries = settings.ARQ_MAX_TRIES
    retry_delay = settings.ARQ_RETRY_DELAY

    # Performance settings
    max_jobs = 3  # Limit concurrent jobs for resource management
    keep_result = 7200  # Keep results for 2 hours
    health_check_interval = 60

    # Worker lifecycle
    @staticmethod
    async def on_startup(ctx):
        logger.info("=== ARQ WORKER STARTED ===")

    @staticmethod
    async def on_shutdown(ctx):
        logger.info("=== ARQ WORKER STOPPED ===")