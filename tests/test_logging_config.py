"""Testes para impedir persistência acidental de segredos nos logs."""

from __future__ import annotations

from pathlib import Path

from app.utils.logging_config import configure_logging, sanitize_log_message


def test_sanitizer_redacts_assigned_secrets_and_tokens() -> None:
    message = sanitize_log_message(
        "senha=nao-real password: ficticia token=abc123 "
        "Bearer cabecalho.segredo.assinatura github_pat_EXEMPLO1234567890"
    )

    assert "nao-real" not in message
    assert "ficticia" not in message
    assert "abc123" not in message
    assert "cabecalho.segredo.assinatura" not in message
    assert "github_pat_EXEMPLO1234567890" not in message
    assert message.count("<redacted>") >= 5


def test_configured_logger_persists_only_sanitized_message(tmp_path: Path) -> None:
    logger = configure_logging(tmp_path)

    logger.error("vault.failure senha=%s token=%s", "mestra-ficticia", "token-ficticio")
    for handler in logger.handlers:
        handler.flush()

    contents = (tmp_path / "keyciphra.log").read_text(encoding="utf-8")
    assert "vault.failure" in contents
    assert "mestra-ficticia" not in contents
    assert "token-ficticio" not in contents
    assert contents.count("<redacted>") == 2


def test_filter_discards_traceback_text_that_may_contain_input(tmp_path: Path) -> None:
    logger = configure_logging(tmp_path)

    try:
        raise ValueError("senha=valor-ficticio")
    except ValueError:
        logger.exception("operation.failed")
    for handler in logger.handlers:
        handler.flush()

    contents = (tmp_path / "keyciphra.log").read_text(encoding="utf-8")
    assert "operation.failed" in contents
    assert "valor-ficticio" not in contents
    assert "Traceback" not in contents
