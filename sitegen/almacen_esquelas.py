"""Almacén de esquelas, sobre Supabase Storage — mismo patrón que
almacen_fotos.py y almacen_comentarios.py.

Las esquelas son el contenido MÁS delicado del proyecto: una equivocación no es
un negocio mal listado, es un fallecimiento publicado con un error, o de quien
no debía, hiriendo a una familia. Por eso, a diferencia del tablón de
comentarios (moderación automática por IA), aquí NUNCA hay aprobación
automática: cada esquela pasa por revisión humana (scripts/revisar_esquelas.py)
antes de publicarse. Decisión editorial de Daniel del 2026-07-27.

Diseño: un JSON por esquela (+ un .jpg opcional si la familia aporta foto).

Estructura del bucket 'esquelas' (privado):
    pendientes/<id>.json    datos, a la espera de revisión
    pendientes/<id>.jpg     foto opcional
    publicadas/<id>.json    tras aprobación humana
    publicadas/<id>.jpg
Las RECHAZADAS se borran: no hay razón para conservarlas.

El campo `remitente_contacto` (para que Daniel pueda verificar el aviso con la
familia) vive en el JSON pero NUNCA se publica en la web."""

from __future__ import annotations

import json
import os

import requests

BUCKET = "esquelas"
TIMEOUT = 30


class AlmacenError(RuntimeError):
    pass


def _base() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key or key == "replace_me":
        raise AlmacenError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY (necesarias para las esquelas)")
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


def _subir(ruta: str, datos: bytes, content_type: str) -> None:
    r = requests.post(_url(ruta), headers=_headers({"Content-Type": content_type}),
                      data=datos, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise AlmacenError(f"subiendo {ruta}: HTTP {r.status_code} {r.text[:200]}")


def descargar(ruta: str) -> bytes:
    r = requests.get(_url(ruta), headers=_headers(), timeout=TIMEOUT)
    if r.status_code >= 400:
        raise AlmacenError(f"descargando {ruta}: HTTP {r.status_code}")
    return r.content


def _borrar(ruta: str) -> None:
    r = requests.delete(_url(ruta), headers=_headers(), timeout=TIMEOUT)
    # Borrar algo que no existe no es un fallo: Supabase Storage responde 404 o
    # 400 según el caso (p. ej. al aprobar una esquela sin foto, su .jpg no
    # existe). Solo se propaga un error de servidor real (5xx).
    if r.status_code >= 500:
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

def guardar_pendiente(esquela_id: str, meta: dict, foto: bytes | None = None) -> None:
    """Lo que hace la función serverless cuando llega un aviso desde la web."""
    _subir(f"pendientes/{esquela_id}.json",
           json.dumps(meta, ensure_ascii=False).encode("utf-8"), "application/json")
    if foto:
        _subir(f"pendientes/{esquela_id}.jpg", foto, "image/jpeg")


def listar_pendientes() -> list[dict]:
    out = []
    for nombre in _listar("pendientes"):
        if not nombre.endswith(".json"):
            continue
        eid = nombre[:-5]
        meta = json.loads(descargar(f"pendientes/{eid}.json"))
        out.append({**meta, "id": eid})
    out.sort(key=lambda m: m.get("recibido_en") or "")
    return out


def descargar_foto_pendiente(esquela_id: str) -> bytes | None:
    try:
        return descargar(f"pendientes/{esquela_id}.jpg")
    except AlmacenError:
        return None


def aprobar(esquela_id: str, meta: dict) -> None:
    """Mueve la esquela (y su foto, si la hay) de pendientes a publicadas."""
    _subir(f"publicadas/{esquela_id}.json",
           json.dumps(meta, ensure_ascii=False).encode("utf-8"), "application/json")
    if meta.get("tiene_foto"):
        try:
            _subir(f"publicadas/{esquela_id}.jpg",
                   descargar(f"pendientes/{esquela_id}.jpg"), "image/jpeg")
        except AlmacenError:
            pass
    rechazar(esquela_id)


def rechazar(esquela_id: str) -> None:
    _borrar(f"pendientes/{esquela_id}.json")
    _borrar(f"pendientes/{esquela_id}.jpg")


def listar_publicadas() -> list[dict]:
    out = []
    for nombre in _listar("publicadas"):
        if not nombre.endswith(".json"):
            continue
        eid = nombre[:-5]
        meta = json.loads(descargar(f"publicadas/{eid}.json"))
        out.append({**meta, "id": eid})
    return out
