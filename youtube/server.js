require('dotenv').config();
const express = require('express');
const axios = require('axios');
const path = require('path');
const { exec } = require('child_process');

// Debug: ist der API-Key geladen?
console.log(
  'Loaded YouTube API Key:',
  process.env.YOUTUBE_API_KEY ? '[OK]' : '[NOT FOUND]'
);

const app = express();
const PORT = 3000;
const API_KEY = process.env.YOUTUBE_API_KEY;

app.use(express.static('views'));
app.use(express.json());

// -----------------------------
// YouTube Video Search
// -----------------------------
app.get('/search/youtube', async (req, res) => {
  const query = req.query.q;
  if (!query) return res.status(400).send('Missing query');

  try {
    const response = await axios.get(
      'https://www.googleapis.com/youtube/v3/search',
      {
        params: {
          part: 'snippet',
          maxResults: 10,
          q: query,
          type: 'video',
          key: API_KEY
        }
      }
    );

    const videos = response.data.items.map(item => ({
      title: item.snippet.title,
      videoId: item.id.videoId,
      thumbnail: item.snippet.thumbnails.medium.url
    }));

    res.json(videos);
  } catch (error) {
    if (error.response) {
      console.error(
        'YouTube API Error:',
        error.response.status,
        error.response.data
      );
    } else {
      console.error('YouTube network Error:', error.message);
    }
    res.status(500).send('Error fetching YouTube data');
  }
});

// -----------------------------
// YouTube Music Search (via venv-python)
// -----------------------------
// Pfade zum Skript und zum venv-Python
const ytmusicScript = path.join(
  __dirname,
  'ytmusic-search',
  'ytmusic_search.py'
);
// Das Python-Venv aus deinem Dockerfile liegt unter /opt/venv
const venvPython = path.join(
  '/opt/venv/bin',
  'python3'
);

app.get('/search/ytmusic', (req, res) => {
  const query = req.query.q;
  if (!query) return res.status(400).send('Missing query');

  // Aufruf mit dem venv-Python, damit ytmusicapi verfügbar ist
  const command = `"${venvPython}" "${ytmusicScript}" "${query.replace(/"/g, '\\"')}"`;

  exec(command, (error, stdout, stderr) => {
    if (error) {
      console.error('Exec error:', error.message);
      console.error('stderr:', stderr);
      return res.status(500).send('Error fetching YouTube Music data');
    }

    try {
      const result = JSON.parse(stdout);
      res.json(result);
    } catch (parseError) {
      console.error('Parse error:', parseError.message);
      console.error('Raw stdout was:', stdout);
      res.status(500).send('Error parsing YouTube Music data');
    }
  });
});

// -----------------------------
// Play request to ytmusic-streamer Flask server
// -----------------------------
app.post('/play_ytmusic', async (req, res) => {
  const { videoId } = req.body;
  if (!videoId) return res.status(400).send('Missing videoId');

  try {
    const response = await axios.post(
      'http://ytmusic_streamer:8080/play',
      { videoId }
    );
    res.json({
      success: true,
      message: 'Sent to music streamer',
      response: response.data
    });
  } catch (error) {
    console.error('Error sending to music streamer:', error.message);
    res.status(500).send('Failed to send play command to music streamer');
  }
});

// -----------------------------
// SONOS-STREAM-PROXY
// -----------------------------
app.get('/sonos_stream', async (req, res) => {
  const upstream = 'http://icecast:8000/stream'; // Dein Icecast-Stream
  try {
    const response = await axios.get(upstream, { responseType: 'stream' });
    // Sonos-kompatible Header
    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('icy-metadata', '1');
    response.data.pipe(res);
  } catch (err) {
    console.error('Proxy error:', err);
    res.sendStatus(500);
  }
});

const { spawn } = require('child_process');
app.get('/stream/:videoId', (req, res) => {
  const { videoId } = req.params;
  // 1) setze Header auf audio/mpeg, Sonos liest das
  res.setHeader('Content-Type', 'audio/mpeg');
  // 2) benutze yt-dlp + ffmpeg, um genau einen Track zu streamen
  //    ffmpeg beendet sich automatisch, wenn das Audio zu Ende ist
  const cmd = `yt-dlp -f bestaudio -o - "https://music.youtube.com/watch?v=${videoId}"` +
              ` | ffmpeg -i - -vn -c:a libmp3lame -b:a 192k -f mp3 -`;
  const proc = spawn(cmd, { shell: true });
  proc.stdout.pipe(res);
  // falls der Client abbricht, killen wir den Prozess
  res.on('close', () => proc.kill());
});

// -----------------------------
app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
