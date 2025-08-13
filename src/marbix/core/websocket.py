# src/marbix/core/websocket.py
from typing import Dict, Optional, List
from fastapi import WebSocket
import logging
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time updates with result caching"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.cached_messages: Dict[str, List[dict]] = {}  # Cache messages for each request_id
        self.connection_timestamps: Dict[str, datetime] = {}  # Track connection times
        
    async def connect(self, websocket: WebSocket, request_id: str):
        """Accept and store a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[request_id] = websocket
        self.connection_timestamps[request_id] = datetime.utcnow()
        
        # Send any cached messages immediately
        if request_id in self.cached_messages:
            for cached_msg in self.cached_messages[request_id]:
                try:
                    await websocket.send_json(cached_msg)
                except Exception as e:
                    logger.error(f"Failed to send cached message to {request_id}: {e}")
                    break
        
        logger.info(f"WebSocket connected for request_id: {request_id}")

    def disconnect(self, request_id: str):
        """Remove a WebSocket connection"""
        if request_id in self.active_connections:
            del self.active_connections[request_id]
            if request_id in self.connection_timestamps:
                del self.connection_timestamps[request_id]
            logger.info(f"WebSocket disconnected for request_id: {request_id}")

    async def send_message(self, request_id: str, message: dict):
        """Send a message to a specific WebSocket connection and cache it"""
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()
        
        # Cache the message
        if request_id not in self.cached_messages:
            self.cached_messages[request_id] = []
        self.cached_messages[request_id].append(message)
        
        # Keep only last 50 messages to prevent memory issues
        if len(self.cached_messages[request_id]) > 50:
            self.cached_messages[request_id] = self.cached_messages[request_id][-50:]
        
        # Send to active connection if available
        if request_id in self.active_connections:
            websocket = self.active_connections[request_id]
            try:
                await websocket.send_json(message)
                logger.debug(f"Message sent to request_id: {request_id}")
            except Exception as e:
                logger.error(f"Error sending message to {request_id}: {e}")
                self.disconnect(request_id)
        else:
            logger.debug(f"Message cached for disconnected request_id: {request_id}")

    async def send_immediate_status(self, request_id: str, status: str, message: str = None, result: str = None, error: str = None):
        """Send immediate status update when client connects"""
        status_msg = {
            "request_id": request_id,
            "type": "status_update",
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if message:
            status_msg["message"] = message
        if result:
            status_msg["result"] = result
        if error:
            status_msg["error"] = error
            
        await self.send_message(request_id, status_msg)

    async def send_progress_update(self, request_id: str, stage: str, message: str, progress: Optional[float] = None):
        """Send progress update during processing"""
        progress_msg = {
            "request_id": request_id,
            "type": "progress_update",
            "stage": stage,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if progress is not None:
            progress_msg["progress"] = progress
            
        await self.send_message(request_id, progress_msg)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected WebSockets"""
        disconnected = []
        for request_id, websocket in self.active_connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to {request_id}: {e}")
                disconnected.append(request_id)
        
        # Clean up disconnected clients
        for request_id in disconnected:
            self.disconnect(request_id)

    def cleanup_old_connections(self, max_age_hours: int = 24):
        """Clean up old cached messages and connection data"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        # Clean up old cached messages
        old_requests = []
        for request_id, timestamp in self.connection_timestamps.items():
            if timestamp < cutoff_time:
                old_requests.append(request_id)
        
        for request_id in old_requests:
            if request_id in self.cached_messages:
                del self.cached_messages[request_id]
            if request_id in self.connection_timestamps:
                del self.connection_timestamps[request_id]
        
        if old_requests:
            logger.info(f"Cleaned up {len(old_requests)} old request caches")

    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)

    def get_cached_message_count(self, request_id: str) -> int:
        """Get number of cached messages for a request"""
        return len(self.cached_messages.get(request_id, []))

# Global instance
manager = ConnectionManager()

# Periodic cleanup task
async def cleanup_websocket_cache():
    """Periodically clean up old WebSocket caches to prevent memory leaks"""
    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour
            manager.cleanup_old_connections(max_age_hours=24)
            logger.debug(f"WebSocket cleanup completed. Active connections: {manager.get_connection_count()}")
        except Exception as e:
            logger.error(f"WebSocket cleanup error: {e}")

# Start cleanup task when module is imported
try:
    import asyncio
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If loop is already running, create task
        loop.create_task(cleanup_websocket_cache())
    else:
        # If loop is not running, schedule for later
        loop.call_later(1, lambda: loop.create_task(cleanup_websocket_cache()))
except Exception as e:
    logger.warning(f"Could not start WebSocket cleanup task: {e}")