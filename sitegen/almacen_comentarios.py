"""Almacén compartido de comentarios del grupo de discusión de Telegram,
sobre Supabase Storage — mismo patrón que almacen_fotos.py (el bot vive en
Railway, disco efímero; la moderación y el build corren en el portátil).

Diseño: un objeto JSON por comentario, no una cola compartida (evita que dos
mensajes casi simultáneos se pisen al leer-modificar-escribir).

Estructura del bucket 'comentarios' (privado):
    pendientes/<id>.json   texto, autor, pueblo (si se detecta), fecha
    aprobados/<id>.json    lo mismo, tras pasar moderación (IA o humana)

Los RECHAZADOS no se guardan en ningún sitio: se borran sin más. No hay
razón para conservar spam o insultos."""

from __future__ import annotations

import json
import os

import requests

BUCKET = "comentarios"
TIMEOUT = 30


class AlmacenError(RuntimeError):
    pass


def _base() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key or key == "replace_me":
        raise AlmacenError(
            "Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env "
            "(son necesarias para el tablón de comentarios)"
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
    """Crea el bucket 'comentarios' si todavía no existe. Idempotente: si ya
    está creado, Supabase devuelve un error que se ignora."""
    url, _ = _base()
    requests.post(f"{url}/storage/v1/bucket",
                  headers=_headers({"Content-Type": "application/json"}),
                  json={"id": BUCKET, "name": BUCKET, "public": False}, timeout=TIMEOUT)


def _subir_json(ruta: str, datos: dict) -> None:
    r = requests.post(_url(ruta), headers=_headers({"Content-Type": "application/json"}),
                       data=json.dumps(datos, ensure_ascii=False).encode("utf-8"), timeout=TIMEOUT)
    if r.status_code >= 400:
        raise AlmacenError(f"subiendo {ruta}: HTTP {r.status_code} {r.text[:200]}")


def _descargar_json(ruta: str) -> dict:
    r = requests.get(_url(ruta), headers=_headers(), timeout=TIMEOUT)
    if r.status_code >= 400:
        raise AlmacenError(f"descargando {ruta}: HTTP {r.status_code}")
    return r.json()


def _borrar(ruta: str) -> None:
    r = requests.delete(_url(ruta), headers=_headers(), timeout=TIMEOUT)
    if r.status_code >= 400 and r.status_code != 404:
        raise AlmacenError(f"borrando {ruta}: HTTP {r.status_code}")


def _listar(carpeta: str) -> list[str]:
    url, _ = _base()
    r = requests.post(f"{url}/storage/v1/object/list/{BUCKET}",
                       headers=_headers({"Content-Type": "application/json"}),
                       json={"prefix": f"{carpeta}/", "limit": 1000}, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise AlmacenError(f"listando {carpeta}: HTTP {r.status_code} {r.text[:200]}")
    return [o["name"] for o in r.json()]


# ------------------------------------------------------------- alto nivel

def guardar_pendiente(comentario_id: str, meta: dict) -> None:
    """Lo que hace el bot cuando llega un mensaje del grupo de discusión."""
    _subir_json(f"pendientes/{comentario_id}.json", meta)


def listar_pendientes() -> list[dict]:
    out = []
    for nombre in _listar("pendientes"):
        if not nombre.endswith(".json"):
            continue
        cid = nombre[:-5]
        meta = _descargar_json(f"pendientes/{cid}.json")
        out.append({**meta, "id": cid})
    out.sort(key=lambda m: m.get("recibido_en") or "")
    return out


def aprobar(comentario_id: str, meta: dict) -> None:
    _subir_json(f"aprobados/{comentario_id}.json", meta)
    rechazar(comentario_id)


def rechazar(comentario_id: str) -> None:
    _borrar(f"pendientes/{comentario_id}.json")


def listar_aprobados() -> list[dict]:
    out = []
    for nombre in _listar("aprobados"):
        if not nombre.endswith(".json"):
            continue
        cid = nombre[:-5]
        meta = _descargar_json(f"aprobados/{cid}.json")
        out.append({**meta, "id": cid})
    out.sort(key=lambda m: m.get("recibido_en") or "", reverse=True)
    return out
