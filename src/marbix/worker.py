# src/marbix/worker.py

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime
from arq.connections import RedisSettings

from marbix.core.config import settings
from marbix.core.deps import get_db
from marbix.services.make_service import make_service
from marbix.services.enhancement_service import enhancement_service
from marbix.agents.researcher.researcher_agent import conduct_research_async
from marbix.agents.strategy_generator.strategy_agent import generate_strategy_async
from marbix.schemas.enhanced_strategy import EnhancementPromptType
from marbix.models.enhanced_strategy import EnhancementStatus

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

        # Step 2: Update sources as JSON array
        sources_array = []
        if research_result.get("sources"):
            sources_array = research_result["sources"][:50]  # Limit to 50 sources
            try:
                make_service.update_request_status(
                    request_id=request_id,
                    status="processing",
                    sources=sources_array,  # Store as JSON array
                    db=db
                )
                logger.info(f"Sources updated for {request_id}: {len(sources_array)} URLs")
            except Exception as e:
                logger.warning(f"Failed to update sources: {e}")

        # Step 3: Strategy generation
        logger.info(f"Starting strategy generation for {request_id}")
        strategy_result = await generate_strategy_async(
            db=db,
            request_data=request_data,
            research_output=research_result,
            request_id=request_id,
            prompt_name="claude-prompt"
        )

        if not strategy_result.get("success"):
            error_msg = strategy_result.get("error", "Strategy generation failed")
            logger.error(f"Strategy generation failed for {request_id}: {error_msg}")
            raise Exception(f"Strategy generation failed: {error_msg}")

        # Step 4: Save final result with sources preserved
        logger.info(f"Saving completed strategy for {request_id}")
        try:
            make_service.update_request_status(
                request_id=request_id,
                status="completed",
                result=strategy_result["strategy"],
                sources=sources_array,  # Preserve sources when saving final result
                db=db
            )
            logger.info(f"✅ Strategy generation completed successfully for {request_id} with {len(sources_array)} sources")

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
            request_data=request_data,
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


async def enhance_strategy_workflow(ctx, enhancement_id: str, strategy_id: str, user_id: str, **kwargs):
    """
    ENHANCEMENT WORKFLOW: Process strategy enhancement with 9 separate AI calls
    """
    db = None
    try:
        logger.info(f"Starting strategy enhancement workflow for {enhancement_id}")
        
        # Get database session
        try:
            db = next(get_db())
        except Exception as db_error:
            logger.error(f"Database connection failed: {str(db_error)}")
            raise Exception("Database connection failed")
        
        # Get original strategy
        original_strategy = enhancement_service.get_strategy_by_id(strategy_id, db)
        if not original_strategy or not original_strategy.result:
            raise Exception(f"Original strategy {strategy_id} not found or incomplete")
        
        if original_strategy.status != "completed":
            raise Exception(f"Original strategy {strategy_id} is not completed (status: {original_strategy.status})")
        
        strategy_text = original_strategy.result
        logger.info(f"Retrieved original strategy {strategy_id} ({len(strategy_text)} chars)")
        
        # Update status to processing
        enhancement_service.update_enhancement_status(
            enhancement_id=enhancement_id,
            status=EnhancementStatus.PROCESSING,
            db=db
        )
        
        # Define enhancement sections with their corresponding prompt types
        enhancement_sections = [
            ("Analys_rynka", EnhancementPromptType.MARKET_ANALYSIS),
            ("Drivers", EnhancementPromptType.DRIVERS),
            ("Competitors", EnhancementPromptType.COMPETITORS),
            ("Customer_Journey", EnhancementPromptType.CUSTOMER_JOURNEY),
            ("Product", EnhancementPromptType.PRODUCT),
            ("Communication", EnhancementPromptType.COMMUNICATION),
            ("TEAM", EnhancementPromptType.TEAM),
            ("Metrics", EnhancementPromptType.METRICS),
            ("Next_Steps", EnhancementPromptType.NEXT_STEPS),
        ]
        
        successful_enhancements = 0
        total_sections = len(enhancement_sections)
        
        # Process all enhancement sections IN PARALLEL for 9x speed boost
        logger.info(f"Starting parallel enhancement of {total_sections} sections")
        
        async def enhance_single_section(section_name: str, prompt_type):
            """Helper function to enhance a single section"""
            try:
                logger.info(f"🚀 Starting parallel enhancement: {section_name}")
                
                # Enhance this specific section
                result = await enhancement_service.enhance_strategy_section(
                    enhancement_id=enhancement_id,
                    section_name=section_name,
                    prompt_type=prompt_type,
                    original_strategy=strategy_text,
                    db=db
                )
                
                if result.success:
                    # Save enhanced section to database
                    save_success = enhancement_service.save_enhanced_section(
                        enhancement_id=enhancement_id,
                        section_name=section_name,
                        content=result.content,
                        db=db
                    )
                    
                    if save_success:
                        logger.info(f"✅ Enhanced and saved section {section_name}")
                        return True
                    else:
                        logger.error(f"❌ Failed to save enhanced section {section_name}")
                        return False
                else:
                    logger.error(f"❌ Failed to enhance section {section_name}: {result.error}")
                    return False
                
            except Exception as section_error:
                logger.error(f"Error processing section {section_name}: {str(section_error)}")
                return False
        
        # Execute all sections in parallel using asyncio.gather
        tasks = [
            enhance_single_section(section_name, prompt_type) 
            for section_name, prompt_type in enhancement_sections
        ]
        
        # Wait for all sections to complete in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful enhancements
        for i, result in enumerate(results):
            section_name = enhancement_sections[i][0]
            if isinstance(result, Exception):
                logger.error(f"❌ Exception in section {section_name}: {result}")
            elif result is True:
                successful_enhancements += 1
        
        # Update final status
        if successful_enhancements == total_sections:
            enhancement_service.update_enhancement_status(
                enhancement_id=enhancement_id,
                status=EnhancementStatus.COMPLETED,
                db=db
            )
            logger.info(f"✅ Enhancement workflow completed successfully for {enhancement_id}")
            logger.info(f"Enhanced {successful_enhancements}/{total_sections} sections")
        else:
            enhancement_service.update_enhancement_status(
                enhancement_id=enhancement_id,
                status=EnhancementStatus.PARTIAL,
                db=db,
                error=f"Only {successful_enhancements}/{total_sections} sections enhanced successfully"
            )
            logger.warning(f"⚠️ Enhancement partially completed: {successful_enhancements}/{total_sections} sections")
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Enhancement workflow failed for {enhancement_id}: {error_msg}")
        
        # Update database with error status
        try:
            if db:
                enhancement_service.update_enhancement_status(
                    enhancement_id=enhancement_id,
                    status=EnhancementStatus.ERROR,
                    db=db,
                    error=error_msg
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


# ARQ Worker Settings
class WorkerSettings:
    functions = [generate_strategy, research_only_workflow, strategy_only_workflow, enhance_strategy_workflow]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    job_timeout = settings.ARQ_JOB_TIMEOUT
    max_tries = settings.ARQ_MAX_TRIES
    retry_delay = settings.ARQ_RETRY_DELAY
