"""Central configuration, loaded from environment / .env."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

# Load .env if python-dotenv is present; otherwise rely on real env vars.
try:  # optional dependency, not required in production
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except Exception:  # pragma: no cover
    # Minimal .env loader so the app runs without python-dotenv installed.
    _env = Path(__file__).resolve().parent.parent / ".env"
    if _env.exists():
        for line in _env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-insecure-key-change-me")

    TEMPLATES_ROOT: Path = Path(
        os.getenv("TEMPLATES_ROOT", str(BASE_DIR / "sample_root"))
    ).expanduser()
    OUTPUT_ROOT: Path = Path(os.getenv("OUTPUT_ROOT", str(BASE_DIR / "output"))).expanduser()

    AUTH_MODE: str = os.getenv("AUTH_MODE", "local").strip().lower()
    LOCAL_PASSWORD: str = os.getenv("LOCAL_PASSWORD", "cbes")

    ENTRA_TENANT_ID: str = os.getenv("ENTRA_TENANT_ID", "")
    ENTRA_CLIENT_ID: str = os.getenv("ENTRA_CLIENT_ID", "")
    ENTRA_CLIENT_SECRET: str = os.getenv("ENTRA_CLIENT_SECRET", "")
    ENTRA_REDIRECT_URI: str = os.getenv(
        "ENTRA_REDIRECT_URI", "http://localhost:8000/auth/callback"
    )

    STAMP_DATE: bool = _bool("STAMP_DATE", False)
    OVERWRITE_EXISTING: bool = _bool("OVERWRITE_EXISTING", False)

    # Optional address / map providers (all features work without them).
    GETADDRESS_API_KEY: str = os.getenv("GETADDRESS_API_KEY", "")
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")

    @property
    def entra_metadata_url(self) -> str:
        return (
            f"https://login.microsoftonline.com/{self.ENTRA_TENANT_ID}"
            "/v2.0/.well-known/openid-configuration"
        )


@lru_cache
def get_settings() -> "Settings":
    return Settings()


@lru_cache
def load_departments() -> dict:
    return json.loads((CONFIG_DIR / "departments.json").read_text(encoding="utf-8"))


@lru_cache
def load_field_map() -> dict:
    return json.loads((CONFIG_DIR / "field_map.json").read_text(encoding="utf-8"))
