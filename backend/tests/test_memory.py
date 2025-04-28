# backend/test_save_memory.py

import asyncio
import sys
import os

# Add parent directory to path so we can import main
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import process_transcription

async def test_memory_save():
    # Simulate fake voice input
    fake_transcription = "I want to start a voicebot agency for dentists."

    # Await the async function
    organized_output = await process_transcription(fake_transcription)

    print("Processed memory (save):", organized_output)

async def test_memory_retrieve():
    # Simulate fake voice input
    fake_transcription = "What ideas did I have this week?"

    # Await the async function
    organized_output = await process_transcription(fake_transcription)

    print("Processed memory (retrieve):", organized_output)

if __name__ == "__main__":
    # Uncomment one of these to test

    # asyncio.run(test_memory_save())
    asyncio.run(test_memory_retrieve())
