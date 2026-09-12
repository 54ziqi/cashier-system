"""配置加载：default.toml → {profile}.toml → 环境变量 → 默认值"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any

try:
    import tomllib as _toml
except ModuleNotFoundError:
    import tomli as _toml

from pydantic import BaseModel


def default_home() -> Path:
    env = os.environ.get("CASHIER_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".cashier"


class ServerCfg(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    auto_port: bool = True
    open_browser: bool = True


class DBCfg(BaseModel):
    filename: str = "cashier.db"
    wal: bool = True
    cache_size_kb: int = -8000
    busy_timeout_ms: int = 30000


class SecurityCfg(BaseModel):
    bcrypt_rounds: int = 10
    session_hours: int = 8
    max_login_failures: int = 5
    lock_minutes: int = 15


class LicenseCfg(BaseModel):
    grace_days: int = 7
    allow_trial: bool = True


class LoggingCfg(BaseModel):
    level: str = "INFO"
    max_bytes: int = 5_000_000
    backup_count: int = 3


class FeaturesCfg(BaseModel):
    agents: bool = True
    hardware: bool = False
    websocket: bool = False
    cloud_sync: bool = False


class Settings(BaseModel):
    profile: str = "lite"
    home: Path = default_home()
    server: ServerCfg = ServerCfg()
    db: DBCfg = DBCfg()
    security: SecurityCfg = SecurityCfg()
    license: LicenseCfg = LicenseCfg()
    logging: LoggingCfg = LoggingCfg()
    features: FeaturesCfg = FeaturesCfg()

    @property
    def db_path(self) -> Path:
        return self.home / "data" / self.db.filename

    @property
    def secrets_dir(self) -> Path:
        return self.home / "data" / "secrets"

    @property
    def logs_dir(self) -> Path:
        return self.home / "logs"

    @property
    def backup_dir(self) -> Path:
        return self.home / "data" / "backup"

    @property
    def license_path(self) -> Path:
        return self.home / "data" / "license.lic"

    def ensure_dirs(self) -> None:
        for p in (self.home / "data", self.secrets_dir,
                  self.logs_dir, self.backup_dir):
            p.mkdir(parents=True, exist_ok=True)


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return _toml.load(f)


def _env_overrides() -> dict:
    out: dict[str, Any] = {}
    for key, val in os.environ.items():
        if not key.startswith("CASHIER_"):
            continue
        parts = key[len("CASHIER_"):].lower().split("__")
        if len(parts) < 2:
            continue
        node = out
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        raw = val
        if raw.isdigit():
            raw = int(raw)
        elif raw.lower() in ("true", "false"):
            raw = raw.lower() == "true"
        node[parts[-1]] = raw
    return out


def load_settings(profile: str = "lite") -> Settings:
    here = Path(__file__).resolve().parent
    cfg_dir = (here.parent / "config") if (here.parent / "config").exists() \
              else (here / "config")

    merged = _load_toml(cfg_dir / "default.toml")
    merged = _deep_merge(merged, _load_toml(cfg_dir / f"{profile}.toml"))
    merged = _deep_merge(merged, _env_overrides())
    merged["profile"] = profile
    return Settings(**merged)
