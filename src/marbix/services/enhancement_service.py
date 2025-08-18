# src/marbix/services/enhancement_service.py

import logging
import uuid
import re
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from marbix.models.enhanced_strategy import EnhancedStrategy, EnhancementStatus, EnhancementPromptType
from marbix.models.make_request import MakeRequest
from marbix.schemas.enhanced_strategy import SectionEnhancementResult
from marbix.utils.prompt_utils import get_prompt_by_name
from marbix.agents.strategy_generator.strategy_agent import generate_strategy_async

logger = logging.getLogger(__name__)

class EnhancementService:
    """Service for enhancing strategies with 9 detailed sections"""

    @staticmethod
    def create_enhancement_record(original_strategy_id: str, user_id: str, db: Session) -> EnhancedStrategy:
        """Create initial enhancement record"""
        enhancement_id = str(uuid.uuid4())
        
        enhancement = EnhancedStrategy(
            id=enhancement_id,
            original_strategy_id=original_strategy_id,
            user_id=user_id,
            status=EnhancementStatus.PENDING
        )
        
        db.add(enhancement)
        db.commit()
        db.refresh(enhancement)
        
        logger.info(f"Created enhancement record {enhancement_id} for strategy {original_strategy_id}")
        return enhancement

    @staticmethod
    def get_enhancement_by_id(enhancement_id: str, db: Session) -> Optional[EnhancedStrategy]:
        """Get enhancement by ID"""
        return db.query(EnhancedStrategy).filter(EnhancedStrategy.id == enhancement_id).first()

    @staticmethod
    def get_strategy_by_id(strategy_id: str, db: Session) -> Optional[MakeRequest]:
        """Get original strategy by ID"""
        return db.query(MakeRequest).filter(MakeRequest.request_id == strategy_id).first()

    @staticmethod
    def update_enhancement_status(enhancement_id: str, status: EnhancementStatus, db: Session, error: str = None):
        """Update enhancement status"""
        enhancement = db.query(EnhancedStrategy).filter(EnhancedStrategy.id == enhancement_id).first()
        if enhancement:
            enhancement.status = status
            enhancement.updated_at = datetime.utcnow()
            if error:
                enhancement.error = error
            if status == EnhancementStatus.COMPLETED:
                enhancement.completed_at = datetime.utcnow()
            db.commit()
            logger.info(f"Updated enhancement {enhancement_id} status to {status}")

    @staticmethod
    def extract_strategy_section(strategy_text: str, section_number: int) -> str:
        """
        Extract specific section from strategy text based on section number.
        Sections are numbered 1-9 as per the strategy format.
        """
        try:
            # Define section patterns based on the strategy format
            section_patterns = {
                1: r"1\.\s*Анализ Рынка.*?(?=2\.|$)",
                2: r"2\.\s*Драйверы Рынка.*?(?=3\.|$)", 
                3: r"3\.\s*Анализ Конкурентов.*?(?=4\.|$)",
                4: r"4\.\s*Customer Journey.*?(?=5\.|$)",
                5: r"5\.\s*Анализ Продукта.*?(?=6\.|$)",
                6: r"6\.\s*Коммуникационная Стратегия.*?(?=7\.|$)",
                7: r"7\.\s*Команда.*?(?=8\.|$)",
                8: r"8\.\s*Метрики и Контроль.*?(?=9\.|$)",
                9: r"9\.\s*Следующие Шаги.*?$"
            }
            
            pattern = section_patterns.get(section_number)
            if not pattern:
                return ""
                
            match = re.search(pattern, strategy_text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(0).strip()
            else:
                logger.warning(f"Could not extract section {section_number} from strategy")
                return ""
                
        except Exception as e:
            logger.error(f"Error extracting section {section_number}: {e}")
            return ""

    @staticmethod
    async def enhance_strategy_section(
        enhancement_id: str,
        section_name: str,
        prompt_type: EnhancementPromptType,
        original_strategy: str,
        db: Session
    ) -> SectionEnhancementResult:
        """
        Enhance a specific section using AI generation.
        
        Flow:
        1. Get prompt from database by prompt_type name
        2. Extract the relevant section from original strategy
        3. Use full strategy as system prompt
        4. Call generate_strategy_async with section content + prompt
        5. Return enhanced section content
        """
        try:
            logger.info(f"Enhancing section {section_name} with prompt type {prompt_type}")
            
            # 1. Get prompt from database
            prompt_record = get_prompt_by_name(db, prompt_type.value)
            if not prompt_record:
                error_msg = f"Prompt not found for type: {prompt_type.value}"
                logger.error(error_msg)
                return SectionEnhancementResult(
                    section_name=section_name,
                    prompt_type=prompt_type,
                    success=False,
                    error=error_msg
                )
            
            # 2. Extract relevant section from original strategy
            section_mapping = {
                EnhancementPromptType.MARKET_ANALYSIS: 1,
                EnhancementPromptType.DRIVERS: 2,
                EnhancementPromptType.COMPETITORS: 3,
                EnhancementPromptType.CUSTOMER_JOURNEY: 4,
                EnhancementPromptType.PRODUCT: 5,
                EnhancementPromptType.COMMUNICATION: 6,
                EnhancementPromptType.TEAM: 7,
                EnhancementPromptType.METRICS: 8,
                EnhancementPromptType.NEXT_STEPS: 9
            }
            
            section_number = section_mapping.get(prompt_type)
            if not section_number:
                error_msg = f"Unknown prompt type: {prompt_type}"
                logger.error(error_msg)
                return SectionEnhancementResult(
                    section_name=section_name,
                    prompt_type=prompt_type,
                    success=False,
                    error=error_msg
                )
            
            # Extract current section content
            current_section = EnhancementService.extract_strategy_section(original_strategy, section_number)
            
            # 3. Prepare context for AI generation
            # Use full strategy as system context + current section + enhancement prompt
            system_prompt = f"""You are enhancing a marketing strategy. Here is the full original strategy for context:

{original_strategy}

---

Focus on enhancing this specific section: {current_section}

Follow the enhancement instructions carefully and provide a detailed, improved version of this section."""

            user_message = f"{current_section}\n\n{prompt_record.content}"
            
            # 4. Call strategy generation agent
            fake_business_context = {"enhancement_mode": True}  # Minimal context since we're enhancing
            fake_research_output = user_message  # Use the section + prompt as "research"
            
            result = await generate_strategy_async(
                db=db,
                business_context=fake_business_context,
                research_output=fake_research_output,
                request_id=enhancement_id,
                prompt_name=prompt_type.value,
                system_prompt_override=system_prompt
            )
            
            if result.get("success"):
                enhanced_content = result.get("strategy", "")
                logger.info(f"Successfully enhanced section {section_name} ({len(enhanced_content)} chars)")
                
                return SectionEnhancementResult(
                    section_name=section_name,
                    prompt_type=prompt_type,
                    success=True,
                    content=enhanced_content
                )
            else:
                error_msg = result.get("error", "AI generation failed")
                logger.error(f"AI generation failed for section {section_name}: {error_msg}")
                return SectionEnhancementResult(
                    section_name=section_name,
                    prompt_type=prompt_type,
                    success=False,
                    error=error_msg
                )
                
        except Exception as e:
            error_msg = f"Error enhancing section {section_name}: {str(e)}"
            logger.error(error_msg)
            return SectionEnhancementResult(
                section_name=section_name,
                prompt_type=prompt_type,
                success=False,
                error=error_msg
            )

    @staticmethod
    def save_enhanced_section(
        enhancement_id: str,
        section_name: str,
        content: str,
        db: Session
    ) -> bool:
        """Save enhanced section content to database"""
        try:
            enhancement = db.query(EnhancedStrategy).filter(EnhancedStrategy.id == enhancement_id).first()
            if not enhancement:
                logger.error(f"Enhancement record {enhancement_id} not found")
                return False
            
            # Map section name to database field
            field_mapping = {
                "Analys_rynka": "Analys_rynka",
                "Drivers": "Drivers", 
                "Competitors": "Competitors",
                "Customer_Journey": "Customer_Journey",
                "Product": "Product",
                "Communication": "Communication",
                "TEAM": "TEAM",
                "Metrics": "Metrics",
                "Next_Steps": "Next_Steps"
            }
            
            field_name = field_mapping.get(section_name)
            if not field_name:
                logger.error(f"Unknown section name: {section_name}")
                return False
            
            # Set the field value
            setattr(enhancement, field_name, content)
            enhancement.updated_at = datetime.utcnow()
            
            db.commit()
            logger.info(f"Saved enhanced section {section_name} for enhancement {enhancement_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving enhanced section {section_name}: {e}")
            db.rollback()
            return False

# Global service instance
enhancement_service = EnhancementService()
