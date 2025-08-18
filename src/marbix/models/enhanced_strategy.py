# src/marbix/models/enhanced_strategy.py

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum

from marbix.db.base import Base

class EnhancementStatus(str, enum.Enum):
    """Status of strategy enhancement"""
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    ERROR = "error"
    PARTIAL = "partial"

class EnhancementPromptType(str, enum.Enum):
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

class EnhancedStrategy(Base):
    """Enhanced strategy with 9 detailed sections"""
    __tablename__ = "enhanced_strategies"

    id = Column(String, primary_key=True, index=True)
    original_strategy_id = Column(String, ForeignKey("make_requests.request_id"), nullable=False)
    user_id = Column(String, nullable=False)
    
    # Enhancement status
    status = Column(SQLEnum(EnhancementStatus), default=EnhancementStatus.PENDING)
    error = Column(Text, nullable=True)
    
    # 9 Enhanced sections (without PRO_ prefix as requested)
    Analys_rynka = Column(Text, nullable=True)      # Market Analysis
    Drivers = Column(Text, nullable=True)           # Market Drivers  
    Competitors = Column(Text, nullable=True)       # Competitor Analysis
    Customer_Journey = Column(Text, nullable=True)  # Customer Journey
    Product = Column(Text, nullable=True)           # Product Analysis
    Communication = Column(Text, nullable=True)     # Communication Strategy
    TEAM = Column(Text, nullable=True)              # Team Structure
    Metrics = Column(Text, nullable=True)           # Metrics & Control
    Next_Steps = Column(Text, nullable=True)        # Next Steps
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationship to original strategy
    original_strategy = relationship("MakeRequest", back_populates="enhancements")

# Note: Reverse relationship will be defined in MakeRequest model to avoid circular imports
