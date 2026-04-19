from pathlib import Path

def get_app_dir() -> Path:
    """Get the application base directory for storing config and data."""
    # 1. If there's a config.json in the current working directory, prioritize it
    if Path("config.json").exists():
        return Path(".").resolve()
    
    # 2. Check known legacy cloning directories for the user
    for legacy_dir in [Path.home() / "podplayer", Path.home() / "fluffy-goggles"]:
        if (legacy_dir / "config.json").exists():
            return legacy_dir.resolve()

    # 3. Default to a hidden directory in the user's home folder
    app_dir = Path.home() / ".podplayer"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir

APP_DIR = get_app_dir()
