from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List, Set
import asyncio
import os
import time
import json
from datetime import datetime
from dotenv import load_dotenv
import aiohttp
from services.infrence.llm_service import classify_text, summarize_text, extract_metadata, title_text, detect_intent, extract_retrieval_filters, generate_conversational_response, generate_conversational_response_streaming
from services.memory.memory_service import save_memory_to_db
from logging_config import logger
from websockets.exceptions import ConnectionClosed
from services.TTS.eleven_labs_service import stream_speech
from services.STT.fireworks_whisper_service import Utterance, create_stt_connection, receive_from_fireworks, stream_audio_to_stt, detect_pause_and_finalize

# Load environment variables
load_dotenv()
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")

# Global state tracking
processing_tasks = {}
last_activity = {}
utterance_counter = {}  # Track utterance count per session
conversation_history = {}  # Store complete conversation history
current_utterances = {}  # Track current utterance per session
processed_segment_ids = {}  # Track which segment IDs have been processed per session
connected_websockets = {}  # Track WebSocket connections by session_id

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
class ConversationTurn(BaseModel):
    utterance: str
    response: str
    timestamp: datetime

async def process_transcription(text: str) -> dict:
    try:
        logger.info(f"Processing transcription: {text[:50]}...")

        # First determine intent - this needs to happen first
        intent = await detect_intent(text)
        logger.info(f"Detected intent: {intent}")

        if intent == "Save":
            # Run classification, summarization, title, and metadata extraction in parallel
            classification_task = classify_text(text)
            summary_task = summarize_text(text)
            title_task = title_text(text)
            metadata_task = extract_metadata(text)
            
            # Wait for all tasks to complete
            classification, summary, memory_title, memory_metadata = await asyncio.gather(
                classification_task, summary_task, title_task, metadata_task
            )
            
            logger.info(f"Classified as: {classification}")
            logger.info(f"Generated title: {memory_title}")

            organized_output = {
                "intent": "Save",
                "type": classification,
                "content": summary,
                "title": memory_title,
                "memory_metadata": memory_metadata
            }

            # This DB operation can run in the background
            # We don't need to wait for it to complete before responding
            asyncio.create_task(save_memory_to_db(
                type_=classification,
                content=summary,
                memory_metadata=memory_metadata,
                user_id="00000000-0000-0000-0000-000000000001"
            ))

            return organized_output

        elif intent == "Retrieve":
            # Extract filters and retrieve memories in parallel
            filters = await extract_retrieval_filters(text)
            from services.memory.memory_service import retrieve_memory_from_db

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

async def process_utterance_callback(utterance, session_id):
    """Callback for processing complete utterances"""
    try:
        # Get the final text of this utterance
        text = utterance.text
        
        # Process the transcription
        result = await process_transcription(text)
        logger.info(f"Processing result: {result}")
        
        # Generate streaming conversational response
        response_stream = await generate_conversational_response_streaming(result, text)
        
        # Handle special string case (for Retrieve with no results)
        if isinstance(response_stream, str):
            response_buffer = response_stream
            
            # Store response
            utterance.response = response_buffer
            
            # Send to client
            if session_id in connected_websockets:
                websocket = connected_websockets[session_id]
                await websocket.send_text(response_buffer)
                
                # Full response as one audio file
                async for audio_chunk in stream_speech(response_buffer):
                    try:
                        await websocket.send_bytes(audio_chunk)
                    except Exception as e:
                        logger.error(f"Error sending audio chunk: {e}")
                        break
        else:
            # Create buffer for partial responses
            response_buffer = ""
            sentence_buffer = ""
            last_tts_time = time.time()
            
            # Stream to client as chunks arrive
            if session_id in connected_websockets:
                websocket = connected_websockets[session_id]
                
                # Stream the response chunks
                async for chunk in response_stream:
                    if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                        content = chunk.choices[0].delta.content
                        if content:
                            response_buffer += content
                            sentence_buffer += content
                            
                            # Send text to client
                            await websocket.send_text(content)
                            
                            # Check for complete sentences
                            sentence_complete = False
                            for ending in [".", "!", "?", ":", ";"]:
                                if ending in sentence_buffer[-3:] and len(sentence_buffer) > 20:
                                    sentence_complete = True
                                    break
                            
                            # Process only complete sentences or large chunks
                            now = time.time()
                            if sentence_complete or len(sentence_buffer) > 150 or (now - last_tts_time > 3.5 and len(sentence_buffer) > 50):
                                # Ensure we have a complete sentence when possible
                                if not sentence_complete and "," in sentence_buffer:
                                    # Try to break at a comma if no sentence end is found
                                    last_comma = sentence_buffer.rfind(",")
                                    if last_comma > len(sentence_buffer) // 2:
                                        # Only use comma if it's in the latter half
                                        speak_chunk = sentence_buffer[:last_comma+1]
                                        sentence_buffer = sentence_buffer[last_comma+1:]
                                    else:
                                        speak_chunk = sentence_buffer
                                        sentence_buffer = ""
                                else:
                                    speak_chunk = sentence_buffer
                                    sentence_buffer = ""
                                
                                if speak_chunk.strip():
                                    logger.info(f"TTS: {speak_chunk[:40]}...")
                                    # Generate a single coherent audio file
                                    async for audio_chunk in stream_speech(speak_chunk):
                                        try:
                                            await websocket.send_bytes(audio_chunk)
                                        except Exception as e:
                                            logger.error(f"Error sending audio chunk: {e}")
                                            break
                                
                                last_tts_time = now
                
                # Process any remaining text
                if sentence_buffer.strip():
                    logger.info(f"TTS final: {sentence_buffer[:40]}...")
                    async for audio_chunk in stream_speech(sentence_buffer):
                        try:
                            await websocket.send_bytes(audio_chunk)
                        except Exception as e:
                            logger.error(f"Error sending audio chunk: {e}")
                
                # Store the full response
                utterance.response = response_buffer
        
        # Add to conversation history
        if session_id not in conversation_history:
            conversation_history[session_id] = []
        
        conversation_history[session_id].append(
            ConversationTurn(
                utterance=text,
                response=utterance.response,
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
        
    except Exception as e:
        logger.error(f"Error in process_utterance_callback: {e}", exc_info=True)

async def finalize_after_pause(session_id: str):
    """Start the pause detection process that will finalize utterances"""
    try:
        async def callback(utterance):
            await process_utterance_callback(utterance, session_id)
            
        await detect_pause_and_finalize(
            session_id,
            current_utterances,
            last_activity,
            callback
        )
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
    
    # Store the WebSocket connection
    connected_websockets[session_id] = websocket
    
    # Initialize session tracking structures
    utterance_counter[session_id] = 0
    current_utterances[session_id] = Utterance(0)  # First utterance
    conversation_history[session_id] = []
    processed_segment_ids[session_id] = set()
    last_activity[session_id] = time.time()
    
    try:
        # Start pause detection task
        processing_tasks[session_id] = asyncio.create_task(finalize_after_pause(session_id))
        
        # Create connection to Fireworks STT service
        session, fw_ws = await create_stt_connection(FIREWORKS_API_KEY)
        
        # Create a task to receive from Fireworks
        receive_task = asyncio.create_task(
            receive_from_fireworks(
                fw_ws, 
                websocket, 
                session_id, 
                current_utterances, 
                utterance_counter, 
                processed_segment_ids, 
                last_activity
            )
        )
        
        # Main loop to receive audio from client and send to Fireworks
        while True:
            audio_data = await websocket.receive_bytes()
            await stream_audio_to_stt(fw_ws, audio_data)
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected from WebSocket session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Clean up tasks and session data
        if 'receive_task' in locals():
            receive_task.cancel()
        if 'session' in locals():
            await session.close()
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
        if session_id in connected_websockets:
            del connected_websockets[session_id]

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Jarvis backend server")
    uvicorn.run(app, host="0.0.0.0", port=8000)
