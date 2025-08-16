# src/marbix/core/websocket.py
from typing import Dict, Optional
from fastapi import WebSocket
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Simplified WebSocket manager focused on real-time delivery"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.connection_timestamps: Dict[str, datetime] = {}

        
    async def connect(self, websocket: WebSocket, request_id: str):
        """Accept and store a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[request_id] = websocket
        self.connection_timestamps[request_id] = datetime.utcnow()
        logger.info(f"🔌 WebSocket connected for request_id: {request_id}")

    def disconnect(self, request_id: str):
        """Remove a WebSocket connection"""
        if request_id in self.active_connections:
            del self.active_connections[request_id]
            if request_id in self.connection_timestamps:
                del self.connection_timestamps[request_id]
            logger.info(f"🔌❌ WebSocket disconnected for request_id: {request_id}")
        else:
            logger.warning(f"⚠️ Attempted to disconnect non-existent connection: {request_id}")

    async def send_message(self, request_id: str, message: dict):
        """Send a message to active WebSocket connection (API process only)"""
        if request_id in self.active_connections:
            websocket = self.active_connections[request_id]
            try:
                await websocket.send_json(message)
                logger.info(f"✅ Sent {message.get('type', 'unknown')} to {request_id}")
                return True
            except Exception as e:
                logger.error(f"❌ Error sending to {request_id}: {e}")
                self.disconnect(request_id)
                return False
        else:
            logger.debug(f"No active connection for {request_id}")
            return False

    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)

# Global instance
manager = ConnectionManager()