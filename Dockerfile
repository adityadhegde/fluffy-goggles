FROM python:3.12-slim

# Install system dependencies for mpv, audio playback, and build tools
RUN apt-get update && apt-get install -y \
    libmpv1 \
    mpv \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

# Set up a working directory
WORKDIR /app

# Copy the entire project
COPY . .

# Install the application and its dependencies
RUN pip install --no-cache-dir -e .

# Set environment variables for terminal and audio
ENV TERM=xterm-256color
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Start the application
ENTRYPOINT ["podplayer"]
