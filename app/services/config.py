"""Lecture de la configuration à partir de l'environnement (.env)."""

import os

from dotenv import load_dotenv

load_dotenv()


def get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def get_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


def get_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


# Limites de l'import documentaire
MAX_FILE_SIZE_MB = get_int("MAX_FILE_SIZE_MB", 10)
ALLOWED_EXTENSIONS = {
    ext.strip()
    for ext in get("ALLOWED_EXTENSIONS", "pdf,txt,docx,md,json,csv").split(",")
    if ext.strip()
}