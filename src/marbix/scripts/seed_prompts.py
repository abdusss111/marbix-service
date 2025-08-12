#!/usr/bin/env python3
"""
Script to seed the database with initial prompts.
Run this script after setting up the database and running migrations.
"""

import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from marbix.db.session import get_db
from marbix.crud.prompt import create_prompt
from marbix.schemas.prompt import PromptCreate

# Sample prompts to seed the database
SAMPLE_PROMPTS = [
    {
        "name": "business_strategy_generator",
        "description": "Generate a comprehensive business strategy based on business type, goals, and constraints",
        "content": """You are a business strategy expert. Based on the following information, create a comprehensive business strategy:

Business Type: {business_type}
Business Goal: {business_goal}
Location: {location}
Promotion Budget: {promotion_budget}
Team Budget: {team_budget}

Please provide:
1. Market Analysis
2. Competitive Strategy
3. Marketing Plan
4. Operational Plan
5. Financial Projections
6. Risk Assessment
7. Implementation Timeline

Make sure the strategy is practical, actionable, and tailored to the specific business context.""",
        "category": "business_strategy",
        "tags": ["business", "strategy", "planning", "marketing"],
        "is_active": True
    },
    {
        "name": "content_optimizer",
        "description": "Optimize content for better engagement and SEO performance",
        "content": """You are a content optimization expert. Please analyze and improve the following content:

Original Content:
{content}

Target Audience: {target_audience}
Content Type: {content_type}
SEO Keywords: {seo_keywords}

Please provide:
1. Improved version with better readability
2. SEO optimization suggestions
3. Engagement enhancement tips
4. Content structure improvements
5. Call-to-action recommendations

Focus on making the content more engaging, SEO-friendly, and aligned with the target audience.""",
        "category": "content_optimization",
        "tags": ["content", "seo", "optimization", "engagement"],
        "is_active": True
    },
    {
        "name": "customer_service_response",
        "description": "Generate professional and helpful customer service responses",
        "content": """You are a customer service representative. Please respond to the following customer inquiry:

Customer Inquiry: {customer_inquiry}
Customer Name: {customer_name}
Issue Type: {issue_type}
Priority Level: {priority_level}

Please provide:
1. Acknowledgment of the customer's concern
2. Professional and empathetic response
3. Clear explanation of the solution
4. Next steps or actions to be taken
5. Contact information for follow-up

Maintain a professional, helpful, and solution-oriented tone throughout the response.""",
        "category": "customer_service",
        "tags": ["customer_service", "communication", "support", "response"],
        "is_active": True
    },
    {
        "name": "data_analysis_report",
        "description": "Generate comprehensive data analysis reports with insights and recommendations",
        "content": """You are a data analyst. Please analyze the following data and create a comprehensive report:

Data Summary: {data_summary}
Key Metrics: {key_metrics}
Time Period: {time_period}
Business Context: {business_context}

Please provide:
1. Executive Summary
2. Key Findings and Insights
3. Data Trends and Patterns
4. Comparative Analysis
5. Recommendations and Action Items
6. Risk Factors and Considerations
7. Next Steps and Follow-up Actions

Present the information in a clear, structured format with actionable insights.""",
        "category": "data_analysis",
        "tags": ["data", "analysis", "report", "insights", "analytics"],
        "is_active": True
    },
    {
        "name": "email_template_generator",
        "description": "Generate professional email templates for various business purposes",
        "content": """You are a business communication expert. Please create a professional email template for:

Email Purpose: {email_purpose}
Recipient Type: {recipient_type}
Tone: {tone}
Key Message: {key_message}
Call to Action: {call_to_action}

Please provide:
1. Subject Line
2. Greeting
3. Opening Paragraph
4. Main Content
5. Closing Paragraph
6. Signature
7. Alternative Versions (if applicable)

Ensure the email is professional, clear, and achieves the intended purpose.""",
        "category": "communication",
        "tags": ["email", "template", "communication", "business"],
        "is_active": True
    }
]

def seed_prompts():
    """Seed the database with sample prompts."""
    print("Starting to seed prompts...")
    
    # Get database session
    db = next(get_db())
    
    try:
        for prompt_data in SAMPLE_PROMPTS:
            # Check if prompt already exists
            from marbix.crud.prompt import get_prompt_by_name
            existing_prompt = get_prompt_by_name(db, prompt_data["name"])
            
            if existing_prompt:
                print(f"Prompt '{prompt_data['name']}' already exists, skipping...")
                continue
            
            # Create prompt
            prompt_create = PromptCreate(**prompt_data)
            created_prompt = create_prompt(db, prompt_create)
            print(f"Created prompt: {created_prompt.name} (ID: {created_prompt.id})")
        
        print("Prompt seeding completed successfully!")
        
    except Exception as e:
        print(f"Error seeding prompts: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_prompts()
