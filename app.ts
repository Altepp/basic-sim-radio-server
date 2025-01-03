import express from 'express';
import type { Request, Response } from 'express';
import fs from 'fs';
import path from 'path';
import * as mm from 'music-metadata';

const app = express();

const port = 8000;
const MUSIC_DIR = 'music'; // Folder containing the audio files

let playlist: string[] = [];

let clients: Response[] = [];

let currentSongIndex = 0;
let currentSongPosition = 0;

let currentPlayTime = Date.now();
let streamBuffer: Buffer | null = null;
let isStreaming = false;

interface SongInfo {
    buffer: Buffer;
    duration: number;
    startTime: number;
    bitrate: number;
}

let currentSong: SongInfo | null = null;

app.get("/radio", (req: Request, res: Response) => {
    res.setHeader("Content-Type", "audio/mpeg");
    res.setHeader("Transfer-Encoding", "chunked");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");
    console.log("New client connected.");
    
    // Send the current song's data from the current position
    if (currentSong && currentSongPosition < currentSong.buffer.length) {
        const initialChunk = currentSong.buffer.slice(
            currentSongPosition
        );
        res.write(initialChunk);
    }
    
    clients.push(res);

    res.on("close", () => {
        console.log("Client disconnected.");
        clients = clients.filter(client => client !== res);
    });
});

// Function to load all MP3 files from the music directory
const loadPlaylist = () => {
    playlist = fs.readdirSync(MUSIC_DIR)
        .filter(file => file.endsWith('.mp3'))
        .map(file => path.join(MUSIC_DIR, file));

    if (playlist.length === 0) {
        console.error("No MP3 files found in the music directory.");
    } else {
        console.log(`Loaded ${playlist.length} songs.`);
    }
};

// Function to start streaming a new song
const startNewSong = async () => {
    try {
        const songPath = playlist[currentSongIndex];
        const buffer = fs.readFileSync(songPath);
        const metadata = await mm.parseBuffer(buffer);
        
        currentSong = {
            buffer,
            duration: metadata.format.duration || 0,
            startTime: Date.now(),
            bitrate: metadata.format.bitrate || 320000 // default to 320kbps if not found
        };
        
        currentSongPosition = 0;
        console.log(`Now playing: ${path.basename(songPath)} (${Math.floor(currentSong.duration)}s, ${Math.floor(currentSong.bitrate/1000)}kbps)`);
    } catch (error) {
        console.error('Error loading song:', error);
        currentSongIndex = (currentSongIndex + 1) % playlist.length;
        setTimeout(startNewSong, 1000);
    }
};

// Replace the streaming manager with this updated version
const streamManager = setInterval(async () => {
    if (playlist.length === 0) {
        loadPlaylist();
        if (playlist.length > 0) {
            await startNewSong();
        }
        return;
    }

    if (clients.length > 0 && !isStreaming && currentSong) {
        isStreaming = true;
        
        try {
            // Check if it's time to switch songs
            const elapsedTime = (Date.now() - currentSong.startTime) / 1000;
            if (elapsedTime >= currentSong.duration) {
                currentSongIndex = (currentSongIndex + 1) % playlist.length;
                await startNewSong();
                isStreaming = false;
                return;
            }

            // Calculate chunk size based on bitrate (0.1 second of audio)
            const CHUNK_SIZE = Math.floor(currentSong.bitrate / 8 / 10); // bytes per 100ms

            if (currentSongPosition < currentSong.buffer.length) {
                const chunk = currentSong.buffer.slice(
                    currentSongPosition,
                    currentSongPosition + CHUNK_SIZE
                );
                
                clients.forEach(client => {
                    if (!client.destroyed) {
                        client.write(chunk);
                    }
                });

                currentSongPosition += chunk.length;
            }
        } catch (error) {
            console.error('Streaming error:', error);
        }
        
        isStreaming = false;
    }
}, 100);

// Clean up on server shutdown
process.on('SIGINT', () => {
    clearInterval(streamManager);
    clients.forEach(client => client.end());
    process.exit(0);
});

app.listen(port, () => {
    console.log(`Server listening on port ${port}`);
});