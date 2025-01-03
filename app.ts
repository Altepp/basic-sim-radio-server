import express from 'express';
import type { Request, Response } from 'express';
import path from 'path';
import fs from 'fs';
import { randomInt } from 'crypto';
import * as ffmpeg from 'fluent-ffmpeg';

const app = express();
const port = 8000;

// Set the music directory
const musicDirectory = path.join(__dirname, 'music');

// Serve the radio stream at /radio
app.get('/radio', (req: Request, res: Response) => {
  const files = fs.readdirSync(musicDirectory);
  const mp3Files = files.filter(file => file.endsWith('.mp3'));

  if (mp3Files.length === 0) {
    return res.status(404).send('No MP3 files found.');
  }

  // Select a random MP3 file
  const randomFile = mp3Files[randomInt(mp3Files.length)];
  const filePath = path.join(musicDirectory, randomFile);

  res.setHeader('Content-Type', 'audio/mpeg');
  res.setHeader('Transfer-Encoding', 'chunked');

  // Use ffmpeg to stream the MP3 file with correct bitrate
  ffmpeg(filePath)
    .audioCodec('libmp3lame')
    .format('mp3')
    .pipe(res, { end: true });
});

app.listen(port, () => {
  console.log(`Web radio stream server is running on port ${port}`);
});
