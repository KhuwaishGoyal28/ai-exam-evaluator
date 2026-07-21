"""
Structured logging setup using structlog.
Call configure_logging() once at app startup.

Why stdlib.LoggerFactory (not PrintLoggerFactory):
  PrintLogger has no .name attribute, which breaks the add_logger_name
  processor. Using stdlib.LoggerFactory routes through Python's standard
  logging module, which supports named loggers correctly.
"""
import logging
import structlog


def configure_logging(debug: bool = False) -> None:
    """Configure structlog with stdlib backend. Safe to call multiple times."""
    log_level = logging.DEBUG if debug else logging.INFO

    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        force=True,  # reconfigures even if basicConfig was already called
    )

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if debug:
        # Human-readable coloured output in dev
        renderer = structlog.dev.ConsoleRenderer()
    else:
        # Machine-readable JSON in production
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Return a named bound logger. Pass __name__ for module-level loggers."""
    return structlog.get_logger(name)
