"""Application startup restores its loggers after Alembic configures logging."""

from app.core.logging import configure_logging, get_logger


def test_configure_logging_reenables_existing_application_child_logger():
    child = get_logger("extraction")
    original = child.disabled
    try:
        child.disabled = True  # Alembic fileConfig disables existing loggers.
        configure_logging("development")
        assert child.disabled is False
    finally:
        child.disabled = original
