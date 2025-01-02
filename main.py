import time
import threading
from flask import Flask, Response
import os

app = Flask(__name__)

# Playlist configuration
MUSIC_DIR = "music"  # Directory containing audio files
playlist = []
current_file_index = 0

# Shared state
buffer_size = 1024
current_position = 0
clients = []
lock = threading.Lock()

def load_playlist():
    """Load all MP3 files from the music directory."""
    global playlist
    playlist = [os.path.join(MUSIC_DIR, f) for f in os.listdir(MUSIC_DIR) if f.endswith('.mp3')]
    if not playlist:
        raise Exception("No MP3 files found in the music directory!")
    print(f"Loaded {len(playlist)} songs")

def stream_audio_to_clients():
    """Continuously reads audio files and sends them to all connected clients."""
    global current_position, current_file_index
    
    while True:
        current_audio_file = playlist[current_file_index]
        
        with open(current_audio_file, "rb") as f:
            file_size = os.path.getsize(current_audio_file)
            f.seek(current_position)

            while chunk := f.read(buffer_size):
                with lock:
                    current_position += len(chunk)
                    for queue in clients:
                        queue.append(chunk)
                time.sleep(0.01)

            # Move to next file when current one ends
            with lock:
                current_position = 0
                current_file_index = (current_file_index + 1) % len(playlist)
                print(f"Now playing: {playlist[current_file_index]}")

@app.route('/radio')
def stream_audio():
    """Handles client connections."""
    def generate():
        queue = []
        with lock:
            clients.append(queue)
        
        try:
            while True:
                if queue:
                    chunk = queue.pop(0)
                    yield chunk
                else:
                    yield b''
                time.sleep(0.01)
        finally:
            with lock:
                if queue in clients:
                    clients.remove(queue)

    headers = {
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
        'Access-Control-Allow-Origin': '*'
    }
    
    return Response(
        generate(),
        mimetype="audio/mpeg",
        headers=headers,
        direct_passthrough=True
    )

@app.route('/now-playing')
def now_playing():
    """Returns the currently playing song."""
    return {'current_song': os.path.basename(playlist[current_file_index])}

if __name__ == '__main__':
    # Create music directory if it doesn't exist
    os.makedirs(MUSIC_DIR, exist_ok=True)
    
    # Load the playlist
    load_playlist()
    
    # Start the audio streaming thread
    threading.Thread(target=stream_audio_to_clients, daemon=True).start()
    
    print(f"Radio server live at http://127.0.0.1:8000/radio")
    print(f"Place your MP3 files in the '{MUSIC_DIR}' directory")
    app.run(host='0.0.0.0', port=8000)
