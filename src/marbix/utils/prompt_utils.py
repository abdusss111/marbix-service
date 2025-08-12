from sqlalchemy.orm import Session
from marbix.crud.prompt import get_prompt_by_name, get_prompt_by_id
from marbix.models.prompt import Prompt
from typing import Optional

def get_prompt_content_by_name(db: Session, prompt_name: str) -> Optional[str]:
    """
    Get prompt content by name. This is a utility function to easily retrieve
    prompt content without hardcoding prompts in your code.
    
    :param db: Database session
    :param prompt_name: Name of the prompt to retrieve
    :return: Prompt content string or None if not found
    """
    prompt = get_prompt_by_name(db, prompt_name)
    if prompt and prompt.is_active:
        return prompt.content
    return None

def get_prompt_content_by_id(db: Session, prompt_id: str) -> Optional[str]:
    """
    Get prompt content by ID.
    
    :param db: Database session
    :param prompt_id: ID of the prompt to retrieve
    :return: Prompt content string or None if not found
    """
    prompt = get_prompt_by_id(db, prompt_id)
    if prompt and prompt.is_active:
        return prompt.content
    return None

def get_prompt_by_name_or_id(db: Session, identifier: str) -> Optional[str]:
    """
    Get prompt content by name or ID. This function tries to find the prompt
    by name first, then by ID if name lookup fails.
    
    :param db: Database session
    :param identifier: Name or ID of the prompt
    :return: Prompt content string or None if not found
    """
    # Try to get by name first
    content = get_prompt_content_by_name(db, identifier)
    if content:
        return content
    
    # If not found by name, try by ID
    return get_prompt_content_by_id(db, identifier)

def format_prompt_with_variables(prompt_content: str, **variables) -> str:
    """
    Format a prompt template with variables. This allows you to use
    placeholders in your prompts and fill them dynamically.
    
    Example:
        prompt_content = "Hello {name}, your balance is {amount}"
        result = format_prompt_with_variables(prompt_content, name="John", amount="$100")
        # Result: "Hello John, your balance is $100"
    
    :param prompt_content: Prompt template with placeholders
    :param variables: Keyword arguments for variable substitution
    :return: Formatted prompt string
    """
    try:
        return prompt_content.format(**variables)
    except KeyError as e:
        raise ValueError(f"Missing required variable in prompt template: {e}")
    except Exception as e:
        raise ValueError(f"Error formatting prompt template: {e}")

def get_formatted_prompt(db: Session, prompt_name: str, **variables) -> Optional[str]:
    """
    Get a prompt by name and format it with variables in one call.
    
    :param db: Database session
    :param prompt_name: Name of the prompt to retrieve
    :param variables: Keyword arguments for variable substitution
    :return: Formatted prompt string or None if not found
    """
    content = get_prompt_content_by_name(db, prompt_name)
    if content and variables:
        return format_prompt_with_variables(content, **variables)
    return content
