import express from 'express';
import type { Request, Response } from 'express';
import fs from 'fs';
import path from 'path';

const app = express();
const port = 8000;
const MUSIC_DIR = 'music'; // Folder containing the audio files

// Array to hold the list of songs
let playlist: string[] = [];
let currentSongIndex = 0;
let currentSongStartTime: number = 0;
let currentReadStream: fs.ReadStream | null = null;

// Function to load all MP3 files from the music directory
const loadPlaylist = () => {
    // Clear the playlist and load new songs
    playlist = fs.readdirSync(MUSIC_DIR)
        .filter(file => file.endsWith('.mp3'))  // Only MP3 files
        .map(file => path.join(MUSIC_DIR, file));
    
    if (playlist.length === 0) {
        console.error("No MP3 files found in the music directory.");
    } else {
        console.log(`Loaded ${playlist.length} songs.`);
    }
};

// Load the playlist when the server starts
loadPlaylist();

// Function to start playing the next song
const playNextSong = () => {
    if (playlist.length === 0) {
        console.error("No songs available to play.");
        return;
    }

    currentSongStartTime = Date.now();
    const currentSong = playlist[currentSongIndex];

    // Close the previous stream if it exists
    if (currentReadStream) {
        currentReadStream.close();
    }

    currentReadStream = fs.createReadStream(currentSong);

    currentReadStream.on('end', () => {
        if (playlist.length > 0) {
            currentSongIndex = (currentSongIndex + 1) % playlist.length;
            playNextSong();
        }
    });

    currentReadStream.on('error', (err) => {
        console.error(`Error playing song: ${err.message}`);
        if (playlist.length > 0) {
            currentSongIndex = (currentSongIndex + 1) % playlist.length;
            playNextSong();
        }
    });

    // Simulate playing the song in the background
    currentReadStream.resume();
};

// Start playing the first song when the server starts
playNextSong();

// Route to serve the audio stream
app.get('/radio', (req: Request, res: Response): void => {
    if (playlist.length === 0) {
        res.status(404).send('No audio files in the playlist.');
        return;
    }

    const currentSong = playlist[currentSongIndex];
    const fileStats = fs.statSync(currentSong);
    const fileSize = fileStats.size;

    // Calculate the current playback position
    const elapsedTime = Date.now() - currentSongStartTime;
    const startByte = Math.floor((elapsedTime / fileStats.mtimeMs) * fileSize);

    // Set the appropriate headers for streaming
    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('Content-Length', fileSize - startByte);
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    
    // Create a readable stream for the current song starting from the current position
    const readStream = fs.createReadStream(currentSong, { start: startByte });
    readStream.pipe(res);

    // Close the stream when the response ends
    res.on('close', () => {
        readStream.destroy();
    });
});

// Route to get the current song playing
app.get('/now-playing', (req: Request, res: Response): void => {
    if (playlist.length === 0) {
        res.json({ current_song: 'No songs available' });
        return;
    }
    const currentSong = path.basename(playlist[currentSongIndex]);
    res.json({ current_song: currentSong });
});

// Route to skip to the next song (admin console)
app.post('/skip-song', (req: Request, res: Response): void => {
    if (playlist.length === 0) {
        res.status(404).send('No audio files in the playlist.');
        return;
    }
    currentSongIndex = (currentSongIndex + 1) % playlist.length;
    playNextSong();
    res.send('Skipped to the next song.');
});

// Route to reload the playlist manually
app.get('/reload-playlist', (req: Request, res: Response) => {
    loadPlaylist();
    res.send('Playlist reloaded');
});

// Start the server
app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
