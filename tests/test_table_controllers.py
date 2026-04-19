from datetime import datetime

import pytest

from feed_controller.table_controllers import (
    EpisodeController,
    EpisodeMetadataController,
    FeedController,
)


def test_feed_controller_insert_and_get(feed_controller: FeedController):
    feed_url = "https://example.com/feed.xml"
    feed = feed_controller.insert_data(
        feed_url=feed_url, title="Test Feed", description="A test feed"
    )
    
    assert feed.id is not None
    assert feed.title == "Test Feed"
    assert feed.feed_url == feed_url
    assert feed.description == "A test feed"

    # Test get_by_url
    fetched_feed = feed_controller.get_by_url(feed_url)
    assert fetched_feed is not None
    assert fetched_feed.id == feed.id

    # Test get_feed_by_id
    fetched_feed_by_id = feed_controller.get_feed_by_id(feed.id)
    assert fetched_feed_by_id is not None
    assert fetched_feed_by_id.feed_url == feed_url


def test_feed_controller_duplicate_insert(feed_controller: FeedController):
    feed_url = "https://example.com/feed.xml"
    feed_controller.insert_data(feed_url, "Title", "Description")

    with pytest.raises(ValueError, match="already exists"):
        feed_controller.insert_data(feed_url, "Title 2", "Description 2")


def test_feed_controller_get_all_and_delete(feed_controller: FeedController):
    feed1 = feed_controller.insert_data("url1", "Title 1", "Desc 1")
    feed2 = feed_controller.insert_data("url2", "Title 2", "Desc 2")

    feeds = feed_controller.get_all_feeds()
    assert len(feeds) == 2
    
    feed_controller.delete_feed_by_id(feed1.id)
    
    feeds_after = feed_controller.get_all_feeds()
    assert len(feeds_after) == 1
    assert feeds_after[0].id == feed2.id
    
    assert feed_controller.get_feed_by_id(feed1.id) is None


def test_episode_controller_insert_and_get(
    feed_controller: FeedController, episode_controller: EpisodeController
):
    feed = feed_controller.insert_data("url1", "Feed 1", "Desc 1")
    
    publish_date = datetime(2026, 1, 1, 12, 0, 0)
    episode = episode_controller.insert_data(
        feed_id=feed.id,
        title="Ep 1",
        description="Ep Desc",
        show_notes="Show notes here",
        audio_url="https://example.com/audio1.mp3",
        publish_date=publish_date,
        duration=3600,
    )
    
    assert episode.id is not None
    assert episode.title == "Ep 1"
    assert episode.feed_id == feed.id
    
    fetched = episode_controller.get_episode_by_id(episode.id)
    assert fetched is not None
    assert fetched.audio_url == "https://example.com/audio1.mp3"


def test_episode_controller_queries(
    feed_controller: FeedController, episode_controller: EpisodeController
):
    feed = feed_controller.insert_data("url1", "Feed 1", "Desc 1")
    
    ep1 = episode_controller.insert_data(
        feed_id=feed.id,
        title="Ep 1",
        description="",
        show_notes="",
        audio_url="https://audio1.mp3"
    )
    ep2 = episode_controller.insert_data(
        feed_id=feed.id,
        title="Ep 2",
        description="",
        show_notes="",
        audio_url="https://audio2.mp3"
    )
    
    all_eps = episode_controller.get_all_episodes()
    assert len(all_eps) == 2
    
    eps_by_feed = episode_controller.get_episodes_by_feed_id(feed.id)
    assert len(eps_by_feed) == 2
    
    ep_by_url = episode_controller.get_episode_by_audio_url("https://audio1.mp3")
    assert ep_by_url is not None
    assert ep_by_url.id == ep1.id
    
    assert episode_controller.episode_exists(feed.id, "https://audio2.mp3") is True
    assert episode_controller.episode_exists(feed.id, "https://nonexistent.mp3") is False


def test_episode_controller_delete(
    feed_controller: FeedController, episode_controller: EpisodeController
):
    feed = feed_controller.insert_data("url1", "Feed 1", "Desc 1")
    ep = episode_controller.insert_data(
        feed_id=feed.id,
        title="Ep",
        description="",
        show_notes="",
        audio_url="url"
    )
    
    episode_controller.delete_episode_by_id(ep.id)
    assert episode_controller.get_episode_by_id(ep.id) is None


def test_episode_metadata_controller(
    feed_controller: FeedController,
    episode_controller: EpisodeController,
    metadata_controller: EpisodeMetadataController,
):
    feed = feed_controller.insert_data("url1", "Feed", "Desc")
    ep = episode_controller.insert_data(
        feed_id=feed.id,
        title="Ep",
        description="",
        show_notes="",
        audio_url="url"
    )
    
    assert metadata_controller.latest_metadata_for_episode(ep.id) is None
    
    metadata = metadata_controller.insert_data(
        episode_id=ep.id,
        is_downloaded=True,
        download_path="/path/to/dl",
        is_listened=False,
        current_position=100
    )
    
    assert metadata.id is not None
    assert metadata.episode_id == ep.id
    assert metadata.is_downloaded is True
    assert metadata.download_path == "/path/to/dl"
    assert metadata.current_position == 100
    
    # Insert a newer metadata
    metadata2 = metadata_controller.insert_data(
        episode_id=ep.id,
        is_downloaded=True,
        download_path="/path/to/dl",
        is_listened=True,
        current_position=200
    )
    
    latest = metadata_controller.latest_metadata_for_episode(ep.id)
    assert latest is not None
    assert latest.id == metadata2.id
    assert latest.current_position == 200
    assert latest.is_listened is True
