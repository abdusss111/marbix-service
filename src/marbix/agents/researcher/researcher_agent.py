"""
Researcher Agent for conducting market research using Perplexity API.

This agent is designed to be called asynchronously in ARQ workers and uses
prompts stored in the database instead of hardcoded prompts.
"""

import asyncio
import httpx
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from marbix.core.config import settings
from marbix.utils.prompt_utils import get_formatted_prompt
from marbix.crud.prompt import increment_prompt_usage

# Configure logging
logger = logging.getLogger(__name__)

# API configuration
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
MODEL_NAME = "sonar-deep-research"

# Rate limiting and retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 5
REQUEST_TIMEOUT = 600  # 10 minutes


class ResearcherAgent:
    """
    Async researcher agent that conducts market research using Perplexity API.
    
    This agent retrieves prompts from the database and uses them to generate
    comprehensive research requests to the Perplexity API.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the researcher agent.
        
        :param db: Database session for retrieving prompts and updating usage
        """
        self.db = db
        self.api_key = settings.PERPLEXITY_API_KEY
        
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY is required")
    
    async def conduct_research(
        self, 
        request_data: Dict[str, Any], 
        request_id: str,
        prompt_name: str = "perplexity-prompt"
    ) -> Dict[str, Any]:
        """
        Conduct comprehensive market research using Perplexity API.
        
        :param request_data: Business data for research context
        :param request_id: Unique identifier for the research request
        :param prompt_name: Name of the prompt to retrieve from database
        :return: Research results with content and sources
        """
        try:
            logger.info(f"Starting research for request {request_id} using prompt '{prompt_name}'")
            
            # Get research prompt from database
            research_prompt = await self._get_research_prompt(prompt_name, request_data)
            if not research_prompt:
                return {
                    "success": False,
                    "error": f"Research prompt '{prompt_name}' not found in database"
                }
            
            # Conduct the research
            research_result = await self._make_research_request(research_prompt, request_id)
            
            # Increment prompt usage if research was successful
            if research_result.get("success"):
                await self._increment_prompt_usage(prompt_name)
            
            return research_result
            
        except Exception as e:
            error_msg = f"Research failed for {request_id}: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    async def _get_research_prompt(self, prompt_name: str, request_data: Dict[str, Any]) -> Optional[str]:
        """
        Retrieve and format research prompt from database.
        
        :param prompt_name: Name of the prompt to retrieve
        :param request_data: Business data for variable substitution
        :return: Formatted prompt string or None if not found
        """
        try:
            # Extract key business data for prompt formatting
            business_context = {
                "business_type": request_data.get("business_type", "").strip(),
                "business_goal": request_data.get("business_goal", "").strip(),
                "product_data": request_data.get("product_data", "").strip(),
                "target_audience_info": request_data.get("target_audience_info", "").strip(),
                "location": request_data.get("location", "Global").strip(),
                "company_name": request_data.get("company_name", "").strip(),
                "competitors": request_data.get("competitors", "").strip(),
                "current_volume": request_data.get("current_volume", "").strip(),
                "actions": request_data.get("actions", "").strip(),
                "promotion_budget": request_data.get("promotion_budget", "").strip(),
                "team_budget": request_data.get("team_budget", "").strip()
            }
            
            # Get formatted prompt from database
            prompt = get_formatted_prompt(self.db, prompt_name, **business_context)
            
            if not prompt:
                logger.warning(f"Prompt '{prompt_name}' not found or inactive")
                return None
            
            logger.info(f"Successfully retrieved prompt '{prompt_name}' from database")
            return prompt
            
        except Exception as e:
            logger.error(f"Error retrieving prompt '{prompt_name}': {str(e)}")
            return None
    
    async def _make_research_request(self, research_prompt: str, request_id: str) -> Dict[str, Any]:
        """
        Make research request to Perplexity API with retry logic.
        
        :param research_prompt: Formatted research prompt
        :param request_id: Request identifier for logging
        :return: Research results with content and sources
        """
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(REQUEST_TIMEOUT),
                    limits=httpx.Limits(max_connections=10)
                ) as client:
                    
                    response = await client.post(
                        PERPLEXITY_API_URL,
                        json={
                            "model": MODEL_NAME,
                            "messages": [
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
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        research_content = result["choices"][0]["message"]["content"]
                        
                        # Extract sources safely
                        sources = await self._extract_sources(result)
                        
                        logger.info(f"Research completed for {request_id}, found {len(sources)} sources")
                        
                        return {
                            "success": True,
                            "research_content": research_content,
                            "sources": sources,
                            "model_used": MODEL_NAME,
                            "completed_at": datetime.now().isoformat()
                        }
                    
                    elif response.status_code == 429:  # Rate limited
                        wait_time = min(RETRY_DELAY * (2 ** attempt), 120)
                        logger.warning(f"Rate limited, waiting {wait_time}s before retry {attempt + 1}")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    else:
                        error_text = response.text[:500]
                        logger.error(f"Perplexity API error {response.status_code}: {error_text}")
                        
                        if attempt == MAX_RETRIES - 1:  # Last attempt
                            return {
                                "success": False,
                                "error": f"Research API error: {response.status_code}"
                            }
                        
                        await asyncio.sleep(RETRY_DELAY)
                        
            except httpx.TimeoutException:
                logger.warning(f"Request timeout on attempt {attempt + 1}")
                if attempt == MAX_RETRIES - 1:
                    return {
                        "success": False,
                        "error": "Request timeout after all retries"
                    }
                await asyncio.sleep(RETRY_DELAY)
                
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {str(e)}")
                if attempt == MAX_RETRIES - 1:
                    return {
                        "success": False,
                        "error": f"Unexpected error: {str(e)}"
                    }
                await asyncio.sleep(RETRY_DELAY)
        
        return {
            "success": False,
            "error": "All retry attempts failed"
        }
    
    async def _extract_sources(self, api_result: Dict[str, Any]) -> List[str]:
        """
        Extract sources from Perplexity API response.
        
        :param api_result: API response dictionary
        :return: List of source URLs
        """
        sources = []
        try:
            if "citations" in api_result and api_result["citations"]:
                sources = [
                    citation.get("url", "")
                    for citation in api_result["citations"]
                    if citation.get("url") and citation["url"].startswith("http")
                ][:20]  # Limit to 20 sources
        except Exception as e:
            logger.warning(f"Failed to extract citations: {str(e)}")
        
        return sources
    
    async def _increment_prompt_usage(self, prompt_name: str):
        """
        Increment usage count for the prompt.
        
        :param prompt_name: Name of the prompt to update
        """
        try:
            from marbix.crud.prompt import get_prompt_by_name
            
            prompt = get_prompt_by_name(self.db, prompt_name)
            if prompt:
                increment_prompt_usage(self.db, prompt.id)
                logger.debug(f"Incremented usage for prompt '{prompt_name}'")
        except Exception as e:
            logger.warning(f"Failed to increment prompt usage: {str(e)}")


# Convenience function for direct usage in ARQ workers
async def conduct_research_async(
    db: Session,
    request_data: Dict[str, Any],
    request_id: str,
    prompt_name: str = "perplexity-prompt"
) -> Dict[str, Any]:
    """
    Convenience function for conducting research asynchronously.
    
    This function can be called directly from ARQ workers.
    
    :param db: Database session
    :param request_data: Business data for research
    :param request_id: Request identifier
    :param prompt_name: Name of the prompt to use
    :return: Research results
    """
    agent = ResearcherAgent(db)
    return await agent.conduct_research(request_data, request_id, prompt_name)
