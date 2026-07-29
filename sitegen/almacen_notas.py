"""Almacén de notas privadas del administrador, sobre Supabase Storage —
mismo patrón que almacen_comentarios.py. El bot vive en Railway (disco
efímero), así que las notas que Daniel manda al bot se guardan en Supabase,
no en disco.

Son NOTAS PRIVADAS: nunca se publican en la web. Es un bloc de notas personal
("apunta cosas que se me ocurran") accesible solo por el administrador
identificado con ADMIN_TELEGRAM_ID (ver bot/telegram_bot.py).

Estructura del bucket 'notas' (privado):
    notas/<id>.json   texto, fecha, y de quién (username de Telegram)
"""

from __future__ import annotations

import json
import os

import requests

BUCKET = "notas"
TIMEOUT = 30


class AlmacenError(RuntimeError):
    pass


def _base() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key or key == "replace_me":
        raise AlmacenError(
            "Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env "
            "(son necesarias para el bloc de notas del bot)"
        )
    return url, key


def disponible() -> bool:
    try:
        _base()
        return True
    except AlmacenError:
        return False


def _headers(extra: dict | None = None) -> dict:
    _, key = _base()
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    if extra:
        h.update(extra)
    return h


def _url(ruta: str) -> str:
    url, _ = _base()
    return f"{url}/storage/v1/object/{BUCKET}/{ruta}"


def asegurar_bucket() -> None:
    """Crea el bucket 'notas' si no existe. Idempotente: si ya está, Supabase
    devuelve un error que se ignora."""
    url, _ = _base()
    requests.post(f"{url}/storage/v1/bucket",
                  headers=_headers({"Content-Type": "application/json"}),
                  json={"id": BUCKET, "name": BUCKET, "public": False}, timeout=TIMEOUT)


def guardar(nota_id: str, meta: dict) -> None:
    r = requests.post(_url(f"notas/{nota_id}.json"),
                      headers=_headers({"Content-Type": "application/json"}),
                      data=json.dumps(meta, ensure_ascii=False).encode("utf-8"), timeout=TIMEOUT)
    if r.status_code >= 400:
        raise AlmacenError(f"guardando nota: HTTP {r.status_code} {r.text[:200]}")


def listar() -> list[dict]:
    """Todas las notas, de la más reciente a la más antigua."""
    url, _ = _base()
    r = requests.post(f"{url}/storage/v1/object/list/{BUCKET}",
                      headers=_headers({"Content-Type": "application/json"}),
                      json={"prefix": "notas/", "limit": 1000}, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise AlmacenError(f"listando notas: HTTP {r.status_code} {r.text[:200]}")
    out = []
    for o in r.json():
        nombre = o["name"]
        if not nombre.endswith(".json"):
            continue
        nid = nombre[:-5]
        rr = requests.get(_url(f"notas/{nid}.json"), headers=_headers(), timeout=TIMEOUT)
        if rr.status_code < 400:
            out.append({**rr.json(), "id": nid})
    out.sort(key=lambda m: m.get("fecha") or "", reverse=True)
    return out
