from unittest.mock import MagicMock

import pytest

from feed_controller.ingester import FeedManager
from feed_controller.table_controllers import (
    EpisodeController,
    EpisodeMetadataController,
    FeedController,
)


@pytest.fixture
def feed_manager(
    feed_controller: FeedController,
    episode_controller: EpisodeController,
    metadata_controller: EpisodeMetadataController,
):
    return FeedManager(
        feed_controller,
        episode_controller,
        metadata_controller,
    )


class MockFeedparserResult:
    def __init__(self, feed_data, entries_data):
        self.feed = feed_data
        self.entries = []
        for e in entries_data:
            entry = MagicMock()
            entry.get.side_effect = e.get
            if "enclosures" in e:
                enclosure = MagicMock()
                enclosure.href = e["enclosures"][0]["href"]
                entry.enclosures = [enclosure]
            else:
                entry.enclosures = []
            self.entries.append(entry)


def test_ingest_feed(feed_manager: FeedManager, mocker, feed_controller, episode_controller):
    feed_data = {"title": "Test Podcast", "description": "A test podcast"}
    entries_data = [
        {
            "title": "Episode 1",
            "description": "Desc 1",
            "summary": "Notes 1",
            "itunes_duration": "3600",
            "enclosures": [{"href": "http://audio1.mp3"}],
            "published_parsed": (2026, 1, 1, 12, 0, 0, 0, 0, 0),
        },
        {
            "title": "Episode 2",
            "description": "Desc 2",
            "enclosures": [{"href": "http://audio2.mp3"}],
        },
    ]

    mock_parse = mocker.patch("feedparser.parse")
    mock_parse.return_value = MockFeedparserResult(feed_data, entries_data)

    feed_url = "http://testfeed.com/feed.xml"
    feed_manager.ingest_feed(feed_url)

    mock_parse.assert_called_once_with(feed_url)

    feeds = feed_manager.get_feeds()
    assert len(feeds) == 1
    feed = feeds[0]
    assert feed.title == "Test Podcast"
    assert feed.feed_url == feed_url

    episodes = episode_controller.get_episodes_by_feed_id(feed.id)
    assert len(episodes) == 2
    ep_titles = [ep.title for ep in episodes]
    assert "Episode 1" in ep_titles
    assert "Episode 2" in ep_titles

    ep1 = next(ep for ep in episodes if ep.title == "Episode 1")
    assert ep1.audio_url == "http://audio1.mp3"
    assert ep1.duration == 3600


def test_ingest_feed_already_exists(feed_manager: FeedManager, mocker):
    feed_data = {"title": "Test Podcast", "description": "A test podcast"}
    entries_data = [{"title": "Episode 1", "enclosures": [{"href": "http://audio1.mp3"}]}]
    
    mock_parse = mocker.patch("feedparser.parse")
    mock_parse.return_value = MockFeedparserResult(feed_data, entries_data)
    
    feed_url = "http://testfeed.com/feed.xml"
    
    # First ingest
    feed_manager.ingest_feed(feed_url)
    
    # Second ingest should catch ValueError and fetch existing
    feed_manager.ingest_feed(feed_url)
    
    feeds = feed_manager.get_feeds()
    assert len(feeds) == 1


def test_synchronize_feed(
    feed_manager: FeedManager, mocker, episode_controller, feed_controller
):
    feed_url = "http://testfeed.com/feed.xml"

    # Stage 1: Ingest initial feed with 2 episodes
    feed_data = {"title": "Sync Podcast", "description": "A podcast"}
    entries_data_1 = [
        {"title": "Episode 1", "enclosures": [{"href": "http://audio1.mp3"}]},
        {"title": "Episode 2", "enclosures": [{"href": "http://audio2.mp3"}]},
    ]
    
    mock_parse = mocker.patch("feedparser.parse")
    mock_parse.return_value = MockFeedparserResult(feed_data, entries_data_1)
    
    feed_manager.ingest_feed(feed_url)
    
    feed = feed_manager.get_feeds()[0]
    episodes = episode_controller.get_episodes_by_feed_id(feed.id)
    assert len(episodes) == 2

    # Stage 2: Synchronize with a new feed where Ep 1 is deleted, Ep 2 is kept, Ep 3 is added
    entries_data_2 = [
        {"title": "Episode 2", "enclosures": [{"href": "http://audio2.mp3"}]},
        {"title": "Episode 3", "enclosures": [{"href": "http://audio3.mp3"}]},
    ]
    mock_parse.return_value = MockFeedparserResult(feed_data, entries_data_2)
    
    feed_manager.synchronize_feed(feed_url)
    
    updated_episodes = episode_controller.get_episodes_by_feed_id(feed.id)
    assert len(updated_episodes) == 2
    
    titles = [ep.title for ep in updated_episodes]
    assert "Episode 2" in titles
    assert "Episode 3" in titles
    assert "Episode 1" not in titles


def test_extractors(feed_manager: FeedManager):
    entry = MagicMock()
    entry.get.side_effect = lambda k, d=None: {"itunes_duration": "123", "published_parsed": (2026, 1, 1, 12, 0, 0, 0, 0, 0)}.get(k, d)
    
    duration = feed_manager._extract_duration(entry)
    assert duration == 123
    
    date = feed_manager._extract_publish_date(entry)
    assert date.year == 2026

    # Test corrupted duration
    entry2 = MagicMock()
    entry2.get.side_effect = lambda k, d=None: {"itunes_duration": "invalid"}.get(k, d)
    assert feed_manager._extract_duration(entry2) is None
    
    # Test boolean parsers
    assert feed_manager._parse_bool("true") is True
    assert feed_manager._parse_bool("yes") is True
    assert feed_manager._parse_bool("false") is False
    assert feed_manager._parse_bool(1) is True
    
    # Test int parsers
    assert feed_manager._parse_int("10") == 10
    assert feed_manager._parse_int("10.5") == 10
    assert feed_manager._parse_int("invalid", default=5) == 5
