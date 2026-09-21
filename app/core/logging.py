import logging


def configure_logging() -> None:
    """Configure application logs without replacing Uvicorn's handlers."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
