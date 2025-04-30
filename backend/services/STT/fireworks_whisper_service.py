import json
import time
import asyncio
import aiohttp
from logging_config import logger
from typing import Dict, Set, Optional, Tuple, AsyncGenerator

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

# Constants
PAUSE_THRESHOLD = 1  # seconds - reduced from 2s
SILENCE_THRESHOLD = 2  # seconds for a new utterance - reduced from 3s

async def create_stt_connection(api_key: str):
    """Create a WebSocket connection to Fireworks AI STT service"""
    session = aiohttp.ClientSession()
    ws = await session.ws_connect(
        "wss://audio-streaming.us-virginia-1.direct.fireworks.ai/v1/audio/transcriptions/streaming?response_format=verbose_json&language=en",
        headers={"Authorization": api_key}
    )
    return session, ws

async def receive_from_fireworks(
    fw_ws, 
    client_ws, 
    session_id: str,
    current_utterances: Dict[str, Utterance],
    utterance_counter: Dict[str, int],
    processed_segment_ids: Dict[str, Set[str]],
    last_activity: Dict[str, float]
):
    """Handle receiving transcriptions from Fireworks AI"""
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
                    
                    if should_create_new_utterance(time_since_last, current_utterance):
                        # Process the current utterance before starting a new one
                        if not current_utterance.processed:
                            current_utterance.end_time = now
                            # Force processing
                            last_activity[session_id] = now - PAUSE_THRESHOLD - 0.1
                            
                            # Wait briefly for processing to complete
                            await asyncio.sleep(0.2)
                        
                        # Create a new utterance
                        utterance_counter[session_id] += 1
                        current_utterances[session_id] = Utterance(utterance_counter[session_id])
                        current_utterance = current_utterances[session_id]
                        logger.info(f"New utterance detected after {time_since_last:.2f}s silence (#{current_utterance.id})")
                    
                    last_transcript_time = now
                    
                    # Process the segments
                    process_segments(
                        message_data["segments"], 
                        current_utterance, 
                        processed_segment_ids.get(session_id, set())
                    )
                    
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

def should_create_new_utterance(time_since_last: float, current_utterance: Utterance) -> bool:
    """Determine if we should start a new utterance based on silence duration"""
    return time_since_last > SILENCE_THRESHOLD and current_utterance.text.strip()

def process_segments(segments: list, utterance: Utterance, processed_ids: Set[str]) -> None:
    """Process transcription segments and update the utterance"""
    new_segments = {}
    for segment in segments:
        segment_id = segment["id"]
        
        # Only consider segments not processed in previous utterances
        if segment_id not in processed_ids:
            new_segments[segment_id] = segment["text"]
            # Track segment for this utterance
            utterance.segment_ids.add(segment_id)
    
    # Update utterance with new segments
    utterance.segments.update(new_segments)
    
    # Reconstruct the text only from segments belonging to this utterance
    utterance.text = " ".join(utterance.segments.values())

async def stream_audio_to_stt(fw_ws, audio_data: bytes) -> None:
    """Stream audio data to the STT service"""
    await fw_ws.send_bytes(audio_data)

async def detect_pause_and_finalize(
    session_id: str,
    current_utterances: Dict[str, Utterance],
    last_activity: Dict[str, float],
    process_callback
):
    """Monitor for pauses and call processing callback when utterance is complete"""
    try:
        check_interval = 0.2  # Check more frequently (was 1s)
        while True:
            await asyncio.sleep(check_interval)
            time_since_last = time.time() - last_activity.get(session_id, 0)

            if time_since_last >= PAUSE_THRESHOLD and session_id in current_utterances:
                utterance = current_utterances[session_id]
                
                if not utterance.processed and utterance.text.strip():
                    # Mark as processed to prevent duplicate processing
                    utterance.processed = True
                    utterance.end_time = time.time()
                    
                    # Call the processing callback with the finalized utterance
                    await process_callback(utterance)
            
            if session_id not in current_utterances:
                break
                
    except Exception as e:
        logger.error(f"Error in detect_pause_and_finalize: {e}", exc_info=True)
