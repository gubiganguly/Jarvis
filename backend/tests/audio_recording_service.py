import asyncio
import websockets
import sounddevice as sd
import numpy as np
import queue
import io
import tempfile
import os
import subprocess
from pydub import AudioSegment
from pydub.playback import play

# Settings
WEBSOCKET_URL = "ws://localhost:8000/stream"
SAMPLERATE = 16000
CHANNELS = 1
BLOCKSIZE = 800  # 50ms at 16kHz

async def send_audio():
    # Thread-safe queue for audio data
    audio_queue = queue.Queue()
    
    # Flag to control recording state
    is_listening = True
    
    # Buffer for collecting audio chunks
    audio_buffer = bytearray()
    audio_format = None
    
    async with websockets.connect(WEBSOCKET_URL) as websocket:
        print("Connected to Jarvis voice assistant.")

        # Callback to queue microphone audio
        def audio_callback(indata, frames, time, status):
            if status:
                print(f"Status: {status}")
            
            # Only capture audio when we're not playing a response
            if is_listening:
                audio_queue.put(indata.tobytes())

        # Task to send audio data to server
        async def send_audio_data():
            while True:
                if not audio_queue.empty() and is_listening:
                    try:
                        data = audio_queue.get_nowait()
                        await websocket.send(data)
                    except queue.Empty:
                        pass
                await asyncio.sleep(0.001)

        # Start the sending task
        send_task = asyncio.create_task(send_audio_data())
        
        try:
            # Start microphone stream
            with sd.InputStream(
                samplerate=SAMPLERATE, 
                channels=CHANNELS,
                blocksize=BLOCKSIZE, 
                dtype='int16', 
                callback=audio_callback
            ):
                print("🎤 Listening... (speak to Jarvis)")
                
                while True:
                    # Receive data from server
                    response = await websocket.recv()
                    
                    if isinstance(response, str):
                        # Text transcription or response
                        print(f"🔤 [{response}]")
                    else:
                        # Check if this is a format indicator message
                        if response.startswith(b"AUDIO_FORMAT:"):
                            # Extract the format
                            audio_format = response[13:].decode('utf-8')
                            print(f"🔊 Receiving audio in {audio_format} format...")
                            # Clear the buffer for a new audio stream
                            audio_buffer = bytearray()
                        else:
                            # Add to buffer
                            audio_buffer.extend(response)
                            
                            # If this seems to be the last chunk (usually larger)
                            if len(response) > 1000:
                                # Pause microphone capture while playing
                                is_listening = False
                                
                                try:
                                    # Save buffer to temporary file
                                    with tempfile.NamedTemporaryFile(suffix=f'.{audio_format}', delete=False) as temp_file:
                                        temp_path = temp_file.name
                                        temp_file.write(audio_buffer)
                                    
                                    print(f"🔊 Playing {len(audio_buffer)} bytes of audio...")
                                    
                                    # Play the audio file using a subprocess
                                    if os.name == 'posix':  # macOS/Linux
                                        subprocess.run(['afplay' if 'darwin' in os.uname().sysname.lower() else 'aplay', temp_path])
                                    else:  # Windows
                                        os.startfile(temp_path)
                                        
                                    # Clean up
                                    os.unlink(temp_path)
                                    
                                except Exception as e:
                                    print(f"Error playing audio: {e}")
                                
                                # Clear buffer for next audio
                                audio_buffer = bytearray()
                                
                                # Resume microphone capture
                                is_listening = True
                                print("🎤 Listening again...")
                        
        except websockets.ConnectionClosed:
            print("Connection closed")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            # Clean up
            send_task.cancel()
            try:
                await send_task
            except asyncio.CancelledError:
                pass
            print("Disconnected from Jarvis")

if __name__ == "__main__":
    print("Starting Jarvis voice conversation client...")
    try:
        asyncio.run(send_audio())
    except KeyboardInterrupt:
        print("Exiting...")
