# backend/services/memory_service.py
from sqlalchemy import select
import os
import asyncio
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, DateTime, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

from openai import AsyncOpenAI
from dotenv import load_dotenv
from logging_config import logger

from models.memory_model import Base, Memory, MemoryType
from services.infrence.llm_service import classify_text, summarize_text, extract_metadata, title_text

# Load environment variables from .env file
load_dotenv()

# Connect to OpenAI
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# SQLAlchemy setup
DATABASE_URL = os.getenv("DATABASE_URL")  # like: postgresql+asyncpg://jarvis:jarvispassword@localhost:5432/jarvis_memory
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()


# Async function to save memory
async def save_memory_to_db(type_: str, content: str, memory_metadata: dict, user_id: str):
    logger.info(f"Saving memory to DB for user {user_id}, type: {type_}")
    async with async_session() as session:
        async with session.begin():
            try:
                # Get OpenAI embedding
                logger.debug("Generating embedding for memory content")
                embed_response = client.embeddings.create(
                    model="text-embedding-3-small",
                    input=[content]
                )
                vector = embed_response.data[0].embedding
                
                # Generate title
                memory_title = title_text(content)
                logger.debug(f"Generated title: {memory_title}")

                # Create a Memory object
                memory = Memory(
                    type=MemoryType(type_),
                    content=content,
                    title=memory_title,
                    memory_metadata=memory_metadata,
                    vector=vector,
                    user_id=user_id
                )

                # Add it to session
                session.add(memory)
                logger.info(f"Memory saved successfully with title: {memory_title}")
            except Exception as e:
                logger.error(f"Error saving memory to db: {e}", exc_info=True)
                raise

# Async function to retrieve memories
async def retrieve_memory_from_db(
    query_text: str,
    user_id: str,
    memory_type: str = None,
    date_from: datetime = None,
    date_to: datetime = None,
    top_k: int = 5
) -> list:
    """Retrieve memories from database based on semantic similarity and optional filters."""
    async with async_session() as session:
        try:
            # Step 1: Embed the query
            embed_response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=[query_text]
            )
            query_vector = embed_response.data[0].embedding

            # Step 2: Build the base select query
            stmt = select(Memory).where(Memory.user_id == user_id)

            # Step 3: Add optional filters
            if memory_type:
                stmt = stmt.where(Memory.type == MemoryType(memory_type))
            if date_from:
                stmt = stmt.where(Memory.created_at >= date_from)
            if date_to:
                stmt = stmt.where(Memory.created_at <= date_to)

            # Step 4: Order by vector similarity
            stmt = stmt.order_by(Memory.vector.l2_distance(query_vector)).limit(top_k)

            # Step 5: Execute the query
            results = await session.execute(stmt)
            memories = results.scalars().all()

            # Step 6: Format results
            memory_list = []
            for mem in memories:
                memory_list.append({
                    "id": str(mem.id),
                    "title": mem.title,
                    "type": mem.type.value,
                    "content": mem.content,
                    "memory_metadata": mem.memory_metadata,
                    "created_at": mem.created_at.isoformat()
                })

            return memory_list

        except Exception as e:
            print(f"Error retrieving memory from db: {e}")
            return []
