"""Metadados validados de uma versão distribuível do KeyCiphra."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class InvalidReleaseManifest(ValueError):
    """Indica metadados de atualização inválidos ou inesperados."""


def version_tuple(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise InvalidReleaseManifest("Versão inválida no manifesto de atualização.")
    match = VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise InvalidReleaseManifest("Versão inválida no manifesto de atualização.")
    return tuple(int(part) for part in match.groups())


@dataclass(frozen=True, slots=True)
class ReleaseManifest:
    schema_version: int
    version: str
    installer_url: str
    installer_sha256: str

    @classmethod
    def from_json(cls, document: str) -> ReleaseManifest:
        try:
            value = json.loads(document)
        except (json.JSONDecodeError, TypeError) as exc:
            raise InvalidReleaseManifest("Manifesto de atualização inválido.") from exc
        required = {"schema_version", "version", "installer_url", "installer_sha256"}
        if not isinstance(value, dict) or set(value) != required:
            raise InvalidReleaseManifest("Campos inesperados no manifesto de atualização.")
        if value["schema_version"] != 1:
            raise InvalidReleaseManifest("Versão de manifesto não suportada.")
        version_tuple(value["version"])
        if not isinstance(value["installer_url"], str):
            raise InvalidReleaseManifest("URL do instalador não é segura.")
        url = urlparse(value["installer_url"])
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.fragment
        ):
            raise InvalidReleaseManifest("URL do instalador não é segura.")
        digest = value["installer_sha256"]
        if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
            raise InvalidReleaseManifest("SHA-256 inválido no manifesto de atualização.")
        return cls(
            schema_version=1,
            version=value["version"],
            installer_url=value["installer_url"],
            installer_sha256=digest,
        )

    def is_newer_than(self, current_version: str) -> bool:
        return version_tuple(self.version) > version_tuple(current_version)
