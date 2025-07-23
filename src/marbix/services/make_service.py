# src/marbix/services/make_service.py
import httpx
import uuid
import asyncio
from typing import Dict, Optional
from datetime import datetime
import logging
from sqlalchemy.orm import Session

from marbix.core.config import settings
from marbix.core.deps import get_db
from marbix.models.make_request import MakeRequest
from marbix.schemas.make_integration import (
    MakeWebhookRequest,
    MakeWebhookPayload,
    ProcessingStatus
)

logger = logging.getLogger(__name__)

class MakeService:
    """Service for handling Make webhook integration with database persistence"""
    
    def __init__(self):
        self.webhook_url = settings.WEBHOOK_URL
        self.api_base_url = settings.API_BASE_URL
        
    async def send_to_make(self, request: MakeWebhookRequest, user_id: str, db: Session) -> ProcessingStatus:
        """Send request to Make webhook and save to database"""
        request_id = str(uuid.uuid4())
        
        # Save to database
        db_request = MakeRequest(
            request_id=request_id,
            user_id=user_id,
            status="processing",
            request_data=request.dict()
        )
        db.add(db_request)
        db.commit()
        
        # Prepare callback URL
        callback_url = f"{self.api_base_url}/api/callback/{request_id}"
        
        # Create payload
        payload = MakeWebhookPayload(
            **request.dict(exclude_none=True),
            callback_url=callback_url,
            request_id=request_id
        )
        
        # Send to Make
        async with httpx.AsyncClient() as client:
            try:
                # Log the payload for debugging
                logger.info(f"Sending to Make webhook: {self.webhook_url}")
                logger.info(f"Payload: {payload.dict()}")
                
                response = await client.post(
                    self.webhook_url,
                    data=payload.json(),  # Send as string
                    timeout=30.0,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                )
                
                if response.status_code != 200:
                    logger.error(f"Make webhook error: {response.status_code} - {response.text}")
                    db_request.status = "error"
                    db_request.error = "Failed to send to Make"
                    db.commit()
                    raise Exception("Failed to send request to processing service")
                
                logger.info(f"Request {request_id} sent to Make successfully")
                
                return ProcessingStatus(
                    request_id=request_id,
                    status="processing",
                    message="Request sent for processing",
                    created_at=db_request.created_at
                )
                
            except httpx.TimeoutException:
                logger.error(f"Timeout sending request {request_id} to Make")
                db_request.status = "error"
                db_request.error = "Timeout"
                db.commit()
                raise
            except Exception as e:
                logger.error(f"Error sending to Make: {str(e)}")
                db_request.status = "error"
                db_request.error = str(e)
                db.commit()
                raise
    
    def update_request_status(self, request_id: str, result: str, sources: str, 
                            status: str = "completed", error: Optional[str] = None,
                            db: Session = None):
        """Update the status of a request in database"""
        request = db.query(MakeRequest).filter(MakeRequest.request_id == request_id).first()
        
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        request.sources = sources
        request.status = status
        request.result = result
        request.completed_at = datetime.utcnow()
        
        if error:
            request.error = error
            
        db.commit()
        logger.info(f"Updated request {request_id} status to {status}")
    
    def get_request_status(self, request_id: str, db: Session) -> Optional[ProcessingStatus]:
        """Get the current status of a request from database"""
        request = db.query(MakeRequest).filter(MakeRequest.request_id == request_id).first()
        
        if not request:
            return None
        
        return ProcessingStatus(
            request_id=request.request_id,
            status=request.status,
            result=request.result,
            error=request.error,
            created_at=request.created_at,
            completed_at=request.completed_at
        )
    
    async def cleanup_old_requests(self, db: Session, days: int = 7):
        """Clean up requests older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        deleted = db.query(MakeRequest).filter(
            MakeRequest.created_at < cutoff_date
        ).delete()
        
        db.commit()
        logger.info(f"Cleaned up {deleted} old requests")

    async def update_request_sources(self, request_id: str, sources: str, db: Session) -> bool:
    """Update sources for a specific request"""
    try:
        # Find the request in database (adjust table/model name as needed)
        request_record = db.query(YourRequestModel).filter(
            YourRequestModel.request_id == request_id
        ).first()
        
        if not request_record:
            logger.error(f"Request {request_id} not found in database")
            return False
        
        # Update the sources field
        request_record.sources = sources
        request_record.updated_at = datetime.utcnow()  # If you have this field
        
        db.commit()
        db.refresh(request_record)
        
        logger.info(f"Sources updated successfully for request_id: {request_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update sources for request_id {request_id}: {str(e)}")
        db.rollback()
        return False

# Global instance
make_service = MakeService()