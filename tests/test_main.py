from unittest.mock import MagicMock

import pytest

from main import PodPlayerTUI, main


@pytest.fixture
def mock_curses(mocker):
    curses = mocker.patch("main.curses")
    stdscr = MagicMock()
    stdscr.getmaxyx.return_value = (24, 80)
    stdscr.getstr.return_value = b"test_input"
    curses.KEY_UP = 259
    curses.KEY_DOWN = 258
    curses.KEY_ENTER = 343
    curses.KEY_BACKSPACE = 263
    curses.ACS_HLINE = 0
    curses.A_REVERSE = 1
    return curses, stdscr


@pytest.fixture
def mock_app(mocker):
    return mocker.patch("main.PodPlayerApp").return_value


def test_tui_initialization(mock_curses, mock_app):
    curses, stdscr = mock_curses
    tui = PodPlayerTUI(stdscr)
    
    assert tui.stdscr == stdscr
    assert tui.app == mock_app
    assert tui.screen == "feeds"


def test_tui_run_loop(mock_curses, mock_app, mocker):
    curses, stdscr = mock_curses
    tui = PodPlayerTUI(stdscr)
    
    # Run once then exit on 'q'
    stdscr.getch.side_effect = [ord("j"), ord("q")]
    
    tui.run()
    
    assert stdscr.getch.call_count == 2
    mock_app.start_auto_refresh.assert_called_once()
    mock_app.close.assert_called_once()


def test_tui_draw_feeds(mock_curses, mock_app):
    curses, stdscr = mock_curses
    mock_app.list_feeds.return_value = [{"id": 1, "title": "Feed 1"}]
    
    tui = PodPlayerTUI(stdscr)
    tui.screen = "feeds"
    tui.draw()
    
    stdscr.erase.assert_called_once()
    stdscr.refresh.assert_called_once()
    # verify "Feeds:" was written
    stdscr.addstr.assert_any_call(3, 2, "Feeds:")


def test_tui_handle_feeds_key(mock_curses, mock_app):
    curses, stdscr = mock_curses
    mock_app.list_feeds.return_value = [{"id": 1, "title": "Feed 1"}, {"id": 2, "title": "Feed 2"}]
    
    tui = PodPlayerTUI(stdscr)
    tui.screen = "feeds"
    
    # Test navigation down
    tui.handle_key(curses.KEY_DOWN)
    assert tui.selected_feed == 1
    
    # Test navigation up
    tui.handle_key(curses.KEY_UP)
    assert tui.selected_feed == 0
    
    # Test select feed
    tui.handle_key(curses.KEY_ENTER)
    assert tui.screen == "episodes"


def test_tui_handle_episodes_key(mock_curses, mock_app):
    curses, stdscr = mock_curses
    mock_app.list_feeds.return_value = [{"id": 1, "title": "Feed 1"}]
    mock_app.list_episodes.return_value = [{"id": 1, "title": "Ep 1"}, {"id": 2, "title": "Ep 2"}]
    
    tui = PodPlayerTUI(stdscr)
    tui.screen = "episodes"
    
    tui.handle_key(curses.KEY_DOWN)
    assert tui.selected_episode == 1
    
    tui.handle_key(ord("p"))
    mock_app.play_episode.assert_called_once_with(2)
    
    tui.handle_key(ord("b"))
    assert tui.screen == "feeds"


def test_tui_handle_search(mock_curses, mock_app):
    curses, stdscr = mock_curses
    
    tui = PodPlayerTUI(stdscr)
    tui.screen = "search"
    tui.search_query = "py"
    
    tui.handle_key(ord("t"))
    assert tui.search_query == "pyt"
    
    tui.handle_key(curses.KEY_BACKSPACE)
    assert tui.search_query == "py"
    
    mock_app.search_episodes.return_value = [{"id": 1, "title": "Pytest"}]
    tui.handle_key(curses.KEY_ENTER)
    
    mock_app.search_episodes.assert_called_once_with("py")
    assert len(tui.filter_results) == 1


def test_tui_prompt_input(mock_curses, mock_app):
    curses, stdscr = mock_curses
    tui = PodPlayerTUI(stdscr)
    
    result = tui.prompt_input("Test:")
    assert result == "test_input"
    curses.echo.assert_called_once()
    curses.noecho.assert_called_once()


def test_tui_draw_methods(mock_curses, mock_app):
    curses, stdscr = mock_curses
    tui = PodPlayerTUI(stdscr)
    
    mock_app.list_feeds.return_value = [{"id": 1, "title": "Feed 1", "url": "url1"}]
    mock_app.list_episodes.return_value = [{"id": 1, "title": "Ep 1", "audio_url": "aud1"}]
    
    # Test episodes screen
    tui.screen = "episodes"
    tui.draw()
    stdscr.addstr.assert_any_call(3, 2, "Feed: Feed 1")
    
    # Test search screen
    tui.screen = "search"
    tui.search_query = "q"
    tui.filter_results = [{"id": 1, "title": "Ep 1", "feed_title": "Feed 1"}]
    tui.draw()
    stdscr.addstr.assert_any_call(3, 2, "Search: q")


def test_tui_feeds_actions(mock_curses, mock_app, mocker):
    curses, stdscr = mock_curses
    mock_app.list_feeds.return_value = [{"id": 1, "title": "Feed 1"}]
    tui = PodPlayerTUI(stdscr)
    tui.screen = "feeds"
    
    # Test a
    mocker.patch.object(tui, "prompt_input", return_value="url")
    mock_app.add_feed.return_value = True
    tui.handle_key(ord("a"))
    mock_app.add_feed.assert_called_once_with("url")
    
    # Test r
    tui.handle_key(ord("r"))
    mock_app.refresh_feeds.assert_called_once()
    
    # Test s
    tui.handle_key(ord("s"))
    assert tui.screen == "search"
    
    # Test h
    tui.screen = "feeds"
    tui.handle_key(ord("h"))
    assert "Press 'b'" in tui.message


def test_tui_episodes_actions(mock_curses, mock_app, mocker):
    curses, stdscr = mock_curses
    mock_app.list_feeds.return_value = [{"id": 1, "title": "Feed 1"}]
    mock_app.list_episodes.return_value = [{"id": 1, "title": "Ep 1"}]
    tui = PodPlayerTUI(stdscr)
    tui.screen = "episodes"
    
    # Test d
    mock_app.download_episode.return_value = True
    tui.handle_key(ord("d"))
    mock_app.download_episode.assert_called_once_with(1)
    
    # Test < (seek backward)
    tui.handle_key(ord("<"))
    mock_app.player.skip_backward.assert_called_once()
    
    # Test > (seek forward)
    tui.handle_key(ord(">"))
    mock_app.player.skip_forward.assert_called_once()
    
    # Test default navigation
    tui.handle_key(ord("x"))
    mock_app.player.stop.assert_called_once()
    
    # Test Spacebar (play/pause toggle)
    mock_app.player.current_episode_id = 1
    mock_app.player.is_playing.return_value = True
    tui.handle_key(ord(" "))
    mock_app.player.pause.assert_called_once()


def test_tui_search_actions(mock_curses, mock_app):
    curses, stdscr = mock_curses
    tui = PodPlayerTUI(stdscr)
    tui.screen = "search"
    
    # Test Esc
    tui.handle_key(27)
    assert tui.screen == "feeds"
