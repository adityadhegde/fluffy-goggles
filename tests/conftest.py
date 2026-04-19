import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from feed_controller.table_controllers import (
    Base,
    EpisodeController,
    EpisodeMetadataController,
    FeedController,
)


@pytest.fixture(scope="function")
def db_engine():
    """Create an in-memory SQLite database engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session_factory(db_engine):
    """Create a session factory bound to the in-memory engine."""
    return sessionmaker(bind=db_engine)


@pytest.fixture(scope="function")
def db_session(db_session_factory):
    """Provide a session directly for test queries."""
    with db_session_factory() as session:
        yield session


@pytest.fixture(scope="function")
def feed_controller(db_session_factory):
    """Provide a FeedController connected to the in-memory db."""
    return FeedController(db_session_factory)


@pytest.fixture(scope="function")
def episode_controller(db_session_factory):
    """Provide an EpisodeController connected to the in-memory db."""
    return EpisodeController(db_session_factory)


@pytest.fixture(scope="function")
def metadata_controller(db_session_factory):
    """Provide an EpisodeMetadataController connected to the in-memory db."""
    return EpisodeMetadataController(db_session_factory)
