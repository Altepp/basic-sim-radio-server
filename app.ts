import express from 'express';
import fs from 'fs';
import path from 'path';
import { Readable } from 'stream';

const app = express();
const PORT = 8000;
const CHUNK_SIZE = 2048;  // Smaller chunk size
const musicDir = path.join(__dirname, 'music');

let currentFile: fs.ReadStream | null = null;
let currentFilePath: string | null = null;
let currentFileIndex = 0;
let files: string[] = [];
let currentFileStartTime: number | null = null;
let playbackTimer: NodeJS.Timer | null = null;

function loadFiles() {
    files = fs.readdirSync(musicDir).filter(file => file.endsWith('.mp3'));
}

function openNextFile() {
    if (currentFile) {
        currentFile.close();
    }
    if (files.length > 0) {
        currentFilePath = path.join(musicDir, files[currentFileIndex]);
        currentFile = fs.createReadStream(currentFilePath, { highWaterMark: CHUNK_SIZE });
        currentFile.on('error', (err) => {
            console.error(`Error reading file ${currentFilePath}:`, err);
            openNextFile(); // Try to open the next file if there's an error
        });
        currentFileStartTime = Date.now();
        currentFileIndex = (currentFileIndex + 1) % files.length;
    }
}

function radioManager() {
    loadFiles();
    openNextFile();
}

function startPlaybackTimer() {
    if (playbackTimer) {
        clearInterval(playbackTimer);
    }
    playbackTimer = setInterval(() => {
        if (currentFile && currentFile.readableLength === 0) {
            openNextFile();
        }
    }, 1000);
}

function getCurrentPlaybackPosition() {
    if (currentFileStartTime) {
        return (Date.now() - currentFileStartTime) / 1000; // in seconds
    }
    return 0;
}

app.get('/radio', (req, res) => {
    console.log('Client connected to /radio');
    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('Transfer-Encoding', 'chunked');
    if (currentFilePath) {
        const playbackPosition = getCurrentPlaybackPosition();
        currentFile = fs.createReadStream(currentFilePath, { highWaterMark: CHUNK_SIZE });
        currentFile.on('open', () => {
            console.log(`Opened file: ${currentFilePath} at position: ${playbackPosition} seconds`);
            if (currentFile) {
                currentFile.pipe(res);
            }
        });
        currentFile.on('error', (err) => {
            console.error(`Error reading file ${currentFilePath}:`, err);
            res.end();
        });
        res.on('close', () => {
            console.log('Client disconnected');
            if (currentFile) {
                currentFile.destroy();
            }
        });
    } else {
        console.log('No file is currently being played');
        res.status(404).send('No file is currently being played.');
    }
});

app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
    radioManager();
    startPlaybackTimer();
});
