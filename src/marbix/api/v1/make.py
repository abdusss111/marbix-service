# src/marbix/api/v1/make.py
from fastapi import APIRouter, HTTPException, Depends, WebSocket, Request
import asyncio
import logging

from marbix.core.deps import get_current_user
from marbix.core.websocket import manager
from marbix.schemas.make_integration import (
    MakeWebhookRequest,
    MakeCallbackResponse,
    ProcessingStatus,
    WebSocketMessage
)
from marbix.services.make_service import make_service
from marbix.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/make", tags=["make"])

@router.post("/strategy", response_model=ProcessingStatus)
async def process_request(
    request: MakeWebhookRequest,
    current_user: User = Depends(get_current_user)
):
    """Initiate processing with Make webhook"""
    try:
        status = await make_service.send_to_make(request)
        return status
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/callback/{request_id}")
async def handle_callback(
    request_id: str, 
    request: Request
):
    """Handle callback from Make - accepts both JSON and plain text"""
    logger.info(f"Received callback for request_id: {request_id}")
    
    try:
        content_type = request.headers.get("content-type", "")
        
        if "application/json" in content_type:
            # JSON payload
            data = await request.json()
            if isinstance(data, dict):
                result = data.get("result", "")
                status = data.get("status", "completed")
                error = data.get("error", None)
            else:
                # Just in case it's a JSON string
                result = str(data)
                status = "completed"
                error = None
        else:
            # Plain text payload
            result = await request.body()
            result = result.decode("utf-8")
            status = "completed"
            error = None
        
        # Update request status
        make_service.update_request_status(
            request_id=request_id,
            result=result,
            status=status,
            error=error
        )
        
        # Send result through WebSocket if connected
        message = WebSocketMessage(
            request_id=request_id,
            status=status,
            result=result,
            error=error
        )
        
        await manager.send_message(request_id, message.dict())
        
        # Schedule cleanup
        asyncio.create_task(make_service.cleanup_request(request_id))
        
        return {"status": "ok", "message": "Callback processed"}
        
    except ValueError as e:
        logger.warning(f"Callback for unknown request_id: {request_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error handling callback: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/status/{request_id}", response_model=ProcessingStatus)
async def get_status(
    request_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get status of a request (fallback for WebSocket)"""
    status = make_service.get_request_status(request_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Request not found")
    
    return status

@router.websocket("/ws/{request_id}")
async def websocket_endpoint(websocket: WebSocket, request_id: str):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket, request_id)
    
    try:
        # Check if result already available
        status = make_service.get_request_status(request_id)
        
        if not status:
            await websocket.send_json({
                "request_id": request_id,
                "status": "error",
                "error": "Request not found"
            })
            await websocket.close()
            return
        
        if status.status == "completed":
            # Send result immediately if already completed
            message = WebSocketMessage(
                request_id=request_id,
                status="completed",
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
        
        # Keep connection alive
        while True:
            # Wait for client messages (ping/pong)
            data = await websocket.receive_text()
            
            # Handle ping
            if data == "ping":
                await websocket.send_text("pong")
                
    except Exception as e:
        logger.error(f"WebSocket error for {request_id}: {str(e)}")
    finally:
        manager.disconnect(request_id)