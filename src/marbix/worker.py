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
# FIX: Change this import to match your actual structure
from marbix.agents.strategy_generator.strategy_agent import generate_strategy_async

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# No API prompt strings here — agents will read prompts from DB

async def send_realtime_status(request_id: str, status: str, message: str, progress: float, stage: str = None, error: str = None):
    """
    NEW: Send real-time status updates via WebSocket manager
    """
    try:
        from marbix.core.websocket import manager
        
        status_msg = {
            "request_id": request_id,
            "type": "status_update",
            "status": status,
            "message": message,
            "progress": progress,
            "timestamp": datetime.now().isoformat()
        }
        
        if stage:
            status_msg["stage"] = stage
        if error:
            status_msg["error"] = error
            status_msg["type"] = "error"
        
        await manager.send_message(request_id, status_msg)
        logger.info(f"Sent real-time status for {request_id}: {status} - {message}")
        
    except Exception as e:
        logger.error(f"Failed to send real-time status for {request_id}: {str(e)}")


async def generate_strategy(ctx, request_id: str, user_id: str, request_data: Dict[str, Any], **kwargs):
    """
    NEW FLOW: Complete strategy generation workflow with real-time WebSocket updates
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
            await send_realtime_status(request_id, "error", "Database connection failed", 0.0)
            raise Exception("Database connection failed")

        # Step 1: Worker started - notify real-time status
        await send_realtime_status(
            request_id=request_id,
            status="processing",
            message="Worker started. Initializing research phase...",
            progress=0.1,
            stage="initialization"
        )

        # Step 2: Deep research via Researcher Agent (DB prompt: perplexity-prompt)
        logger.info(f"Starting deep research for {request_id}")
        await send_realtime_status(
            request_id=request_id,
            status="processing",
            message="Starting deep market research using Perplexity AI...",
            progress=0.15,
            stage="research"
        )
        
        research_result = await conduct_research_async(
            db=db,
            request_data=request_data,
            request_id=request_id,
            prompt_name="perplexity-prompt",
        )

        if not research_result.get("success"):
            error_msg = research_result.get("error", "Unknown research error")
            await send_realtime_status(
                request_id=request_id,
                status="error",
                message="Research phase failed",
                progress=0.2,
                stage="research",
                error=error_msg
            )
            raise Exception(f"Research failed: {error_msg}")

        # Research completed successfully
        await send_realtime_status(
            request_id=request_id,
            status="processing",
            message="Market research completed! Preparing strategy generation...",
            progress=0.5,
            stage="research_complete"
        )

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
                await send_realtime_status(
                    request_id=request_id,
                    status="processing",
                    message=f"Research sources saved ({len(research_result['sources'])} sources found)",
                    progress=0.55,
                    stage="sources_update"
                )
            except Exception as sources_error:
                logger.warning(f"Failed to update sources: {str(sources_error)}")

        # Step 4: Generate strategy via Claude Strategy Agent (DB prompt: claude-prompt)
        logger.info(f"Starting Claude strategy generation for {request_id}")
        await send_realtime_status(
            request_id=request_id,
            status="processing",
            message="Starting AI strategy generation using Claude Sonnet 4...",
            progress=0.6,
            stage="strategy_generation"
        )
        
        strategy_result = await generate_strategy_async(
            db=db,
            request_data=request_data,
            research_output=research_result,
            request_id=request_id,
            prompt_name="claude-prompt"
        )

        if not strategy_result.get("success"):
            error_msg = strategy_result.get("error", "Unknown strategy error")
            await send_realtime_status(
                request_id=request_id,
                status="error",
                message="Strategy generation failed",
                progress=0.7,
                stage="strategy_generation",
                error=error_msg
            )
            raise Exception(f"Strategy generation failed: {error_msg}")

        # Strategy generation completed
        await send_realtime_status(
            request_id=request_id,
            status="processing",
            message="Strategy generated successfully! Finalizing and saving...",
            progress=0.9,
            stage="strategy_complete"
        )

        # Step 5: Update database with success
        try:
            make_service.update_request_status(
                request_id=request_id,
                status="completed",
                result=strategy_result["strategy"],
                db=db
            )
            
            await send_realtime_status(
                request_id=request_id,
                status="processing",
                message="Strategy saved to database. Preparing final delivery...",
                progress=0.95,
                stage="saving"
            )
            
        except Exception as db_error:
            logger.error(f"Failed to update success status: {str(db_error)}")
            await send_realtime_status(
                request_id=request_id,
                status="error",
                message="Failed to save strategy to database",
                progress=0.95,
                stage="saving",
                error=str(db_error)
            )
            raise

        # Step 6: NEW FLOW - Send final completion via WebSocket with strategy content
        try:
            from marbix.core.websocket import manager
            
            # Send final completion message
            completion_msg = {
                "request_id": request_id,
                "type": "strategy_complete",
                "status": "completed",
                "result": strategy_result["strategy"],
                "sources": sources_text if sources_text else None,
                "progress": 1.0,
                "message": "Strategy generation completed successfully!",
                "timestamp": datetime.now().isoformat()
            }
            
            await manager.send_message(request_id, completion_msg)
            logger.info(f"Sent final strategy completion via WebSocket for {request_id}")
            
        except Exception as ws_err:
            logger.error(f"Failed to send final completion via WebSocket for {request_id}: {str(ws_err)}")
            # Fallback - try again with safe_notify_user
            await safe_notify_user(
                request_id=request_id,
                status="completed",
                message="Complete marketing strategy generated successfully!",
                result=strategy_result["strategy"],
                sources=sources_text if sources_text else None
            )

        logger.info(f"NEW FLOW: Strategy generation completed successfully for {request_id}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Strategy generation failed for {request_id}: {error_msg}")

        # Send real-time error status
        await send_realtime_status(
            request_id=request_id,
            status="error",
            message="Strategy generation failed. Please try again.",
            progress=0.0,
            stage="error",
            error=error_msg
        )

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

        # Re-raise for ARQ retry logic
        raise

    finally:
        # Always close database connection
        if db:
            try:
                db.close()
            except Exception as close_error:
                logger.warning(f"Failed to close database connection: {str(close_error)}")
        


async def research_only_workflow(ctx, request_id: str, user_id: str, request_data: Dict[str, Any], **kwargs):
    """
    Research-only workflow using Perplexity API
    """
    db = None
    try:
        logger.info(f"Starting research-only workflow for request {request_id}")
        
        # Get database session
        db = next(get_db())
        
        # Initial notification
        await safe_notify_user(
            request_id=request_id,
            status="processing",
            message="Starting deep market research..."
        )
        
        # Send progress update
        await make_service.send_progress_update(
            request_id=request_id,
            stage="research",
            message="Starting deep market research...",
            progress=0.1
        )
        
        # Conduct research
        await make_service.send_progress_update(
            request_id=request_id,
            stage="research",
            message="Conducting deep market research...",
            progress=0.3
        )
        
        research_result = await conduct_research_async(
            db=db,
            request_data=request_data,
            request_id=request_id,
            prompt_name="perplexity-prompt",
        )
        
        if not research_result.get("success"):
            raise Exception(f"Research failed: {research_result.get('error', 'Unknown error')}")
        
        # Research completed successfully
        await make_service.send_progress_update(
            request_id=request_id,
            stage="research",
            message="Research completed successfully!",
            progress=0.8
        )
        
        # Update database with research results
        sources_text = ""
        if research_result.get("sources"):
            sources_text = "\n".join(research_result["sources"][:50])
            try:
                await make_service.update_request_sources(
                    request_id=request_id,
                    sources=sources_text,
                    db=db
                )
            except Exception as e:
                logger.warning(f"Failed to update sources: {str(e)}")
        
        # Update status and notify completion
        make_service.update_request_status(
            request_id=request_id,
            status="completed",
            result=research_result["research_content"],
            db=db
        )
        
        await safe_notify_user(
            request_id=request_id,
            status="completed",
            message="Research completed successfully!",
            result=research_result["research_content"],
            sources=sources_text if sources_text else None
        )
        
        logger.info(f"Research-only workflow completed for {request_id}")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Research workflow failed for {request_id}: {error_msg}")
        
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
        
        await safe_notify_user(
            request_id=request_id,
            status="error",
            message="Research failed. Please try again.",
            error=error_msg
        )
        raise
        
    finally:
        if db:
            try:
                db.close()
            except Exception as e:
                logger.warning(f"Failed to close database connection: {str(e)}")


async def strategy_only_workflow(ctx, request_id: str, user_id: str, request_data: Dict[str, Any], research_output: Dict[str, Any], **kwargs):
    """
    Strategy-only workflow using Google ADK (requires pre-existing research)
    """
    db = None
    try:
        logger.info(f"Starting strategy-only workflow for request {request_id}")
        
        # Get database session
        db = next(get_db())
        
        # Validate research output
        if not research_output or not research_output.get("success"):
            raise Exception("Invalid or missing research output")
        
        # Initial notification
        await safe_notify_user(
            request_id=request_id,
            status="processing",
            message="Generating marketing strategy using Claude..."
        )
        
        # Send progress update
        await make_service.send_progress_update(
            request_id=request_id,
            stage="strategy_generation",
            message="Starting strategy generation...",
            progress=0.1
        )
        
        # Generate strategy
        await make_service.send_progress_update(
            request_id=request_id,
            stage="strategy_generation",
            message="Generating marketing strategy...",
            progress=0.3
        )
        
        strategy_result = await generate_strategy_async(
            db=db,
            request_data=request_data,
            research_output=research_output,
            request_id=request_id,
            prompt_name="claude-prompt"
        )
        
        if not strategy_result.get("success"):
            raise Exception(f"Strategy generation failed: {strategy_result.get('error', 'Unknown error')}")
        
        # Strategy generation completed
        await make_service.send_progress_update(
            request_id=request_id,
            stage="strategy_generation",
            message="Strategy generated successfully!",
            progress=0.8
        )
        
        # Update database
        make_service.update_request_status(
            request_id=request_id,
            status="completed",
            result=strategy_result["strategy"],
            db=db
        )
        
        # Stream result and notify
        try:
            await make_service.send_strategy_result(
                request_id=request_id,
                strategy_text=strategy_result["strategy"],
                sources=research_output.get("sources", [])
            )
        except Exception as ws_err:
            logger.warning(f"WebSocket streaming failed: {ws_err}")
            # Send a properly formatted completion message
            try:
                from marbix.core.websocket import manager
                completion_msg = {
                    "request_id": request_id,
                    "type": "strategy_complete",
                    "status": "completed",
                    "result": strategy_result["strategy"],
                    "progress": 1.0,
                    "timestamp": datetime.now().isoformat()
                }
                if research_output.get("sources"):
                    completion_msg["sources"] = research_output.get("sources")
                
                await manager.send_message(request_id, completion_msg)
                logger.info(f"Sent fallback completion message for {request_id}")
            except Exception as fallback_err:
                logger.error(f"Fallback completion message failed for {request_id}: {str(fallback_err)}")
                # Last resort - use safe_notify_user
                await safe_notify_user(
                    request_id=request_id,
                    status="completed",
                    message="Strategy generated successfully!",
                    result=strategy_result["strategy"]
                )
        
        logger.info(f"Strategy-only workflow completed for {request_id}")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Strategy workflow failed for {request_id}: {error_msg}")
        
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
        
        await safe_notify_user(
            request_id=request_id,
            status="error",
            message="Strategy generation failed. Please try again.",
            error=error_msg
        )
        raise
        
    finally:
        if db:
            try:
                db.close()
            except Exception as e:
                logger.warning(f"Failed to close database connection: {str(e)}")


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
    functions = [generate_strategy, research_only_workflow, strategy_only_workflow]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    job_timeout = settings.ARQ_JOB_TIMEOUT
    max_tries = settings.ARQ_MAX_TRIES
    retry_delay = settings.ARQ_RETRY_DELAY
    
    # Prevent multiple workers from running the same job
    job_id_generator = lambda: f"marbix_worker_{datetime.now().timestamp()}"

    # Memory optimization settings
    max_jobs = 1  # Only 1 job at a time to prevent conflicts
    keep_result = 1800  # Keep results for 30 minutes (reduced further)
    health_check_interval = 10  # Very frequent health checks
    retry_delay = 0  # Immediate retry on failure
    
    # Worker lifecycle
    @staticmethod
    async def on_startup(ctx):
        logger.info("=== ARQ WORKER STARTED ===")
        
        # Check if another worker is already running
        try:
            from arq.connections import ArqRedis
            arq_redis = ArqRedis.from_dsn(settings.REDIS_URL)
            
            # Check for existing workers
            worker_info = await arq_redis.info()
            active_workers = worker_info.get('connected_clients', 0)
            
            if active_workers > 1:
                logger.warning(f"Multiple workers detected: {active_workers}. This may cause job conflicts.")
            
            # Clear any stale jobs on startup
            await arq_redis.flushdb()
            logger.info("Cleared Redis database on startup")
            
        except Exception as e:
            logger.warning(f"Failed to check workers or clear Redis on startup: {str(e)}")

    @staticmethod
    async def on_shutdown(ctx):
        logger.info("=== ARQ WORKER STOPPED ===")
        # Cleanup any remaining resources
        try:
            if hasattr(ctx, 'db') and ctx.db:
                ctx.db.close()
        except Exception as e:
            logger.warning(f"Failed to cleanup resources on shutdown: {str(e)}")