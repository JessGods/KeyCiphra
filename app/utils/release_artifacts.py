"""Utilitários para gerar metadados do instalador final."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse

from app.models.release_manifest import version_tuple


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(installer: Path, version: str, base_url: str) -> dict[str, object]:
    version_tuple(version)
    parsed = urlparse(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "A URL pública da versão deve usar HTTPS e não pode conter credenciais, "
            "parâmetros ou fragmentos."
        )
    return {
        "schema_version": 1,
        "version": version,
        "installer_url": urljoin(base_url.rstrip("/") + "/", installer.name),
        "installer_sha256": sha256_file(installer),
    }
