import logging


LOGGER_NAME = "peoplematch"


def configure_logging(environment: str) -> None:
    level = logging.DEBUG if environment.lower() == "development" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger(LOGGER_NAME).setLevel(level)
    # Alembic's fileConfig can disable loggers imported before a migration.
    # An application startup must restore its own descendants, not only parent.
    for name, logger in logging.root.manager.loggerDict.items():
        if name.startswith(f"{LOGGER_NAME}.") and isinstance(logger, logging.Logger):
            logger.disabled = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
