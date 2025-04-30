"""
ElevenLabs Text-to-Speech Service for Jarvis Voice Assistant

Provides streaming and non-streaming TTS capabilities using the ElevenLabs API.
Converts text responses into natural-sounding speech for voice interactions.
"""

import os
import asyncio
import aiohttp
from typing import AsyncGenerator, Optional
import json
from dotenv import load_dotenv
from logging_config import logger

# Load environment variables
load_dotenv(override=True)
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
ELEVEN_LABS_VOICE_ID = os.getenv("ELEVEN_LABS_VOICE_ID")

if not ELEVEN_LABS_API_KEY:
    raise ValueError("ELEVEN_LABS_API_KEY environment variable is not set")

# Default voice configuration - use the voice ID from .env if available
DEFAULT_VOICE = ELEVEN_LABS_VOICE_ID or "Adam"
API_BASE_URL = "https://api.elevenlabs.io/v1"

# Log the voice being used
logger.info(f"Using ElevenLabs voice: {DEFAULT_VOICE}")

async def text_to_speech(text: str, voice: str = DEFAULT_VOICE) -> bytes:
    """
    Convert text to speech using ElevenLabs API (non-streaming).
    
    Args:
        text: The text to convert to speech
        voice: The voice ID or name to use
        
    Returns:
        Audio data as bytes
    """
    try:
        logger.info(f"Converting to speech: {text[:50]}...")
        
        # If we're already using a voice ID from env, don't look it up
        if voice == ELEVEN_LABS_VOICE_ID and ELEVEN_LABS_VOICE_ID and len(ELEVEN_LABS_VOICE_ID) > 20:
            voice_id = voice
        else:
            # Get the voice ID if a name was provided
            voice_id = await _get_voice_id(voice)
        
        # Make the API request using aiohttp
        url = f"{API_BASE_URL}/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": ELEVEN_LABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "output_format": "mp3"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise ValueError(f"ElevenLabs API error: {response.status} - {error_text}")
                
                return await response.read()
                
    except Exception as e:
        logger.error(f"Error in text_to_speech: {e}", exc_info=True)
        raise

async def stream_speech(text: str, voice: str = DEFAULT_VOICE) -> AsyncGenerator[bytes, None]:
    """Stream text to speech using ElevenLabs API."""
    try:
        logger.info(f"Streaming speech: {text[:50]}...")
        
        # Cache voice ID lookup
        if voice == ELEVEN_LABS_VOICE_ID and ELEVEN_LABS_VOICE_ID and len(ELEVEN_LABS_VOICE_ID) > 20:
            voice_id = voice
        else:
            if not hasattr(stream_speech, "voice_id_cache"):
                stream_speech.voice_id_cache = {}
            
            if voice in stream_speech.voice_id_cache:
                voice_id = stream_speech.voice_id_cache[voice]
            else:
                voice_id = await _get_voice_id(voice)
                stream_speech.voice_id_cache[voice] = voice_id
        
        # IMPORTANT: Always use the non-streaming endpoint for consistent audio quality
        # This ensures we get a single coherent audio file rather than chunks
        audio_data = await text_to_speech(text, voice_id)
        yield b"AUDIO_FORMAT:mp3"
        yield audio_data
        return
                
    except Exception as e:
        logger.error(f"Error in stream_speech: {e}", exc_info=True)
        raise

async def get_available_voices() -> list:
    """
    Get list of available voices from ElevenLabs.
    """
    try:
        url = f"{API_BASE_URL}/voices"
        headers = {"xi-api-key": ELEVEN_LABS_API_KEY}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                voices_data = await response.json()
                
                # Check if our voice ID from .env is in the list and log its name
                if ELEVEN_LABS_VOICE_ID:
                    for voice in voices_data["voices"]:
                        if voice["voice_id"] == ELEVEN_LABS_VOICE_ID:
                            logger.info(f"Using voice: {voice['name']} (ID: {ELEVEN_LABS_VOICE_ID})")
                            break
                
                return [voice["name"] for voice in voices_data["voices"]]
                
    except Exception as e:
        logger.error(f"Error getting available voices: {e}", exc_info=True)
        return []

async def _get_voice_id(voice_name_or_id: str) -> str:
    """
    Helper function to get voice ID from name.
    Returns the input if it's already an ID or looks up the ID by name.
    """
    # Check if input looks like a voice ID (UUID format)
    if len(voice_name_or_id) > 20:
        return voice_name_or_id
    
    # If it's a name, look up the ID
    try:
        url = f"{API_BASE_URL}/voices"
        headers = {"xi-api-key": ELEVEN_LABS_API_KEY}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                voices_data = await response.json()
                
                for voice in voices_data["voices"]:
                    if voice["name"].lower() == voice_name_or_id.lower():
                        return voice["voice_id"]
                
                # If not found, return a default voice ID
                logger.warning(f"Voice '{voice_name_or_id}' not found, using default voice")
                return ELEVEN_LABS_VOICE_ID or voices_data["voices"][0]["voice_id"]
                
    except Exception as e:
        logger.error(f"Error finding voice ID: {e}", exc_info=True)
        # Return the custom voice ID if available, otherwise use Adam
        return ELEVEN_LABS_VOICE_ID or "21m00Tcm4TlvDq8ikWAM"  # Adam voice ID as fallback
