FROM ubuntu:22.04

# Prevent tzdata interactive dialog + ensure noninteractive installs
ENV DEBIAN_FRONTEND=noninteractive

# Install necessary packages
RUN apt-get update && \
    apt-get install -y \
        pulseaudio \
        ffmpeg \
        icecast2 \
        curl \
        python3 \
        python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Install latest yt-dlp from GitHub (bypass repo version)
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp && \
    chmod a+rx /usr/local/bin/yt-dlp

# Prepare working directory
WORKDIR /app

# Copy Icecast config and start script
COPY icecast.xml /etc/icecast2/icecast.xml
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose Icecast port
EXPOSE 8000

# Default command
CMD ["/app/start.sh"]




RUN apt-get update && apt-get install -y python3 python3-pip
RUN pip3 install flask
COPY server.py /home/streamer/server.py

CMD ["python3", "/home/streamer/server.py"]

