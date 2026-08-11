from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata root for domain models introduced in later phases."""


target_metadata = Base.metadata
