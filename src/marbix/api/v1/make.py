# src/marbix/api/v1/make.py
from fastapi import APIRouter, HTTPException, Depends, WebSocket, Request
from sqlalchemy.orm import Session
import asyncio
import logging
import json
from marbix.core.deps import get_current_user, get_db

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

router = APIRouter()

@router.post("/strategy", response_model=ProcessingStatus)
async def process_request(
    request: MakeWebhookRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Initiate processing with Make webhook"""
    # Debug: Get raw body first

    try:
        current_user.number = request.user_number
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

        status = await make_service.send_to_make(request, current_user.id, db)
        return status
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/callback/{request_id}")
async def handle_callback(
    request_id: str, 
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle callback from Make - accepts both JSON and plain text"""
    logger.info(f"Received callback for request_id: {request_id}")
    
    try:
        content_type = request.headers.get("content-type", "")
        
        if "application/json" in content_type:
            # JSON payload
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
                # Try to get raw body
                body = await request.body()
                result = body.decode("utf-8", errors="ignore")
                status = "completed"
                error = None
        else:
            # Plain text payload
            body = await request.body()
            result = body.decode("utf-8", errors="ignore")
            status = "completed"
            error = None
        
        # Update request status in database
        make_service.update_request_status(
            request_id=request_id,
            result=result,
            status=status,
            error=error,
            db=db
        )
        
        # Send result through WebSocket if connected
        message = WebSocketMessage(
            request_id=request_id,
            status=status,
            result=result,
            error=error
        )
        
        await manager.send_message(request_id, message.dict())
        
        # Schedule cleanup - removed as method doesn't exist
        # asyncio.create_task(make_service.cleanup_request(request_id))
        
        return {"status": "ok", "message": "Callback processed"}
        
    except ValueError as e:
        logger.warning(f"Callback for unknown request_id: {request_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error handling callback: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")



# Add this endpoint to your existing router in src/marbix/api/v1/make.py

from pydantic import BaseModel, field_validator
from typing import List, Union
import re

class SourcesCallbackRequest(BaseModel):
    sources: Union[List[str], str] = []
    
    @field_validator('sources', mode='before')
    @classmethod
    def parse_sources(cls, v):
        """Handle both string and array inputs from Make.com"""
        if isinstance(v, str):
            # Handle string input like "[url1, url2, url3]"
            if v.startswith('[') and v.endswith(']'):
                # Remove brackets and split by comma
                v = v[1:-1]  # Remove [ and ]
                # Split by comma and clean each URL
                sources = [url.strip() for url in v.split(', ') if url.strip()]
                return sources
            else:
                # Single URL as string
                return [v.strip()] if v.strip() else []
        elif isinstance(v, list):
            # Already a proper list
            return v
        else:
            return []

@router.post("/callback/{request_id}/sources")
async def handle_sources_callback(
    request_id: str, 
    sources_data: SourcesCallbackRequest,  # Accept JSON with array
    db: Session = Depends(get_db)
):
    """Handle sources callback from Make - accepts JSON array, stores as text"""
    logger.info(f"Received sources callback for request_id: {request_id}")
    
    try:
        # Get the sources array
        sources_array = sources_data.sources
        logger.info(f"Received {len(sources_array)} sources for {request_id}")
        
        
        # Update sources in database (as text)
        updated = make_service.update_request_sources(
            request_id=request_id,
            sources=sources_array,  # Pass as string
            db=db
        )
        
        if not updated:
            logger.error(f"Failed to update sources for request_id: {request_id} - request not found")
            raise HTTPException(status_code=404, detail="Request not found")
        
        # Get current request status to send through WebSocket
        current_status = make_service.get_request_status(request_id, db)
        
        if current_status:
            # Send updated info through WebSocket if connected
            message = WebSocketMessage(
                request_id=request_id,
                status=current_status.status,
                result=current_status.result,
                # Alternative if WebSocketMessage expects array: sources=sources_array,
                error=current_status.error
            )
            
            await manager.send_message(request_id, message.dict())
        
        return {
            "status": "ok", 
            "message": "Sources updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error handling sources callback for request_id {request_id}: {str(e)}")
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
    
    return status

@router.websocket("/ws/{request_id}")
async def websocket_endpoint(websocket: WebSocket, request_id: str):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket, request_id)
    
    try:
        # Get DB session for checking status
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