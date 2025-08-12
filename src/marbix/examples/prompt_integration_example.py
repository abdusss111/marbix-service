"""
Example: How to integrate the prompt management system into your existing code.

This file demonstrates the before/after approach of replacing hardcoded prompts
with database-driven prompts.
"""

from marbix.utils.prompt_utils import get_prompt_content_by_name, get_formatted_prompt
from sqlalchemy.orm import Session

# ============================================================================
# BEFORE: Hardcoded prompts in your code
# ============================================================================

def generate_business_strategy_hardcoded(business_data):
    """OLD WAY: Hardcoded prompt"""
    
    # This is what you want to avoid - hardcoded prompts scattered throughout code
    prompt = """You are a business strategy expert. Based on the following information, create a comprehensive business strategy:

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

Make sure the strategy is practical, actionable, and tailored to the specific business context."""

    # Format the prompt with variables
    formatted_prompt = prompt.format(**business_data)
    
    # Use the prompt (e.g., with an AI model)
    # response = ai_model.generate(formatted_prompt)
    
    return formatted_prompt

def generate_email_template_hardcoded(email_data):
    """OLD WAY: Another hardcoded prompt"""
    
    prompt = """You are a business communication expert. Please create a professional email template for:

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

Ensure the email is professional, clear, and achieves the intended purpose."""

    formatted_prompt = prompt.format(**email_data)
    return formatted_prompt

# ============================================================================
# AFTER: Database-driven prompts
# ============================================================================

def generate_business_strategy_dynamic(db: Session, business_data):
    """NEW WAY: Database-driven prompt"""
    
    try:
        # Get the prompt from the database
        prompt = get_formatted_prompt(
            db,
            "business_strategy_generator",
            **business_data
        )
        
        if not prompt:
            raise ValueError("Business strategy prompt not found in database")
        
        # Use the prompt (e.g., with an AI model)
        # response = ai_model.generate(prompt)
        
        return prompt
        
    except Exception as e:
        # Fallback to a basic prompt if database lookup fails
        print(f"Warning: Could not retrieve prompt from database: {e}")
        return f"Generate a business strategy for {business_data.get('business_type', 'business')}"

def generate_email_template_dynamic(db: Session, email_data):
    """NEW WAY: Database-driven prompt"""
    
    try:
        prompt = get_formatted_prompt(
            db,
            "email_template_generator",
            **email_data
        )
        
        if not prompt:
            raise ValueError("Email template prompt not found in database")
        
        return prompt
        
    except Exception as e:
        print(f"Warning: Could not retrieve prompt from database: {e}")
        return f"Generate an email for {email_data.get('email_purpose', 'business communication')}"

# ============================================================================
# Advanced Usage Examples
# ============================================================================

def get_prompt_with_fallback(db: Session, prompt_name: str, fallback_content: str = None):
    """
    Get a prompt with a fallback if the database lookup fails.
    This is useful for critical prompts that must always work.
    """
    
    prompt = get_prompt_content_by_name(db, prompt_name)
    
    if prompt:
        return prompt
    
    if fallback_content:
        print(f"Warning: Using fallback prompt for '{prompt_name}'")
        return fallback_content
    
    raise ValueError(f"Prompt '{prompt_name}' not found and no fallback provided")

def batch_prompt_processing(db: Session, prompt_names: list, variables: dict):
    """
    Process multiple prompts in batch.
    Useful when you need to generate multiple types of content.
    """
    
    results = {}
    
    for prompt_name in prompt_names:
        try:
            prompt = get_formatted_prompt(db, prompt_name, **variables)
            results[prompt_name] = prompt
        except Exception as e:
            results[prompt_name] = f"Error: {str(e)}"
    
    return results

# ============================================================================
# Integration with Existing Services
# ============================================================================

class BusinessService:
    """Example service class showing prompt integration"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_business_plan(self, business_data: dict):
        """Create a business plan using database-driven prompts"""
        
        # Get the strategy prompt
        strategy_prompt = get_formatted_prompt(
            self.db,
            "business_strategy_generator",
            **business_data
        )
        
        if not strategy_prompt:
            raise ValueError("Business strategy prompt not found")
        
        # Use the prompt with your AI model
        # strategy_response = self.ai_model.generate(strategy_prompt)
        
        # You could also get additional prompts for different sections
        # marketing_prompt = get_formatted_prompt(self.db, "marketing_plan_generator", **business_data)
        # financial_prompt = get_formatted_prompt(self.db, "financial_plan_generator", **business_data)
        
        return {
            "strategy_prompt": strategy_prompt,
            "business_data": business_data,
            # "strategy_response": strategy_response,
            # Add other sections as needed
        }

# ============================================================================
# Usage Examples
# ============================================================================

def example_usage():
    """Example of how to use the prompt system"""
    
    # This would be your actual database session
    # db = get_db()
    
    # Example business data
    business_data = {
        "business_type": "Restaurant",
        "business_goal": "Increase revenue by 30%",
        "location": "Downtown",
        "promotion_budget": "$5000",
        "team_budget": "$10000"
    }
    
    # Example email data
    email_data = {
        "email_purpose": "Customer Onboarding",
        "recipient_type": "New Customer",
        "tone": "Professional and Welcoming",
        "key_message": "Welcome to our service!",
        "call_to_action": "Schedule your first consultation"
    }
    
    print("=== BEFORE: Hardcoded Prompts ===")
    print(generate_business_strategy_hardcoded(business_data))
    print("\n" + "="*50 + "\n")
    
    print("=== AFTER: Database-Driven Prompts ===")
    # In real usage, you would pass the actual database session
    # print(generate_business_strategy_dynamic(db, business_data))
    print("(Database session required for actual usage)")
    
    print("\n=== Batch Processing Example ===")
    prompt_names = ["business_strategy_generator", "email_template_generator"]
    # results = batch_prompt_processing(db, prompt_names, business_data)
    print(f"Would process {len(prompt_names)} prompts in batch")

if __name__ == "__main__":
    example_usage()
