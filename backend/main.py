from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List, Set
import asyncio
import os
import time
import json
import websockets
from datetime import datetime
from dotenv import load_dotenv
import aiohttp
from services.llm_service import classify_text, summarize_text, extract_metadata, title_text, detect_intent, extract_retrieval_filters, generate_conversational_response
from services.memory_service import save_memory_to_db
from logging_config import logger
from websockets.exceptions import ConnectionClosed

# Load environment variables
load_dotenv()
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")

# Utterance tracking structures
class Utterance:
    def __init__(self, id: int):
        self.id = id
        self.start_time = time.time()
        self.end_time = None
        self.segments = {}  # Store segments by ID
        self.segment_ids = set()  # Track which segment IDs belong to this utterance
        self.text = ""
        self.response = ""
        self.processed = False

# Global state tracking
processing_tasks = {}
last_activity = {}
utterance_counter = {}  # Track utterance count per session
conversation_history = {}  # Store complete conversation history
current_utterances = {}  # Track current utterance per session
processed_segment_ids = {}  # Track which segment IDs have been processed per session
PAUSE_THRESHOLD = 2  # seconds
SILENCE_THRESHOLD = 3  # seconds for a new utterance

app = FastAPI(title="Jarvis Backend API")

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class VapiWebhookRequest(BaseModel):
    session_id: str
    text: str

class MemoryItem(BaseModel):
    content: str
    user_id: str
    metadata: Optional[Dict[str, Any]] = None

class ConversationTurn(BaseModel):
    utterance: str
    response: str
    timestamp: datetime

async def process_transcription(text: str) -> dict:
    try:
        logger.info(f"Processing transcription: {text[:50]}...")

        intent = detect_intent(text)
        logger.info(f"Detected intent: {intent}")

        if intent == "Save":
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

            await save_memory_to_db(
                type_=classification,
                content=summary,
                memory_metadata=memory_metadata,
                user_id="00000000-0000-0000-0000-000000000001"
            )

            return organized_output

        elif intent == "Retrieve":
            filters = extract_retrieval_filters(text)
            from services.memory_service import retrieve_memory_from_db

            date_from = None
            date_to = None
            if filters.get("date_from"):
                date_from = datetime.fromisoformat(filters["date_from"])
            if filters.get("date_to"):
                date_to = datetime.fromisoformat(filters["date_to"])

            memories = await retrieve_memory_from_db(
                query_text=text,
                user_id="00000000-0000-0000-0000-000000000001",
                memory_type=filters.get("memory_type"),
                date_from=date_from,
                date_to=date_to,
                top_k=5
            )

            return {
                "intent": "Retrieve",
                "query": text,
                "filters": filters,
                "results": memories
            }

        else:
            return {"intent": "Neither", "message": "No memory action needed."}

    except Exception as e:
        logger.error(f"Error processing transcription: {e}", exc_info=True)
        return {"error": str(e)}


async def finalize_after_pause(session_id: str):
    try:
        while True:
            await asyncio.sleep(1)
            time_since_last = time.time() - last_activity.get(session_id, 0)

            if time_since_last >= PAUSE_THRESHOLD and session_id in current_utterances:
                utterance = current_utterances[session_id]
                
                if not utterance.processed and utterance.text.strip():
                    # Mark as processed to prevent duplicate processing
                    utterance.processed = True
                    utterance.end_time = time.time()
                    
                    # Get the final text of this utterance
                    text = utterance.text
                    
                    # Process the transcription
                    result = await process_transcription(text)
                    logger.info(f"Processing result: {result}")
                    
                    # Enhanced logging for retrieve intent
                    if result.get("intent") == "Retrieve" and "results" in result:
                        logger.info("Retrieved memories:")
                        for i, memory in enumerate(result["results"]):
                            logger.info(f"Memory {i+1}:")
                            logger.info(f"  Title: {memory.get('title')}")
                            logger.info(f"  Type: {memory.get('type')}")
                            logger.info(f"  Content: {memory.get('content')}")
                            logger.info(f"  Created: {memory.get('created_at')}")
                            logger.info(f"  Metadata: {memory.get('memory_metadata')}")
                    
                    # Generate conversational response - pass original text too
                    response = generate_conversational_response(result, text)
                    logger.info(f"Conversational response: {response}")
                    
                    # Store the response in the utterance object
                    utterance.response = response
                    
                    # Add to conversation history
                    if session_id not in conversation_history:
                        conversation_history[session_id] = []
                    
                    conversation_history[session_id].append(
                        ConversationTurn(
                            utterance=text,
                            response=response,
                            timestamp=datetime.now()
                        )
                    )
                    
                    # Add this utterance's segment IDs to processed_segment_ids
                    if session_id not in processed_segment_ids:
                        processed_segment_ids[session_id] = set()
                    processed_segment_ids[session_id].update(utterance.segment_ids)
                    
                    # Prepare for next utterance
                    utterance_counter[session_id] += 1
                    current_utterances[session_id] = Utterance(utterance_counter[session_id])
                    
                    logger.info(f"Reset transcription state for session {session_id} after processing")
                    logger.info(f"Processed segment IDs: {processed_segment_ids[session_id]}")
            
            if session_id not in current_utterances:
                break
    except Exception as e:
        logger.error(f"Error in finalize_after_pause: {e}", exc_info=True)
    finally:
        if session_id in processing_tasks:
            del processing_tasks[session_id]

@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(time.time())
    
    # Initialize session tracking structures
    utterance_counter[session_id] = 0
    current_utterances[session_id] = Utterance(0)  # First utterance
    conversation_history[session_id] = []
    processed_segment_ids[session_id] = set()
    last_activity[session_id] = time.time()
    
    try:
        # Start pause detection task
        processing_tasks[session_id] = asyncio.create_task(finalize_after_pause(session_id))
        
        # Create aiohttp ClientSession and WebSocketClientProtocol
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                "wss://audio-streaming.us-virginia-1.direct.fireworks.ai/v1/audio/transcriptions/streaming?response_format=verbose_json&language=en",
                headers={"Authorization": FIREWORKS_API_KEY}
            ) as fw_ws:
                # Create a task to receive from Fireworks
                receive_task = asyncio.create_task(
                    receive_from_fireworks_aiohttp(fw_ws, websocket, session_id)
                )
                
                # Main loop to receive audio from client and send to Fireworks
                while True:
                    audio_data = await websocket.receive_bytes()
                    await fw_ws.send_bytes(audio_data)
                    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from WebSocket session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Clean up tasks and session data
        if 'receive_task' in locals():
            receive_task.cancel()
        if session_id in processing_tasks:
            processing_tasks[session_id].cancel()
            del processing_tasks[session_id]
        if session_id in utterance_counter:
            del utterance_counter[session_id]
        if session_id in current_utterances:
            del current_utterances[session_id]
        if session_id in processed_segment_ids:
            del processed_segment_ids[session_id]
        if session_id in conversation_history:
            # Could persist conversation history to database here
            del conversation_history[session_id]
        if session_id in last_activity:
            del last_activity[session_id]

async def receive_from_fireworks_aiohttp(fw_ws, client_ws, session_id):
    last_transcript_time = time.time()
    
    try:
        async for msg in fw_ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                message_data = json.loads(msg.data)
                now = time.time()
                
                # Check if it's a final checkpoint
                if message_data.get("checkpoint_id") == "final":
                    await client_ws.send_text("Transcription completed")
                    break
                    
                # Process segments from Fireworks
                if "segments" in message_data:
                    # Check if we should start a new utterance due to silence
                    time_since_last = now - last_transcript_time
                    current_utterance = current_utterances[session_id]
                    
                    if time_since_last > SILENCE_THRESHOLD and current_utterance.text.strip():
                        # Process the current utterance before starting a new one
                        if not current_utterance.processed:
                            current_utterance.end_time = now
                            # Let finalize_after_pause handle the processing
                            last_activity[session_id] = now - PAUSE_THRESHOLD - 0.1  # Force processing
                            
                            # Wait briefly for processing to complete
                            await asyncio.sleep(0.2)
                        
                        # Create a new utterance
                        utterance_counter[session_id] += 1
                        current_utterances[session_id] = Utterance(utterance_counter[session_id])
                        current_utterance = current_utterances[session_id]
                        logger.info(f"New utterance detected after {time_since_last:.2f}s silence (#{current_utterance.id})")
                    
                    last_transcript_time = now
                    
                    # Filter out already processed segments
                    new_segments = {}
                    for segment in message_data["segments"]:
                        segment_id = segment["id"]
                        
                        # Only consider segments not processed in previous utterances
                        if segment_id not in processed_segment_ids.get(session_id, set()):
                            new_segments[segment_id] = segment["text"]
                            # Track segment for this utterance
                            current_utterance.segment_ids.add(segment_id)
                    
                    # Update utterance with new segments
                    current_utterance.segments.update(new_segments)
                    
                    # Reconstruct the text only from segments belonging to this utterance
                    current_utterance.text = " ".join(current_utterance.segments.values())
                    
                    # Update last activity time
                    last_activity[session_id] = time.time()
                    
                    # Send current utterance text to client
                    await client_ws.send_text(current_utterance.text)
                    logger.info(f"Utterance #{current_utterance.id}: {current_utterance.text}")
            
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {fw_ws.exception()}")
                break
                
    except Exception as e:
        logger.error(f"Error receiving from Fireworks: {e}", exc_info=True)

async def process_utterance(text, session_id):
    try:
        if text.strip():
            logger.info(f"Processing utterance: {text[:50]}...")
            result = await process_transcription(text)
            logger.info(f"Utterance processing result: {result}")
            
            # Generate conversational response
            response = generate_conversational_response(result, text)
            logger.info(f"Conversational response for utterance: {response}")
            
            return response
    except Exception as e:
        logger.error(f"Error processing utterance: {e}", exc_info=True)
        return None

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Jarvis backend server")
    uvicorn.run(app, host="0.0.0.0", port=8000)
