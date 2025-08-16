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
from marbix.agents.strategy_generator.strategy_agent import generate_strategy_async

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def generate_strategy(ctx, request_id: str, user_id: str, request_data: Dict[str, Any], **kwargs):
    """
    SIMPLIFIED: Complete strategy generation workflow - database polling handles real-time updates
    """
    db = None
    try:
        logger.info(f"Starting strategy generation for request {request_id}, user {user_id}")

        # Validate inputs
        if not request_id or not user_id or not request_data:
            raise ValueError("Missing required parameters")

        # Get database session
        try:
            db = next(get_db())
        except Exception as db_error:
            logger.error(f"Database connection failed: {str(db_error)}")
            raise Exception("Database connection failed")

        # Step 1: Research phase
        logger.info(f"Starting research for {request_id}")
        research_result = await conduct_research_async(
            db=db,
            request_data=request_data,
            request_id=request_id,
            prompt_name="perplexity-prompt",
        )

        if not research_result.get("success"):
            error_msg = research_result.get("error", "Research failed")
            logger.error(f"Research failed for {request_id}: {error_msg}")
            raise Exception(f"Research failed: {error_msg}")

        # Step 2: Update sources
        sources_text = ""
        if research_result.get("sources"):
            sources_text = "\n".join(research_result["sources"][:50])
            try:
                await make_service.update_request_sources(
                    request_id=request_id,
                    sources=sources_text,
                    db=db
                )
                logger.info(f"Sources updated for {request_id}")
            except Exception as e:
                logger.warning(f"Failed to update sources: {e}")

        # Step 3: Strategy generation
        logger.info(f"Starting strategy generation for {request_id}")
        strategy_result = await generate_strategy_async(
            db=db,
            business_context=request_data,
            research_output=research_result["response"],
            request_id=request_id,
            prompt_name="claude-prompt"
        )

        if not strategy_result.get("success"):
            error_msg = strategy_result.get("error", "Strategy generation failed")
            logger.error(f"Strategy generation failed for {request_id}: {error_msg}")
            raise Exception(f"Strategy generation failed: {error_msg}")

        # Step 4: Save final result
        logger.info(f"Saving completed strategy for {request_id}")
        try:
            make_service.update_request_status(
                request_id=request_id,
                status="completed",
                result=strategy_result["strategy"],
                db=db
            )
            logger.info(f"✅ Strategy generation completed successfully for {request_id}")

        except Exception as db_error:
            logger.error(f"Failed to save strategy: {db_error}")
            raise

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Strategy generation failed for {request_id}: {error_msg}")

        # Update database with error status
        try:
            if db:
                make_service.update_request_status(
                    request_id=request_id,
                    status="error",
                    error=error_msg,
                    db=db
                )
        except Exception as db_err:
            logger.error(f"Failed to update error status: {db_err}")

        raise  # Re-raise for ARQ retry handling

    finally:
        if db:
            try:
                db.close()
            except Exception as close_err:
                logger.warning(f"Error closing database: {close_err}")


async def research_only_workflow(ctx, request_id: str, user_id: str, request_data: Dict[str, Any], **kwargs):
    """Research-only workflow for testing"""
    db = None
    try:
        logger.info(f"Starting research-only workflow for {request_id}")
        
        db = next(get_db())
        
        research_result = await conduct_research_async(
            db=db,
            request_data=request_data,
            request_id=request_id,
            prompt_name="perplexity-prompt"
        )
        
        if research_result.get("success"):
            logger.info(f"Research completed for {request_id}")
        else:
            logger.error(f"Research failed for {request_id}")
            
        return research_result
        
    except Exception as e:
        logger.error(f"Research workflow failed for {request_id}: {e}")
        raise
    finally:
        if db:
            db.close()


async def strategy_only_workflow(ctx, request_id: str, user_id: str, request_data: Dict[str, Any], research_output: Dict[str, Any], **kwargs):
    """Strategy-only workflow"""
    db = None
    try:
        logger.info(f"Starting strategy-only workflow for {request_id}")
        
        db = next(get_db())
        
        strategy_result = await generate_strategy_async(
            db=db,
            business_context=request_data,
            research_output=research_output,
            request_id=request_id,
            prompt_name="claude-prompt"
        )
        
        if strategy_result.get("success"):
            # Save to database
            make_service.update_request_status(
                request_id=request_id,
                status="completed",
                result=strategy_result["strategy"],
                db=db
            )
            logger.info(f"Strategy-only workflow completed for {request_id}")
        else:
            logger.error(f"Strategy generation failed for {request_id}")
            make_service.update_request_status(
                request_id=request_id,
                status="error",
                error=strategy_result.get("error", "Unknown error"),
                db=db
            )
            
        return strategy_result
        
    except Exception as e:
        logger.error(f"Strategy workflow failed for {request_id}: {e}")
        if db:
            make_service.update_request_status(
                request_id=request_id,
                status="error", 
                error=str(e),
                db=db
            )
        raise
    finally:
        if db:
            db.close()


# ARQ Worker Settings
class WorkerSettings:
    functions = [generate_strategy, research_only_workflow, strategy_only_workflow]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    job_timeout = settings.ARQ_JOB_TIMEOUT
    max_tries = settings.ARQ_MAX_TRIES
    retry_delay = settings.ARQ_RETRY_DELAY
