"""
Configuration for the Strategy Generator Agent using Anthropic Claude API.
"""

from typing import Dict, Any
from marbix.core.config import settings


def get_anthropic_config() -> Dict[str, Any]:
    """
    Get Anthropic Claude configuration settings from environment.
    
    Returns:
        Dictionary with Anthropic configuration
    """
    return {
        "model_name": getattr(settings, 'STRATEGY_MODEL_NAME', 'claude-sonnet-4-20250514'),
        "max_tokens": getattr(settings, 'STRATEGY_MAX_TOKENS', 6000),
        "temperature": getattr(settings, 'STRATEGY_TEMPERATURE', 0.3),
        "api_key": getattr(settings, 'ANTHROPIC_API_KEY', None),
        "base_url": "https://api.anthropic.com/v1/messages",
        "timeout": getattr(settings, 'STRATEGY_TIMEOUT', 300),
    }


def validate_configuration() -> bool:
    """
    Validate that all required configuration is present.
    
    Returns:
        True if configuration is valid, False otherwise
    """
    try:
        # Check for required environment variables
        if not getattr(settings, 'ANTHROPIC_API_KEY', None):
            return False
        
        if not getattr(settings, 'DATABASE_URL', None):
            return False
        
        return True
        
    except Exception:
        return False


def get_model_config() -> Dict[str, Any]:
    """
    Get model-specific configuration.
    
    Returns:
        Dictionary with model configuration
    """
    return {
        "claude-sonnet-4-20250514": {
            "max_tokens": 6000,
            "temperature": 0.3,
            "anthropic_version": "2023-06-01"
        },

        "claude-3-5-haiku-20241022": {
            "max_tokens": 4000,
            "temperature": 0.3,
            "anthropic_version": "2023-06-01"
        },
        "claude-3-opus-20240229": {
            "max_tokens": 8000,
            "temperature": 0.3,
            "anthropic_version": "2023-06-01"
        }
    }