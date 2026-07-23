"""Almacén de chivatazos anónimos, sobre Supabase Storage — mismo patrón que
almacen_fotos.py y almacen_comentarios.py.

A diferencia de los comentarios del tablón (moderación autónoma, sin
intervención humana), un chivatazo puede ser una acusación sin verificar
sobre una irregularidad concreta — publicar algo así sin que una persona lo
valore antes sería el mismo riesgo que el proyecto lleva evitando desde el
principio con las piezas del radar (editorial/politica_editorial.md). Por
eso aquí NO hay aprobación automática ni publicación: los chivatazos solo
se listan (scripts/listar_chivatazos.py) para que Daniel decida con criterio
editorial si dan pie a una investigación — igual que con las pistas del
radar, nunca se publica el chivatazo en sí, como mucho alimenta una pieza
propia con hechos verificados aparte.

Anonimato: deliberadamente NO se guarda IP, user-agent ni ningún dato de
quien envía — solo el texto, el pueblo (si lo indican) y la fecha.

Estructura del bucket 'chivatazos' (privado):
    pendientes/<id>.json   sin revisar todavía
    archivados/<id>.json   ya visto/valorado (se conserva, no se borra —
                            puede ser el único registro de algo real)
"""

from __future__ import annotations

import json
import os

import requests

BUCKET = "chivatazos"
TIMEOUT = 30


class AlmacenError(RuntimeError):
    pass


def _base() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key or key == "replace_me":
        raise AlmacenError(
            "Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY (necesarias para el buzón de chivatazos)"
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

def guardar_pendiente(chivatazo_id: str, meta: dict) -> None:
    _subir_json(f"pendientes/{chivatazo_id}.json", meta)


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


def archivar(chivatazo_id: str, meta: dict) -> None:
    """Marca como ya visto/valorado, sin borrarlo: puede ser el único
    registro de algo real, aunque de momento no dé para una pieza."""
    _subir_json(f"archivados/{chivatazo_id}.json", meta)
    _borrar(f"pendientes/{chivatazo_id}.json")
