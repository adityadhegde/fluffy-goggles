import os
from unittest.mock import MagicMock

import pytest

from app.app import PodPlayerApp


@pytest.fixture
def podplayer_app(mocker):
    # Use in-memory SQLite database
    app = PodPlayerApp(db_path=":memory:")
    
    # Mock player to prevent real media initialization
    mocker.patch.object(app, "player")
    
    return app


def test_add_and_list_feeds(podplayer_app: PodPlayerApp, mocker):
    mock_ingest = mocker.patch.object(podplayer_app.feed_manager, "ingest_feed")
    
    # Needs to manually insert since ingest is mocked
    podplayer_app.feed_controller.insert_data("url", "Feed Title", "Desc")
    
    result = podplayer_app.add_feed("url")
    assert result is True
    mock_ingest.assert_called_once_with("url")
    
    feeds = podplayer_app.list_feeds()
    assert len(feeds) == 1
    assert feeds[0]["title"] == "Feed Title"


def test_list_and_play_episodes(podplayer_app: PodPlayerApp):
    feed = podplayer_app.feed_controller.insert_data("url", "Feed", "Desc")
    ep = podplayer_app.episode_controller.insert_data(feed.id, "Ep 1", "Desc", "Notes", "audio1.mp3")
    
    episodes = podplayer_app.list_episodes(feed.id)
    assert len(episodes) == 1
    assert episodes[0]["title"] == "Ep 1"
    
    result = podplayer_app.play_episode(ep.id)
    assert result is True
    podplayer_app.player.play.assert_called_once_with(ep.id, "audio1.mp3")
    assert ep.id in podplayer_app.playback_history


def test_play_episode_invalid(podplayer_app: PodPlayerApp):
    result = podplayer_app.play_episode(999)
    assert result is False


def test_seek_and_position(podplayer_app: PodPlayerApp):
    podplayer_app.player.get_current_position.return_value = 45.0
    
    pos = podplayer_app.get_current_position()
    assert pos == 45.0
    
    podplayer_app.seek_to_position(100.0)
    podplayer_app.player.seek.assert_called_once_with(100.0, reference="absolute")


def test_download_and_delete(podplayer_app: PodPlayerApp, tmp_path, mocker):
    mock_response = mocker.MagicMock()
    mock_response.iter_content.return_value = [b"dummy_data"]
    mocker.patch("requests.get", return_value=mock_response)
    
    feed = podplayer_app.feed_controller.insert_data("url", "Feed", "Desc")
    ep = podplayer_app.episode_controller.insert_data(feed.id, "Ep", "Desc", "Notes", "audio.mp3")
    
    # Use temporary directory for downloads
    download_dir = str(tmp_path / "downloads")
    
    result = podplayer_app.download_episode(ep.id, download_dir=download_dir, sync=True)
    assert result is True
    
    metadata = podplayer_app.metadata_controller.latest_metadata_for_episode(ep.id)
    assert metadata.is_downloaded is True
    assert metadata.download_path.startswith(download_dir)
    assert os.path.exists(metadata.download_path)
    
    delete_result = podplayer_app.delete_download(ep.id)
    assert delete_result is True
    assert not os.path.exists(metadata.download_path)
    
    metadata_after = podplayer_app.metadata_controller.latest_metadata_for_episode(ep.id)
    assert metadata_after.is_downloaded is False
    assert metadata_after.download_path is None


def test_playback_history_and_queue(podplayer_app: PodPlayerApp):
    feed = podplayer_app.feed_controller.insert_data("url", "Feed", "Desc")
    ep1 = podplayer_app.episode_controller.insert_data(feed.id, "Ep 1", "Desc", "Notes", "audio1.mp3")
    ep2 = podplayer_app.episode_controller.insert_data(feed.id, "Ep 2", "Desc", "Notes", "audio2.mp3")
    
    podplayer_app.play_episode(ep1.id)
    podplayer_app.play_episode(ep2.id)
    
    history = podplayer_app.get_playback_history()
    assert len(history) == 2
    assert history[0]["id"] == ep1.id
    assert history[1]["id"] == ep2.id
    
    podplayer_app.add_to_queue(ep1.id)
    podplayer_app.add_to_queue(ep2.id)
    
    queue = podplayer_app.get_queue()
    assert len(queue) == 2
    
    podplayer_app.reorder_queue([ep2.id, ep1.id])
    assert podplayer_app.playback_queue == [ep2.id, ep1.id]
    
    podplayer_app.remove_from_queue(ep2.id)
    assert podplayer_app.playback_queue == [ep1.id]


def test_auto_refresh(podplayer_app: PodPlayerApp, mocker):
    mock_sync = mocker.patch.object(podplayer_app.feed_manager, "synchronize_feed")
    mock_thread = mocker.patch("threading.Thread")
    mocker.patch("time.sleep")
    
    # Add a feed
    podplayer_app.feed_controller.insert_data("url", "Feed", "Desc")
    
    podplayer_app.start_auto_refresh()
    mock_thread.assert_called_once()
    
    # Manually run the loop synchronously
    podplayer_app._auto_refresh_stop_flag = False
    
    # Make sync set the stop flag so loop exits after 1 iteration
    def sync_side_effect(url):
        podplayer_app._auto_refresh_stop_flag = True
        
    mock_sync.side_effect = sync_side_effect
    
    podplayer_app._auto_refresh_loop()
    
    mock_sync.assert_called_once_with("url")



def test_search(podplayer_app: PodPlayerApp):
    feed1 = podplayer_app.feed_controller.insert_data("url1", "Python News", "Latest python stuff")
    feed2 = podplayer_app.feed_controller.insert_data("url2", "Tech Talk", "General tech")
    
    ep1 = podplayer_app.episode_controller.insert_data(feed1.id, "Pytest basics", "desc", "notes", "aud1.mp3")
    ep2 = podplayer_app.episode_controller.insert_data(feed2.id, "Hardware news", "desc", "notes", "aud2.mp3")
    
    feed_results = podplayer_app.search_feeds("python")
    assert len(feed_results) == 1
    assert feed_results[0]["id"] == feed1.id
    
    ep_results = podplayer_app.search_episodes("pytest")
    assert len(ep_results) == 1
    assert ep_results[0]["id"] == ep1.id


def test_close(podplayer_app: PodPlayerApp):
    podplayer_app.close()
    assert podplayer_app._auto_refresh_stop_flag is True
    podplayer_app.player.close.assert_called_once()
