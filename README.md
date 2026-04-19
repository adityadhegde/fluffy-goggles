# Podplayer

## Introduction

This python CLI app lets you add, remove, sync, play, pause Podcasts using this RSS feeds. 

The backend relies on MPV (`python-mpv`), BeautifulSoup4, and `requests`.

## Installation & Usage

You can install and run PodPlayer using several methods depending on your environment. Since it relies on `mpv` for audio playback, make sure your system supports it.

### Prerequisites (System Dependencies)
On Debian/Ubuntu:
```bash
sudo apt-get update && sudo apt-get install -y mpv libmpv1
```
On macOS:
```bash
brew install mpv
```

### 1. pip + git
Clone the repository and install it in a virtual environment:

```bash
git clone https://github.com/your-username/podplayer.git
cd podplayer
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
podplayer
```

### 2. uv
If you use [uv](https://github.com/astral-sh/uv), you can run the project directly from the directory without manually managing environments:

```bash
git clone https://github.com/your-username/podplayer.git
cd podplayer
uv run podplayer
```
Or, you can install it globally as a tool:
```bash
uv tool install .
podplayer
```

### 3. Docker Compose (Linux optimized)
You can run the application containerized. The provided `docker-compose.yml` mounts your local sound devices (`/dev/snd`), which works well out-of-the-box on Linux hosts.

```bash
git clone https://github.com/your-username/podplayer.git
cd podplayer
docker compose build
docker compose run --rm podplayer
```

*Note: Docker audio passthrough on Windows/macOS may require extra configuration such as PulseAudio network forwarding.*