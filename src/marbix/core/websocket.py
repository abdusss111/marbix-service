# src/marbix/core/websocket.py
from typing import Dict
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, request_id: str):
        """Accept and store a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[request_id] = websocket
        logger.info(f"WebSocket connected for request_id: {request_id}")

    def disconnect(self, request_id: str):
        """Remove a WebSocket connection"""
        if request_id in self.active_connections:
            del self.active_connections[request_id]
            logger.info(f"WebSocket disconnected for request_id: {request_id}")

    async def send_message(self, request_id: str, message: dict):
        """Send a message to a specific WebSocket connection"""
        if request_id in self.active_connections:
            websocket = self.active_connections[request_id]
            try:
                await websocket.send_json(message)
                logger.info(f"Message sent to request_id: {request_id}")
            except Exception as e:
                logger.error(f"Error sending message to {request_id}: {e}")
                self.disconnect(request_id)

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

# Global instance
manager = ConnectionManager()