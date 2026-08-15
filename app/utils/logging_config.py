"""Logging técnico rotativo com defesa contra inclusão acidental de segredos."""

from __future__ import annotations

import logging
import re
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOGGER_NAME = "keyciphra"
MAX_LOG_BYTES = 512 * 1_024
LOG_BACKUP_COUNT = 3

_ASSIGNED_SECRET = re.compile(
    r"(?i)\b(senha(?:_mestra)?|password|token|secret|segredo|chave(?:_derivada)?|clipboard)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER_TOKEN = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_COMMON_TOKEN = re.compile(
    r"\b(?:github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})\b"
)


def sanitize_log_message(message: str) -> str:
    sanitized = _ASSIGNED_SECRET.sub(lambda match: f"{match.group(1)}=<redacted>", message)
    sanitized = _BEARER_TOKEN.sub("Bearer <redacted>", sanitized)
    return _COMMON_TOKEN.sub("<redacted>", sanitized)


class SensitiveDataFilter(logging.Filter):
    """Formata e sanitiza a mensagem antes de qualquer handler persistir dados."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = sanitize_log_message(record.getMessage())
        record.args = ()
        # Tracebacks podem carregar valores arbitrários; registramos apenas eventos e tipos.
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True


def configure_logging(log_directory: Path) -> logging.Logger:
    directory = Path(log_directory)
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "keyciphra.log"
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for existing in logger.handlers[:]:
        existing.close()
        logger.removeHandler(existing)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=MAX_LOG_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    formatter = logging.Formatter(
        "%(asctime)sZ %(levelname)s %(message)s",
        "%Y-%m-%dT%H:%M:%S",
    )
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    handler.addFilter(SensitiveDataFilter())
    logger.addHandler(handler)
    log_path.chmod(0o600)
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)
