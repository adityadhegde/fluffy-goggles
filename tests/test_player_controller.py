from unittest.mock import MagicMock

import pytest

from feed_controller.table_controllers import EpisodeController, EpisodeMetadataController
from player.controller import PlayerController


@pytest.fixture
def mock_mpv(mocker):
    mock = mocker.patch("mpv.MPV")
    instance = mock.return_value
    instance.time_pos = 0.0
    instance.duration = 100.0
    instance.pause = False
    instance.volume = 50
    return instance


@pytest.fixture
def player_controller(episode_controller: EpisodeController, metadata_controller: EpisodeMetadataController, mock_mpv):
    return PlayerController(episode_controller, metadata_controller)


def test_player_initialization(player_controller: PlayerController, mock_mpv):
    assert player_controller.player == mock_mpv
    mock_mpv.register_event_callback.assert_called_once()
    assert mock_mpv.observe_property.call_count == 2


def test_player_play(player_controller: PlayerController, mock_mpv, episode_controller, metadata_controller, feed_controller):
    # Setup episode
    feed = feed_controller.insert_data("url", "Feed", "Desc")
    ep = episode_controller.insert_data(feed.id, "Ep", "Desc", "Notes", "http://audio.mp3")
    
    player_controller.play(ep.id, ep.audio_url)
    
    assert player_controller.current_episode_id == ep.id
    mock_mpv.play.assert_called_once_with("http://audio.mp3")


def test_player_play_with_metadata(player_controller: PlayerController, mock_mpv, episode_controller, metadata_controller, feed_controller):
    feed = feed_controller.insert_data("url", "Feed", "Desc")
    ep = episode_controller.insert_data(feed.id, "Ep", "Desc", "Notes", "http://audio.mp3")
    
    metadata_controller.insert_data(ep.id, is_downloaded=True, download_path="/local.mp3", current_position=30)
    
    player_controller.play(ep.id, ep.audio_url)
    
    mock_mpv.play.assert_called_once_with("/local.mp3")
    assert player_controller.pending_seek_position == 30


def test_player_pause_resume_stop(player_controller: PlayerController, mock_mpv, episode_controller, feed_controller):
    feed = feed_controller.insert_data("url", "Feed", "Desc")
    ep = episode_controller.insert_data(feed.id, "Ep", "Desc", "Notes", "http://audio.mp3")
    
    player_controller.play(ep.id, ep.audio_url)
    
    player_controller.pause()
    assert mock_mpv.pause is True
    
    player_controller.resume()
    assert mock_mpv.pause is False
    
    player_controller.stop()
    assert player_controller.current_episode_id is None
    mock_mpv.stop.assert_called_once()


def test_player_seeking(player_controller: PlayerController, mock_mpv):
    player_controller.seek(10.5)
    mock_mpv.seek.assert_called_with(10.5, reference="absolute", precision="exact")
    
    player_controller.skip_forward()
    mock_mpv.seek.assert_called_with(5, reference="relative", precision="exact")
    
    player_controller.skip_backward()
    mock_mpv.seek.assert_called_with(-5, reference="relative", precision="exact")


def test_player_volume(player_controller: PlayerController, mock_mpv):
    player_controller.set_volume(80)
    assert mock_mpv.volume == 80
    
    player_controller.set_volume(150)
    assert mock_mpv.volume == 100
    
    player_controller.set_volume(-10)
    assert mock_mpv.volume == 0
    
    mock_mpv.volume = 50
    player_controller.increase_volume(20)
    assert mock_mpv.volume == 70
    
    player_controller.decrease_volume(30)
    assert mock_mpv.volume == 40


def test_player_event_handlers(player_controller: PlayerController, mock_mpv, episode_controller, metadata_controller, feed_controller):
    feed = feed_controller.insert_data("url", "Feed", "Desc")
    ep = episode_controller.insert_data(feed.id, "Ep", "Desc", "Notes", "http://audio.mp3")
    
    player_controller.play(ep.id, ep.audio_url)
    
    # Simulate end of file
    class MpvEventEndFile:
        pass
    
    mock_mpv.time_pos = 100.0
    player_controller._on_mpv_event(MpvEventEndFile())
    
    meta = metadata_controller.latest_metadata_for_episode(ep.id)
    assert meta.current_position == 100
    
    # Simulate pause property change
    mock_mpv.time_pos = 120.0
    player_controller._on_pause_property("pause", True)
    
    meta2 = metadata_controller.latest_metadata_for_episode(ep.id)
    assert meta2.current_position == 120

    # Simulate duration property change
    player_controller.pending_seek_position = 50
    player_controller._on_duration_property("duration", 200.0)
    mock_mpv.seek.assert_called_with(50, reference="absolute", precision="exact")
    assert player_controller.pending_seek_position == 0
