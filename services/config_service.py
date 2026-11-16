import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]


def get_setting(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    env_path = BASE_DIR / ".env"
    if not env_path.is_file():
        return default
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, separator, raw_value = line.partition("=")
            if separator and key.strip() == name:
                return raw_value.strip().strip("\"'") or default
    except OSError:
        return default
    return default


def get_flask_secret_key() -> str:
    configured = get_setting("FLASK_SECRET_KEY")
    if configured:
        return configured

    secret_path = BASE_DIR / "instance" / "flask_secret_key"
    try:
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        if secret_path.is_file():
            stored = secret_path.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        generated = secrets.token_urlsafe(48)
        with secret_path.open("x", encoding="utf-8") as secret_file:
            secret_file.write(generated)
        return generated
    except FileExistsError:
        return secret_path.read_text(encoding="utf-8").strip()
    except OSError:
        return secrets.token_urlsafe(48)