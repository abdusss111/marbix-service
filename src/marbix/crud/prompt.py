from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from marbix.models.prompt import Prompt
from marbix.schemas.prompt import PromptCreate, PromptUpdate
from typing import List, Optional
from datetime import datetime

def create_prompt(db: Session, prompt_data: PromptCreate, created_by: Optional[str] = None) -> Prompt:
    """
    Create a new prompt in the database.
    
    :param db: SQLAlchemy Session
    :param prompt_data: Prompt creation data
    :param created_by: ID of the user creating the prompt
    :return: Created Prompt instance
    """
    db_prompt = Prompt(
        **prompt_data.model_dump(),
        created_by=created_by
    )
    db.add(db_prompt)
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def get_prompt_by_id(db: Session, prompt_id: str) -> Optional[Prompt]:
    """
    Fetch a prompt by its unique ID.
    
    :param db: SQLAlchemy Session
    :param prompt_id: The prompt's unique identifier
    :return: Prompt instance or None if not found
    """
    return db.query(Prompt).filter(Prompt.id == prompt_id).first()

def get_prompt_by_name(db: Session, name: str) -> Optional[Prompt]:
    """
    Fetch a prompt by its name.
    
    :param db: SQLAlchemy Session
    :param name: The prompt's name
    :return: Prompt instance or None if not found
    """
    return db.query(Prompt).filter(Prompt.name == name).first()

def get_prompts(
    db: Session, 
    skip: int = 0, 
    limit: int = 100,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None
) -> List[Prompt]:
    """
    Fetch prompts with optional filtering and pagination.
    
    :param db: SQLAlchemy Session
    :param skip: Number of records to skip
    :param limit: Maximum number of records to return
    :param category: Filter by category
    :param is_active: Filter by active status
    :param search: Search in name, description, and content
    :return: List of Prompt instances
    """
    query = db.query(Prompt)
    
    # Apply filters
    if category:
        query = query.filter(Prompt.category == category)
    
    if is_active is not None:
        query = query.filter(Prompt.is_active == is_active)
    
    if search:
        search_filter = or_(
            Prompt.name.ilike(f"%{search}%"),
            Prompt.description.ilike(f"%{search}%"),
            Prompt.content.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    return query.order_by(Prompt.created_at.desc()).offset(skip).limit(limit).all()

def update_prompt(db: Session, prompt_id: str, prompt_data: PromptUpdate) -> Optional[Prompt]:
    """
    Update an existing prompt.
    
    :param db: SQLAlchemy Session
    :param prompt_id: The prompt's unique identifier
    :param prompt_data: Updated prompt data
    :return: Updated Prompt instance or None if not found
    """
    db_prompt = get_prompt_by_id(db, prompt_id)
    if not db_prompt:
        return None
    
    update_data = prompt_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_prompt, field, value)
    
    db_prompt.updated_at = datetime.now()
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def delete_prompt(db: Session, prompt_id: str) -> bool:
    """
    Delete a prompt from the database.
    
    :param db: SQLAlchemy Session
    :param prompt_id: The prompt's unique identifier
    :return: True if deleted, False if not found
    """
    db_prompt = get_prompt_by_id(db, prompt_id)
    if not db_prompt:
        return False
    
    db.delete(db_prompt)
    db.commit()
    return True

def increment_prompt_usage(db: Session, prompt_id: str) -> Optional[Prompt]:
    """
    Increment the usage count and update last_used_at for a prompt.
    
    :param db: SQLAlchemy Session
    :param prompt_id: The prompt's unique identifier
    :return: Updated Prompt instance or None if not found
    """
    db_prompt = get_prompt_by_id(db, prompt_id)
    if not db_prompt:
        return None
    
    db_prompt.usage_count += 1
    db_prompt.last_used_at = datetime.now()
    db.commit()
    db.refresh(db_prompt)
    return db_prompt

def get_prompts_by_category(db: Session, category: str) -> List[Prompt]:
    """
    Fetch all prompts in a specific category.
    
    :param db: SQLAlchemy Session
    :param category: Category to filter by
    :return: List of Prompt instances
    """
    return db.query(Prompt).filter(
        and_(Prompt.category == category, Prompt.is_active == True)
    ).order_by(Prompt.name).all()

def get_active_prompts(db: Session) -> List[Prompt]:
    """
    Fetch all active prompts.
    
    :param db: SQLAlchemy Session
    :return: List of active Prompt instances
    """
    return db.query(Prompt).filter(Prompt.is_active == True).order_by(Prompt.name).all()
