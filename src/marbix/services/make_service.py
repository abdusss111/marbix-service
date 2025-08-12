# src/marbix/services/make_service.py

import httpx
import uuid
import asyncio
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
from arq import create_pool

from marbix.core.config import settings
from marbix.core.deps import get_db
from marbix.models.make_request import MakeRequest
from marbix.schemas.make_integration import (
    MakeWebhookRequest,
    ProcessingStatus
)
from marbix.core.websocket import manager

logger = logging.getLogger(__name__)


class MakeService:
    """Service for handling strategy generation with ARQ workers and database persistence"""

    def __init__(self):
        self.api_base_url = settings.API_BASE_URL
        # Legacy Make.com support (optional)
        self.webhook_url = getattr(settings, 'WEBHOOK_URL', None)

    async def create_request_record(
            self,
            request_id: str,
            user_id: str,
            request_data: dict,
            db: Session
    ) -> ProcessingStatus:
        """Create initial request record in database"""
        try:
            db_request = MakeRequest(
                request_id=request_id,
                user_id=user_id,
                status="processing",
                request_data=request_data,
                retry_count=0,
                max_retries=settings.ARQ_MAX_TRIES
            )

            db.add(db_request)
            db.commit()
            db.refresh(db_request)

            logger.info(f"Created request record {request_id} for user {user_id}")

            return ProcessingStatus(
                request_id=request_id,
                status="processing",
                message="Request queued for processing",
                created_at=db_request.created_at
            )

        except Exception as e:
            logger.error(f"Failed to create request record {request_id}: {str(e)}")
            db.rollback()
            raise

    def update_request_status(
            self,
            request_id: str,
            status: str = "completed",
            result: Optional[str] = None,
            error: Optional[str] = None,
            sources: Optional[str] = None,
            db: Session = None
    ):
        """Update the status of a request in database"""
        try:
            request = db.query(MakeRequest).filter(
                MakeRequest.request_id == request_id
            ).first()

            if not request:
                logger.error(f"Request {request_id} not found for status update")
                raise ValueError(f"Request {request_id} not found")

            # Update fields
            request.status = status

            if result is not None:
                request.result = result

            if error is not None:
                request.error = error

            if sources is not None:
                request.sources = sources

            # Mark as completed if final status
            if status in ["completed", "failed", "error"]:
                request.completed_at = datetime.utcnow()
                request.callback_received_at = datetime.utcnow()

            db.commit()
            db.refresh(request)

            logger.info(f"Updated request {request_id} status to {status}")

        except Exception as e:
            logger.error(f"Failed to update request {request_id}: {str(e)}")
            db.rollback()
            raise

    def increment_retry_count(self, request_id: str, db: Session) -> bool:
        """Increment retry count for a request"""
        try:
            request = db.query(MakeRequest).filter(
                MakeRequest.request_id == request_id
            ).first()

            if not request:
                logger.error(f"Request {request_id} not found for retry increment")
                return False

            request.retry_count += 1
            db.commit()

            logger.info(f"Incremented retry count for {request_id} to {request.retry_count}")
            return True

        except Exception as e:
            logger.error(f"Failed to increment retry count for {request_id}: {str(e)}")
            db.rollback()
            return False

    def get_request_status(self, request_id: str, db: Session) -> Optional[ProcessingStatus]:
        """Get the current status of a request from database"""
        try:
            request = db.query(MakeRequest).filter(
                MakeRequest.request_id == request_id
            ).first()

            if not request:
                logger.warning(f"Request {request_id} not found")
                return None

            return ProcessingStatus(
                request_id=request.request_id,
                user_id=request.user_id,
                status=request.status,
                result=request.result,
                error=request.error,
                sources=request.sources,
                created_at=request.created_at,
                completed_at=request.completed_at,
                retry_count=request.retry_count
            )

        except Exception as e:
            logger.error(f"Failed to get status for {request_id}: {str(e)}")
            return None

    async def update_request_sources(self, request_id: str, sources: str, db: Session) -> bool:
        """Update sources for a specific request"""
        try:
            request_record = db.query(MakeRequest).filter(
                MakeRequest.request_id == request_id
            ).first()

            if not request_record:
                logger.error(f"Request {request_id} not found for sources update")
                return False

            request_record.sources = sources
            db.commit()
            db.refresh(request_record)

            logger.info(f"Sources updated for request {request_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update sources for {request_id}: {str(e)}")
            db.rollback()
            return False

    async def notify_user_status(
            self,
            request_id: str,
            status: str,
            message: str = None,
            result: str = None,
            error: str = None,
            sources: str = None
    ):
        """Notify user via WebSocket about status changes"""
        try:
            notification = {
                "request_id": request_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat()
            }

            if message:
                notification["message"] = message
            if result:
                notification["result"] = result
            if error:
                notification["error"] = error
            if sources:
                notification["sources"] = sources

            await manager.send_message(request_id, notification)
            logger.info(f"Sent notification for {request_id}: {status}")

        except Exception as e:
            logger.error(f"Failed to notify user for {request_id}: {str(e)}")

    async def send_strategy_result(
            self,
            request_id: str,
            strategy_text: str,
            sources: Optional[str] = None,
            chunk_size: int = 4000,
    ) -> None:
        """Send strategy text over WebSocket in chunks, then a completion message.

        This avoids large single-payload messages and provides incremental delivery.
        """
        try:
            if not strategy_text:
                await self.notify_user_status(
                    request_id=request_id,
                    status="error",
                    message="Empty strategy content",
                    error="empty_strategy"
                )
                return

            total_len = len(strategy_text)
            total_chunks = (total_len + chunk_size - 1) // chunk_size

            for i in range(total_chunks):
                chunk = strategy_text[i * chunk_size:(i + 1) * chunk_size]
                msg = {
                    "request_id": request_id,
                    "status": "processing",
                    "type": "strategy_chunk",
                    "seq": i + 1,
                    "total": total_chunks,
                    "chunk": chunk,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                await manager.send_message(request_id, msg)

            # Final completion message
            complete_msg = {
                "request_id": request_id,
                "status": "completed",
                "type": "strategy_complete",
                "timestamp": datetime.utcnow().isoformat(),
            }
            if sources:
                complete_msg["sources"] = sources

            await manager.send_message(request_id, complete_msg)
            logger.info(f"Strategy streamed via WS for {request_id} in {total_chunks} chunks")

        except Exception as e:
            logger.error(f"Failed to stream strategy via WS for {request_id}: {str(e)}")

    async def cleanup_old_requests(self, db: Session, days: int = 7):
        """Clean up requests older than specified days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Only delete completed/failed requests to preserve processing ones
            deleted = db.query(MakeRequest).filter(
                MakeRequest.created_at < cutoff_date,
                MakeRequest.status.in_(["completed", "failed", "error"])
            ).delete(synchronize_session=False)

            db.commit()
            logger.info(f"Cleaned up {deleted} old requests older than {days} days")

        except Exception as e:
            logger.error(f"Failed to cleanup old requests: {str(e)}")
            db.rollback()

    async def get_user_requests(
            self,
            user_id: str,
            db: Session,
            limit: int = 10,
            status_filter: Optional[str] = None
    ) -> list[ProcessingStatus]:
        """Get user's recent requests with optional status filter"""
        try:
            query = db.query(MakeRequest).filter(
                MakeRequest.user_id == user_id
            )

            if status_filter:
                query = query.filter(MakeRequest.status == status_filter)

            requests = query.order_by(
                MakeRequest.created_at.desc()
            ).limit(limit).all()

            return [
                ProcessingStatus(
                    request_id=req.request_id,
                    user_id=req.user_id,
                    status=req.status,
                    result=req.result,
                    error=req.error,
                    sources=req.sources,
                    created_at=req.created_at,
                    completed_at=req.completed_at,
                    retry_count=req.retry_count
                )
                for req in requests
            ]

        except Exception as e:
            logger.error(f"Failed to get user requests for {user_id}: {str(e)}")
            return []

    # Legacy Make.com methods for backward compatibility
    async def send_to_make(
            self,
            request: MakeWebhookRequest,
            user_id: str,
            db: Session,
            request_id: Optional[str] = None
    ) -> ProcessingStatus:
        """Legacy method for Make.com integration (deprecated)"""
        logger.warning("send_to_make is deprecated, use ARQ worker instead")

        if not self.webhook_url:
            raise ValueError("WEBHOOK_URL not configured for legacy Make.com support")

        # Implementation kept for backward compatibility
        # This should be removed once migration is complete
        request_id = request_id or str(uuid.uuid4())

        try:
            # Create request record
            status = await self.create_request_record(
                request_id=request_id,
                user_id=user_id,
                request_data=request.dict(),
                db=db
            )

            # Send to Make.com (legacy)
            callback_url = f"{self.api_base_url}/api/callback/{request_id}"

            payload = {
                **request.dict(exclude_none=True),
                "callback_url": callback_url,
                "request_id": request_id
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }
                )

                if response.status_code != 200:
                    raise Exception(f"Make webhook error: {response.status_code}")

            logger.info(f"Legacy request {request_id} sent to Make.com")
            return status

        except Exception as e:
            logger.error(f"Legacy Make.com request failed: {str(e)}")
            self.update_request_status(
                request_id=request_id,
                status="error",
                error=str(e),
                db=db
            )
            raise


# Global service instance
make_service = MakeService()