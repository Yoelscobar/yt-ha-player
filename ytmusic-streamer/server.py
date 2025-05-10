from flask import Flask, request, jsonify
import subprocess
import time
import os
import signal

app = Flask(__name__)
current_process = None

@app.route('/play', methods=['POST'])
def play():
    global current_process
    data = request.get_json()
    video_id = data.get('videoId')
    if not video_id:
        return jsonify({'error': 'Missing videoId'}), 400

    # Stop current stream
    if current_process:
        print("Stopping previous stream...")
        os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
        current_process.wait()
        print("Previous stream stopped.")

    video_url = f'https://music.youtube.com/watch?v={video_id}'
    cmd = f'yt-dlp -f bestaudio -o - {video_url} | ffmpeg -re -i - -vn -c:a libmp3lame -b:a 192k -content_type audio/mpeg -f mp3 icecast://source:hackme@icecast:8000/stream'

    print(f"Starting new stream: {video_url}")
    current_process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
    return jsonify({'status': 'started', 'video': video_url})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
