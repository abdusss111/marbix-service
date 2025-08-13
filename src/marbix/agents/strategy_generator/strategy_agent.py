"""
Strategy Generator Agent for creating marketing strategies using Google ADK.

This agent takes the researcher agent's output as input and processes it to generate
clear, actionable marketing strategies using Google Agent Development Kit (ADK).
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from marbix.utils.prompt_utils import get_formatted_prompt
from marbix.crud.prompt import increment_prompt_usage, get_prompt_by_name

# Google ADK imports
try:
    from google.adk.agents import LlmAgent, InvocationContext
    from google.adk.models import Model
    from google.adk.tools.base_tool import BaseTool
    from google.adk.artifacts import InMemoryArtifactService
    from google.adk.memory import InMemoryMemoryService
    from google.adk.sessions import SessionService
    from google.adk.platform import Platform
    GOOGLE_ADK_AVAILABLE = True
except ImportError:
    GOOGLE_ADK_AVAILABLE = False
    class BaseTool:
        def __init__(self, *args, **kwargs):
            pass

logger = logging.getLogger(__name__)


class StrategyGenerationTool(BaseTool):
    """Custom tool for strategy generation using Google ADK."""
    
    def __init__(self, db: Session):
        # BaseTool in ADK requires name and description
        super().__init__(name="generate_marketing_strategy", description=
            "Generate comprehensive marketing strategy based on research output and business data")
        self.db = db
    
    async def run_async(self, context: Any, **kwargs) -> Dict[str, Any]:
        """ADK tool entry: fetch formatted prompt from DB."""
        try:
            research_output: Dict[str, Any] = kwargs.get("research_output", {})
            request_data: Dict[str, Any] = kwargs.get("request_data", {})
            request_id: str = kwargs.get("request_id", "unknown")
            prompt_name: str = kwargs.get("prompt_name", "marketing_strategy_generator")

            if not self._validate_inputs(research_output, request_data):
                return {"success": False, "error": "Invalid input data provided"}

            strategy_prompt = self._get_strategy_prompt(prompt_name, request_data, research_output)
            if not strategy_prompt:
                return {"success": False, "error": "Strategy prompt not found in database"}

            return {"success": True, "prompt": strategy_prompt, "request_id": request_id}

        except Exception as e:
            logger.error(f"Strategy generation tool error: {str(e)}")
            return {"success": False, "error": f"Tool execution failed: {str(e)}"}
    
    def _validate_inputs(self, research_output: Dict[str, Any], request_data: Dict[str, Any]) -> bool:
        """Validate input data for strategy generation."""
        if not research_output.get("success"):
            return False
        
        if not research_output.get("research_content"):
            return False
        
        required_fields = ["business_type", "business_goal"]
        return all(request_data.get(field) for field in required_fields)
    
    def _get_strategy_prompt(self, prompt_name: str, request_data: Dict[str, Any], research_output: Dict[str, Any]) -> Optional[str]:
        """Retrieve and format strategy prompt from database."""
        try:
            business_context = {
                "business_type": request_data.get("business_type", "").strip(),
                "business_goal": request_data.get("business_goal", "").strip(),
                "product_description": request_data.get("product_data", "").strip(),
                "target_audience": request_data.get("target_audience_info", "").strip(),
                "location": request_data.get("location", "").strip(),
                "company_name": request_data.get("company_name", "").strip(),
                "promotion_budget": request_data.get("promotion_budget", "").strip(),
                "team_budget": request_data.get("team_budget", "").strip(),
                "research_content": research_output.get("research_content", ""),
                "research_sources_count": len(research_output.get("sources", [])),
                "research_model_used": research_output.get("model_used", "")
            }
            
            prompt = get_formatted_prompt(self.db, prompt_name, **business_context)
            return prompt
            
        except Exception as e:
            logger.error(f"Error retrieving strategy prompt: {str(e)}")
            return None


class StrategyGeneratorAgent:
    """Strategy generator agent using Google ADK framework."""
    
    def __init__(self, db: Session, model_name: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize the strategy generator agent with Google ADK.
        
        Args:
            db: Database session for retrieving prompts and updating usage
            model_name: Name of the model to use
        """
        self.db = db
        self.model_name = model_name
        
        if not GOOGLE_ADK_AVAILABLE:
            raise ImportError("Google ADK is required. Install with: pip install google-adk")
        
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize Google ADK agent."""
        try:
            self.strategy_tool = StrategyGenerationTool(self.db)
            
            self.agent = Agent(
                name="marketing_strategy_generator",
                model=self.model_name,
                description="Generates comprehensive marketing strategies based on research output",
                instruction="""
                You are a marketing strategy expert. Use the generate_marketing_strategy tool to get the 
                formatted prompt from the database, then generate a comprehensive marketing strategy based 
                on that prompt and the provided research data.
                
                Always provide specific, actionable recommendations that can be implemented immediately.
                Focus on practical steps and measurable outcomes.
                """,
                tools=[self.strategy_tool]
            )
            
            logger.info(f"Google ADK agent initialized with model: {self.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google ADK agent: {str(e)}")
            raise
    
    async def generate_strategy(
        self,
        request_data: Dict[str, Any],
        research_output: Dict[str, Any],
        request_id: str,
        prompt_name: str
    ) -> Dict[str, Any]:
        """
        Generate comprehensive marketing strategy using Google ADK.
        
        Args:
            request_data: Original business request data
            research_output: Output from the researcher agent
            request_id: Unique identifier for the request
            prompt_name: Name of the prompt to retrieve from database
            
        Returns:
            Generated strategy with success status and content
        """
        try:
            logger.info(f"Starting ADK strategy generation for request {request_id}")
            
            if not self._validate_research_output(research_output):
                return {
                    "success": False,
                    "error": "Invalid research output provided"
                }
            
            # Use ADK run_async with proper context; tool fetches DB prompt
            context = InvocationContext(
                agent=self.agent,
                user_content=f"Generate marketing strategy for business: {request_data.get('business_type', 'Unknown')}",
                invocation_id=request_id,
                artifact_service=self.artifact_service,
                memory_service=self.memory_service,
                session_service=self.session_service,
            )

            result = await self.agent.run_async(
                context,
                research_output=research_output,
                request_data=request_data,
                request_id=request_id,
                prompt_name=prompt_name,
            )

            if result and hasattr(result, 'content'):
                strategy_content = result.content
                
                await self._increment_prompt_usage(prompt_name)
                
                logger.info(f"Strategy generated successfully for {request_id}")
                
                return {
                    "success": True,
                    "strategy": strategy_content,
                    "model_used": self.model_name,
                    "generated_at": datetime.now().isoformat(),
                    "request_id": request_id
                }
            else:
                return {
                    "success": False,
                    "error": "ADK agent returned empty result"
                }
                
        except Exception as e:
            error_msg = f"ADK strategy generation failed for {request_id}: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    

    
    def _validate_research_output(self, research_output: Dict[str, Any]) -> bool:
        """Validate that research output contains required fields."""
        if not research_output.get("success"):
            return False
        
        if not research_output.get("research_content"):
            return False
        
        return True
    
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
    model_name: str = "gemini-2.0-flash"
) -> Dict[str, Any]:
    """
    Convenience function for generating strategies asynchronously using Google ADK.
    
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