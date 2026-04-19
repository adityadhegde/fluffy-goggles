# using the config file, the main.py file initializes the database connection 
# and creates instances of the FeedController, EpisodeController, and EpisodeMetadataController. 
# It then creates an instance of the PodPlayerApp, which is responsible for all application logic, 
# including ingesting feeds and managing playback.
# this is exposed to the user through a TUI   
# that allows them to interact with the application, such as adding new feeds, 
# listing episodes, and controlling playback.


import json
import curses
import textwrap
from typing import List
from pathlib import Path

from app.app import PodPlayerApp
from logger import get_logger
from config import APP_DIR

logger = get_logger(__name__)


class PodPlayerTUI:
    """Text-based UI for the podcast player."""

    def __init__(self, stdscr: "curses._CursesWindow"):
        self.stdscr = stdscr
        
        config = {}
        try:
            config_path = APP_DIR / "config.json"
            if config_path.exists():
                with open(config_path, "r") as f:
                    config = json.load(f)
        except Exception:
            pass
            
        self.seek_step = config.get("seek_step", 10)
        
        db_path = config.get("sqllite3_path", "podplayer.db")
        if not Path(db_path).is_absolute():
            db_path = str(APP_DIR / db_path)
            
        self.download_dir = config.get("download_directory", "downloads")
        if not Path(self.download_dir).is_absolute():
            self.download_dir = str(APP_DIR / self.download_dir)
            
        self.app = PodPlayerApp(db_path=db_path)
        self.screen = "feeds"
        self.selected_feed = 0
        self.selected_episode = 0
        self.message = "Press ? for help."
        self.search_query = ""
        self.filter_results: List[dict] = []
        self.search_mode = "input"
        self.selected_search_result = 0
        self.playing_episode_id: int | None = None

    def run(self) -> None:
        logger.info("Initializing TUI and starting application loops.")
        curses.curs_set(0)
        self.stdscr.nodelay(False)
        self.stdscr.keypad(True)
        self.app.start_auto_refresh()

        while True:
            self.draw()
            key = self.stdscr.getch()
            logger.debug(f"Key pressed: {key}")
            if key == ord("q"):
                logger.info("Quit command received. Shutting down application.")
                self.app.close()
                break
            self.handle_key(key)

    def draw(self) -> None:
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        self.draw_header(width)
        if self.screen == "feeds":
            self.draw_feed_list(height, width)
        elif self.screen == "episodes":
            self.draw_episode_list(height, width)
        elif self.screen == "search":
            self.draw_search_results(height, width)
        elif self.screen == "help":
            self.draw_help_screen(height, width)
        self.draw_footer(height, width)
        self.stdscr.refresh()

    def draw_header(self, width: int) -> None:
        title = "PodPlayer TUI"
        self.stdscr.addstr(0, 2, title, curses.A_REVERSE)
        self.stdscr.addstr(0, len(title) + 4, "(feeds / episodes / search)")
        self.stdscr.hline(1, 0, curses.ACS_HLINE, width)

    def draw_footer(self, height: int, width: int) -> None:
        self.stdscr.hline(height - 3, 0, curses.ACS_HLINE, width)
        wrapped = textwrap.wrap(self.message, width - 4)
        for i, line in enumerate(wrapped[-2:]):
            self.stdscr.addstr(height - 2 + i, 2, line)

    def draw_feed_list(self, height: int, width: int) -> None:
        feeds = self.app.list_feeds()
        if not feeds:
            self.stdscr.addstr(3, 2, "No feeds available. Press 'a' to add a feed.")
            return

        self.stdscr.addstr(3, 2, "Feeds:")
        visible_count = height - 8
        top = max(0, self.selected_feed - visible_count + 1)
        for index, feed in enumerate(feeds[top : top + visible_count]):
            line = f" {feed['id']}: {feed['title']}"
            y = 5 + index
            if top + index == self.selected_feed:
                self.stdscr.addstr(y, 2, line[: width - 4], curses.A_REVERSE)
            else:
                self.stdscr.addstr(y, 2, line[: width - 4])

    def draw_episode_list(self, height: int, width: int) -> None:
        feeds = self.app.list_feeds()
        if not feeds:
            self.message = "No feeds available. Press 'a' to add a feed."
            self.screen = "feeds"
            return

        feed = feeds[self.selected_feed]
        episodes = self.app.list_episodes(feed["id"])
        self.stdscr.addstr(3, 2, f"Feed: {feed['title']}")
        self.stdscr.addstr(4, 2, f"Episodes: {len(episodes)}")
        self.stdscr.addstr(5, 2, "Use arrow keys to select, p=play, d=download, b=back")

        visible_count = height - 11
        top = max(0, self.selected_episode - visible_count + 1)
        for index, episode in enumerate(episodes[top : top + visible_count]):
            line = f" {episode['id']}: {episode['title']}"
            y = 7 + index
            if top + index == self.selected_episode:
                self.stdscr.addstr(y, 2, line[: width - 4], curses.A_REVERSE)
            else:
                self.stdscr.addstr(y, 2, line[: width - 4])

    def draw_search_results(self, height: int, width: int) -> None:
        self.stdscr.addstr(3, 2, f"Search: {self.search_query}")
        if self.search_mode == "input":
            self.stdscr.addstr(4, 2, "Type query, press Enter to search, Esc to cancel.")
        else:
            self.stdscr.addstr(4, 2, "Up/Down/j/k to select, p/Enter to play, Esc to search again.")

        visible_count = height - 8
        top = max(0, self.selected_search_result - visible_count + 1)
        for index, item in enumerate(self.filter_results[top : top + visible_count]):
            line = f" {item['id']}: {item['title']} ({item.get('feed_title', item.get('url', ''))})"
            y = 6 + index
            if self.search_mode == "results" and top + index == self.selected_search_result:
                self.stdscr.addstr(y, 2, line[: width - 4], curses.A_REVERSE)
            else:
                self.stdscr.addstr(y, 2, line[: width - 4])

    def draw_help_screen(self, height: int, width: int) -> None:
        self.stdscr.addstr(3, 2, "Help & Keyboard Shortcuts:", curses.A_BOLD)
        help_text = [
            "Global:",
            "  q        : Quit application",
            "  h / ?    : Show this help screen",
            "  b        : Back / Close help",
            "",
            "Feeds:",
            "  j / k    : Move selection down / up",
            "  Enter    : Open selected feed",
            "  a        : Add new feed",
            "  r        : Refresh feeds manually",
            "  s        : Search across feeds and episodes",
            "",
            "Episodes / Playback:",
            "  j / k    : Move selection down / up",
            "  Spacebar : Play / Pause / Resume",
            "  Enter    : Play / Pause / Resume",
            "  d        : Download selected episode",
            "  x        : Stop playback",
            "  < / >    : Seek backward / forward",
            "  + / ]    : Increase volume",
            "  - / [    : Decrease volume",
        ]
        for i, line in enumerate(help_text):
            if 5 + i < height - 3:
                self.stdscr.addstr(5 + i, 2, line[:width - 4])

    def handle_key(self, key: int) -> None:
        if self.screen == "feeds":
            self.handle_feeds_key(key)
        elif self.screen == "episodes":
            self.handle_episodes_key(key)
        elif self.screen == "search":
            self.handle_search_key(key)
        elif self.screen == "help":
            if key in (ord("b"), ord("h"), ord("?")):
                self.screen = getattr(self, "previous_screen", "feeds")
                self.message = ""

    def handle_feeds_key(self, key: int) -> None:
        feeds = self.app.list_feeds()
        if key in (curses.KEY_DOWN, ord("j")):
            self.selected_feed = min(len(feeds) - 1, self.selected_feed + 1)
        elif key in (curses.KEY_UP, ord("k")):
            self.selected_feed = max(0, self.selected_feed - 1)
        elif key in (ord("\n"), curses.KEY_ENTER):
            logger.info("Transitioning to 'episodes' screen.")
            self.screen = "episodes"
            self.selected_episode = 0
        elif key == ord("a"):
            self.handle_add_feed()
        elif key == ord("r"):
            self.app.refresh_feeds()
            self.message = "Feeds refreshed."
        elif key == ord("s"):
            self.handle_search()
        elif key == ord("h"):
            self.show_help()
        else:
            self.default_navigation(key)

    def handle_episodes_key(self, key: int) -> None:
        feeds = self.app.list_feeds()
        if not feeds:
            self.screen = "feeds"
            return

        episodes = self.app.list_episodes(feeds[self.selected_feed]["id"])
        if key in (curses.KEY_DOWN, ord("j")):
            self.selected_episode = min(len(episodes) - 1, self.selected_episode + 1)
        elif key in (curses.KEY_UP, ord("k")):
            self.selected_episode = max(0, self.selected_episode - 1)
        elif key in (ord(" "), ord("p"), ord("\n"), curses.KEY_ENTER):
            if episodes:
                ep_id = episodes[self.selected_episode]["id"]
                if self.app.player.current_episode_id == ep_id:
                    if self.app.player.is_playing():
                        self.app.player.pause()
                        self.message = "Playback paused."
                    else:
                        self.app.player.resume()
                        self.message = "Playback resumed."
                else:
                    self.app.play_episode(ep_id)
                    self.message = "Playing episode."
        elif key == ord("d"):
            if episodes:
                success = self.app.download_episode(episodes[self.selected_episode]["id"], download_dir=self.download_dir)
                self.message = "Downloaded metadata saved." if success else "Download failed."
        elif key == ord("b"):
            self.screen = "feeds"
        elif key == ord("h"):
            self.show_help()
        else:
            self.default_navigation(key)

    def handle_search_key(self, key: int) -> None:
        if getattr(self, "search_mode", "input") == "input":
            if key == 27:
                self.screen = "feeds"
                self.search_query = ""
                self.filter_results = []
            elif key in (ord("\n"), curses.KEY_ENTER):
                self.filter_results = self.app.search_episodes(self.search_query)
                self.message = f"Found {len(self.filter_results)} results."
                self.search_mode = "results"
                self.selected_search_result = 0
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                self.search_query = self.search_query[:-1]
            else:
                ch = chr(key)
                if ch.isprintable():
                    self.search_query += ch
        else:
            if key == 27:
                self.search_mode = "input"
                self.message = "Press Enter to search, Esc to cancel."
            elif key in (curses.KEY_DOWN, ord("j")):
                self.selected_search_result = min(len(self.filter_results) - 1, self.selected_search_result + 1)
            elif key in (curses.KEY_UP, ord("k")):
                self.selected_search_result = max(0, self.selected_search_result - 1)
            elif key in (ord(" "), ord("p"), ord("\n"), curses.KEY_ENTER):
                if self.filter_results:
                    ep_id = self.filter_results[self.selected_search_result]["id"]
                    if self.app.player.current_episode_id == ep_id:
                        if self.app.player.is_playing():
                            self.app.player.pause()
                            self.message = "Playback paused."
                        else:
                            self.app.player.resume()
                            self.message = "Playback resumed."
                    else:
                        self.app.play_episode(ep_id)
                        self.message = "Playing episode."
            elif key == ord("d"):
                if self.filter_results:
                    ep_id = self.filter_results[self.selected_search_result]["id"]
                    success = self.app.download_episode(ep_id, download_dir=self.download_dir)
                    self.message = "Downloaded metadata saved." if success else "Download failed."
            else:
                self.default_navigation(key)

    def handle_add_feed(self) -> None:
        feed_url = self.prompt_input("Add feed URL: ")
        if not feed_url:
            self.message = "Add feed canceled."
            return

        if self.app.add_feed(feed_url):
            self.message = "Feed added successfully."
        else:
            self.message = "Failed to add feed."

    def handle_search(self) -> None:
        logger.info("Transitioning to 'search' screen.")
        self.screen = "search"
        self.search_query = ""
        self.filter_results = []
        self.search_mode = "input"
        self.selected_search_result = 0

    def show_help(self) -> None:
        if self.screen != "help":
            self.previous_screen = self.screen
            self.screen = "help"
            self.message = "Press 'b' to return."

    def prompt_input(self, prompt_text: str) -> str:
        curses.echo()
        curses.curs_set(1)
        height, width = self.stdscr.getmaxyx()
        self.stdscr.addstr(height - 2, 2, prompt_text)
        self.stdscr.clrtoeol()
        self.stdscr.refresh()
        value = self.stdscr.getstr(height - 2, len(prompt_text) + 2, width - len(prompt_text) - 4)
        curses.noecho()
        curses.curs_set(0)
        return value.decode("utf-8").strip()

    def default_navigation(self, key: int) -> None:
        if key == ord("?"):
            self.show_help()
        elif key == ord("x"):
            self.app.player.stop()
            self.message = "Stopped playback."
        elif key == ord(" "):
            if self.app.player.current_episode_id is not None:
                if self.app.player.is_playing():
                    self.app.player.pause()
                    self.message = "Playback paused."
                else:
                    self.app.player.resume()
                    self.message = "Playback resumed."
            else:
                self.message = "No active playback to pause/resume."
        elif key == ord(">"):
            self.app.player.skip_forward(self.seek_step)
            self.message = f"Skipped forward {self.seek_step}s."
        elif key == ord("<"):
            self.app.player.skip_backward(self.seek_step)
            self.message = f"Skipped backward {self.seek_step}s."
        elif key in (ord("+"), ord("]")):
            self.app.player.increase_volume()
            self.message = "Volume increased."
        elif key in (ord("-"), ord("[")):
            self.app.player.decrease_volume()
            self.message = "Volume decreased."


def main(stdscr: "curses._CursesWindow") -> None:
    tui = PodPlayerTUI(stdscr)
    tui.run()


def entrypoint() -> None:
    """Entry point for the command-line script."""
    import os
    import sys
    from config import APP_DIR
    
    # Redirect C-level stderr to the log file to prevent ALSA/PipeWire warnings 
    # from directly writing to the terminal and corrupting the curses TUI.
    try:
        log_path = APP_DIR / "podplayer.log"
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        os.dup2(fd, sys.stderr.fileno())
    except Exception:
        pass

    curses.wrapper(main)


if __name__ == "__main__":
    entrypoint()

