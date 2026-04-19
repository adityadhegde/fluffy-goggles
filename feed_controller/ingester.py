# This script defines a class does the following:
# 1. It reads a feed from a specified URL.
# 2. It extracts the feed's title and description.
# 3. It inserts the feed's information into a database using a controller.
# 4. It iterates through each episode in the feed, extracting relevant details and inserting them into the database as well.
# 5. It also manages EpisodeMetadata records when provided.

from datetime import datetime
from typing import Any

import feedparser
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker
from feed_controller.table_controllers import (
    EpisodeController,
    EpisodeMetadataController,
    FeedController,
    Feed,
)
from logger import get_logger

logger = get_logger(__name__)


class FeedManager:
    """Class responsible for ingesting podcast feed data into the database."""

    def __init__(
        self,
        feed_controller: FeedController,
        episode_controller: EpisodeController,
        metadata_controller: EpisodeMetadataController | None = None,
    ):
        self.feed_controller = feed_controller
        self.episode_controller = episode_controller
        self.metadata_controller = metadata_controller

    def get_feeds(self) -> list[Feed]:
        """Retrieve all feeds from the database."""
        return self.feed_controller.get_all_feeds()

    def ingest_feed(self, feed_url: str) -> None:
        """Ingest a podcast feed from the specified URL."""
        logger.info(f"Ingesting feed from URL: {feed_url}")
        parsed_feed = feedparser.parse(feed_url)
        title = parsed_feed.feed.get("title", "No Title")
        description = parsed_feed.feed.get("description", "No Description")

        try:
            feed = self.feed_controller.insert_data(feed_url, title, description)
            logger.debug(f"Inserted new feed: {title}")
        except ValueError:
            logger.warning(f"Feed already exists, retrieving existing feed for {feed_url}.")
            feed = self.feed_controller.get_by_url(feed_url)
            if feed is None:
                logger.error(f"Failed to retrieve existing feed with URL '{feed_url}'.")
                raise ValueError(f"Failed to retrieve existing feed with URL '{feed_url}'.")

        for entry in parsed_feed.entries:
            episode = self._insert_episode_from_entry(feed.id, entry)
            self._insert_episode_metadata_from_entry(episode.id, entry)

    def synchronize_feed(self, feed_url: str) -> None:
        """Synchronize the feed data by re-ingesting the feed."""
        logger.info(f"Synchronizing feed: {feed_url}")
        new_parsed_feed = feedparser.parse(feed_url)
        existing_feed = self.feed_controller.get_by_url(feed_url)

        if not existing_feed:
            logger.info("Feed not found during sync, ingesting instead.")
            self.ingest_feed(feed_url)
            return

        existing_episodes = self.episode_controller.get_episodes_by_feed_id(existing_feed.id)
        existing_episode_titles = {ep.title for ep in existing_episodes}
        new_episode_titles = {
            self._normalize_entry_title(entry)
            for entry in self._get_entries(new_parsed_feed)
        }

        for episode in existing_episodes:
            if episode.title not in new_episode_titles:
                if self.metadata_controller:
                    self.metadata_controller.delete_metadata_by_episode_id(episode.id)
                self.episode_controller.delete_episode_by_id(episode.id)

        for entry in self._get_entries(new_parsed_feed):
            episode_title = self._normalize_entry_title(entry)
            if episode_title not in existing_episode_titles:
                episode = self._insert_episode_from_entry(existing_feed.id, entry)
                self._insert_episode_metadata_from_entry(episode.id, entry)

    def _insert_episode_from_entry(self, feed_id: int, entry: Any) -> Any:
        episode_title = entry.get("title", "No Title")
        episode_description = entry.get("description", "No Description")
        show_notes = entry.get("summary", "No Show Notes")
        audio_url = self._extract_audio_url(entry)
        duration = self._extract_duration(entry)
        publish_date = self._extract_publish_date(entry)

        return self.episode_controller.insert_data(
            feed_id=feed_id,
            title=episode_title,
            description=episode_description,
            show_notes=show_notes,
            audio_url=audio_url,
            publish_date=publish_date,
            duration=duration,
        )

    def _insert_episode_metadata_from_entry(self, episode_id: int, entry: Any) -> None:
        if self.metadata_controller is None:
            return

        metadata = self._extract_episode_metadata(entry)
        self.metadata_controller.insert_data(
            episode_id=episode_id,
            is_downloaded=metadata["is_downloaded"],
            download_path=metadata["download_path"],
            is_listened=metadata["is_listened"],
            current_position=metadata["current_position"],
        )

    def _extract_audio_url(self, entry: Any) -> str:
        if entry.enclosures:
            return entry.enclosures[0].href
        return entry.get("enclosures", [{}])[0].get("href", "") if entry.get("enclosures") else ""

    def _extract_duration(self, entry: Any) -> int | None:
        duration = entry.get("itunes_duration") or entry.get("duration")
        if duration is None:
            return None
        try:
            return int(duration)
        except (ValueError, TypeError):
            return None

    def _extract_publish_date(self, entry: Any) -> datetime | None:
        publish_date = entry.get("published_parsed") or entry.get("updated_parsed")
        if publish_date is None:
            return None
        return datetime(*publish_date[:6])

    def _extract_episode_metadata(self, entry: Any) -> dict[str, Any]:
        def first_not_none(*keys: str) -> Any:
            for key in keys:
                value = entry.get(key)
                if value is not None:
                    return value
            return None

        return {
            "is_downloaded": self._parse_bool(first_not_none("is_downloaded", "downloaded", "episode_downloaded", "podcast_downloaded")),
            "download_path": first_not_none(
                "download_path",
                "episode_download_path",
                "podcast_download_path",
                "file_path",
            ),
            "is_listened": self._parse_bool(first_not_none("is_listened", "listened", "episode_listened", "podcast_listened")),
            "current_position": self._parse_int(first_not_none("current_position", "playback_position", "position"), default=0),
        }

    def _parse_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "t"}
        return False

    def _parse_int(self, value: Any, default: int = 0) -> int:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default

    def _get_entries(self, parsed_feed: Any) -> list[Any]:
        entries = getattr(parsed_feed, "entries", None)
        if isinstance(entries, list):
            return [entry for entry in entries if entry is not None]
        return []

    def _normalize_entry_title(self, entry: Any) -> str:
        """Extract and normalize entry title to ensure it's a hashable string."""
        title = entry.get("title", "No Title")
        if isinstance(title, str):
            return title
        if isinstance(title, list):
            return str(title[0]) if title else "No Title"
        return str(title) if title is not None else "No Title"
