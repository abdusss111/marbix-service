"""
Strategy Generator Agent Package using Google ADK.
"""

from .config import (
    get_google_adk_config,
    validate_configuration
)

try:
    from .strategy_agent import (
        StrategyGeneratorAgent,
        StrategyGenerationTool,
        generate_strategy_async
    )
except ImportError:
    class StrategyGeneratorAgent:
        def __init__(self, *args, **kwargs):
            raise ImportError("Google ADK is not available")
    
    class StrategyGenerationTool:
        def __init__(self, *args, **kwargs):
            raise ImportError("Google ADK is not available")
    
    def generate_strategy_async(*args, **kwargs):
        raise ImportError("Google ADK is not available")

__all__ = [
    "StrategyGeneratorAgent",
    "StrategyGenerationTool",
    "generate_strategy_async",
    "get_google_adk_config",
    "validate_configuration"
]

__version__ = "1.0.0"