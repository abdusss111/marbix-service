# src/marbix/models/make_request.py
from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.sql import func
from marbix.db.base import Base

class MakeRequest(Base):
    __tablename__ = "make_requests"
    
    request_id = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=False)
    status = Column(String, default="processing")
    request_data = Column(JSON)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    sources = Column(Text, nullable=True)