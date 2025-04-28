from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
import os
import time
import json
import websockets
from datetime import datetime
from dotenv import load_dotenv
import aiohttp
from services.llm_service import classify_text, summarize_text, extract_metadata, title_text, detect_intent, extract_retrieval_filters
from services.memory_service import save_memory_to_db
from logging_config import logger
from websockets.exceptions import ConnectionClosed

# Load environment variables
load_dotenv()

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")

# Add these to your existing imports and globals
transcript_buffer = {}
processing_tasks = {}
last_activity = {}
PAUSE_THRESHOLD = 2  # seconds

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

            if time_since_last >= PAUSE_THRESHOLD and session_id in transcript_buffer:
                text = transcript_buffer.pop(session_id)
                asyncio.create_task(process_transcription(text))
                break

            if session_id not in transcript_buffer:
                break
    finally:
        if session_id in processing_tasks:
            del processing_tasks[session_id]

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/vapi-webhook")
async def vapi_webhook(request: VapiWebhookRequest):
    session_id = request.session_id

    if session_id not in transcript_buffer:
        transcript_buffer[session_id] = ""

    transcript_buffer[session_id] += " " + request.text if transcript_buffer[session_id] else request.text
    last_activity[session_id] = time.time()

    if session_id in processing_tasks and not processing_tasks[session_id].done():
        processing_tasks[session_id].cancel()

    processing_tasks[session_id] = asyncio.create_task(finalize_after_pause(session_id))

    return {"status": "buffered", "session_id": session_id, "current_buffer": transcript_buffer[session_id]}

@app.post("/memory/save")
async def save_memory(memory: MemoryItem):
    logger.info(f"Manually saving memory for user {memory.user_id}")
    return {"status": "saved", "memory_id": "placeholder_id"}

def format_memory_response(result: dict) -> str:
    if result["intent"] == "Save":
        return f"I've saved your {result['type'].lower()} about {result['title']}."
    elif result["intent"] == "Retrieve":
        if result["results"]:
            memories = "\n".join([f"• {m['title']}: {m['content']}" for m in result["results"][:3]])
            return f"Here are your memories:\n{memories}"
        else:
            return "I couldn't find any matching memories."
    else:
        return "I'm listening."

@app.websocket("/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(time.time())
    transcription_state = {}
    
    try:
        # Create aiohttp ClientSession and WebSocketClientProtocol
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(
                "wss://audio-streaming.us-virginia-1.direct.fireworks.ai/v1/audio/transcriptions/streaming?response_format=verbose_json&language=en",
                headers={"Authorization": FIREWORKS_API_KEY}
            ) as fw_ws:
                # Create a task to receive from Fireworks
                receive_task = asyncio.create_task(receive_from_fireworks_aiohttp(fw_ws, websocket, transcription_state))
                
                # Main loop to receive audio from client and send to Fireworks
                while True:
                    audio_data = await websocket.receive_bytes()
                    await fw_ws.send_bytes(audio_data)
                    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from WebSocket session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Clean up any tasks
        if 'receive_task' in locals():
            receive_task.cancel()

async def receive_from_fireworks_aiohttp(fw_ws, client_ws, state):
    try:
        async for msg in fw_ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                message_data = json.loads(msg.data)
                
                # Check if it's a final checkpoint
                if message_data.get("checkpoint_id") == "final":
                    await client_ws.send_text("Transcription completed")
                    break
                    
                # Update state with new segments
                if "segments" in message_data:
                    # Update state with new segments
                    for segment in message_data["segments"]:
                        state[segment["id"]] = segment["text"]
                    
                    # Construct full transcript from all segments
                    full_transcript = " ".join(state.values())
                    
                    # Send transcript to client
                    await client_ws.send_text(full_transcript)
                    logger.info(f"Transcription: {full_transcript}")
            
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(f"WebSocket error: {fw_ws.exception()}")
                break
                
    except Exception as e:
        logger.error(f"Error receiving from Fireworks: {e}", exc_info=True)

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Jarvis backend server")
    uvicorn.run(app, host="0.0.0.0", port=8000)
