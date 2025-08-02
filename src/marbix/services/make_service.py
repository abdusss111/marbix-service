import httpx
import uuid
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
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
from marbix.core.websocket import manager

logger = logging.getLogger(__name__)

class MakeService:
    """Service for handling Make webhook integration with database persistence"""
    
    def __init__(self):
        self.webhook_url = settings.WEBHOOK_URL
        self.api_base_url = settings.API_BASE_URL
        
    async def send_to_make(self, request: MakeWebhookRequest, user_id: str, db: Session, request_id: Optional[str] = None) -> ProcessingStatus:
        """Send request to Make webhook and save to database"""
        
        # Use provided request_id or generate new one
        if not request_id:
            request_id = str(uuid.uuid4())
            
            # Save NEW request to database
            db_request = MakeRequest(
                request_id=request_id,
                user_id=user_id,
                status="processing",
                request_data=request.dict(),
                retry_count=0,
                max_retries=3
            )
            db.add(db_request)
            db.commit()
            
            # Schedule the 6-minute check for NEW requests only
            asyncio.create_task(self._schedule_retry_check(request_id))
        else:
            # This is a retry - get existing request
            db_request = db.query(MakeRequest).filter(MakeRequest.request_id == request_id).first()
            if not db_request:
                raise ValueError(f"Request {request_id} not found for retry")
        
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
                logger.info(f"Sending to Make webhook: {self.webhook_url} (Request: {request_id})")
                
                response = await client.post(
                    self.webhook_url,
                    data=payload.json(),
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
                
            except Exception as e:
                logger.error(f"Error sending to Make: {str(e)}")
                db_request.status = "error"
                db_request.error = str(e)
                db.commit()
                raise
    
    async def _schedule_retry_check(self, request_id: str):
        """Schedule a check after 6 minutes to see if callback was received"""
        logger.info(f"Scheduling retry check for {request_id} in 6 minutes")
        
        # Wait 6 minutes
        await asyncio.sleep(6 * 60)  # 6 minutes = 360 seconds
        
        # Check if retry is needed
        await self._check_and_retry(request_id)
    
    async def _check_and_retry(self, request_id: str):
        """Check if callback was received, if not - retry the request"""
        try:
            # Get fresh database session
            db = next(get_db())
            
            try:
                # Get the request from database
                db_request = db.query(MakeRequest).filter(
                    MakeRequest.request_id == request_id
                ).first()
                
                if not db_request:
                    logger.warning(f"Request {request_id} not found for retry check")
                    return
                
                # If callback was already received, do nothing
                if db_request.callback_received_at is not None:
                    logger.info(f"Request {request_id} already received callback, no retry needed")
                    return
                
                # If we've exceeded max retries, mark as failed
                if db_request.retry_count >= db_request.max_retries:
                    logger.error(f"Request {request_id} exceeded max retries ({db_request.max_retries})")
                    db_request.status = "failed"
                    db_request.error = f"Failed after {db_request.max_retries} retry attempts"
                    db.commit()
                    
                    # Notify user of permanent failure
                    await self._notify_user_failure(request_id)
                    return
                
                # Increment retry count
                db_request.retry_count += 1
                db.commit()
                
                logger.info(f"No callback received for {request_id}, attempting retry {db_request.retry_count}/{db_request.max_retries}")
                
                # Notify user of retry
                await self._notify_user_retry(request_id, db_request.retry_count)
                
                # Recreate the original request and retry
                original_request = MakeWebhookRequest(**db_request.request_data)
                
                # Retry the request (this will schedule another 6-minute check)
                await self.send_to_make(original_request, db_request.user_id, db, request_id=request_id)
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error in retry check for {request_id}: {str(e)}")
    
    async def _notify_user_retry(self, request_id: str, retry_count: int):
        """Notify user that request is being retried"""
        try:
            message = {
                "request_id": request_id,
                "status": "retrying",
                "message": f"No response received, retrying request (attempt {retry_count})...",
                "retry_count": retry_count
            }
            await manager.send_message(request_id, message)
        except Exception as e:
            logger.error(f"Error notifying user of retry for {request_id}: {str(e)}")
    
    async def _notify_user_failure(self, request_id: str):
        """Notify user of permanent failure"""
        try:
            message = {
                "request_id": request_id,
                "status": "failed",
                "message": "Request failed after multiple attempts. Please try submitting again.",
                "error": "Request timed out after maximum retry attempts"
            }
            await manager.send_message(request_id, message)
        except Exception as e:
            logger.error(f"Error notifying permanent failure for {request_id}: {str(e)}")
    
    def update_request_status(self, request_id: str, result: str, status: str = "completed", error: Optional[str] = None, db: Session = None):
        """Update the status of a request in database"""
        request = db.query(MakeRequest).filter(MakeRequest.request_id == request_id).first()
        
        if not request:
            raise ValueError(f"Request {request_id} not found")
        
        # IMPORTANT: Mark callback as received to prevent retries
        request.callback_received_at = datetime.utcnow()
        request.status = status
        request.result = result
        request.completed_at = datetime.utcnow()
        
        if error:
            request.error = error
            
        db.commit()
        logger.info(f"Updated request {request_id} status to {status}, callback received at {request.callback_received_at}")
    
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
            request_record = db.query(MakeRequest).filter(
                MakeRequest.request_id == request_id
            ).first()
            
            if not request_record:
                logger.error(f"Request {request_id} not found in database")
                return False
            
            request_record.sources = sources
            db.commit()
            db.refresh(request_record)
            
            logger.info(f"Sources updated successfully for request_id: {request_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update sources for request_id {request_id}: {str(e)}")
            db.rollback()
            return False

make_service = MakeService()
