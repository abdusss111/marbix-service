"""
Configuration for the Strategy Generator Agent using Google ADK.

This file contains all configuration settings for the strategy generation process,
including model parameters, ADK settings, and operational configurations.
"""

from typing import Dict, Any
from marbix.core.config import settings

# Google ADK Model Configuration
GOOGLE_ADK_MODEL = "claude-3-5-sonnet-20241022"
GOOGLE_ADK_MAX_TOKENS = 6000
GOOGLE_ADK_TEMPERATURE = 0.3

# Strategy Generation Settings
STRATEGY_MAX_RETRIES = 3
STRATEGY_RETRY_DELAY = 5

# Content Limits
MAX_RESEARCH_CONTENT_LENGTH = 8000  # Characters to prevent token overflow
MAX_STRATEGY_LENGTH = 10000  # Maximum strategy length in characters

# Prompt Configuration
DEFAULT_STRATEGY_PROMPT_NAME = "marketing_strategy_generator"
DEFAULT_RESEARCH_PROMPT_NAME = "business_research_agent"

# Google ADK Agent Configuration
ADK_AGENT_NAME = "marketing_strategy_generator"
ADK_AGENT_DESCRIPTION = "Generates comprehensive marketing strategies based on research output"

# ADK Services Configuration
ADK_ARTIFACT_SERVICE_TYPE = "InMemoryArtifactService"
ADK_MEMORY_SERVICE_TYPE = "InMemoryMemoryService"
ADK_SESSION_SERVICE_TYPE = "SessionService"

# Strategy Output Structure
STRATEGY_SECTIONS = [
    "executive_summary",
    "market_opportunity",
    "target_audience_strategy",
    "marketing_mix_strategy",
    "digital_marketing_plan",
    "implementation_roadmap",
    "budget_allocation",
    "success_metrics_kpis"
]

# Validation Rules
REQUIRED_RESEARCH_FIELDS = [
    "success",
    "research_content"
]

REQUIRED_BUSINESS_FIELDS = [
    "business_type",
    "business_goal",
    "product_data"
]

# Error Messages
ERROR_MESSAGES = {
    "research_failed": "Research phase failed, cannot generate strategy",
    "prompt_not_found": "Strategy prompt not found in database",
    "invalid_research_output": "Invalid research output provided",
    "adk_generation_failed": "Google ADK failed to generate strategy",
    "adk_not_available": "Google ADK is not available",
    "timeout": "Strategy generation timed out",
    "database_error": "Database operation failed"
}

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Performance Monitoring
ENABLE_PERFORMANCE_MONITORING = True
PERFORMANCE_METRICS = [
    "prompt_retrieval_time",
    "adk_generation_time",
    "total_processing_time",
    "token_usage",
    "api_latency"
]

def get_google_adk_config() -> Dict[str, Any]:
    """
    Get Google ADK configuration settings.
    
    :return: Dictionary with Google ADK configuration
    """
    return {
        "model_name": GOOGLE_ADK_MODEL,
        "max_tokens": GOOGLE_ADK_MAX_TOKENS,
        "temperature": GOOGLE_ADK_TEMPERATURE,
        "agent_name": ADK_AGENT_NAME,
        "agent_description": ADK_AGENT_DESCRIPTION,
        "artifact_service_type": ADK_ARTIFACT_SERVICE_TYPE,
        "memory_service_type": ADK_MEMORY_SERVICE_TYPE,
        "session_service_type": ADK_SESSION_SERVICE_TYPE
    }

def get_strategy_config() -> Dict[str, Any]:
    """
    Get strategy generation configuration settings.
    
    :return: Dictionary with strategy generation configuration
    """
    return {
        "max_retries": STRATEGY_MAX_RETRIES,
        "retry_delay": STRATEGY_RETRY_DELAY,
        "max_research_length": MAX_RESEARCH_CONTENT_LENGTH,
        "max_strategy_length": MAX_STRATEGY_LENGTH,
        "default_prompt_name": DEFAULT_STRATEGY_PROMPT_NAME
    }

def validate_configuration() -> bool:
    """
    Validate that all required configuration is present.
    
    :return: True if configuration is valid, False otherwise
    """
    try:
        # Check if Google ADK is available
        from google.adk.agents import LlmAgent
        from google.adk.models import Model
        from google.adk.tools import BaseTool
        
        # Check if database configuration is present
        if not settings.DATABASE_URL:
            print("ERROR: DATABASE_URL is required in environment variables")
            return False
        
        # Check if Google API key is present (for ADK)
        if not settings.GOOGLE_API_KEY:
            print("ERROR: GOOGLE_API_KEY is required in environment variables")
            return False
        
        return True
        
    except ImportError:
        print("ERROR: Google ADK is required. Install with: pip install google-adk")
        return False
    except Exception as e:
        print(f"ERROR: Configuration validation failed: {str(e)}")
        return False
