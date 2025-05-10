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

app.use(express.static('views')); // Annahme: index.html ist in einem Ordner 'views'
// Wenn index.html im Hauptverzeichnis (wie youtube-docker) liegt, dann:
// app.use(express.static(__dirname)); // oder app.use(express.static(path.join(__dirname)));


app.use(express.json());

// -----------------------------
// YouTube Video Search
// -----------------------------
app.get('/search/youtube', async (req, res) => {
  const query = req.query.q;
  if (!query) return res.status(400).send('Missing query');

  try {
    // 1. Videos suchen, um IDs zu bekommen
    const searchResponse = await axios.get(
      'https://www.googleapis.com/youtube/v3/search',
      {
        params: {
          part: 'snippet',
          maxResults: 10, // Du kannst die Anzahl anpassen
          q: query,
          type: 'video',
          key: API_KEY
        }
      }
    );

    const videoItems = searchResponse.data.items;
    if (!videoItems || videoItems.length === 0) {
      return res.json([]);
    }

    const videoIds = videoItems.map(item => item.id.videoId).join(',');

    // 2. Videodetails (inkl. Dauer) für die gefundenen IDs abrufen
    const detailsResponse = await axios.get(
      'https://www.googleapis.com/youtube/v3/videos',
      {
        params: {
          part: 'snippet,contentDetails',
          id: videoIds,
          key: API_KEY
        }
      }
    );

    const videosWithDetails = detailsResponse.data.items.map(item => ({
      title: item.snippet.title,
      videoId: item.id,
      thumbnail: item.snippet.thumbnails.medium.url,
      duration: formatISO8601Duration(item.contentDetails.duration) // Dauer hinzufügen
    }));

    res.json(videosWithDetails);
  } catch (error) {
    if (error.response) {
      console.error(
        'YouTube API Error:',
        error.response.status,
        error.response.data.error ? error.response.data.error.message : error.response.data
      );
    } else {
      console.error('YouTube network Error:', error.message);
    }
    res.status(500).send('Error fetching YouTube data');
  }
});

// Hilfsfunktion zum Formatieren der ISO 8601 Dauer
function formatISO8601Duration(isoDuration) {
  if (!isoDuration) return 'N/A';
  const match = isoDuration.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
  if (!match) return 'N/A';

  const hours = parseInt(match[1]) || 0;
  const minutes = parseInt(match[2]) || 0;
  const seconds = parseInt(match[3]) || 0;

  let formatted = '';
  if (hours > 0) {
    formatted += String(hours).padStart(2, '0') + ':';
  }
  formatted += String(minutes).padStart(2, '0') + ':';
  formatted += String(seconds).padStart(2, '0');
  return formatted;
}


// -----------------------------
// YouTube Music Search (via venv-python)
// -----------------------------
const ytmusicScript = path.join(
  __dirname,
  'ytmusic-search',
  'ytmusic_search.py'
);
const venvPython = path.join(
  '/opt/venv/bin', // Pfad in deinem Docker Container
  'python3'
);

app.get('/search/ytmusic', (req, res) => {
  const query = req.query.q;
  if (!query) return res.status(400).send('Missing query');

  // Stelle sicher, dass Anführungszeichen im Query korrekt escaped werden
  const escapedQuery = query.replace(/"/g, '\\"');
  const command = `"${venvPython}" "${ytmusicScript}" "${escapedQuery}"`;

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
    // Annahme: ytmusic_streamer läuft als Service im Docker-Netzwerk
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
    if (error.response) {
        console.error('Streamer response error:', error.response.status, error.response.data);
    }
    res.status(500).send('Failed to send play command to music streamer');
  }
});

// -----------------------------
// SONOS-STREAM-PROXY (für direkte Icecast-Weiterleitung)
// -----------------------------
app.get('/sonos_stream', async (req, res) => {
  const upstream = 'http://icecast:8000/stream'; // Dein Icecast-Stream im Docker-Netzwerk
  try {
    const response = await axios.get(upstream, { responseType: 'stream' });
    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('icy-metadata', '1'); // Wichtig für manche Sonos-Setups
    response.data.pipe(res);
  } catch (err) {
    console.error('Proxy error to Icecast:', err.message);
    res.sendStatus(500);
  }
});


// -----------------------------
// Dynamischer Stream einzelner Tracks via yt-dlp (für PlayNext/Enqueue)
// -----------------------------
const { spawn } = require('child_process');
app.get('/stream/:videoId', (req, res) => {
  const { videoId } = req.params;
  if (!videoId) {
    return res.status(400).send('Missing videoId');
  }

  // Sicherheitsüberprüfung für videoId (einfach, kann erweitert werden)
  if (!/^[a-zA-Z0-9_-]{11}$/.test(videoId)) {
      return res.status(400).send('Invalid videoId format');
  }

  res.setHeader('Content-Type', 'audio/mpeg');

  // Verwende die vollständige URL für yt-dlp, um Eindeutigkeit zu gewährleisten
  const youtubeVideoUrl = `https://www.youtube.com/watch?v=${videoId}`;

  // Befehl angepasst für bessere Fehlerbehandlung und Logging
  // `-f bestaudio` wählt den besten Audio-Stream
  // `-o -` leitet den Output zu stdout
  // `ffmpeg -i pipe:0 ...` liest von stdin (pipe:0)
  // `-vn` kein Video
  // `-c:a libmp3lame` encodiert zu MP3
  // `-b:a 192k` Bitrate
  // `-f mp3` Ausgabeformat MP3
  // `-` output zu stdout
  const cmd = `yt-dlp -f bestaudio -o - "${youtubeVideoUrl}" | ffmpeg -i pipe:0 -vn -c:a libmp3lame -b:a 192k -f mp3 -`;
  
  console.log(`Spawning stream for ${videoId}: ${cmd}`);
  const proc = spawn(cmd, { shell: true });

  proc.stdout.pipe(res);

  proc.stderr.on('data', (data) => {
    console.error(`[yt-dlp/ffmpeg stderr for ${videoId}]: ${data}`);
  });

  proc.on('error', (err) => {
    console.error(`Failed to start subprocess for ${videoId}:`, err);
    if (!res.headersSent) {
      res.sendStatus(500);
    }
  });
  
  proc.on('close', (code) => {
    console.log(`Subprocess for ${videoId} exited with code ${code}`);
  });

  res.on('close', () => {
    console.log(`Client disconnected for ${videoId}, killing subprocess.`);
    proc.kill();
  });
});


// -----------------------------
app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
  // Für Docker: Oft besser, auf 0.0.0.0 zu lauschen statt localhost
  // console.log(`Server running on http://0.0.0.0:${PORT}`);
});