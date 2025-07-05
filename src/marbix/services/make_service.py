# src/marbix/services/make_service.py
import httpx
import uuid
import asyncio
from typing import Dict, Optional
from datetime import datetime
import logging

from marbix.core.config import settings
from marbix.schemas.make_integration import (
    MakeWebhookRequest,
    MakeWebhookPayload,
    ProcessingStatus
)

logger = logging.getLogger(__name__)

class MakeService:
    """Service for handling Make webhook integration"""
    
    def __init__(self):
        self.webhook_url = settings.WEBHOOK_URL  # Using existing WEBHOOK_URL
        self.api_base_url = settings.API_BASE_URL
        self.pending_requests: Dict[str, dict] = {}
        
    async def send_to_make(self, request: MakeWebhookRequest) -> ProcessingStatus:
        """Send request to Make webhook and return processing status"""
        request_id = str(uuid.uuid4())
        
        # Store request info
        self.pending_requests[request_id] = {
            "status": "processing",
            "created_at": datetime.utcnow(),
            "request_data": request.dict()
        }
        
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
                response = await client.post(
                    self.webhook_url,
                    json=payload.dict(),
                    timeout=30.0
                )
                
                if response.status_code != 200:
                    logger.error(f"Make webhook error: {response.status_code} - {response.text}")
                    self.pending_requests[request_id]["status"] = "error"
                    self.pending_requests[request_id]["error"] = "Failed to send to Make"
                    raise Exception("Failed to send request to processing service")
                
                logger.info(f"Request {request_id} sent to Make successfully")
                
                return ProcessingStatus(
                    request_id=request_id,
                    status="processing",
                    message="Request sent for processing",
                    created_at=self.pending_requests[request_id]["created_at"]
                )
                
            except httpx.TimeoutException:
                logger.error(f"Timeout sending request {request_id} to Make")
                self.pending_requests[request_id]["status"] = "error"
                self.pending_requests[request_id]["error"] = "Timeout"
                raise
            except Exception as e:
                logger.error(f"Error sending to Make: {str(e)}")
                self.pending_requests[request_id]["status"] = "error"
                self.pending_requests[request_id]["error"] = str(e)
                raise
    
    def update_request_status(self, request_id: str, result: str, 
                            status: str = "completed", error: Optional[str] = None):
        """Update the status of a pending request"""
        if request_id not in self.pending_requests:
            raise ValueError(f"Request {request_id} not found")
        
        self.pending_requests[request_id]["status"] = status
        self.pending_requests[request_id]["result"] = result
        self.pending_requests[request_id]["completed_at"] = datetime.utcnow()
        
        if error:
            self.pending_requests[request_id]["error"] = error
    
    def get_request_status(self, request_id: str) -> Optional[ProcessingStatus]:
        """Get the current status of a request"""
        if request_id not in self.pending_requests:
            return None
        
        request_info = self.pending_requests[request_id]
        
        return ProcessingStatus(
            request_id=request_id,
            status=request_info["status"],
            result=request_info.get("result"),
            error=request_info.get("error"),
            created_at=request_info["created_at"],
            completed_at=request_info.get("completed_at")
        )
    
    async def cleanup_request(self, request_id: str, delay: int = 300):
        """Clean up completed requests after delay (default 5 minutes)"""
        await asyncio.sleep(delay)
        if request_id in self.pending_requests:
            del self.pending_requests[request_id]
            logger.info(f"Cleaned up request {request_id}")

# Global instance
make_service = MakeService()