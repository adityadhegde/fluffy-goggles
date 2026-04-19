# Implement a MPV controller class which does the following:
# 1. It initializes an MPV player instance.
# 2. It provides methods to play, pause, stop, 
#    and seek within a podcast to a specific timestamp.
#    forward or rewind by 5 seconds(configurable).
# 3. Increase or decrease the volume by 10% max 100 min 0.
# 4. Store the current playback position in the database using the EpisodeMetadataController.
# 5. When a podcast is played, it retrieves the last known playback position from the
#    database and resumes from there.
# 6. It handles events such as end of playback or pause to update the database 
#    accordingly.

import mpv

from feed_controller.table_controllers import EpisodeController, EpisodeMetadataController
from logger import get_logger

logger = get_logger(__name__)


class PlayerController:
    """Controller for managing podcast playback using MPV."""

    def __init__(
        self,
        episode_controller: EpisodeController,
        metadata_controller: EpisodeMetadataController,
        skip_duration: int = 5,
    ):
        """
        Initialize the player controller.

        Args:
            episode_controller: Controller for episode data.
            metadata_controller: Controller for episode metadata.
            skip_duration: Duration in seconds to skip forward/backward (default: 5).
        """
        self.episode_controller = episode_controller
        self.metadata_controller = metadata_controller
        self.skip_duration = skip_duration
        self.player = mpv.MPV()
        self.current_episode_id: int | None = None
        self.pending_seek_position: int = 0
        self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        """Set up event handlers for the MPV player."""
        self.player.register_event_callback(self._on_mpv_event)
        self.player.observe_property("pause", self._on_pause_property)
        self.player.observe_property("duration", self._on_duration_property)

    def _on_mpv_event(self, event: object) -> None:
        """Handle MPV events like end of file."""
        if event.__class__.__name__ == "MpvEventEndFile":
            logger.debug("MPV End of file event received.")
            if self.current_episode_id:
                self._update_playback_position()

    def _on_pause_property(self, name: str, value: object) -> None:
        """Handle pause property changes."""
        if name == "pause" and self.current_episode_id and bool(value):
            self._update_playback_position()

    def _on_duration_property(self, name: str, value: object) -> None:
        """Handle duration property changes - seek once file is loaded."""
        if self.pending_seek_position > 0 and value and float(value) > 0:
            try:
                self.player.seek(self.pending_seek_position, reference="absolute", precision="exact")
                self.pending_seek_position = 0
            except Exception:
                pass  # Seek may fail in some conditions, continue anyway

    def _update_playback_position(self) -> None:
        """Update the current playback position in the database."""
        if self.current_episode_id is None:
            return

        current_position = int(self.player.time_pos) if self.player.time_pos else 0
        metadata = self.metadata_controller.latest_metadata_for_episode(self.current_episode_id)

        self.metadata_controller.insert_data(
            episode_id=self.current_episode_id,
            is_downloaded=metadata.is_downloaded if metadata else False,
            download_path=metadata.download_path if metadata else None,
            is_listened=metadata.is_listened if metadata else False,
            current_position=current_position,
        )

    def play(self, episode_id: int, audio_url: str) -> None:
        """
        Play an episode from its last known position.
        If it is the first time playing, it starts from the beginning.
        If the episode is downloaded, it plays from the local file path instead of the URL.

        Args:
            episode_id: The ID of the episode to play.
            audio_url: The URL of the episode audio.
        """
        self.current_episode_id = episode_id

        # Retrieve last known playback position and metadata
        metadata = self.metadata_controller.latest_metadata_for_episode(episode_id)
        start_position = metadata.current_position if metadata else 0

        # Determine the source: use downloaded file if available, otherwise use URL
        source = audio_url
        if metadata and metadata.is_downloaded and metadata.download_path:
            source = metadata.download_path

        logger.info(f"MPV playing from source: {source} (Start position: {start_position})")
        # Play the audio
        self.player.play(source)

        # Store position to seek once file is loaded
        if start_position > 0:
            self.pending_seek_position = start_position

    def pause(self) -> None:
        """Pause the current playback."""
        self.player.pause = True
        self._update_playback_position()

    def resume(self) -> None:
        """Resume playback."""
        self.player.pause = False

    def stop(self) -> None:
        """Stop playback and save the current position."""
        self._update_playback_position()
        self.player.stop()
        self.current_episode_id = None

    def seek(self, seconds: float, reference: str = "absolute") -> None:
        """
        Seek to a specific position in the playback.

        Args:
            seconds: The position in seconds.
            reference: Either "absolute" or "relative".
        """
        self.player.seek(seconds, reference=reference, precision="exact")

    def skip_forward(self, duration: int | None = None) -> None:
        """
        Skip forward by the configured duration (default 5 seconds).

        Args:
            duration: Duration in seconds to skip (uses default if None).
        """
        skip = duration or self.skip_duration
        self.seek(skip, reference="relative")

    def skip_backward(self, duration: int | None = None) -> None:
        """
        Skip backward by the configured duration (default 5 seconds).

        Args:
            duration: Duration in seconds to skip (uses default if None).
        """
        skip = duration or self.skip_duration
        self.seek(-skip, reference="relative")

    def set_volume(self, volume: int) -> None:
        """
        Set the volume to a specific percentage (0-100).

        Args:
            volume: Volume level as a percentage (clamped to 0-100).
        """
        clamped_volume = max(0, min(100, volume))
        self.player.volume = clamped_volume

    def increase_volume(self, percent: int = 10) -> None:
        """
        Increase the volume by a percentage (default 10%).

        Args:
            percent: Percentage to increase (default 10%).
        """
        current_volume = int(self.player.volume) if self.player.volume else 50
        new_volume = min(100, current_volume + percent)
        self.set_volume(new_volume)

    def decrease_volume(self, percent: int = 10) -> None:
        """
        Decrease the volume by a percentage (default 10%).

        Args:
            percent: Percentage to decrease (default 10%).
        """
        current_volume = int(self.player.volume) if self.player.volume else 50
        new_volume = max(0, current_volume - percent)
        self.set_volume(new_volume)

    def get_current_position(self) -> float:
        """Get the current playback position in seconds."""
        return self.player.time_pos if self.player.time_pos else 0.0

    def get_duration(self) -> float:
        """Get the total duration of the current media in seconds."""
        return self.player.duration if self.player.duration else 0.0

    def is_playing(self) -> bool:
        """Check if the player is currently playing."""
        return not self.player.pause if self.player.pause is not None else False

    def close(self) -> None:
        """Close the player and save any pending state."""
        self._update_playback_position()
        self.player.quit()

