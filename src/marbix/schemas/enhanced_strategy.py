# src/marbix/schemas/enhanced_strategy.py

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

class EnhancementStatus(str, Enum):
    """Status of strategy enhancement"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    PARTIAL = "partial"

class EnhancementPromptType(str, Enum):
    """Types of enhancement prompts mapping to strategy sections"""
    MARKET_ANALYSIS = "market_analysis"      # Analys_rynka
    DRIVERS = "drivers"                      # Drivers  
    COMPETITORS = "competitors"              # Competitors
    CUSTOMER_JOURNEY = "customer_journey"    # Customer_Journey
    PRODUCT = "product"                      # Product
    COMMUNICATION = "communication"          # Communication
    TEAM = "team"                           # TEAM
    METRICS = "metrics"                     # Metrics
    NEXT_STEPS = "next_steps"               # Next_Steps

class EnhancementRequest(BaseModel):
    """Request to enhance a strategy"""
    pass  # No additional parameters needed - strategy ID comes from URL

class EnhancementResponse(BaseModel):
    """Response when enhancement is initiated"""
    enhancement_id: str
    original_strategy_id: str
    status: EnhancementStatus
    message: str
    created_at: datetime

class EnhancedStrategyResponse(BaseModel):
    """Full enhanced strategy response"""
    id: str
    original_strategy_id: str
    user_id: str
    status: EnhancementStatus
    error: Optional[str] = None
    
    # 9 Enhanced sections
    Analys_rynka: Optional[str] = None      # Market Analysis
    Drivers: Optional[str] = None           # Market Drivers  
    Competitors: Optional[str] = None       # Competitor Analysis
    Customer_Journey: Optional[str] = None  # Customer Journey
    Product: Optional[str] = None           # Product Analysis
    Communication: Optional[str] = None     # Communication Strategy
    TEAM: Optional[str] = None              # Team Structure
    Metrics: Optional[str] = None           # Metrics & Control
    Next_Steps: Optional[str] = None        # Next Steps
    
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SectionEnhancementResult(BaseModel):
    """Result of enhancing a single section"""
    section_name: str
    prompt_type: EnhancementPromptType
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
