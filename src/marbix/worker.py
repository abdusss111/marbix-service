# src/marbix/worker.py

import asyncio
import httpx
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from arq.connections import RedisSettings

from marbix.core.config import settings
from marbix.core.deps import get_db
from marbix.services.make_service import make_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# API configurations
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

# Rate limiting and retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 5
REQUEST_TIMEOUT = 600  # 10 minutes


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

        # Step 2: Deep research with Perplexity
        logger.info(f"Starting deep research for {request_id}")
        research_result = await conduct_deep_research(request_data, request_id)

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

        # Step 4: Generate strategy with Claude
        logger.info(f"Starting strategy generation for {request_id}")
        strategy_result = await generate_marketing_strategy(
            request_data,
            research_result.get("research_content", ""),
            request_id
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

        # Step 6: Final notification
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


async def conduct_deep_research(request_data: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """Conduct deep market research using Perplexity API with proper error handling"""

    try:
        # ИСПРАВЛЕННЫЙ mapping полей
        business_type = request_data.get("business_type", "").strip()
        business_goal = request_data.get("business_goal", "").strip()
        product_description = request_data.get("product_data", "").strip()  # ← ИСПРАВЛЕНО
        target_audience = request_data.get("target_audience_info", "").strip()  # ← ИСПРАВЛЕНО
        location = request_data.get("location", "Global").strip()
        company_name = request_data.get("company_name", "").strip()  # ← ДОБАВЛЕНО
        competitors = request_data.get("competitors", "").strip()  # ← ДОБАВЛЕНО
        current_volume = request_data.get("current_volume", "").strip()  # ← ДОБАВЛЕНО

        # Validate required fields
        if not business_type or not product_description:
            return {
                "success": False,
                "error": "Missing required business information"
            }

        # Обновленный research prompt
        research_prompt = f"""
        Conduct comprehensive market research for this business:

        🏢 BUSINESS CONTEXT:
        • Company: {company_name}
        • Business Type: {business_type}
        • Business Goal: {business_goal}
        • Product/Service: {product_description}
        • Target Audience: {target_audience}
        • Location: {location}
        • Current Volume: {current_volume}
        • Known Competitors: {competitors}

        # остальной prompt без изменений...

       📊 REQUIRED RESEARCH AREAS:

       1. MARKET LANDSCAPE ANALYSIS
       • Current market size and growth projections
       • Key market drivers and emerging trends
       • Market segmentation and demographics
       • Geographic market opportunities

       2. COMPETITIVE INTELLIGENCE
       • Direct and indirect competitors
       • Competitor pricing and positioning
       • Market share distribution
       • Competitive gaps and opportunities

       3. CUSTOMER BEHAVIOR INSIGHTS
       • Customer journey and decision factors
       • Pain points and unmet needs
       • Digital behavior and preferences
       • Buying patterns and cycles

       4. MARKETING CHANNEL EFFECTIVENESS
       • Best performing channels for this industry
       • Cost-per-acquisition benchmarks
       • ROI expectations by channel
       • Emerging marketing opportunities

       5. INDUSTRY TRENDS & REGULATIONS
       • Technology trends affecting the industry
       • Regulatory considerations
       • Best practices and standards

       Provide data-driven insights with specific metrics and actionable findings.
       """

        # Make API request with retries
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                        timeout=httpx.Timeout(REQUEST_TIMEOUT),
                        limits=httpx.Limits(max_connections=10)
                ) as client:

                    response = await client.post(
                        PERPLEXITY_API_URL,
                        json={
                            "model": "llama-3.1-sonar-large-128k-online",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are a senior market research analyst. Provide detailed, data-driven insights with credible sources and actionable intelligence."
                                },
                                {
                                    "role": "user",
                                    "content": research_prompt
                                }
                            ],
                            "max_tokens": 6000,
                            "temperature": 0.1,
                            "return_citations": True
                        },
                        headers={
                            "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
                            "Content-Type": "application/json"
                        }
                    )

                    if response.status_code == 200:
                        result = response.json()
                        research_content = result["choices"][0]["message"]["content"]

                        # Extract sources safely
                        sources = []
                        try:
                            if "citations" in result and result["citations"]:
                                sources = [
                                              citation.get("url", "")
                                              for citation in result["citations"]
                                              if citation.get("url") and citation["url"].startswith("http")
                                          ][:20]  # Limit to 20 sources
                        except Exception as citation_error:
                            logger.warning(f"Failed to extract citations: {str(citation_error)}")

                        logger.info(f"Research completed for {request_id}, found {len(sources)} sources")

                        return {
                            "success": True,
                            "research_content": research_content,
                            "sources": sources
                        }

                    elif response.status_code == 429:  # Rate limited
                        wait_time = min(RETRY_DELAY * (2 ** attempt), 120)  # Exponential backoff, max 2 minutes
                        logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}")
                        await asyncio.sleep(wait_time)
                        continue

                    else:
                        error_text = response.text[:500]  # Limit error text
                        logger.error(f"Perplexity API error {response.status_code}: {error_text}")

                        if attempt == MAX_RETRIES - 1:  # Last attempt
                            return {
                                "success": False,
                                "error": f"Research API error: {response.status_code}"
                            }

                        await asyncio.sleep(RETRY_DELAY)

            except httpx.TimeoutException:
                logger.warning(f"Research request timeout, attempt {attempt + 1}")
                if attempt == MAX_RETRIES - 1:
                    return {
                        "success": False,
                        "error": "Research request timed out"
                    }
                await asyncio.sleep(RETRY_DELAY)

            except Exception as request_error:
                logger.error(f"Research request failed: {str(request_error)}")
                if attempt == MAX_RETRIES - 1:
                    return {
                        "success": False,
                        "error": f"Research failed: {str(request_error)}"
                    }
                await asyncio.sleep(RETRY_DELAY)

        return {
            "success": False,
            "error": "Research failed after all retries"
        }

    except Exception as e:
        logger.error(f"Deep research failed: {str(e)}")
        return {
            "success": False,
            "error": f"Research error: {str(e)}"
        }


async def generate_marketing_strategy(
        request_data: Dict[str, Any],
        research_content: str,
        request_id: str
) -> Dict[str, Any]:
    """Generate marketing strategy using Claude API with proper error handling"""

    try:
        # Extract and validate business parameters
        business_type = request_data.get("business_type", "")
        business_goal = request_data.get("business_goal", "")
        product_description = request_data.get("product_service_description", "")
        target_audience = request_data.get("target_audience", "")
        promotion_budget = request_data.get("promotion_budget", "Not specified")
        team_budget = request_data.get("team_budget", "Not specified")

        # Build strategy prompt
        strategy_prompt = f"""
       Based on the market research provided, create a comprehensive marketing strategy:

       🎯 BUSINESS OVERVIEW:
       • Business Type: {business_type}
       • Business Goal: {business_goal}
       • Product/Service: {product_description}
       • Target Audience: {target_audience}
       • Promotion Budget: {promotion_budget}
       • Team Budget: {team_budget}

       📊 MARKET RESEARCH:
       {research_content[:8000]}  # Limit research content to prevent token overflow

       📋 CREATE A COMPREHENSIVE MARKETING STRATEGY:

       ## 1. EXECUTIVE SUMMARY
       • Strategic overview and key recommendations
       • Expected outcomes and success metrics
       • Investment summary

       ## 2. MARKET OPPORTUNITY
       • Key opportunities from research
       • Competitive positioning
       • Market entry strategy

       ## 3. TARGET AUDIENCE STRATEGY
       • Customer personas and segments
       • Customer journey mapping
       • Messaging framework

       ## 4. MARKETING MIX STRATEGY
       • Product positioning
       • Pricing recommendations
       • Distribution strategy
       • Promotional tactics

       ## 5. DIGITAL MARKETING PLAN
       • Website and SEO strategy
       • Social media approach
       • Content marketing plan
       • Paid advertising strategy

       ## 6. IMPLEMENTATION ROADMAP
       • 30-day quick wins
       • 90-day milestones
       • 6-month strategic goals
       • Resource requirements

       ## 7. BUDGET ALLOCATION
       • Channel budget breakdown
       • ROI projections
       • Performance metrics

       ## 8. SUCCESS METRICS & KPIs
       • Key performance indicators
       • Measurement framework
       • Reporting schedule

       Make recommendations specific, actionable, and budget-appropriate.
       """

        # Make API request with retries
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                        timeout=httpx.Timeout(REQUEST_TIMEOUT),
                        limits=httpx.Limits(max_connections=10)
                ) as client:

                    response = await client.post(
                        CLAUDE_API_URL,
                        json={
                            "model": "claude-3-5-sonnet-20241022",
                            "max_tokens": 6000,
                            "temperature": 0.3,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": strategy_prompt
                                }
                            ]
                        },
                        headers={
                            "x-api-key": settings.OPENAI_API_KEY,
                            "Content-Type": "application/json",
                            "anthropic-version": "2023-06-01"
                        }
                    )

                    if response.status_code == 200:
                        result = response.json()
                        strategy = result["content"][0]["text"]

                        logger.info(f"Strategy generated for {request_id}")

                        return {
                            "success": True,
                            "strategy": strategy
                        }

                    elif response.status_code == 429:  # Rate limited
                        wait_time = min(RETRY_DELAY * (2 ** attempt), 120)
                        logger.warning(f"Claude rate limited, waiting {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue

                    else:
                        error_text = response.text[:500]
                        logger.error(f"Claude API error {response.status_code}: {error_text}")

                        if attempt == MAX_RETRIES - 1:
                            return {
                                "success": False,
                                "error": f"Strategy API error: {response.status_code}"
                            }

                        await asyncio.sleep(RETRY_DELAY)

            except httpx.TimeoutException:
                logger.warning(f"Strategy request timeout, attempt {attempt + 1}")
                if attempt == MAX_RETRIES - 1:
                    return {
                        "success": False,
                        "error": "Strategy generation timed out"
                    }
                await asyncio.sleep(RETRY_DELAY)

            except Exception as request_error:
                logger.error(f"Strategy request failed: {str(request_error)}")
                if attempt == MAX_RETRIES - 1:
                    return {
                        "success": False,
                        "error": f"Strategy generation failed: {str(request_error)}"
                    }
                await asyncio.sleep(RETRY_DELAY)

        return {
            "success": False,
            "error": "Strategy generation failed after all retries"
        }

    except Exception as e:
        logger.error(f"Strategy generation error: {str(e)}")
        return {
            "success": False,
            "error": f"Strategy error: {str(e)}"
        }


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