# this script is the main entry point for the application.
# It initializes the database, sets up the controllers, and implement the following user interfaces.
# 1. Add a new feed by providing its URL.
# 2. List all available feeds
# 3. List all episodes for a selected feed.
# 4. Play an episode by selecting it from the list.
# 5. Display the current playback position and allow the user to seek to a specific timestamp within the episode.
# 6. Allow user to download an episode for offline listening and manage the downloaded files and their metadata.
# 7. Resume playback from the last saved position when reopening an episode.
# 8. Maintain playback history for previously played episodes
# 9. Allow adding, removing, and reordering episodes in the queue.
# 10. Delete downloaded episodes and manage storage usage.
# 11. Refresh feeds to fetch new episodes (manual trigger).
# 12. Periodically auto-refresh feeds in the background.
# 13. Allow users to search for specific episodes or feeds.
# End of requirements

import os
import threading
import time
from typing import List, Optional
import requests

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from feed_controller.ingester import FeedManager
from feed_controller.table_controllers import (
    EpisodeController,
    EpisodeMetadataController,
    FeedController,
)
from player.controller import PlayerController


class PodPlayerApp:
    """Main application class for the podcast player."""

    def __init__(self, db_path: str = "podplayer.db"):
        """Initialize the application with database and controllers."""
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Initialize controllers
        self.feed_controller = FeedController(self.SessionLocal)
        self.episode_controller = EpisodeController(self.SessionLocal)
        self.metadata_controller = EpisodeMetadataController(self.SessionLocal)

        # Create tables
        self.feed_controller.create_tables(self.engine)
        self.episode_controller.create_tables(self.engine)
        self.metadata_controller.create_tables(self.engine)

        # Initialize feed manager and player
        self.feed_manager = FeedManager(
            self.feed_controller, self.episode_controller, self.metadata_controller
        )
        self.player = PlayerController(
            self.episode_controller, self.metadata_controller
        )

        # Application state
        self.playback_queue: List[int] = []  # List of episode IDs
        self.playback_history: List[int] = []  # List of played episode IDs
        self.current_episode_index: Optional[int] = None

        # Auto-refresh thread
        self.auto_refresh_thread: Optional[threading.Thread] = None
        self.auto_refresh_interval = 3600  # 1 hour
        self._auto_refresh_stop_flag = False

    # 1. Add a new feed by providing its URL
    def add_feed(self, feed_url: str) -> bool:
        """Add a new feed by URL. Returns True if successful."""
        try:
            self.feed_manager.ingest_feed(feed_url)
            return True
        except Exception as e:
            print(f"Failed to add feed: {e}")
            return False

    # 2. List all available feeds
    def list_feeds(self) -> List[dict]:
        """Return a list of all feeds with their details."""
        feeds = self.feed_manager.get_feeds()
        return [
            {
                "id": feed.id,
                "title": feed.title,
                "description": feed.description,
                "url": feed.feed_url,
            }
            for feed in feeds
        ]

    # 3. List all episodes for a selected feed
    def list_episodes(self, feed_id: int) -> List[dict]:
        """Return a list of episodes for the given feed ID."""
        episodes = self.episode_controller.get_episodes_by_feed_id(feed_id)
        return [
            {
                "id": episode.id,
                "title": episode.title,
                "description": episode.description,
                "audio_url": episode.audio_url,
                "duration": episode.duration,
                "publish_date": episode.publish_date,
            }
            for episode in episodes
        ]

    # 4. Play an episode by selecting it from the list
    def play_episode(self, episode_id: int) -> bool:
        """Play the selected episode. Returns True if successful."""
        episode = self.episode_controller.get_episode_by_id(episode_id)
        if not episode:
            return False

        self.player.play(episode_id, episode.audio_url)
        self.playback_history.append(episode_id)
        return True

    # 5. Display the current playback position and allow seeking
    def get_current_position(self) -> float:
        """Get the current playback position in seconds."""
        return self.player.get_current_position()

    def seek_to_position(self, seconds: float) -> None:
        """Seek to a specific position in the current episode."""
        self.player.seek(seconds, reference="absolute")

    # 6. Download an episode
    def download_episode(self, episode_id: int, download_dir: str = "downloads", sync: bool = False) -> bool:
        """Download the episode for offline listening. Returns True if successfully started."""
        episode = self.episode_controller.get_episode_by_id(episode_id)
        if not episode:
            return False

        # Create download directory if it doesn't exist
        os.makedirs(download_dir, exist_ok=True)

        safe_title = "".join(c for c in episode.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        download_path = os.path.join(download_dir, f"{episode_id}_{safe_title}.mp3")

        def _download_task():
            try:
                response = requests.get(episode.audio_url, stream=True, timeout=15)
                response.raise_for_status()
                with open(download_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Update DB after successful download
                metadata = self.metadata_controller.latest_metadata_for_episode(episode_id)
                self.metadata_controller.insert_data(
                    episode_id=episode_id,
                    is_downloaded=True,
                    download_path=download_path,
                    is_listened=metadata.is_listened if metadata else False,
                    current_position=metadata.current_position if metadata else 0,
                )
            except Exception as e:
                if os.path.exists(download_path):
                    try:
                        os.remove(download_path)
                    except OSError:
                        pass
                
        if sync:
            _download_task()
        else:
            threading.Thread(target=_download_task, daemon=True).start()

        return True

    # 7. Resume playback (handled automatically in play_episode)

    # 8. Maintain playback history
    def get_playback_history(self) -> List[dict]:
        """Return the playback history."""
        history = []
        for episode_id in self.playback_history:
            episode = self.episode_controller.get_episode_by_id(episode_id)
            if episode:
                history.append({
                    "id": episode.id,
                    "title": episode.title,
                    "feed_title": episode.feed.title,
                })
        return history

    # 9. Queue management
    def add_to_queue(self, episode_id: int) -> None:
        """Add an episode to the playback queue."""
        if episode_id not in self.playback_queue:
            self.playback_queue.append(episode_id)

    def remove_from_queue(self, episode_id: int) -> None:
        """Remove an episode from the playback queue."""
        if episode_id in self.playback_queue:
            self.playback_queue.remove(episode_id)

    def reorder_queue(self, new_order: List[int]) -> None:
        """Reorder the playback queue."""
        self.playback_queue = new_order

    def get_queue(self) -> List[dict]:
        """Get the current playback queue."""
        queue = []
        for episode_id in self.playback_queue:
            episode = self.episode_controller.get_episode_by_id(episode_id)
            if episode:
                queue.append({
                    "id": episode.id,
                    "title": episode.title,
                    "feed_title": episode.feed.title,
                })
        return queue

    # 10. Delete downloaded episodes
    def delete_download(self, episode_id: int) -> bool:
        """Delete the downloaded episode. Returns True if successful."""
        metadata = self.metadata_controller.latest_metadata_for_episode(episode_id)
        if metadata and metadata.is_downloaded and metadata.download_path:
            try:
                os.remove(metadata.download_path)
            except FileNotFoundError:
                pass  # File might already be deleted

            # Insert a new metadata transaction marking file deletion
            self.metadata_controller.insert_data(
                episode_id=episode_id,
                is_downloaded=False,
                download_path=None,
                is_listened=metadata.is_listened,
                current_position=metadata.current_position,
            )
            return True
        return False

    # 11. Refresh feeds manually
    def refresh_feeds(self) -> None:
        """Manually refresh all feeds."""
        feeds = self.feed_manager.get_feeds()
        for feed in feeds:
            self.feed_manager.synchronize_feed(feed.feed_url)

    # 12. Auto-refresh feeds
    def start_auto_refresh(self) -> None:
        """Start the auto-refresh thread."""
        if self.auto_refresh_thread and self.auto_refresh_thread.is_alive():
            return

        self._auto_refresh_stop_flag = False
        self.auto_refresh_thread = threading.Thread(target=self._auto_refresh_loop)
        self.auto_refresh_thread.daemon = True
        self.auto_refresh_thread.start()

    def stop_auto_refresh(self) -> None:
        """Stop the auto-refresh thread."""
        self._auto_refresh_stop_flag = True

    def _auto_refresh_loop(self) -> None:
        """Background loop for auto-refreshing feeds."""
        while not self._auto_refresh_stop_flag:
            time.sleep(self.auto_refresh_interval)
            if not self._auto_refresh_stop_flag:
                self.refresh_feeds()

    # 13. Search for episodes or feeds
    def search_feeds(self, query: str) -> List[dict]:
        """Search for feeds by title or description."""
        feeds = self.feed_manager.get_feeds()
        results = []
        query_lower = query.lower()
        for feed in feeds:
            if (
                query_lower in feed.title.lower()
                or query_lower in (feed.description or "").lower()
            ):
                results.append({
                    "id": feed.id,
                    "title": feed.title,
                    "description": feed.description,
                    "url": feed.feed_url,
                })
        return results

    def search_episodes(self, query: str) -> List[dict]:
        """Search for episodes by title or description."""
        episodes = self.episode_controller.get_all_episodes()
        results = []
        query_lower = query.lower()
        for episode in episodes:
            if (
                query_lower in episode.title.lower()
                or query_lower in (episode.description or "").lower()
            ):
                results.append({
                    "id": episode.id,
                    "title": episode.title,
                    "description": episode.description,
                    "feed_title": episode.feed.title,
                    "audio_url": episode.audio_url,
                })
        return results

    def close(self) -> None:
        """Clean up resources."""
        self.stop_auto_refresh()
        self.player.close()

