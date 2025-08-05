# src/marbix/worker.py

import asyncio
import httpx
import logging
from typing import Dict, Any
from datetime import datetime
from arq import create_pool
from arq.connections import RedisSettings

from marbix.core.config import settings
from marbix.core.deps import get_db
from marbix.services.make_service import make_service
from marbix.core.websocket import manager

logger = logging.getLogger(__name__)

# API configurations
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"


async def generate_strategy(ctx, request_id: str, user_id: str, request_data: Dict[str, Any]):
    """Complete strategy generation workflow: Research → Strategy"""

    db = None
    try:
        logger.info(f"Starting strategy generation for request {request_id}")

        # Get database session
        db = next(get_db())

        # Step 1: Initial notification
        await make_service.notify_user_status(
            request_id=request_id,
            status="processing",
            message="Starting deep market research..."
        )

        # Step 2: Deep research with Perplexity Sonar Deep Research
        research_result = await conduct_deep_research(request_data, request_id)

        if not research_result["success"]:
            raise Exception(f"Research failed: {research_result['error']}")

        # Step 3: Update sources and notify progress
        if research_result.get("sources"):
            sources_text = "\n".join(research_result["sources"])
            await make_service.update_request_sources(
                request_id=request_id,
                sources=sources_text,
                db=db
            )

        await make_service.notify_user_status(
            request_id=request_id,
            status="processing",
            message="Research completed. Generating comprehensive marketing strategy...",
            sources=sources_text if research_result.get("sources") else None
        )

        # Step 4: Generate strategy with Claude Sonnet 4
        strategy_result = await generate_marketing_strategy(
            request_data,
            research_result["research_content"],
            request_id
        )

        if not strategy_result["success"]:
            raise Exception(f"Strategy generation failed: {strategy_result['error']}")

        # Step 5: Final database update
        make_service.update_request_status(
            request_id=request_id,
            status="completed",
            result=strategy_result["strategy"],
            db=db
        )

        # Step 6: Final notification
        await make_service.notify_user_status(
            request_id=request_id,
            status="completed",
            message="Complete marketing strategy generated successfully!",
            result=strategy_result["strategy"],
            sources=sources_text if research_result.get("sources") else None
        )

        logger.info(f"Strategy generation completed for request {request_id}")

    except Exception as e:
        logger.error(f"Strategy generation failed for request {request_id}: {str(e)}")

        if db:
            make_service.update_request_status(
                request_id=request_id,
                status="error",
                error=str(e),
                db=db
            )

        await make_service.notify_user_status(
            request_id=request_id,
            status="error",
            message="Strategy generation failed. Please try again.",
            error=str(e)
        )

        raise

    finally:
        if db:
            db.close()


async def conduct_deep_research(request_data: Dict[str, Any], request_id: str) -> Dict[str, Any]:
    """Conduct deep market research using Perplexity Sonar Deep Research model"""

    try:
        # Extract business information
        business_description = request_data.get("business_description", "[BUSINESS_DESCRIPTION]")
        target_audience = request_data.get("target_audience", "[TARGET_AUDIENCE]")
        industry = request_data.get("industry", "[INDUSTRY]")
        location = request_data.get("location", "[LOCATION]")
        budget_range = request_data.get("budget", "[BUDGET_RANGE]")

        # Deep research prompt with placeholders
        research_prompt = f"""
       Conduct comprehensive deep market research for this business opportunity:

       🏢 BUSINESS CONTEXT:
       • Business: {business_description}
       • Industry: {industry}
       • Target Audience: {target_audience}
       • Geographic Focus: {location}
       • Budget Range: {budget_range}

       📊 REQUIRED DEEP RESEARCH AREAS:

       1. MARKET LANDSCAPE ANALYSIS
       • Current market size and growth projections for {industry}
       • Key market drivers and emerging trends
       • Market segmentation and customer demographics
       • Geographic market variations and opportunities

       2. COMPETITIVE INTELLIGENCE
       • Direct and indirect competitors analysis
       • Competitor pricing strategies and positioning
       • Market share distribution
       • Competitive advantages and weaknesses
       • Gap analysis and white space opportunities

       3. CUSTOMER BEHAVIOR INSIGHTS
       • Customer journey mapping for {target_audience}
       • Purchase decision factors and triggers
       • Pain points and unmet needs
       • Digital behavior and channel preferences
       • Seasonal patterns and buying cycles

       4. MARKETING CHANNEL EFFECTIVENESS
       • Performance data for different marketing channels in {industry}
       • Cost-per-acquisition benchmarks
       • ROI expectations by channel
       • Emerging marketing platforms and opportunities
       • Channel saturation levels and competition

       5. REGULATORY & INDUSTRY CONSTRAINTS
       • Industry regulations affecting marketing
       • Compliance requirements
       • Upcoming regulatory changes
       • Industry best practices and standards

       6. TECHNOLOGY & INNOVATION TRENDS
       • Technological disruptions in {industry}
       • Digital transformation trends
       • Innovation opportunities
       • Technology adoption rates among {target_audience}

       Please provide data-driven insights with specific metrics, statistics, and actionable findings for each area.
       """

        async with httpx.AsyncClient(timeout=600.0) as client:  # 10 minutes timeout
            response = await client.post(
                PERPLEXITY_API_URL,
                json={
                    "model": "llama-3.1-sonar-large-128k-online",  # Deep research model
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a senior market research analyst specializing in comprehensive business intelligence. Provide detailed, data-driven insights with specific metrics, statistics, and credible sources. Focus on actionable intelligence that can inform strategic marketing decisions."
                        },
                        {
                            "role": "user",
                            "content": research_prompt
                        }
                    ],
                    "max_tokens": 8000,
                    "temperature": 0.1,  # Low temperature for factual research
                    "return_citations": True,
                    "search_domain_filter": ["businessinsider.com", "statista.com", "mckinsey.com", "deloitte.com",
                                             "pwc.com", "forbes.com", "hbr.org"]
                },
                headers={
                    "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json"
                }
            )

            if response.status_code != 200:
                logger.error(f"Perplexity research API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Research API error: {response.status_code}"
                }

            result = response.json()
            research_content = result["choices"][0]["message"]["content"]

            # Extract sources/citations
            sources = []
            if "citations" in result:
                sources = [
                              citation.get("url", "")
                              for citation in result["citations"]
                              if citation.get("url")
                          ][:20]  # Limit to top 20 sources

            logger.info(f"Deep research completed for {request_id}, found {len(sources)} sources")

            return {
                "success": True,
                "research_content": research_content,
                "sources": sources
            }

    except Exception as e:
        logger.error(f"Deep research failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


async def generate_marketing_strategy(
        request_data: Dict[str, Any],
        research_content: str,
        request_id: str
) -> Dict[str, Any]:
    """Generate comprehensive marketing strategy using Claude Sonnet 4"""

    try:
        # Extract business parameters
        business_description = request_data.get("business_description", "[BUSINESS_DESCRIPTION]")
        target_audience = request_data.get("target_audience", "[TARGET_AUDIENCE]")
        budget_range = request_data.get("budget", "[BUDGET_RANGE]")
        goals = request_data.get("goals", "[BUSINESS_GOALS]")
        timeframe = request_data.get("timeframe", "[TIMEFRAME]")
        current_marketing = request_data.get("current_marketing", "[CURRENT_MARKETING_EFFORTS]")

        # Comprehensive strategy prompt with placeholders
        strategy_prompt = f"""
       Based on the comprehensive market research provided, create an executive-level marketing strategy for this business:

       🎯 BUSINESS OVERVIEW:
       • Business: {business_description}
       • Target Audience: {target_audience}  
       • Budget Range: {budget_range}
       • Key Goals: {goals}
       • Timeline: {timeframe}
       • Current Marketing: {current_marketing}

       📊 MARKET RESEARCH DATA:
       {research_content}

       📋 DELIVERABLE: Complete Marketing Strategy Document

       Please structure your response as a comprehensive marketing strategy with these sections:

       ## 1. EXECUTIVE SUMMARY
       • Strategic overview and key recommendations
       • Expected ROI and success metrics
       • Investment summary and timeline

       ## 2. MARKET OPPORTUNITY ANALYSIS  
       • Market size and growth potential
       • Key opportunities identified from research
       • Competitive positioning recommendations

       ## 3. TARGET AUDIENCE STRATEGY
       • Primary and secondary audience segments
       • Customer personas and journey mapping
       • Messaging framework for each segment

       ## 4. BRAND POSITIONING & VALUE PROPOSITION
       • Unique value proposition
       • Brand positioning statement
       • Competitive differentiation strategy

       ## 5. MARKETING MIX STRATEGY (4Ps + Digital)
       • Product/Service optimization recommendations
       • Pricing strategy based on market research
       • Distribution channel strategy
       • Promotional mix optimization

       ## 6. CHANNEL STRATEGY & TACTICS
       • Recommended marketing channels with rationale
       • Channel-specific tactics and best practices
       • Integration and cross-channel synergies
       • Budget allocation by channel

       ## 7. DIGITAL MARKETING BLUEPRINT
       • Website and conversion optimization
       • SEO/SEM strategy
       • Social media strategy
       • Content marketing plan
       • Email marketing automation

       ## 8. IMPLEMENTATION ROADMAP
       • 90-day quick wins
       • 6-month milestones  
       • 12-month strategic initiatives
       • Resource requirements and timeline

       ## 9. BUDGET ALLOCATION & ROI PROJECTION
       • Detailed budget breakdown by channel/tactic
       • ROI projections and payback periods
       • Performance benchmarks and KPIs

       ## 10. RISK MITIGATION & CONTINGENCY PLANNING
       • Identified risks and mitigation strategies
       • Performance monitoring framework
       • Pivot strategies and backup plans

       ## 11. SUCCESS METRICS & REPORTING
       • Key Performance Indicators (KPIs)
       • Reporting dashboard recommendations
       • Review and optimization schedule

       Make all recommendations specific, actionable, and backed by the research data. Include specific tactics, tools, budgets, and timelines where possible.
       """

        async with httpx.AsyncClient(timeout=600.0) as client:  # 10 minutes timeout
            response = await client.post(
                CLAUDE_API_URL,
                json={
                    "model": "claude-3-5-sonnet-20241022",  # Claude Sonnet 4
                    "max_tokens": 8000,
                    "temperature": 0.3,
                    "messages": [
                        {
                            "role": "user",
                            "content": strategy_prompt
                        }
                    ]
                },
                headers={
                    "x-api-key": settings.OPENAI_API_KEY,  # Using OPENAI_API_KEY for Claude key
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                }
            )

            if response.status_code != 200:
                logger.error(f"Claude API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Strategy generation API error: {response.status_code}"
                }

            result = response.json()
            strategy = result["content"][0]["text"]

            logger.info(f"Marketing strategy generated for {request_id}")

            return {
                "success": True,
                "strategy": strategy
            }

    except Exception as e:
        logger.error(f"Strategy generation failed: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }


# ARQ Worker Settings
class WorkerSettings:
    functions = [generate_strategy]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    job_timeout = settings.ARQ_JOB_TIMEOUT
    max_tries = settings.ARQ_MAX_TRIES
    retry_delay = settings.ARQ_RETRY_DELAY

    # Worker performance settings
    max_jobs = 5
    keep_result = 7200
    health_check_interval = 60

    # Убираем on_startup и on_shutdown или делаем правильно:
    @staticmethod
    async def on_startup(ctx):
        logger.info("=== WORKER STARTED ===")

    @staticmethod
    async def on_shutdown(ctx):
        logger.info("=== WORKER STOPPED ===")
