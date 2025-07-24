import openai
import json
import asyncio
from typing import Dict, List, Optional
import logging
from datetime import datetime

from marbix.core.config import settings

logger = logging.getLogger(__name__)

class ContentFilterService:
    """Service for content moderation using GPT-based filtering"""
    
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Kazakhstan prohibited business topics (based on OLX.kz rules)
        self.prohibited_topics = [
            # 1. Legislation and Legal Issues
            "Weapons (firearms, cold weapons, pneumatic, signal weapons, crossbows, bows, accessories)",
            "Military vehicles and combat equipment", 
            "Confiscated and contraband goods",
            "Body armor, bulletproof vests, protective helmets, bulletproof shields",
            "Political parties, public organizations and funds sales",
            "Nazi symbolism items",
            "Precious metals and stones trading (unprocessed)",
            "Gambling services and betting systems",
            "Religious literature and materials",
            
            # 2. Beauty and Health
            "Medical products and pharmaceuticals without licensing",
            "Prescription drugs, steroids, anabolics, viagra",
            "Human organs and donor services (blood, sperm trading)",
            "Surrogate motherhood services, breast milk",
            
            # 3. Tobacco, Alcohol, Drugs
            "Alcoholic beverages sales",
            "Tobacco products (including heated tobacco, hookah, e-cigarettes)",
            "Moonshine equipment and ethyl alcohol products",
            "Narcotic and psychotropic substances",
            "Hallucinogenic plants, mushrooms and derivatives",
            "Cannabis seeds and drug preparation ingredients",
            
            # 4. Flora and Fauna
            "Endangered species from Red Book",
            "Wild-caught animals and parts",
            "Poaching equipment (electric fishing rods, nets, traps)",
            "Animals for baiting or testing purposes",
            "Dog meat/fat sales or animal cruelty services",
            
            # 5. Financial Services
            "Suspicious financial services and quick loans",
            "Pyramid schemes and multi-level marketing (MLM)",
            "Foreign currency trading (except numismatic)",
            "Investment fraud and fake financial assistance",
            "Fake money and postal stamps",
            "Securities belonging to third parties",
            "Mobile phone credit transfer schemes",
            
            # 6. Intellectual Property
            "Pirated software installation and sales",
            "Illegal copies of movies, music, games",
            "Spam databases and unauthorized mailing services",
            "State, banking or commercial secrets",
            "Social media accounts and messaging accounts sales",
            
            # 7. Privacy and Human Rights
            "Private detective and surveillance services",
            "Materials violating privacy and defaming individuals",
            "Discrimination based on race, religion, gender",
            "Violence propaganda and hate speech",
            "Personal data databases",
            
            # 8. Dating and Relationships
            "Dating services and relationship platforms",
            "Sex services, prostitution, intimate services",
            "Erotic massage and adult entertainment",
            "Pornography and erotic content",
            "Strip shows and erotic dance services",
            
            # 9. Employment
            "Suspicious job offers without clear employer details",
            "Overseas nightclub work, webcam modeling",
            "Escort services and swinger club employment",
            "Home assembly scams and passive income schemes",
            
            # 10. Special Technical Equipment
            "Surveillance and wiretapping equipment",
            "Anti-radar devices and law enforcement equipment", 
            "Self-defense weapons (stun guns, gas canisters, rubber bullets)",
            "Explosive and pyrotechnic materials",
            "VIN code modification services",
            "Odometer tampering services",
            "Universal keys and lock-picking tools",
            
            # 11. Education
            "Ready-made diplomas, thesis, coursework",
            "Cheating devices and exam aids",
            
            # 12. Advertising
            "Pure promotional content without actual products",
            "Promo codes and referral program links",
            
            # 13. Awards and Documents
            "Government awards, medals, certificates",
            "Identity documents, passports, licenses",
            "Official forms and strict reporting documents",
            
            # 14. Other Prohibited Items
            "Expired food products",
            "Occult services (fortune telling, magic, witchcraft, healing)",
            "Information real estate agencies",
            "Empty boxes, testers without actual products",
            "Non-existent goods (mythical creatures, souls, karma)"
        ]
    
    def _create_system_prompt(self) -> str:
        """Create system prompt with prohibited topics"""
        prohibited_list = "\n".join([f"- {topic}" for topic in self.prohibited_topics])
        
        return f"""You are a content moderation system for a marketing strategy platform in Kazakhstan. 

Your job is to analyze business descriptions and determine if they involve prohibited topics based on Kazakhstan legislation and platform policies.

PROHIBITED BUSINESS TYPES AND ACTIVITIES:
{prohibited_list}

MODERATION GUIDELINES:
1. Analyze the business description thoroughly for any direct or indirect connection to prohibited topics
2. Consider the business intent, target audience, and potential legal/social harm
3. Be strict with clearly prohibited categories but allow legitimate consulting/educational services about these topics
4. Consider cultural and legal context of Kazakhstan
5. Look for hidden meanings or euphemisms that might disguise prohibited activities

RESPONSE FORMAT (JSON only):
{{
    "is_allowed": true/false,
    "violated_topics": ["specific topic categories"] or [],
    "reason": "brief explanation why blocked/allowed",
    "confidence": 0.0-1.0,
    "risk_level": "low/medium/high"
}}

SPECIAL CONSIDERATIONS:
- Educational/consulting services ABOUT these topics may be allowed if clearly legitimate
- Business selling TO prohibited industries (not the prohibited activity itself) may be allowed
- Consider if the business could indirectly facilitate prohibited activities
- Be extra strict with anything involving minors, weapons, drugs, or financial fraud
- Return ONLY valid JSON, no additional text"""

    async def check_content(self, business_description: str) -> Dict:
        """
        Check if business content violates policies
        Returns analysis results
        """
        try:
            logger.info(f"Checking content for violations: {business_description[:100]}...")
            
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # Fast and cost-effective
                messages=[
                    {"role": "system", "content": self._create_system_prompt()},
                    {"role": "user", "content": f"Analyze this business description:\n\n{business_description}"}
                ],
                temperature=0.1,  # Low temperature for consistent results
                max_tokens=300,
                timeout=30.0
            )
            
            content = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                result = json.loads(content)
                filter_result = {
                    "success": True,
                    "is_allowed": result.get("is_allowed", False),
                    "violated_topics": result.get("violated_topics", []),
                    "reason": result.get("reason", ""),
                    "confidence": result.get("confidence", 0.0),
                    "risk_level": result.get("risk_level", "unknown"),
                    "raw_response": content,
                    "checked_at": datetime.utcnow()
                }
                
                logger.info(f"Content check result: {'ALLOWED' if filter_result['is_allowed'] else 'BLOCKED'}")
                if not filter_result['is_allowed']:
                    logger.warning(f"Blocked content - Topics: {filter_result['violated_topics']}, Reason: {filter_result['reason']}")
                
                return filter_result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse GPT response as JSON: {content}")
                return {
                    "success": False,
                    "error": "Invalid JSON response from GPT",
                    "raw_response": content,
                    "is_allowed": False,  # Fail safe
                    "checked_at": datetime.utcnow()
                }
                
        except asyncio.TimeoutError:
            logger.error("Content check timeout")
            return {
                "success": False,
                "error": "Content check timeout",
                "is_allowed": False,
                "checked_at": datetime.utcnow()
            }
        except Exception as e:
            logger.error(f"Content check error: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "is_allowed": False,
                "checked_at": datetime.utcnow()
            }

    async def check_business_request(self, business_data: Dict) -> Dict:
        """
        Check business request data for prohibited content
        Combines multiple fields into comprehensive check
        """
        try:
            # Combine relevant business fields
            business_text = f"""
Business Type: {business_data.get('business_type', '')}
Business Goal: {business_data.get('business_goal', '')}
Product/Service Description: {business_data.get('product_data', '')}
Target Audience: {business_data.get('target_audience_info', '')}
Current Business Activities: {business_data.get('current_volume', '')}
Planned Actions: {business_data.get('actions', '')}
Competitors: {business_data.get('competitors', '')}
Location: {business_data.get('location', '')}
            """.strip()
            
            logger.info(f"Checking business request for user business type: {business_data.get('business_type', 'unknown')}")
            
            return await self.check_content(business_text)
            
        except Exception as e:
            logger.error(f"Error checking business request: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to check business request: {str(e)}",
                "is_allowed": False,
                "checked_at": datetime.utcnow()
            }

    async def bulk_check_content(self, content_list: List[str]) -> List[Dict]:
        """
        Check multiple content pieces in parallel
        """
        try:
            tasks = [self.check_content(content) for content in content_list]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle any exceptions in results
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Bulk check error for item {i}: {str(result)}")
                    processed_results.append({
                        "success": False,
                        "error": str(result),
                        "is_allowed": False,
                        "checked_at": datetime.utcnow()
                    })
                else:
                    processed_results.append(result)
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Bulk content check error: {str(e)}")
            return [{
                "success": False,
                "error": str(e),
                "is_allowed": False,
                "checked_at": datetime.utcnow()
            } for _ in content_list]

    def get_prohibited_topics(self) -> List[str]:
        """Get list of prohibited topics"""
        return self.prohibited_topics.copy()

    async def health_check(self) -> Dict:
        """
        Health check for the content filter service
        """
        try:
            # Test with simple safe content
            test_result = await self.check_content("Digital marketing consulting for small businesses")
            
            return {
                "status": "healthy" if test_result.get("success", False) else "unhealthy",
                "service": "content_filter",
                "last_check": datetime.utcnow(),
                "test_passed": test_result.get("success", False)
            }
        except Exception as e:
            logger.error(f"Content filter health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "service": "content_filter",
                "last_check": datetime.utcnow(),
                "error": str(e),
                "test_passed": False
            }

# Global instance
content_filter_service = ContentFilterService()