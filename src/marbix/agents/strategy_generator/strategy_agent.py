"""
Strategy Generator Agent for creating marketing strategies using Google ADK.

This agent takes the researcher agent's output as input and processes it to generate
clear, actionable marketing strategies using Google Agent Development Kit (ADK).
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from marbix.core.config import settings
from marbix.utils.prompt_utils import get_formatted_prompt
from marbix.crud.prompt import increment_prompt_usage

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
    # Define a minimal BaseTool stub so module import doesn't crash if ADK is missing
    class BaseTool:  # type: ignore
        pass

# Configure logging
logger = logging.getLogger(__name__)

# Model configuration
MODEL_NAME = "claude-3-5-sonnet-20241022"
MAX_TOKENS = 6000
TEMPERATURE = 0.3

# Rate limiting and retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 5


class StrategyGenerationTool(BaseTool):
    """
    Custom tool for strategy generation using Google ADK.
    
    This tool takes research output and business data to generate marketing strategies.
    """
    
    def __init__(self, db: Session):
        super().__init__()
        self.db = db
        self.name = "generate_marketing_strategy"
        self.description = "Generate comprehensive marketing strategy based on research output and business data"
    
    async def run_async(self, context: Any, **kwargs) -> Dict[str, Any]:
        """
        Execute strategy generation using Google ADK.
        
        :param context: ADK tool context
        :param kwargs: Tool arguments including research_output and request_data
        :return: Generated strategy results
        """
        try:
            research_output = kwargs.get("research_output", {})
            request_data = kwargs.get("request_data", {})
            request_id = kwargs.get("request_id", "unknown")
            prompt_name = kwargs.get("prompt_name", "marketing_strategy_generator")
            
            logger.info(f"Strategy generation tool called for request {request_id}")
            
            # Validate inputs
            if not self._validate_inputs(research_output, request_data):
                return {
                    "success": False,
                    "error": "Invalid input data provided"
                }
            
            # Get strategy prompt from database
            strategy_prompt = await self._get_strategy_prompt(prompt_name, request_data, research_output)
            if not strategy_prompt:
                return {
                    "success": False,
                    "error": "Strategy prompt not found in database"
                }
            
            # Return the formatted prompt for the ADK agent to process
            return {
                "success": True,
                "prompt": strategy_prompt,
                "business_context": {
                    "business_type": request_data.get("business_type", ""),
                    "business_goal": request_data.get("business_goal", ""),
                    "research_content_length": len(research_output.get("research_content", "")),
                    "sources_count": len(research_output.get("sources", []))
                }
            }
            
        except Exception as e:
            logger.error(f"Strategy generation tool error: {str(e)}")
            return {
                "success": False,
                "error": f"Tool execution failed: {str(e)}"
            }
    
    def _validate_inputs(self, research_output: Dict[str, Any], request_data: Dict[str, Any]) -> bool:
        """Validate input data for strategy generation."""
        if not research_output.get("success"):
            return False
        
        if not research_output.get("research_content"):
            return False
        
        required_fields = ["business_type", "business_goal"]
        return all(request_data.get(field) for field in required_fields)
    
    async def _get_strategy_prompt(self, prompt_name: str, request_data: Dict[str, Any], research_output: Dict[str, Any]) -> Optional[str]:
        """Retrieve and format strategy prompt from database."""
        try:
            business_context = {
                "business_type": request_data.get("business_type", "").strip(),
                "business_goal": request_data.get("business_goal", "").strip(),
                "product_description": request_data.get("product_data", "").strip(),
                "target_audience": request_data.get("target_audience_info", "").strip(),
                "location": request_data.get("location", "Global").strip(),
                "company_name": request_data.get("company_name", "").strip(),
                "promotion_budget": request_data.get("promotion_budget", "Not specified").strip(),
                "team_budget": request_data.get("team_budget", "Not specified").strip(),
                "research_content": research_output.get("research_content", "")[:8000],
                "research_sources_count": len(research_output.get("sources", [])),
                "research_model_used": research_output.get("model_used", "Unknown")
            }
            
            prompt = get_formatted_prompt(self.db, prompt_name, **business_context)
            return prompt
            
        except Exception as e:
            logger.error(f"Error retrieving strategy prompt: {str(e)}")
            return None


class StrategyGeneratorAgent:
    """
    Strategy generator agent using Google ADK framework.
    
    This agent processes research output from the researcher agent and generates
    comprehensive, actionable marketing strategies using Google ADK.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the strategy generator agent with Google ADK.
        
        :param db: Database session for retrieving prompts and updating usage
        """
        self.db = db
        
        if not GOOGLE_ADK_AVAILABLE:
            raise ImportError("Google ADK is required. Install with: pip install google-adk")
        
        # Initialize ADK components
        self._initialize_adk_components()
    
    def _initialize_adk_components(self):
        """Initialize Google ADK components."""
        try:
            # Initialize platform
            self.platform = Platform()
            
            # Initialize services
            self.artifact_service = InMemoryArtifactService()
            self.memory_service = InMemoryMemoryService()
            self.session_service = SessionService()
            
            # Initialize model
            self.model = Model(
                name=MODEL_NAME,
                temperature=TEMPERATURE,
                max_output_tokens=MAX_TOKENS
            )
            
            # Create strategy generation tool
            self.strategy_tool = StrategyGenerationTool(self.db)
            
            # Create ADK agent
            self.agent = LlmAgent(
                name="marketing_strategy_generator",
                description="Generates comprehensive marketing strategies based on research output",
                model=self.model,
                tools=[self.strategy_tool],
                instruction=self._get_agent_instruction(),
                global_instruction=self._get_global_instruction()
            )
            
            logger.info(f"Google ADK agent initialized with model: {MODEL_NAME}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google ADK components: {str(e)}")
            raise
    
    def _get_agent_instruction(self) -> str:
        """Get the main instruction for the ADK agent."""
        return """
        You are a marketing strategy expert. Your task is to generate comprehensive, 
        actionable marketing strategies based on research output and business data.
        
        Use the generate_marketing_strategy tool to get the formatted prompt and business context.
        Then generate a detailed marketing strategy that includes:
        
        1. Executive Summary
        2. Market Opportunity Analysis
        3. Target Audience Strategy
        4. Marketing Mix Strategy (4Ps)
        5. Digital Marketing Plan
        6. Implementation Roadmap
        7. Budget Allocation & ROI
        8. Success Metrics & KPIs
        9. Risk Management
        10. Next Steps & Recommendations
        
        Make all recommendations specific, actionable, and appropriate for the given budget constraints.
        Focus on practical implementation steps that can be executed immediately.
        Ensure the strategy is data-driven and based on the research insights provided.
        """
    
    def _get_global_instruction(self) -> str:
        """Get global instruction for the ADK agent."""
        return """
        You are a professional marketing strategist with expertise in:
        - Market analysis and competitive intelligence
        - Customer segmentation and targeting
        - Digital marketing and growth strategies
        - Budget planning and ROI optimization
        - Implementation planning and project management
        
        Always provide practical, actionable advice that can be implemented immediately.
        Use data-driven insights and industry best practices.
        Consider budget constraints and resource limitations.
        """
    
    async def generate_strategy(
        self,
        request_data: Dict[str, Any],
        research_output: Dict[str, Any],
        request_id: str,
        prompt_name: str = "marketing_strategy_generator"
    ) -> Dict[str, Any]:
        """
        Generate comprehensive marketing strategy using Google ADK.
        
        :param request_data: Original business request data
        :param research_output: Output from the researcher agent
        :param request_id: Unique identifier for the request
        :param prompt_name: Name of the prompt to retrieve from database
        :return: Generated strategy with success status and content
        """
        try:
            logger.info(f"Starting ADK strategy generation for request {request_id}")
            
            # Validate research output
            if not self._validate_research_output(research_output):
                return {
                    "success": False,
                    "error": "Invalid research output provided"
                }
            
            # Create invocation context
            context = InvocationContext(
                agent=self.agent,
                user_content=f"Generate marketing strategy for business: {request_data.get('business_type', 'Unknown')}",
                invocation_id=request_id,
                artifact_service=self.artifact_service,
                memory_service=self.memory_service,
                session_service=self.session_service
            )
            
            # Run the ADK agent
            result = await self.agent.run_async(
                context,
                research_output=research_output,
                request_data=request_data,
                request_id=request_id,
                prompt_name=prompt_name
            )
            
            if result and hasattr(result, 'content'):
                strategy_content = result.content
                
                # Increment prompt usage if successful
                await self._increment_prompt_usage(prompt_name)
                
                logger.info(f"Strategy generated successfully for {request_id}")
                
                return {
                    "success": True,
                    "strategy": strategy_content,
                    "model_used": MODEL_NAME,
                    "generated_at": datetime.now().isoformat(),
                    "agent_framework": "Google ADK"
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
        required_fields = ["success", "research_content"]
        
        if not research_output.get("success"):
            logger.warning("Research output indicates failure")
            return False
        
        for field in required_fields:
            if field not in research_output:
                logger.warning(f"Research output missing required field: {field}")
                return False
        
        if not research_output.get("research_content"):
            logger.warning("Research output has empty content")
            return False
        
        return True
    
    async def _increment_prompt_usage(self, prompt_name: str):
        """Increment usage count for the strategy prompt."""
        try:
            from marbix.crud.prompt import get_prompt_by_name
            
            prompt = get_prompt_by_name(self.db, prompt_name)
            if prompt:
                increment_prompt_usage(self.db, prompt.id)
                logger.debug(f"Incremented usage for strategy prompt '{prompt_name}'")
        except Exception as e:
            logger.warning(f"Failed to increment strategy prompt usage: {str(e)}")


# Convenience function for direct usage in ARQ workers
async def generate_strategy_async(
    db: Session,
    request_data: Dict[str, Any],
    research_output: Dict[str, Any],
    request_id: str,
    prompt_name: str = "marketing_strategy_generator"
) -> Dict[str, Any]:
    """
    Convenience function for generating strategies asynchronously using Google ADK.
    
    This function can be called directly from ARQ workers.
    
    :param db: Database session
    :param request_data: Business request data
    :param research_output: Research output from researcher agent
    :param request_id: Request identifier
    :param prompt_name: Name of the strategy prompt to use
    :return: Generated strategy results
    """
    agent = StrategyGeneratorAgent(db)
    return await agent.generate_strategy(request_data, research_output, request_id, prompt_name)


# Example usage in ARQ worker context
async def example_worker_function(ctx, request_id: str, user_id: str, request_data: Dict[str, Any]):
    """
    Example of how to use the strategy generator agent in an ARQ worker.
    
    This shows the complete flow: research → strategy generation using Google ADK
    
    :param ctx: ARQ context
    :param request_id: Request identifier
    :param user_id: User identifier
    :param request_data: Business data for research and strategy
    """
    from marbix.core.deps import get_db
    from marbix.agents.researcher.researcher_agent import conduct_research_async
    
    db = next(get_db())
    try:
        # Step 1: Conduct research
        logger.info(f"Starting research phase for {request_id}")
        research_result = await conduct_research_async(
            db=db,
            request_data=request_data,
            request_id=request_id,
            prompt_name="business_research_agent"
        )
        
        if not research_result.get("success"):
            raise Exception(f"Research failed: {research_result.get('error')}")
        
        # Step 2: Generate strategy based on research using Google ADK
        logger.info(f"Starting ADK strategy generation for {request_id}")
        strategy_result = await generate_strategy_async(
            db=db,
            request_data=request_data,
            research_output=research_result,
            request_id=request_id,
            prompt_name="marketing_strategy_generator"
        )
        
        if not strategy_result.get("success"):
            raise Exception(f"Strategy generation failed: {strategy_result.get('error')}")
        
        # Return combined results
        return {
            "success": True,
            "research": research_result,
            "strategy": strategy_result,
            "request_id": request_id,
            "completed_at": datetime.now().isoformat(),
            "framework": "Google ADK"
        }
        
    except Exception as e:
        logger.error(f"Complete workflow failed for {request_id}: {str(e)}")
        raise
    finally:
        db.close()
