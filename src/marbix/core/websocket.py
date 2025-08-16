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
        
        # Enhanced logging for debugging
        logger.info(f"🔌 WebSocket connected for request_id: {request_id}")
        logger.info(f"📊 Total active connections: {len(self.active_connections)}")
        logger.info(f"🔑 Active connection IDs: {list(self.active_connections.keys())}")
        
        # Send any cached messages immediately
        if request_id in self.cached_messages:
            cached_count = len(self.cached_messages[request_id])
            logger.info(f"📤 Sending {cached_count} cached messages to {request_id}")
            for i, cached_msg in enumerate(self.cached_messages[request_id]):
                try:
                    await websocket.send_json(cached_msg)
                    logger.info(f"✅ Sent cached message {i+1}/{cached_count} to {request_id}")
                except Exception as e:
                    logger.error(f"❌ Failed to send cached message {i+1} to {request_id}: {e}")
                    break
        else:
            logger.info(f"📭 No cached messages for {request_id}")
        
        logger.info(f"✅ WebSocket setup completed for request_id: {request_id}")

    def disconnect(self, request_id: str):
        """Remove a WebSocket connection"""
        if request_id in self.active_connections:
            del self.active_connections[request_id]
            if request_id in self.connection_timestamps:
                del self.connection_timestamps[request_id]
            logger.info(f"🔌❌ WebSocket disconnected for request_id: {request_id}")
            logger.info(f"📊 Remaining active connections: {len(self.active_connections)}")
            logger.info(f"🔑 Remaining connection IDs: {list(self.active_connections.keys())}")
        else:
            logger.warning(f"⚠️ Attempted to disconnect non-existent connection: {request_id}")
            logger.info(f"🔑 Current active connections: {list(self.active_connections.keys())}")

    async def send_message(self, request_id: str, message: dict):
        """Send a message to a specific WebSocket connection and cache it"""
        try:
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
                    # Log the message type and size for debugging
                    msg_type = message.get("type", "unknown")
                    msg_size = len(str(message))
                    logger.info(f"📤 Sending WebSocket message: type={msg_type}, size={msg_size}B to {request_id}")
                    logger.info(f"🔑 Connection exists in active_connections: {request_id in self.active_connections}")
                    logger.info(f"📊 Active connections count: {len(self.active_connections)}")
                    
                    # Check for extremely large messages
                    if msg_size > 1024 * 1024:  # 1MB limit
                        logger.warning(f"⚠️ Large WebSocket message detected: {msg_size}B for {request_id}")
                        # Truncate very large results to prevent WebSocket issues
                        if "result" in message and len(message["result"]) > 500000:  # 500KB
                            original_length = len(message["result"])
                            message["result"] = message["result"][:500000] + f"\n\n[Content truncated - original length: {original_length} characters]"
                            logger.info(f"✂️ Truncated result from {original_length} to {len(message['result'])} chars")
                    
                    await websocket.send_json(message)
                    logger.info(f"✅ Message successfully sent to request_id: {request_id}")
                    
                except Exception as e:
                    logger.error(f"❌ Error sending WebSocket message to {request_id}: {e}")
                    logger.error(f"Message type: {message.get('type', 'unknown')}")
                    import traceback
                    logger.error(f"Full traceback: {traceback.format_exc()}")
                    self.disconnect(request_id)
                    raise e  # Re-raise to trigger fallback in worker
            else:
                logger.warning(f"⚠️ No active connection for {request_id}, message cached only")
                logger.info(f"🔑 Available connections: {list(self.active_connections.keys())}")
                logger.info(f"📊 Total cached messages for {request_id}: {len(self.cached_messages.get(request_id, []))}")
                
        except Exception as e:
            logger.error(f"❌ Critical error in send_message for {request_id}: {e}")
            raise e

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
    
    def debug_connection_state(self, request_id: str) -> dict:
        """Debug method to inspect connection state"""
        return {
            "request_id": request_id,
            "is_active": request_id in self.active_connections,
            "total_active_connections": len(self.active_connections),
            "active_connection_ids": list(self.active_connections.keys()),
            "cached_messages_count": len(self.cached_messages.get(request_id, [])),
            "has_timestamp": request_id in self.connection_timestamps,
            "connection_timestamp": self.connection_timestamps.get(request_id, None),
            "manager_instance_id": id(self)
        }

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