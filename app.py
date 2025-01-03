import os
import random
import subprocess
from flask import Flask, Response, render_template
from flask_socketio import SocketIO, emit
import time

# Initialize Flask and Flask-SocketIO
app = Flask(__name__)
socketio = SocketIO(app)

# Directory for MP3 files
MUSIC_DIR = 'music/'

# Function to get random MP3 file
def get_random_mp3():
    files = [f for f in os.listdir(MUSIC_DIR) if f.endswith('.mp3')]
    return random.choice(files)

# Function to stream MP3 using ffmpeg
def stream_mp3(mp3_file):
    # We use ffmpeg to stream the audio directly
    cmd = [
        'ffmpeg', '-re', '-i', os.path.join(MUSIC_DIR, mp3_file), 
        '-f', 'mp3', '-content_type', 'audio/mpeg', 'pipe:1'
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Route to stream audio
@app.route('/radio')
def radio():
    def generate():
        while True:
            # Get random mp3 file
            mp3_file = get_random_mp3()
            process = stream_mp3(mp3_file)

            # Read and stream the audio in chunks
            while True:
                chunk = process.stdout.read(4096)  # Reading 1KB at a time
                if not chunk:
                    break
                yield chunk
                time.sleep(0.1)  # to avoid overwhelming the client with chunks

            # After a song ends, repeat the process with a new song
            process.stdout.close()
            process.wait()

    return Response(generate(), content_type="audio/mpeg")

# Sync time to clients
@socketio.on('connect')
def handle_connect():
    mp3_file = get_random_mp3()
    emit('sync', {'message': f'Starting stream: {mp3_file}'})

@socketio.on('play')
def handle_play(data):
    # You can send current position here for synchronization
    emit('play', data, broadcast=True)

# Main route to load a player
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8000)
