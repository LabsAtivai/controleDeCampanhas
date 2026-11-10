from datetime import datetime, UTC


def utcnow():
    """Database timestamps use naive UTC consistently on MySQL and SQLite."""
    return datetime.now(UTC).replace(tzinfo=None)
