import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    """Allowlisted operational fields only; never serialize exception text or request inputs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        for field in (
            "method",
            "route",
            "status",
            "duration_ms",
            "dependency",
            "category",
            "operation",
            "result_count",
        ):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(level: str) -> None:
    logger = logging.getLogger("careerpilot")
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    # Driver diagnostics may include addresses or query data. App logs safe categories instead.
    for name in ("pymongo", "neo4j"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
