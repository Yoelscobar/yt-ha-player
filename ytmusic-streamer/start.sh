#!/bin/bash

ICECAST_USER=icecast2
ICECAST_CONFIG=/etc/icecast2/icecast.xml
ICECAST_LOG_DIR=/var/log/icecast2

# Start Icecast as non-root
echo "Starting Icecast..."
su -s /bin/bash -c "icecast2 -c $ICECAST_CONFIG -b" $ICECAST_USER

sleep 5

VIDEO_URL=${VIDEO_URL:-"https://music.youtube.com/watch?v=pzw72GFy5FU"}

echo "Starting stream for $VIDEO_URL..."

yt-dlp -f bestaudio -o - "$VIDEO_URL" | ffmpeg -re -i - -vn -c:a libmp3lame -b:a 192k -content_type audio/mpeg -f mp3 icecast://source:hackme@icecast:8000/stream

