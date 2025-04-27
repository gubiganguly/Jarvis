from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, DateTime, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from datetime import datetime
from enum import Enum as PyEnum
import uuid

Base = declarative_base()

class MemoryType(PyEnum):
    BUSINESS_IDEA = "Business Idea"
    TASK = "Task"
    REMINDER = "Reminder"
    NOTE = "Note"
    PLACES = "Places"
    LEARN = "Learn"
    QUESTION = "Question"

class Memory(Base):
    __tablename__ = "memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    type = Column(Enum(MemoryType), nullable=False)
    content = Column(String, nullable=False)
    title = Column(String, nullable=True)
    memory_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    vector = Column(Vector(1536))
