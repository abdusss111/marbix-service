"""
Strategy Generator Agent Package using Google ADK.

This package contains the strategy generator agent that creates marketing strategies
using Google Agent Development Kit (ADK), based on research output from the researcher agent.
"""

from .strategy_agent import (
    StrategyGeneratorAgent,
    StrategyGenerationTool,
    generate_strategy_async,
    example_worker_function
)
from .config import (
    get_google_adk_config,
    get_strategy_config,
    validate_configuration
)

__all__ = [
    "StrategyGeneratorAgent",
    "StrategyGenerationTool",
    "generate_strategy_async", 
    "example_worker_function",
    "get_google_adk_config",
    "get_strategy_config",
    "validate_configuration"
]

__version__ = "1.0.0"
__author__ = "Marbix Team"
__description__ = "Strategy Generator Agent using Google Agent Development Kit (ADK)"
