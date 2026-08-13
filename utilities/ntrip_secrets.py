"""Load NTRIP credentials from config/secrets.yaml (ntrip_aux_client / check_swepos)."""

from __future__ import annotations

from pathlib import Path

import yaml

_REQUIRED = ("caster", "caster_port", "username", "password", "mountpoint", "version")


def default_secrets_path() -> Path:
    repo_config = Path(__file__).resolve().parent.parent / "config" / "secrets.yaml"
    if repo_config.exists():
        return repo_config
    return Path("config/secrets.yaml")


def _normalize(section: dict, source: str) -> dict:
    if not isinstance(section, dict):
        raise ValueError(f"invalid NTRIP section in {source}")

    missing = [key for key in _REQUIRED if key not in section or section[key] in (None, "")]
    if missing:
        raise ValueError(f"missing NTRIP field(s) in {source}: {', '.join(missing)}")

    return {
        "caster": str(section["caster"]),
        "caster_port": int(section["caster_port"]),
        "username": str(section["username"]),
        "password": str(section["password"]),
        "mountpoint": str(section["mountpoint"]),
        "version": str(section["version"]),
    }


def load_ntrip_config(secrets_path: Path) -> dict:
    """Return NTRIP settings dict from secrets.yaml."""
    if not secrets_path.exists():
        raise FileNotFoundError(f"secrets file not found: {secrets_path}")

    with open(secrets_path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if isinstance(data.get("ntrip"), dict):
        return _normalize(data["ntrip"], str(secrets_path))

    # Legacy: septentrio_gnss_driver.ros__parameters.rtk_settings.ntrip_1
    legacy = (
        data.get("septentrio_gnss_driver", {})
        .get("ros__parameters", {})
        .get("rtk_settings", {})
        .get("ntrip_1")
    )
    if isinstance(legacy, dict):
        return _normalize(legacy, str(secrets_path))

    raise ValueError(
        f"invalid secrets format in {secrets_path}: expected top-level 'ntrip:' block "
        "(see config/secrets.yaml.example)"
    )
