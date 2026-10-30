"""Structured JSON logs in production (PRD §15); readable text locally."""
import json
import logging
import sys
from datetime import datetime, timezone

from app.core.config import settings


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "service": "trace-api",
            "env": settings.env or "unset",
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["error"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
        return json.dumps(entry, separators=(",", ":"))


def configure_logging() -> None:
    use_json = settings.LOG_FORMAT == "json" or (settings.LOG_FORMAT == "auto" and settings.is_production)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if use_json else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers[:] = []
        logging.getLogger(name).propagate = True
