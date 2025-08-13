"""
Strategy Generator Agent Package using Anthropic Claude API.
"""

from .config import (
    get_anthropic_config,
    validate_configuration,
    get_model_config
)

try:
    from .strategy_agent import (
        StrategyGeneratorAgent,
        generate_strategy_async
    )
except ImportError:
    class StrategyGeneratorAgent:
        def __init__(self, *args, **kwargs):
            raise ImportError("Strategy generator agent is not available")
    
    def generate_strategy_async(*args, **kwargs):
        raise ImportError("Strategy generator agent is not available")

__all__ = [
    "StrategyGeneratorAgent",
    "generate_strategy_async",
    "get_anthropic_config",
    "validate_configuration",
    "get_model_config"
]

__version__ = "1.0.0"