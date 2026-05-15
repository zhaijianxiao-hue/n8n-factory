import os
from pathlib import Path

from .paths import PO_PARSER_DIR


ENV_FILE_ENV = "PO_PROFILE_LAB_ENV_FILE"
SKIP_ENV_FILE_ENV = "PO_PROFILE_LAB_SKIP_ENV_FILE"


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export "):].strip()
    if "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    return key, _strip_quotes(value.strip())


def _candidate_env_files() -> list[Path]:
    configured = os.environ.get(ENV_FILE_ENV)
    if configured:
        return [Path(configured)]
    return [
        PO_PARSER_DIR / "config" / ".env.local",
        PO_PARSER_DIR / "config" / ".env",
    ]


def load_profile_lab_env(override: bool = False) -> None:
    if os.environ.get(SKIP_ENV_FILE_ENV) in {"1", "true", "True", "yes", "YES"}:
        return

    for env_file in _candidate_env_files():
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_line(line)
            if not parsed:
                continue
            key, value = parsed
            if override or key not in os.environ:
                os.environ[key] = value
