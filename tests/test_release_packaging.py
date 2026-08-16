import re
from pathlib import Path

import pytest

from app.models.release_manifest import InvalidReleaseManifest, ReleaseManifest
from app.utils.release_artifacts import build_manifest
from app.version import APP_VERSION

ALLOWED_HOSTS = frozenset({"downloads.example.invalid"})


def test_release_manifest_accepts_secure_newer_version() -> None:
    manifest = ReleaseManifest.from_json(
        '{"schema_version":1,"version":"0.9.0",'
        '"installer_url":"https://downloads.example.invalid/KeyCiphra.exe",'
        '"installer_sha256":"' + ("a" * 64) + '"}',
        allowed_hosts=ALLOWED_HOSTS,
    )

    assert manifest.is_newer_than("0.8.0")
    assert not manifest.is_newer_than("0.9.0")


@pytest.mark.parametrize(
    "url",
    [
        "http://downloads.example.invalid/KeyCiphra.exe",
        "https://user:secret@downloads.example.invalid/KeyCiphra.exe",
        "https://downloads.example.invalid/KeyCiphra.exe#fragment",
    ],
)
def test_release_manifest_rejects_unsafe_installer_url(url: str) -> None:
    document = (
        '{"schema_version":1,"version":"0.9.0",'
        f'"installer_url":"{url}","installer_sha256":"' + ("a" * 64) + '"}'
    )
    with pytest.raises(InvalidReleaseManifest):
        ReleaseManifest.from_json(document, allowed_hosts=ALLOWED_HOSTS)


def test_release_manifest_rejects_unpinned_https_host() -> None:
    document = (
        '{"schema_version":1,"version":"0.9.0",'
        '"installer_url":"https://attacker.example.invalid/KeyCiphra.exe",'
        '"installer_sha256":"' + ("a" * 64) + '"}'
    )

    with pytest.raises(InvalidReleaseManifest):
        ReleaseManifest.from_json(document, allowed_hosts=ALLOWED_HOSTS)


def test_manifest_generator_hashes_the_final_artifact(tmp_path: Path) -> None:
    installer = tmp_path / "KeyCiphra-Setup-0.9.0.exe"
    installer.write_bytes(b"signed-installer")

    manifest = build_manifest(installer, "0.9.0", "https://example.invalid/releases/v0.9.0")

    assert manifest["installer_url"].endswith(installer.name)
    assert manifest["installer_sha256"] == (
        "c76ade5429d053136e8a576156668895c2650d9ef0913afe2d02ef133ccd7cf0"
    )


def test_installer_is_per_user_and_does_not_delete_private_data() -> None:
    project_root = Path(__file__).resolve().parents[1]
    script = (project_root / "installer" / "KeyCiphra.iss").read_text(encoding="utf-8")

    assert "PrivilegesRequired=lowest" in script
    assert "DefaultDirName={localappdata}\\Programs\\{#MyAppName}" in script
    assert "AppId={{3B01DF75-B9A3-4D33-93A8-412520504F8C}" in script
    assert "[UninstallDelete]" not in script
    assert "{localappdata}\\KeyCiphra" not in script


def test_public_version_is_consistent_across_windows_packaging() -> None:
    project_root = Path(__file__).resolve().parents[1]
    installer_script = (project_root / "installer" / "KeyCiphra.iss").read_text(
        encoding="utf-8"
    )
    version_info = (project_root / "packaging" / "windows_version_info.txt").read_text(
        encoding="utf-8"
    )

    installer_version = re.search(r'#define MyAppVersion "([^"]+)"', installer_script)
    assert installer_version is not None
    assert installer_version.group(1) == APP_VERSION
    assert f"StringStruct('ProductVersion', '{APP_VERSION}')" in version_info
