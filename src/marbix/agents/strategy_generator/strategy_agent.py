"""
Strategy Generator Agent for creating marketing strategies using Anthropic Claude.

This agent takes the researcher agent's output as input and processes it to generate
clear, actionable marketing strategies using Claude Sonnet 4.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import httpx
import asyncio

from marbix.utils.prompt_utils import get_formatted_prompt
from marbix.crud.prompt import increment_prompt_usage, get_prompt_by_name
from marbix.core.config import settings

logger = logging.getLogger(__name__)


class StrategyGeneratorAgent:
    """Strategy generator agent using Anthropic Claude API."""
    
    def __init__(self, db: Session, model_name: str = "claude-sonnet-4-20250514"):
        """
        Initialize the strategy generator agent with Anthropic Claude.
        
        Args:
            db: Database session for retrieving prompts and updating usage
            model_name: Name of the model to use
        """
        self.db = db
        self.model_name = model_name
        self.api_key = settings.ANTHROPIC_API_KEY
        self.base_url = "https://api.anthropic.com/v1/messages"
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required in environment variables")
        
        logger.info(f"Strategy generator agent initialized with model: {self.model_name}")
    
    async def generate_strategy(
        self,
        request_data: Dict[str, Any],
        research_output: Dict[str, Any],
        request_id: str,
        prompt_name: str
    ) -> Dict[str, Any]:
        """
        Generate comprehensive marketing strategy using Claude.
        
        Args:
            request_data: Original business request data
            research_output: Output from the researcher agent
            request_id: Unique identifier for the request
            prompt_name: Name of the prompt to retrieve from database
            
        Returns:
            Generated strategy with success status and content
        """
        try:
            logger.info(f"Starting Claude strategy generation for request {request_id}")
            
            if not self._validate_research_output(research_output):
                return {
                    "success": False,
                    "error": "Invalid research output provided"
                }
            
            # Get strategy prompt from database
            strategy_prompt = self._get_strategy_prompt(prompt_name, request_data, research_output)
            if not strategy_prompt:
                return {
                    "success": False,
                    "error": "Strategy prompt not found in database"
                }
            
            # Generate strategy using Claude
            strategy_content = await self._make_strategy_request(strategy_prompt, research_output)
            
            if strategy_content:
                await self._increment_prompt_usage(prompt_name)
                
                logger.info(f"Strategy generated successfully for {request_id}")
                
                return {
                    "success": True,
                    "strategy": strategy_content,
                    "model_used": self.model_name,
                    "generated_at": datetime.now().isoformat(),
                    "agent_framework": "Custom Anthropic Agent"
                }
            else:
                return {
                    "success": False,
                    "error": "Claude API returned empty result"
                }
                
        except Exception as e:
            error_msg = f"Claude strategy generation failed for {request_id}: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    async def _make_strategy_request(self, prompt: str, research_output: Dict[str, Any]) -> Optional[str]:
        """Make request to Claude API for strategy generation."""
        try:
            # Prepare the message content
            message_content = f"""
{prompt}

RESEARCH OUTPUT:
{research_output.get('research_content', 'No research content available')}

SOURCES:
{chr(10).join(research_output.get('sources', ['No sources available']))}

Please generate a comprehensive marketing strategy based on the above research and prompt.
"""
            
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            
            payload = {
                "model": self.model_name,
                "max_tokens": 6000,
                "temperature": 0.3,
                "messages": [
                    {
                        "role": "user",
                        "content": message_content
                    }
                ]
            }
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result.get("content", [])
                    
                    if content and len(content) > 0:
                        return content[0].get("text", "")
                    else:
                        logger.warning("Claude response had no content")
                        return None
                else:
                    logger.error(f"Claude API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error making Claude API request: {str(e)}")
            return None
    
    def _get_strategy_prompt(self, prompt_name: str, request_data: Dict[str, Any], research_output: Dict[str, Any]) -> Optional[str]:
        """Retrieve and format strategy prompt from database."""
        try:
            business_context = {
                "business_type": request_data.get("business_type", "").strip(),
                "business_goal": request_data.get("business_goal", "").strip(),
                "product_data": request_data.get("product_data", "").strip(),
                "target_audience_info": request_data.get("target_audience_info", "").strip(),
                "location": request_data.get("location", "").strip(),
                "company_name": request_data.get("company_name", "").strip(),
                "competitors": request_data.get("competitors", "").strip(),
                "current_volume": request_data.get("current_volume", "").strip(),
                "actions": request_data.get("actions", "").strip(),
                "promotion_budget": request_data.get("promotion_budget", "").strip(),
                "team_budget": request_data.get("team_budget", "").strip(),
                "research_content": research_output.get("research_content", ""),
                "research_sources_count": len(research_output.get("sources", [])),
                "research_model_used": research_output.get("model_used", ""),
                "citations": self._format_citations(research_output.get("sources", []))
            }
            
            prompt = get_formatted_prompt(self.db, prompt_name, **business_context)
            return prompt
            
        except Exception as e:
            logger.error(f"Error retrieving strategy prompt: {str(e)}")
            return None
    
    def _validate_research_output(self, research_output: Dict[str, Any]) -> bool:
        """Validate that research output contains required fields."""
        if not research_output.get("success"):
            return False
        
        if not research_output.get("research_content"):
            return False
        
        return True
    
    def _format_citations(self, sources: List[str]) -> str:
        """Format sources list into a readable citations string."""
        try:
            if not sources:
                return "No sources available"
            
            # Format sources as numbered list
            formatted_sources = []
            for i, source in enumerate(sources[:10], 1):  # Limit to 10 sources
                if source and source.startswith("http"):
                    formatted_sources.append(f"{i}. {source}")
            
            if formatted_sources:
                return "\n".join(formatted_sources)
            else:
                return "No valid sources available"
                
        except Exception as e:
            logger.warning(f"Failed to format citations: {str(e)}")
            return "Error formatting sources"
    
    async def _increment_prompt_usage(self, prompt_name: str):
        """Increment usage count for the strategy prompt."""
        try:
            prompt = get_prompt_by_name(self.db, prompt_name)
            if prompt:
                increment_prompt_usage(self.db, prompt.id)
                logger.debug(f"Incremented usage for strategy prompt '{prompt_name}'")
        except Exception as e:
            logger.warning(f"Failed to increment strategy prompt usage: {str(e)}")


async def generate_strategy_async(
    db: Session,
    request_data: Dict[str, Any],
    research_output: Dict[str, Any],
    request_id: str,
    prompt_name: str,
    model_name: str = "claude-sonnet-4-20250514"
) -> Dict[str, Any]:
    """
    Convenience function for generating strategies asynchronously using Claude.
    
    Args:
        db: Database session
        request_data: Business request data
        research_output: Research output from researcher agent
        request_id: Request identifier
        prompt_name: Name of the strategy prompt to use
        model_name: Name of the model to use
        
    Returns:
        Generated strategy results
    """
    agent = StrategyGeneratorAgent(db, model_name)
    return await agent.generate_strategy(request_data, research_output, request_id, prompt_name)