"""Caché persistente por hash para no repetir llamadas a la IA entre builds.

Cada namespace es un JSON en data/cache/<namespace>.json. En memoria durante el
build; se vuelca a disco con flush() (registrado en atexit y llamado por build.py).
"""

from __future__ import annotations

import atexit
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = ROOT / "data" / "cache"

_stores: dict[str, dict] = {}
_dirty: set[str] = set()


def _path(namespace: str) -> Path:
    return CACHE_DIR / f"{namespace}.json"


def _load(namespace: str) -> dict:
    if namespace not in _stores:
        p = _path(namespace)
        try:
            _stores[namespace] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except (json.JSONDecodeError, OSError):
            _stores[namespace] = {}
    return _stores[namespace]


def get(namespace: str, key: str):
    return _load(namespace).get(key)


def set(namespace: str, key: str, value) -> None:  # noqa: A001 (nombre intencional)
    _load(namespace)[key] = value
    _dirty.add(namespace)


def flush() -> None:
    if not _dirty:
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for namespace in list(_dirty):
        _path(namespace).write_text(
            json.dumps(_stores[namespace], ensure_ascii=False, indent=1), encoding="utf-8")
    _dirty.clear()


atexit.register(flush)
