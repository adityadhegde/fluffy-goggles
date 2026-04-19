from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import Engine, ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, Session, sessionmaker, joinedload
from logger import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    feed_url: Mapped[str] = mapped_column(String(2048), nullable=False, unique=True)
    episodes: Mapped[list[Episode]] = relationship("Episode", back_populates="feed", cascade="all, delete-orphan")


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(primary_key=True)
    feed_id: Mapped[int] = mapped_column(ForeignKey("feeds.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    show_notes: Mapped[str] = mapped_column(Text, nullable=True)
    audio_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    duration: Mapped[int | None] = mapped_column(Integer, default=None)
    publish_date: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    feed: Mapped[Feed] = relationship("Feed", back_populates="episodes")
    episode_metadata: Mapped[list["EpisodeMetadata"]] = relationship("EpisodeMetadata", back_populates="episode", cascade="all, delete-orphan")


class EpisodeMetadata(Base):
    """Transactional metadata table"""

    __tablename__ = "episode_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[int] = mapped_column(ForeignKey("episodes.id"), nullable=False)
    is_downloaded: Mapped[bool] = mapped_column(default=False)
    download_path: Mapped[str | None] = mapped_column(String(2048), default=None)
    is_listened: Mapped[bool] = mapped_column(default=False)
    episode: Mapped["Episode"] = relationship("Episode", back_populates="episode_metadata")
    current_position: Mapped[int] = mapped_column(Integer, default=0)



class EpisodeMetadataController:
    """Controller for managing episode metadata using SQLAlchemy ORM."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def create_tables(self, engine: Engine) -> None:
        """Create ORM tables in the database."""
        Base.metadata.create_all(engine)

    def insert_data(
        self,
        episode_id: int,
        is_downloaded: bool = False,
        download_path: str | None = None,
        is_listened: bool = False,
        current_position: int = 0,
    ) -> EpisodeMetadata:
        """Insert an episode metadata record using ORM."""
        with self.session_factory() as session:
            metadata = EpisodeMetadata(
                episode_id=episode_id,
                is_downloaded=is_downloaded,
                download_path=download_path,
                is_listened=is_listened,
                current_position=current_position,
            )
            session.add(metadata)
            session.commit()
            session.refresh(metadata)
            return metadata
    
    def latest_metadata_for_episode(self, episode_id: int) -> EpisodeMetadata | None:
        """Get the latest metadata for a given episode."""
        with self.session_factory() as session:
            return session.query(EpisodeMetadata).filter_by(episode_id=episode_id).order_by(EpisodeMetadata.id.desc()).first()

    def delete_metadata_by_episode_id(self, episode_id: int) -> None:
        """Delete all metadata for a given episode."""
        with self.session_factory() as session:
            session.query(EpisodeMetadata).filter_by(episode_id=episode_id).delete()
            session.commit()


class FeedController:

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def create_tables(self, engine: Engine) -> None:
        """Create ORM tables in the database."""
        Base.metadata.create_all(engine)

    def insert_data(self, feed_url: str, title: str, description: str) -> Feed:
        """Insert a feed record using ORM."""
        logger.debug(f"Inserting feed into DB: {feed_url}")
        with self.session_factory() as session:
            existing_feed = session.query(Feed).filter_by(feed_url=feed_url).first()
            if existing_feed is not None:
                logger.warning(f"Feed insertion failed: URL '{feed_url}' already exists.")
                raise ValueError(f"Feed with URL '{feed_url}' already exists.")
            feed = Feed(feed_url=feed_url, title=title, description=description)
            session.add(feed)
            session.commit()
            session.refresh(feed)
            return feed

    def get_by_url(self, feed_url: str) -> Feed | None:
        """Load a feed by its URL."""
        with self.session_factory() as session:
            return session.query(Feed).filter_by(feed_url=feed_url).first()

    def get_feed_by_id(self, feed_id: int) -> Feed | None:
        """Load a feed by primary key."""
        with self.session_factory() as session:
            return session.get(Feed, feed_id)

    def get_all_feeds(self) -> list[Feed]:
        """Load all feeds."""
        with self.session_factory() as session:
            return session.query(Feed).all()

    def delete_feed_by_id(self, feed_id: int) -> None:
        """Delete a feed by primary key."""
        with self.session_factory() as session:
            feed = session.get(Feed, feed_id)
            if feed is not None:
                session.delete(feed)
                session.commit()


class EpisodeController:
    """Controller for managing episodes using SQLAlchemy ORM."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def create_tables(self, engine: Engine) -> None:
        """Create ORM tables in the database."""
        Base.metadata.create_all(engine)

    def insert_data(
        self,
        feed_id: int,
        title: str,
        description: str,
        show_notes: str,
        audio_url: str,
        publish_date: datetime | None = None,
        duration: int | None = None,
    ) -> Episode:
        """Insert an episode record using ORM."""
        logger.debug(f"Inserting episode into DB: {title} (Feed ID: {feed_id})")
        with self.session_factory() as session:
            episode = Episode(
                feed_id=feed_id,
                title=title,
                description=description,
                show_notes=show_notes,
                audio_url=audio_url,
                publish_date=publish_date,
                duration=duration,
            )
            session.add(episode)
            session.commit()
            session.refresh(episode)
            return episode

    def get_episode_by_id(self, episode_id: int) -> Episode | None:
        """Load an episode by primary key."""
        with self.session_factory() as session:
            return session.query(Episode).options(joinedload(Episode.feed)).filter_by(id=episode_id).first()
        
    def get_all_episodes(self) -> list[Episode]:
        """Load all episodes."""
        with self.session_factory() as session:
            return session.query(Episode).options(joinedload(Episode.feed)).all()
        
    def delete_episode_by_id(self, episode_id: int) -> None:
        """Delete an episode by primary key."""
        with self.session_factory() as session:
            episode = session.get(Episode, episode_id)
            if episode is not None:
                session.delete(episode)
                session.commit()

    def get_episode_by_audio_url(self, audio_url: str) -> Episode | None:
        """Load an episode by its audio URL."""
        with self.session_factory() as session:
            return session.query(Episode).filter_by(audio_url=audio_url).first()

    def episode_exists(self, feed_id: int, audio_url: str) -> bool:
        """Check if an episode with the given audio URL exists."""
        with self.session_factory() as session:
            return session.query(Episode).filter_by(feed_id=feed_id, audio_url=audio_url).first() is not None

    def get_episodes_by_feed_id(self, feed_id: int) -> list[Episode]:
        """Load episodes for a given feed."""
        with self.session_factory() as session:
            return session.query(Episode).options(joinedload(Episode.feed)).filter_by(feed_id=feed_id).all()
