"""
Configuration for the Strategy Generator Agent using Google ADK.
"""

from typing import Dict, Any
from marbix.core.config import settings


def get_google_adk_config() -> Dict[str, Any]:
    """
    Get Google ADK configuration settings from environment.
    
    Returns:
        Dictionary with Google ADK configuration
    """
    return {
        "model_name": getattr(settings, 'STRATEGY_MODEL_NAME', 'gemini-2.0-flash'),
        "max_tokens": getattr(settings, 'STRATEGY_MAX_TOKENS', 6000),
        "temperature": getattr(settings, 'STRATEGY_TEMPERATURE', 0.3),
    }


def validate_configuration() -> bool:
    """
    Validate that all required configuration is present.
    
    Returns:
        True if configuration is valid, False otherwise
    """
    try:
        from google.adk.agents import Agent
        from google.adk.tools import BaseTool
        
        if not settings.DATABASE_URL:
            return False
        
        return True
        
    except ImportError:
        return False
    except Exception:
        return False