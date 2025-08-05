# src/marbix/api/v1/make.py
from fastapi import APIRouter, HTTPException, Depends, WebSocket, Request
from sqlalchemy.orm import Session
import asyncio
import logging
import json
from arq import create_pool
from marbix.core.deps import get_current_user, get_db
from marbix.core.config import settings
from marbix.services.content_filter_service import content_filter_service
from marbix.core.websocket import manager
from marbix.schemas.make_integration import (
    MakeWebhookRequest,
    MakeCallbackResponse,
    ProcessingStatus,
    WebSocketMessage
)
from marbix.schemas.strategy import SourcesCallbackRequest
from marbix.services.make_service import make_service
from marbix.models.user import User
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/strategy", response_model=ProcessingStatus)
async def process_request(
        request: MakeWebhookRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Initiate processing with ARQ worker after content filtering"""

    try:
        logger.info(f"Processing strategy request from user {current_user.id}")

        # 1. CONTENT FILTERING - Check business data first
        filter_result = await content_filter_service.check_business_request(request.dict())

        # 2. Handle filter service errors gracefully
        if not filter_result.get("success", False):
            logger.warning(f"Content filter service error: {filter_result.get('error', 'Unknown error')}")
            return ProcessingStatus(
                request_id="",
                status="rejected",
                message="Content filtering service temporarily unavailable. Please try again later.",
                created_at=datetime.utcnow()
            )

        # 3. If content is not allowed, return rejection message
        if not filter_result["is_allowed"]:
            logger.info(
                f"Content rejected for user {current_user.id}. "
                f"Violated topics: {filter_result['violated_topics']}, "
                f"Reason: {filter_result['reason']}"
            )

            return ProcessingStatus(
                request_id="",
                status="rejected",
                message="Your business request contains content that cannot be processed according to our platform policies. Please review and modify your business description.",
                created_at=datetime.utcnow(),
                error=f"Policy violation: {filter_result['reason']}"
            )

        # 4. CONTENT APPROVED - Update user number
        logger.info(f"Content approved for user {current_user.id}. Proceeding with strategy generation.")

        current_user.number = request.user_number
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

        # 5. Generate unique request ID and create database record
        request_id = str(uuid.uuid4())

        # Create initial request record
        status = await make_service.create_request_record(
            request_id=request_id,
            user_id=current_user.id,
            request_data=request.dict(),
            db=db
        )

        # 6. Queue job with ARQ worker
        try:
            redis_pool = await create_pool(settings.redis_settings)

            job = await redis_pool.enqueue_job(
                'generate_strategy',
                request_id=request_id,
                user_id=current_user.id,
                request_data=request.dict(),
                _job_timeout=settings.ARQ_JOB_TIMEOUT,
                _max_tries=settings.ARQ_MAX_TRIES,
                _defer_by=0  # Start immediately
            )

            logger.info(f"Strategy generation job queued. Request ID: {request_id}, Job ID: {job.job_id}")

            # Close Redis pool
            redis_pool.close()
            await redis_pool.wait_closed()

        except Exception as redis_error:
            logger.error(f"Failed to queue job: {str(redis_error)}")

            # Update request status to error
            make_service.update_request_status(
                request_id=request_id,
                status="error",
                error=f"Failed to queue processing job: {str(redis_error)}",
                db=db
            )

            return ProcessingStatus(
                request_id=request_id,
                status="error",
                message="Failed to queue your request for processing. Please try again later.",
                created_at=datetime.utcnow(),
                error=str(redis_error)
            )

        return ProcessingStatus(
            request_id=request_id,
            status="processing",
            message="Your strategy generation has been queued and will be processed shortly.",
            created_at=datetime.utcnow()
        )

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")

        return ProcessingStatus(
            request_id="",
            status="error",
            message="An unexpected error occurred while processing your request. Please try again later.",
            created_at=datetime.utcnow(),
            error=str(e)
        )


@router.post("/callback/{request_id}")
async def handle_callback(
        request_id: str,
        request: Request,
        db: Session = Depends(get_db)
):
    """Legacy callback handler for backward compatibility"""
    logger.info(f"Received legacy callback for request_id: {request_id}")

    try:
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            try:
                data = await request.json()
                if isinstance(data, dict):
                    result = data.get("result", "")
                    status = data.get("status", "completed")
                    error = data.get("error", None)
                else:
                    result = str(data)
                    status = "completed"
                    error = None
            except Exception as e:
                logger.error(f"JSON parse error: {e}")
                body = await request.body()
                result = body.decode("utf-8", errors="ignore")
                status = "completed"
                error = None
        else:
            body = await request.body()
            result = body.decode("utf-8", errors="ignore")
            status = "completed"
            error = None

        # Update request status
        make_service.update_request_status(
            request_id=request_id,
            result=result,
            status=status,
            error=error,
            db=db
        )

        # Send result through WebSocket
        message = WebSocketMessage(
            request_id=request_id,
            status=status,
            result=result,
            error=error
        )

        await manager.send_message(request_id, message.dict())

        return {"status": "ok", "message": "Legacy callback processed"}

    except ValueError as e:
        logger.warning(f"Callback for unknown request_id: {request_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error handling callback: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status/{request_id}", response_model=ProcessingStatus)
async def get_status(
        request_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get status of a request (fallback for WebSocket)"""
    status = make_service.get_request_status(request_id, db)

    if not status:
        raise HTTPException(status_code=404, detail="Request not found")

    # Security: Only return status for user's own requests
    if status.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return status


@router.websocket("/ws/{request_id}")
async def websocket_endpoint(websocket: WebSocket, request_id: str):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket, request_id)

    try:
        db = next(get_db())

        # Check if result already available
        status = make_service.get_request_status(request_id, db)

        if not status:
            await websocket.send_json({
                "request_id": request_id,
                "status": "error",
                "error": "Request not found"
            })
            await websocket.close()
            return

        if status.status in ["completed", "failed", "error"]:
            # Send result immediately if already completed
            message = WebSocketMessage(
                request_id=request_id,
                status=status.status,
                result=status.result,
                error=status.error
            )
            await websocket.send_json(message.dict())
            await websocket.close()
            return
        else:
            # Send current status
            message = WebSocketMessage(
                request_id=request_id,
                status="processing",
                message="Processing your request..."
            )
            await websocket.send_json(message.dict())

        # Keep connection alive with heartbeat
        heartbeat_task = None
        try:
            # Start heartbeat
            async def send_heartbeat():
                while True:
                    await asyncio.sleep(settings.WS_HEARTBEAT_INTERVAL)
                    await websocket.send_json({"type": "heartbeat"})

            heartbeat_task = asyncio.create_task(send_heartbeat())

            # Wait for client messages or completion
            while True:
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=settings.WS_CONNECTION_TIMEOUT
                    )

                    if data == "ping":
                        await websocket.send_text("pong")

                except asyncio.TimeoutError:
                    logger.info(f"WebSocket timeout for {request_id}")
                    break

        finally:
            if heartbeat_task:
                heartbeat_task.cancel()

    except Exception as e:
        logger.error(f"WebSocket error for {request_id}: {str(e)}")
    finally:
        manager.disconnect(request_id)


@router.post("/callback/{request_id}/sources")
async def handle_sources_callback(
        request_id: str,
        sources_data: SourcesCallbackRequest,
        db: Session = Depends(get_db)
):
    """Legacy sources callback handler for backward compatibility"""
    logger.info(f"Received legacy sources callback for request_id: {request_id}")

    try:
        sources_array = sources_data.sources
        logger.info(f"Received {len(sources_array)} sources for {request_id}")

        if sources_array:
            sources_text = "\n".join(sources_array)
            logger.info(f"Sources preview: {sources_text[:200]}...")
        else:
            sources_text = ""

        updated = await make_service.update_request_sources(
            request_id=request_id,
            sources=sources_text,
            db=db
        )

        if not updated:
            logger.error(f"Failed to update sources for request_id: {request_id} - request not found")
            raise HTTPException(status_code=404, detail="Request not found")

        current_status = make_service.get_request_status(request_id, db)

        if current_status:
            message = WebSocketMessage(
                request_id=request_id,
                status=current_status.status,
                result=current_status.result,
                sources=sources_text,
                error=current_status.error
            )

            await manager.send_message(request_id, message.dict())

        return {
            "status": "ok",
            "message": "Legacy sources updated successfully",
            "sources_count": len(sources_array),
            "sources_text_length": len(sources_text)
        }

    except Exception as e:
        logger.error(f"Error handling sources callback for request_id {request_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")