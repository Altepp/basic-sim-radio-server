import time
import threading
from flask import Flask, Response

app = Flask(__name__)

# Path to the audio file
audio_file = "son.mp3"

# Shared state
buffer_size = 1024
current_position = 0  # Byte position in the file
clients = []  # List of connected clients
lock = threading.Lock()


def stream_audio_to_clients():
    """Continuously reads the audio file and sends it to all connected clients."""
    global current_position
    while True:
        with open(audio_file, "rb") as f:
            f.seek(current_position)  # Start from the current shared position

            while chunk := f.read(buffer_size):
                with lock:
                    current_position += len(chunk)
                    # Append the chunk to all client queues
                    for queue in clients:
                        queue.append(chunk)

                time.sleep(0.01)  # Simulate real-time streaming

        # Loop the file when it ends
        with lock:
            current_position = 0


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
                    # Yield an empty chunk to keep connection alive
                    yield b''
                time.sleep(0.01)
        finally:
            with lock:
                if queue in clients:
                    clients.remove(queue)

    headers = {
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',  # Disable nginx buffering
        'Access-Control-Allow-Origin': '*'  # Allow CORS
    }
    
    return Response(
        generate(),
        mimetype="audio/mpeg",
        headers=headers,
        direct_passthrough=True  # Prevent Flask from buffering the response
    )


if __name__ == '__main__':
    # Start the audio streaming thread
    threading.Thread(target=stream_audio_to_clients, daemon=True).start()

    # Start the Flask server
    print("Radio server live at http://127.0.0.1:8000/radio")
    app.run(host='0.0.0.0', port=8000)
