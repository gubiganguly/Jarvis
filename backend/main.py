from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import asyncio
import time
import os
from datetime import datetime
from services.llm_service import classify_text, summarize_text, extract_metadata, title_text, detect_intent, extract_retrieval_filters
from services.memory_service import save_memory_to_db
from logging_config import logger

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

app = FastAPI(title="VAPI Integration API")

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request validation
class VapiWebhookRequest(BaseModel):
    session_id: str
    text: str

class MemoryItem(BaseModel):
    content: str
    user_id: str
    metadata: Optional[Dict[str, Any]] = None

# In-memory buffer to store transcriptions by session_id
transcript_buffer = {}
last_activity = {}
processing_tasks = {}
PAUSE_THRESHOLD = 3  # seconds


async def process_transcription(text: str) -> dict:
    """Process finalized transcription: detect intent and either save or retrieve memories."""
    try:
        logger.info(f"Processing transcription: {text[:50]}...")
        
        # Step 1: Detect Intent
        intent = detect_intent(text)
        logger.info(f"Detected intent: {intent}")

        if intent == "Save":
            # Step 2: Saving a new memory
            logger.debug("Starting classification process")
            classification = classify_text(text)
            summary = summarize_text(text)
            memory_title = title_text(text)
            memory_metadata = extract_metadata(text)

            organized_output = {
                "intent": "Save",
                "type": classification,
                "content": summary,
                "title": memory_title,
                "memory_metadata": memory_metadata
            }

            logger.info(f"Saving memory: {organized_output['title']}")
            logger.debug(f"Memory details: {organized_output}")

            await save_memory_to_db(
                type_=classification,
                content=summary,
                memory_metadata=memory_metadata,
                user_id="00000000-0000-0000-0000-000000000001"
            )

            return organized_output

        elif intent == "Retrieve":
            # Step 3: Retrieval intent
            logger.info("Retrieving memories")

            filters = extract_retrieval_filters(text)
            logger.debug(f"Extracted retrieval filters: {filters}")

            # Optional: parse dates properly if present
            date_from = None
            date_to = None
            if filters.get("date_from"):
                date_from = datetime.fromisoformat(filters["date_from"])
            if filters.get("date_to"):
                date_to = datetime.fromisoformat(filters["date_to"])

            # Call retrieval
            from services.memory_service import retrieve_memory_from_db  # Import here to avoid circular imports
            memories = await retrieve_memory_from_db(
                query_text=text,
                user_id="00000000-0000-0000-0000-000000000001",
                memory_type=filters.get("memory_type"),
                date_from=date_from,
                date_to=date_to,
                top_k=5
            )
            
            logger.info(f"Retrieved {len(memories)} memories")
            logger.debug(f"Retrieved memories: {memories}")

            return {
                "intent": "Retrieve",
                "query": text,
                "filters": filters,
                "results": memories
            }

        else:
            # Step 4: Neither - ignore
            logger.info("Intent was Neither, doing nothing.")
            return {"intent": "Neither", "message": "No memory action needed."}

    except Exception as e:
        logger.error(f"Error processing transcription: {e}", exc_info=True)
        return {"error": str(e)}




async def finalize_after_pause(session_id: str):
    """Wait for pause in speech then process accumulated text."""
    try:
        logger.debug(f"Starting finalization watch for session {session_id}")
        while True:
            await asyncio.sleep(1)
            time_since_last = time.time() - last_activity.get(session_id, 0)

            if time_since_last >= PAUSE_THRESHOLD and session_id in transcript_buffer:
                text = transcript_buffer.pop(session_id)
                logger.info(f"Pause detected, finalizing session {session_id} with {len(text)} chars")
                asyncio.create_task(process_transcription(text))
                break

            if session_id not in transcript_buffer:
                logger.debug(f"Session {session_id} buffer empty, stopping watch")
                break
    finally:
        if session_id in processing_tasks:
            del processing_tasks[session_id]
            logger.debug(f"Removed processing task for session {session_id}")

# Routes
@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    logger.debug("Health check requested")
    return {"status": "ok"}

@app.post("/vapi-webhook")
async def vapi_webhook(request: VapiWebhookRequest):
    """Handle incoming transcription chunks from VAPI."""
    session_id = request.session_id
    
    logger.info(f"Received webhook for session {session_id}: '{request.text}'")
    
    # Update or initialize the buffer for this session
    if session_id not in transcript_buffer:
        transcript_buffer[session_id] = ""
        logger.debug(f"New session buffer created for {session_id}")
    
    # Append new text to the buffer
    transcript_buffer[session_id] += " " + request.text if transcript_buffer[session_id] else request.text
    
    # Update last activity timestamp
    last_activity[session_id] = time.time()
    
    # Start or restart the finalization task
    if session_id in processing_tasks and not processing_tasks[session_id].done():
        processing_tasks[session_id].cancel()
        logger.debug(f"Canceled existing processing task for session {session_id}")
    
    processing_tasks[session_id] = asyncio.create_task(finalize_after_pause(session_id))
    logger.debug(f"Started new finalization task for session {session_id}")
    
    return {"status": "buffered", "session_id": session_id, "current_buffer": transcript_buffer[session_id]}

@app.post("/memory/save")
async def save_memory(memory: MemoryItem):
    """Store user memory content for later retrieval."""
    logger.info(f"Manual memory save request for user {memory.user_id}")
    logger.debug(f"Memory content: {memory.content[:50]}...")
    # Save user memory
    # In the future, this would use a service to persist data
    return {"status": "saved", "memory_id": "placeholder_id"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Jarvis backend server")
    uvicorn.run(app, host="0.0.0.0", port=8000) 