import logging


LOGGER_NAME = "peoplematch"


def configure_logging(environment: str) -> None:
    level = logging.DEBUG if environment.lower() == "development" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logging.getLogger(LOGGER_NAME).setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
