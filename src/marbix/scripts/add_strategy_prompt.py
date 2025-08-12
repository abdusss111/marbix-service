#!/usr/bin/env python3
"""
Script to add the marketing strategy generator prompt to the database.

This prompt is required for the strategy generator agent to function properly.
Run this script after setting up the database and running migrations.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from marbix.db.session import get_db
from marbix.crud.prompt import create_prompt, get_prompt_by_name
from marbix.schemas.prompt import PromptCreate

# Marketing Strategy Generator Prompt
STRATEGY_PROMPT_DATA = {
    "name": "marketing_strategy_generator",
    "description": "Generate comprehensive marketing strategies based on market research output",
    "content": """Based on the market research provided, create a comprehensive marketing strategy:

🎯 BUSINESS OVERVIEW:
• Business Type: {business_type}
• Business Goal: {business_goal}
• Product/Service: {product_description}
• Target Audience: {target_audience}
• Location: {location}
• Company Name: {company_name}
• Promotion Budget: {promotion_budget}
• Team Budget: {team_budget}

📊 MARKET RESEARCH INSIGHTS:
{research_content}

📋 CREATE A COMPREHENSIVE MARKETING STRATEGY:

## 1. EXECUTIVE SUMMARY
• Strategic overview and key recommendations
• Expected outcomes and success metrics
• Investment summary and ROI projections
• Timeline for implementation

## 2. MARKET OPPORTUNITY ANALYSIS
• Key opportunities identified from research
• Competitive positioning and differentiation
• Market entry strategy and timing
• Risk assessment and mitigation

## 3. TARGET AUDIENCE STRATEGY
• Detailed customer personas and segments
• Customer journey mapping and touchpoints
• Messaging framework and value propositions
• Customer acquisition and retention strategies

## 4. MARKETING MIX STRATEGY (4Ps)
• Product positioning and features
• Pricing strategy and competitive analysis
• Distribution channels and partnerships
• Promotional tactics and campaigns

## 5. DIGITAL MARKETING PLAN
• Website strategy and SEO optimization
• Social media approach and content calendar
• Content marketing plan and thought leadership
• Paid advertising strategy (PPC, social ads)
• Email marketing and automation

## 6. IMPLEMENTATION ROADMAP
• 30-day quick wins and immediate actions
• 90-day milestones and key deliverables
• 6-month strategic goals and KPIs
• Resource requirements and team structure
• Budget allocation by quarter

## 7. BUDGET ALLOCATION & ROI
• Channel budget breakdown and priorities
• Cost-per-acquisition targets by channel
• ROI projections and break-even analysis
• Performance metrics and tracking

## 8. SUCCESS METRICS & KPIs
• Key performance indicators by objective
• Measurement framework and tools
• Reporting schedule and dashboards
• A/B testing strategy for optimization

## 9. RISK MANAGEMENT
• Potential challenges and obstacles
• Contingency plans and alternatives
• Market volatility considerations
• Resource backup plans

## 10. NEXT STEPS & RECOMMENDATIONS
• Immediate action items (next 7 days)
• Priority order for implementation
• Success criteria for each phase
• Regular review and adjustment schedule

Make all recommendations specific, actionable, and appropriate for the given budget constraints. 
Focus on practical implementation steps that can be executed immediately.
Ensure the strategy is data-driven and based on the research insights provided.""",
    "category": "marketing_strategy",
    "tags": ["marketing", "strategy", "planning", "research", "claude", "sonnet"],
    "is_active": True
}

def add_strategy_prompt():
    """Add the marketing strategy generator prompt to the database."""
    print("Adding marketing strategy generator prompt to database...")
    
    # Get database session
    db = next(get_db())
    
    try:
        # Check if prompt already exists
        existing_prompt = get_prompt_by_name(db, STRATEGY_PROMPT_DATA["name"])
        
        if existing_prompt:
            print(f"Prompt '{STRATEGY_PROMPT_DATA['name']}' already exists, skipping...")
            return
        
        # Create prompt
        prompt_create = PromptCreate(**STRATEGY_PROMPT_DATA)
        created_prompt = create_prompt(db, prompt_create)
        
        print(f"Successfully created prompt: {created_prompt.name} (ID: {created_prompt.id})")
        print(f"Category: {created_prompt.category}")
        print(f"Tags: {created_prompt.tags}")
        print(f"Active: {created_prompt.is_active}")
        
    except Exception as e:
        print(f"Error adding strategy prompt: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    add_strategy_prompt()
