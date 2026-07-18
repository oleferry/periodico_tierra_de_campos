"""Almacén compartido de fotos de vecinos, sobre Supabase Storage.

Por qué existe: el bot de Telegram vive en Railway (sistema de ficheros
efímero: lo que escribe se borra en cada reinicio) mientras que la revisión
y el build corren en el portátil. Si cada uno guardara en su disco, las fotos
que mandan los vecinos no llegarían nunca a la web. Este módulo es el punto
común de los tres.

Diseño: UN OBJETO POR FOTO, no una cola compartida en un único JSON. Si el
bot tuviera que leer-modificar-escribir un `pendientes.json` común, dos
vecinos mandando foto a la vez podrían pisarse y perder una. Aquí cada envío
escribe ficheros con su propio id, así que no hay carrera posible.

Estructura del bucket 'fotos':
    pendientes/<id>.jpg    imagen ya procesada (recorte + marco de marca)
    pendientes/<id>.json   pueblo, pie de foto, remitente, fecha
    aprobadas/<id>.jpg     lo mismo, tras pasar la revisión humana
    aprobadas/<id>.json

El bucket es PRIVADO: las fotos pendientes no son públicas hasta que alguien
las aprueba. El build descarga las aprobadas y las publica como ficheros
estáticos del sitio.
"""

from __future__ import annotations

import json
import os

import requests

BUCKET = "fotos"
TIMEOUT = 30


class AlmacenError(RuntimeError):
    pass


def _base() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key or key == "replace_me":
        raise AlmacenError(
            "Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY en .env "
            "(son necesarias para las fotos de vecinos)"
        )
    return url, key


def disponible() -> bool:
    """True si hay credenciales para hablar con el almacén."""
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


def subir(ruta: str, datos: bytes, content_type: str) -> None:
    r = requests.post(_url(ruta), headers=_headers({"Content-Type": content_type}),
                      data=datos, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise AlmacenError(f"subiendo {ruta}: HTTP {r.status_code} {r.text[:200]}")


def descargar(ruta: str) -> bytes:
    r = requests.get(_url(ruta), headers=_headers(), timeout=TIMEOUT)
    if r.status_code >= 400:
        raise AlmacenError(f"descargando {ruta}: HTTP {r.status_code}")
    return r.content


def borrar(ruta: str) -> None:
    r = requests.delete(_url(ruta), headers=_headers(), timeout=TIMEOUT)
    if r.status_code >= 400 and r.status_code != 404:
        raise AlmacenError(f"borrando {ruta}: HTTP {r.status_code}")


def listar(carpeta: str) -> list[str]:
    """Nombres de fichero dentro de una carpeta del bucket."""
    url, _ = _base()
    r = requests.post(f"{url}/storage/v1/object/list/{BUCKET}",
                      headers=_headers({"Content-Type": "application/json"}),
                      json={"prefix": f"{carpeta}/", "limit": 1000}, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise AlmacenError(f"listando {carpeta}: HTTP {r.status_code} {r.text[:200]}")
    return [o["name"] for o in r.json()]


# ------------------------------------------------------------- alto nivel

def guardar_pendiente(foto_id: str, imagen: bytes, meta: dict) -> None:
    """Lo que hace el bot cuando un vecino manda una foto."""
    subir(f"pendientes/{foto_id}.jpg", imagen, "image/jpeg")
    subir(f"pendientes/{foto_id}.json",
          json.dumps(meta, ensure_ascii=False).encode("utf-8"), "application/json")


def listar_pendientes() -> list[dict]:
    """Fotos a la espera de revisión, con sus metadatos."""
    out = []
    for nombre in listar("pendientes"):
        if not nombre.endswith(".json"):
            continue
        foto_id = nombre[:-5]
        meta = json.loads(descargar(f"pendientes/{foto_id}.json"))
        out.append({**meta, "id": foto_id})
    out.sort(key=lambda m: m.get("recibida_en") or "")
    return out


def aprobar(foto_id: str, meta: dict) -> None:
    """Mueve una foto de pendientes a aprobadas (con el pie ya editado)."""
    imagen = descargar(f"pendientes/{foto_id}.jpg")
    subir(f"aprobadas/{foto_id}.jpg", imagen, "image/jpeg")
    subir(f"aprobadas/{foto_id}.json",
          json.dumps(meta, ensure_ascii=False).encode("utf-8"), "application/json")
    rechazar(foto_id)


def rechazar(foto_id: str) -> None:
    borrar(f"pendientes/{foto_id}.jpg")
    borrar(f"pendientes/{foto_id}.json")


def listar_aprobadas() -> list[dict]:
    out = []
    for nombre in listar("aprobadas"):
        if not nombre.endswith(".json"):
            continue
        foto_id = nombre[:-5]
        meta = json.loads(descargar(f"aprobadas/{foto_id}.json"))
        out.append({**meta, "id": foto_id})
    return out
