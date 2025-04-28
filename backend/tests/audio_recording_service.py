import asyncio
import websockets
import sounddevice as sd
import numpy as np
import queue

# Settings
WEBSOCKET_URL = "ws://localhost:8000/stream"
SAMPLERATE = 16000
CHANNELS = 1
BLOCKSIZE = 800  # 50ms at 16kHz

async def send_audio():
    # Use a standard Python queue for thread safety
    audio_queue = queue.Queue()
    
    async with websockets.connect(WEBSOCKET_URL) as websocket:
        print("Connected to /stream websocket.")

        # Callback to queue mic audio
        def callback(indata, frames, time, status):
            if status:
                print(status)
            # Add data to thread-safe queue
            audio_queue.put(indata.tobytes())

        # Producer coroutine to send audio data
        async def send_audio_data():
            while True:
                # Non-blocking check for data
                if not audio_queue.empty():
                    try:
                        data = audio_queue.get_nowait()
                        await websocket.send(data)
                    except queue.Empty:
                        pass
                # Small sleep to prevent CPU hogging
                await asyncio.sleep(0.001)
        
        # Start consumer task
        send_task = asyncio.create_task(send_audio_data())
        
        try:
            # Start recording
            with sd.InputStream(samplerate=SAMPLERATE, channels=CHANNELS, 
                              blocksize=BLOCKSIZE, dtype='int16', callback=callback):
                print("Recording... (speak into your mic)")
                while True:
                    response = await websocket.recv()
                    print("[Transcription]", response)
        except websockets.ConnectionClosed:
            print("WebSocket connection closed")
        finally:
            # Cancel the task properly
            send_task.cancel()
            try:
                await send_task  # Wait for cancellation to complete
            except asyncio.CancelledError:
                print("Audio sending task cancelled")

if __name__ == "__main__":
    asyncio.run(send_audio())
