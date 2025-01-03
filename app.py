import os
import random
import subprocess
from threading import Thread, Lock
from queue import Queue
from flask import Flask, Response
import time
import hashlib

# Initialize Flask
app = Flask(__name__)

# Directory for MP3 files
MUSIC_DIR = 'music/'
CACHE_DIR = 'cached_music/'
CURRENT_SONG = None
FFMPEG_PROCESS = None
IS_RUNNING = True
BUFFER_SIZE = 12 * 1024  # 64 KB buffer
clients = []  # List of connected clients
clients_lock = Lock()  # Lock for thread-safe client list management
TARGET_BITRATE = '256k'


def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)


def get_cache_path(original_path):
    # Create unique filename based on original file path
    file_hash = hashlib.md5(original_path.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{file_hash}.mp3")


def process_song(filepath):
    cache_path = get_cache_path(filepath)
    
    # Skip if already cached
    if os.path.exists(cache_path):
        return cache_path
        
    print(f"Processing {filepath} to {TARGET_BITRATE}")
    cmd = [
        'ffmpeg', '-i', filepath,
        '-c:a', 'libmp3lame',
        '-b:a', TARGET_BITRATE,
        '-y',  # Overwrite output files
        cache_path
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return cache_path
    except subprocess.CalledProcessError as e:
        print(f"Error processing {filepath}: {e}")
        return None


def preprocess_all_songs():
    ensure_cache_dir()
    files = [os.path.join(MUSIC_DIR, f) for f in os.listdir(MUSIC_DIR) if f.endswith('.mp3')]
    processed_files = []
    
    print("Processing all songs to normalized bitrate...")
    for filepath in files:
        cached_path = process_song(filepath)
        if cached_path:
            processed_files.append(cached_path)
    
    print(f"Processed {len(processed_files)} songs")
    return processed_files


# Function to get a random MP3 file
def get_random_mp3():
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.mp3')]
    return random.choice(files)


# Function to manage server-side playback
def playback_manager():
    global CURRENT_SONG, FFMPEG_PROCESS, IS_RUNNING

    while IS_RUNNING:
        try:
            if FFMPEG_PROCESS is None or FFMPEG_PROCESS.poll() is not None:
                # Select a new random song and start playback
                CURRENT_SONG = get_random_mp3()
                print(f"Now playing: {CURRENT_SONG}")

                cmd = [
                    'ffmpeg', '-re', '-i', os.path.join(CACHE_DIR, CURRENT_SONG),
                    '-f', 'mp3', '-content_type', 'audio/mpeg', 'pipe:1'
                ]
                if FFMPEG_PROCESS:
                    FFMPEG_PROCESS.terminate()
                    FFMPEG_PROCESS.wait()
                
                FFMPEG_PROCESS = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

            # Continuously read audio data and broadcast it to all clients
            chunk = FFMPEG_PROCESS.stdout.read(BUFFER_SIZE)
            if chunk:
                broadcast_to_clients(chunk)
            else:
                # End of song, don't break the loop
                continue
        except Exception as e:
            print(f"Error in playback manager: {e}")
            time.sleep(1)  # Prevent rapid spinning if there's an error
            continue


# Function to broadcast data to all connected clients
def broadcast_to_clients(chunk):
    with clients_lock:
        for client in clients[:]:  # Iterate over a copy of the list
            try:
                client['queue'].put_nowait(chunk)
            except:
                # If queue is full or client is disconnected, remove it
                try:
                    clients.remove(client)
                except ValueError:
                    pass


# Route to stream the ongoing playback to clients
@app.route('/radio')
def radio():
    def generate(client):
        try:
            while IS_RUNNING:
                try:
                    chunk = client['queue'].get(timeout=5)
                    if chunk:
                        yield chunk
                except Queue.Empty:
                    continue
                except Exception as e:
                    print(f"Error in generator: {e}")
                    break
        finally:
            # Cleanup when the client disconnects
            with clients_lock:
                try:
                    clients.remove(client)
                    print("Client disconnected, cleanup done")
                except ValueError:
                    pass

    # Register the new client with a Queue
    client = {'queue': Queue(maxsize=100)}
    with clients_lock:
        clients.append(client)
        print(f"New client connected. Total clients: {len(clients)}")

    return Response(
        generate(client),
        content_type="audio/mpeg",
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


# Graceful shutdown route
@app.route('/shutdown', methods=['POST'])
def shutdown():
    global IS_RUNNING
    IS_RUNNING = False
    if FFMPEG_PROCESS:
        FFMPEG_PROCESS.terminate()
    return "Server shutting down..."


# Start the playback manager thread when the server starts
def start_playback_manager():
    playback_thread = Thread(target=playback_manager, daemon=True)
    playback_thread.start()


if __name__ == '__main__':
    try:
        # Process all songs before starting the server
        preprocess_all_songs()
        
        # Start the playback manager thread immediately when the server starts
        start_playback_manager()
        app.run(host='0.0.0.0', port=8000, threaded=True)
    except KeyboardInterrupt:
        print("Shutting down...")
        IS_RUNNING = False
        if FFMPEG_PROCESS:
            FFMPEG_PROCESS.terminate()
