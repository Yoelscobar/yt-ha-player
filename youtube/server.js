require('dotenv').config();
const express = require('express');
const axios = require('axios');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');

const execPromise = util.promisify(exec);

// Debug: ist der API-Key geladen?
console.log(
  'Loaded YouTube API Key:',
  process.env.YOUTUBE_API_KEY ? '[OK]' : '[NOT FOUND]'
);

const app = express();
const PORT = 3000;
const API_KEY = process.env.YOUTUBE_API_KEY;

// Pfad zum venv Python (wie in deinem Dockerfile /opt/venv)
const venvPython = path.join('/opt/venv/bin', 'python3');

// Pfade zu den Python-Skripten (angenommen im Unterordner 'ytmusic-search')
const ytmusicSearchScript = path.join(__dirname, 'ytmusic-search', 'ytmusic_search.py');
const ytmusicGetFirstTrackScript = path.join(__dirname, 'ytmusic-search', 'ytmusic_get_first_track.py');


app.use(express.static('views')); // Oder __dirname, wenn index.html im root ist
app.use(express.json());

// -----------------------------
// NEU: Youtube Suggestions
// -----------------------------
app.get('/suggestions', async (req, res) => {
    const query = req.query.q;
    if (!query) {
        return res.json([]);
    }
    try {
        // YouTube/Google Suggestion API (client=firefox liefert oft reines JSON)
        const suggestionUrl = `http://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q=${encodeURIComponent(query)}`;
        
        const response = await axios.get(suggestionUrl, {
            // Der Content-Type ist oft text/javascript, aber der Body ist ein JSON-Array-String
            // Axios sollte in der Lage sein, dies zu handhaben oder als String zurückzugeben
            transformResponse: [(data) => {
                // Manchmal ist die Antwort ein String, der ein JSON-Array darstellt.
                // Wir versuchen, es direkt als JSON zu parsen.
                try {
                    return JSON.parse(data);
                } catch (e) {
                    // Falls es kein valider JSON-String ist oder schon ein Objekt/Array durch Axios geparst wurde
                    return data; 
                }
            }]
        });

        let suggestions = [];
        // Die erwartete Struktur ist ["original_query", [suggestion_array]]
        if (Array.isArray(response.data) && response.data.length > 1 && Array.isArray(response.data[1])) {
             suggestions = response.data[1]; 
        } else {
            // Fallback, falls die Struktur unerwartet ist
            console.warn('Unexpected suggestion API response structure:', response.data);
        }
        
        // Stelle sicher, dass wir nur Strings haben und limitieren die Anzahl
        const cleanedSuggestions = suggestions
            .map(s => (Array.isArray(s) ? String(s[0]) : String(s))) // Manche Vorschläge sind Arrays wie ["suggestion", type_info]
            .slice(0, 7); // Z.B. die Top 7 Vorschläge

        res.json(cleanedSuggestions);

    } catch (error) {
        console.error('Error fetching suggestions from Google API:', error.message);
        if (error.response) {
            console.error('Suggestion API Error Status:', error.response.status);
            console.error('Suggestion API Error Data:', error.response.data);
        }
        res.json([]); // Leeres Array im Fehlerfall
    }
});


// -----------------------------
// YouTube Video Search (bleibt unverändert)
// -----------------------------
app.get('/search/youtube', async (req, res) => {
  const query = req.query.q;
  if (!query) return res.status(400).send('Missing query');
  try {
    const searchResponse = await axios.get('https://www.googleapis.com/youtube/v3/search', {
      params: { part: 'snippet', maxResults: 10, q: query, type: 'video', key: API_KEY }
    });
    const videoItems = searchResponse.data.items;
    if (!videoItems || videoItems.length === 0) return res.json([]);
    const videoIds = videoItems.map(item => item.id.videoId).join(',');
    const detailsResponse = await axios.get('https://www.googleapis.com/youtube/v3/videos', {
      params: { part: 'snippet,contentDetails', id: videoIds, key: API_KEY }
    });
    const videosWithDetails = detailsResponse.data.items.map(item => ({
      title: item.snippet.title,
      videoId: item.id,
      thumbnail: item.snippet.thumbnails.medium.url,
      duration: formatISO8601Duration(item.contentDetails.duration)
    }));
    res.json(videosWithDetails);
  } catch (error) {
    if (error.response) console.error('YouTube API Error:', error.response.status, error.response.data.error ? error.response.data.error.message : error.response.data);
    else console.error('YouTube network Error:', error.message);
    res.status(500).send('Error fetching YouTube data');
  }
});

function formatISO8601Duration(isoDuration) {
  if (!isoDuration) return 'N/A';
  const match = isoDuration.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
  if (!match) return 'N/A';
  const hours = parseInt(match[1]) || 0;
  const minutes = parseInt(match[2]) || 0;
  const seconds = parseInt(match[3]) || 0;
  let formatted = '';
  if (hours > 0) formatted += String(hours).padStart(2, '0') + ':';
  formatted += String(minutes).padStart(2, '0') + ':';
  formatted += String(seconds).padStart(2, '0');
  return formatted;
}

// -----------------------------
// YouTube Music Search (bleibt unverändert)
// -----------------------------
app.get('/search/ytmusic', async (req, res) => {
  const query = req.query.q;
  if (!query) return res.status(400).send('Missing query');
  const escapedQuery = query.replace(/"/g, '\\"');
  const command = `"${venvPython}" "${ytmusicSearchScript}" "${escapedQuery}"`;
  try {
    const { stdout, stderr } = await execPromise(command);
    if (stderr) console.warn('ytmusic_search.py stderr:', stderr);
    const result = JSON.parse(stdout);
    res.json(result);
  } catch (error) {
    console.error('Error executing or parsing ytmusic_search.py:', error.message);
    if (error.stdout) console.error('Raw stdout from ytmusic_search.py:', error.stdout);
    if (error.stderr) console.error('Raw stderr from ytmusic_search.py:', error.stderr);
    res.status(500).send('Error fetching or parsing YouTube Music data');
  }
});

// -----------------------------
// Play request to ytmusic-streamer Flask server (bleibt wie zuletzt angepasst)
// -----------------------------
app.post('/play_ytmusic', async (req, res) => {
  const { id, type } = req.body;

  if (!id || !type) {
    return res.status(400).json({ success: false, message: 'Missing ID or type' });
  }

  let trackVideoIdToPlay;

  try {
    if (type === 'song' || type === 'video') {
      trackVideoIdToPlay = id;
    } else if (type === 'album' || type === 'playlist') {
      const command = `"${venvPython}" "${ytmusicGetFirstTrackScript}" "${id}" "${type}"`;
      console.log(`Executing command to get first track: ${command}`);
      const { stdout, stderr } = await execPromise(command);
      if (stderr) console.warn(`stderr from ytmusic_get_first_track.py for ${type} ${id}:`, stderr);
      
      let scriptResult;
      try { scriptResult = JSON.parse(stdout); } 
      catch (parseError) { 
        console.error(`Failed to parse JSON from ytmusic_get_first_track.py stdout: ${stdout}`);
        throw new Error(`Could not parse first track data for ${type}`);
      }

      if (scriptResult.error || !scriptResult.videoId) {
        const errorMessage = `Could not get first track from ${type}: ${scriptResult.error || 'No videoId found'}`;
        console.error(errorMessage);
        return res.status(500).json({ success: false, message: errorMessage });
      }
      trackVideoIdToPlay = scriptResult.videoId;
      console.log(`Resolved ${type} ID ${id} to track videoId: ${trackVideoIdToPlay}`);
    } else {
      return res.status(400).json({ success: false, message: 'Invalid item type provided' });
    }

    if (!trackVideoIdToPlay) {
        console.error('Could not determine trackVideoIdToPlay.');
        return res.status(500).json({ success: false, message: 'Could not determine track to play.' });
    }

    console.log(`Sending videoId ${trackVideoIdToPlay} to ytmusic_streamer...`);
    const streamerResponse = await axios.post('http://ytmusic_streamer:8080/play', { videoId: trackVideoIdToPlay });
    
    res.json({
      success: true,
      message: `Sent track ${trackVideoIdToPlay} (from ${type} ${id}) to music streamer.`,
      streamerResponse: streamerResponse.data
    });

  } catch (error) {
    console.error(`Error in /play_ytmusic for ID ${id}, type ${type}:`, error.message);
    if (error.isAxiosError && error.response) console.error('Axios error calling streamer:', error.response.status, error.response.data);
    else if (error.stderr) console.error('Python script execution error details:', error.stderr);
    res.status(500).json({ success: false, message: `Failed to process play command: ${error.message}` });
  }
});


// -----------------------------
// SONOS-STREAM-PROXY (bleibt unverändert)
// -----------------------------
app.get('/sonos_stream', async (req, res) => {
  const upstream = 'http://icecast:8000/stream';
  try {
    const response = await axios.get(upstream, { responseType: 'stream' });
    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('icy-metadata', '1');
    response.data.pipe(res);
  } catch (err) {
    console.error('Proxy error to Icecast:', err.message);
    res.sendStatus(500);
  }
});

// -----------------------------
// Dynamischer Stream einzelner Tracks via yt-dlp (bleibt unverändert)
// -----------------------------
const { spawn } = require('child_process');
app.get('/stream/:videoId', (req, res) => {
  const { videoId } = req.params;
  if (!videoId || !/^[a-zA-Z0-9_-]{11}$/.test(videoId)) {
      return res.status(400).send('Invalid or missing videoId');
  }
  res.setHeader('Content-Type', 'audio/mpeg');
  const youtubeVideoUrl = `https://www.youtube.com/watch?v=${videoId}`;
  const cmd = `yt-dlp -f bestaudio -o - "${youtubeVideoUrl}" | ffmpeg -i pipe:0 -vn -c:a libmp3lame -b:a 192k -f mp3 -`;
  console.log(`Spawning stream for ${videoId}: ${cmd}`);
  const proc = spawn(cmd, { shell: true });
  proc.stdout.pipe(res);
  proc.stderr.on('data', (data) => console.error(`[yt-dlp/ffmpeg stderr for ${videoId}]: ${data}`));
  proc.on('error', (err) => {
    console.error(`Failed to start subprocess for ${videoId}:`, err);
    if (!res.headersSent) res.sendStatus(500);
  });
  proc.on('close', (code) => console.log(`Subprocess for ${videoId} exited with code ${code}`));
  res.on('close', () => {
    console.log(`Client disconnected for ${videoId}, killing subprocess.`);
    proc.kill();
  });
});

// -----------------------------
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on http://0.0.0.0:${PORT}`);
});