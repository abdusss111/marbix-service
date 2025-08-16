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
   """NEW FLOW: Initiate processing with immediate WebSocket connection and real-time updates"""

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

       # Create initial request record with status "requested"
       status = await make_service.create_request_record(
           request_id=request_id,
           user_id=current_user.id,
           request_data=request.dict(),
           db=db,
           initial_status="requested"  # NEW: Start with "requested" status
       )

       # 6. NEW: Immediately notify via WebSocket that request was created
       try:
           await manager.send_message(request_id, {
               "request_id": request_id,
               "type": "status_update",
               "status": "requested",
               "message": "Strategy request received and approved. Preparing to start processing...",
               "progress": 0.0,
               "timestamp": datetime.utcnow().isoformat()
           })
           logger.info(f"Sent initial WebSocket notification for {request_id}")
       except Exception as ws_error:
           logger.warning(f"Failed to send initial WebSocket notification: {str(ws_error)}")

       # 7. Queue job with ARQ worker
       try:
           redis_pool = await create_pool(settings.redis_settings)

           # Update status to "processing" before queuing
           make_service.update_request_status(
               request_id=request_id,
               status="processing",
               db=db
           )

           # Notify WebSocket of processing start
           await manager.send_message(request_id, {
               "request_id": request_id,
               "type": "status_update", 
               "status": "processing",
               "message": "Strategy generation job queued. Starting processing...",
               "progress": 0.05,
               "timestamp": datetime.utcnow().isoformat()
           })

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

       except Exception as redis_error:
           logger.error(f"Failed to queue job: {str(redis_error)}")

           # Update request status to error
           make_service.update_request_status(
               request_id=request_id,
               status="error",
               error=f"Failed to queue processing job: {str(redis_error)}",
               db=db
           )

           # Notify WebSocket of error
           await manager.send_message(request_id, {
               "request_id": request_id,
               "type": "error",
               "status": "error",
               "error": f"Failed to queue processing job: {str(redis_error)}",
               "message": "Failed to queue your request for processing. Please try again later.",
               "timestamp": datetime.utcnow().isoformat()
           })

           return ProcessingStatus(
               request_id=request_id,
               status="error",
               message="Failed to queue your request for processing. Please try again later.",
               created_at=datetime.utcnow(),
               error=str(redis_error)
           )

       # 8. NEW: Return immediately with request_id for WebSocket connection
       return ProcessingStatus(
           request_id=request_id,
           status="processing",
           message="Strategy generation started. Connect to WebSocket for real-time updates.",
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

@router.get("/debug/{request_id}")
async def debug_request_status(
       request_id: str,
       db: Session = Depends(get_db)
):
   """Debug endpoint to check raw request status in database"""
   try:
       # Direct database query
       from marbix.models.make_request import MakeRequest
       request = db.query(MakeRequest).filter(
           MakeRequest.request_id == request_id
       ).first()
       
       if not request:
           return {"error": "Request not found", "request_id": request_id}
       
       return {
           "request_id": request.request_id,
           "user_id": request.user_id,
           "status": request.status,
           "result_length": len(request.result) if request.result else 0,
           "sources_length": len(request.sources) if request.sources else 0,
           "error": request.error,
           "created_at": request.created_at.isoformat() if request.created_at else None,
           "completed_at": request.completed_at.isoformat() if request.completed_at else None,
           "result_preview": request.result[:200] + "..." if request.result and len(request.result) > 200 else request.result,
           "websocket_active": request_id in manager.active_connections,
           "cached_messages_count": manager.get_cached_message_count(request_id)
       }
       
   except Exception as e:
       return {"error": str(e), "request_id": request_id}

@router.websocket("/ws/{request_id}")
async def websocket_endpoint(websocket: WebSocket, request_id: str):
    """Simplified real-time WebSocket endpoint with database polling"""
    await manager.connect(websocket, request_id)
    
    db = None
    polling_task = None
    heartbeat_task = None
    
    try:
        db = next(get_db())
        logger.info(f"🔌 WebSocket connected for {request_id}")
        
        # Check initial status
        status = make_service.get_request_status(request_id, db)
        if not status:
            await websocket.send_json({
                "type": "error",
                "error": "Request not found",
                "timestamp": datetime.utcnow().isoformat()
            })
            await websocket.close()
            return

        # If already completed, send immediately and close
        if status.status == "completed":
            await websocket.send_json({
                "request_id": request_id,
                "type": "strategy_complete",
                "status": "completed",
                "result": status.result or "",
                "sources": status.sources or "",
                "progress": 1.0,
                "message": "Strategy completed",
                "timestamp": datetime.utcnow().isoformat()
            })
            logger.info(f"✅ Sent completed strategy to {request_id}")
            await asyncio.sleep(0.5)
            await websocket.close(code=1000, reason="Completed")
            return

        # If error, send error and close
        if status.status == "error":
            await websocket.send_json({
                "request_id": request_id,
                "type": "error",
                "status": "error",
                "error": status.error or "Unknown error",
                "timestamp": datetime.utcnow().isoformat()
            })
            await websocket.close(code=1000, reason="Error")
            return

        # Send initial status
        await websocket.send_json({
            "request_id": request_id,
            "type": "status_update",
            "status": status.status,
            "message": f"Current status: {status.status}",
            "progress": 0.1 if status.status == "processing" else 0.0,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Start polling for status updates
        last_status = status.status
        
        async def poll_status():
            nonlocal last_status
            while True:
                try:
                    await asyncio.sleep(2)  # Poll every 2 seconds
                    current_status = make_service.get_request_status(request_id, db)
                    
                    if not current_status:
                        break
                        
                    # Send update if status changed
                    if current_status.status != last_status:
                        if current_status.status == "completed":
                            await websocket.send_json({
                                "request_id": request_id,
                                "type": "strategy_complete",
                                "status": "completed",
                                "result": current_status.result or "",
                                "sources": current_status.sources or "",
                                "progress": 1.0,
                                "message": "Strategy generation completed!",
                                "timestamp": datetime.utcnow().isoformat()
                            })
                            logger.info(f"✅ Strategy completed and sent to {request_id}")
                            break
                        elif current_status.status == "error":
                            await websocket.send_json({
                                "request_id": request_id,
                                "type": "error",
                                "status": "error",
                                "error": current_status.error or "Unknown error",
                                "timestamp": datetime.utcnow().isoformat()
                            })
                            break
                        else:
                            await websocket.send_json({
                                "request_id": request_id,
                                "type": "status_update",
                                "status": current_status.status,
                                "message": f"Status: {current_status.status}",
                                "progress": 0.5 if current_status.status == "processing" else 0.1,
                                "timestamp": datetime.utcnow().isoformat()
                            })
                        
                        last_status = current_status.status
                        
                except Exception as e:
                    logger.error(f"Polling error for {request_id}: {e}")
                    break

        async def send_heartbeat():
            while True:
                try:
                    await asyncio.sleep(30)  # Heartbeat every 30 seconds
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break

        # Start background tasks
        polling_task = asyncio.create_task(poll_status())
        heartbeat_task = asyncio.create_task(send_heartbeat())

        # Wait for client messages or completion
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=300)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                logger.info(f"WebSocket timeout for {request_id}")
                break
            except Exception as e:
                logger.warning(f"WebSocket receive error for {request_id}: {e}")
                break

    except Exception as e:
        logger.error(f"WebSocket error for {request_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "error": f"WebSocket error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            })
        except:
            pass
    finally:
        # Clean up tasks
        if polling_task:
            polling_task.cancel()
        if heartbeat_task:
            heartbeat_task.cancel()
        if db:
            db.close()
        manager.disconnect(request_id)
        logger.info(f"🔌❌ WebSocket cleaned up for {request_id}")

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