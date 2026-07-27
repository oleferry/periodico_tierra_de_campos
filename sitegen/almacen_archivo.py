"""Almacén del archivo fotográfico comunitario, sobre Supabase Storage — mismo
patrón que almacen_esquelas.py / almacen_fotos.py.

La idea (ver docs/ideas-mundo.md, "archivo fotográfico antes y ahora"): que los
vecinos manden fotos antiguas de su pueblo —la plaza en los sesenta, una
matanza, la escuela llena de niños— y se conserven con su año, su descripción y
el crédito de quien las aporta. Para la diáspora es memoria; para los mayores,
un motivo para participar ("¿quién es esa señora de la foto?").

A diferencia de las esquelas, aquí el nombre de quien aporta la foto SÍ se
publica, como crédito ("aportada por…"), porque es lo justo y lo habitual en un
archivo. La revisión humana (scripts/revisar_archivo.py) sigue siendo
obligatoria: una foto antigua puede tener derechos de un tercero o mostrar a
personas identificables, y eso lo valora una persona, no un automatismo.

Estructura del bucket 'archivo' (privado):
    pendientes/<id>.json + pendientes/<id>.jpg
    publicadas/<id>.json + publicadas/<id>.jpg
Las rechazadas se borran."""

from __future__ import annotations

import json
import os

import requests

BUCKET = "archivo"
TIMEOUT = 30


class AlmacenError(RuntimeError):
    pass


def _base() -> tuple[str, str]:
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
    if not url or not key or key == "replace_me":
        raise AlmacenError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY (necesarias para el archivo)")
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
    # Borrar algo que no existe no es fallo (Supabase da 400 o 404 según el caso).
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

def guardar_pendiente(foto_id: str, meta: dict, foto: bytes) -> None:
    _subir(f"pendientes/{foto_id}.json",
           json.dumps(meta, ensure_ascii=False).encode("utf-8"), "application/json")
    _subir(f"pendientes/{foto_id}.jpg", foto, "image/jpeg")


def listar_pendientes() -> list[dict]:
    out = []
    for nombre in _listar("pendientes"):
        if not nombre.endswith(".json"):
            continue
        fid = nombre[:-5]
        out.append({**json.loads(descargar(f"pendientes/{fid}.json")), "id": fid})
    out.sort(key=lambda m: m.get("recibido_en") or "")
    return out


def descargar_foto_pendiente(foto_id: str) -> bytes | None:
    try:
        return descargar(f"pendientes/{foto_id}.jpg")
    except AlmacenError:
        return None


def aprobar(foto_id: str, meta: dict) -> None:
    _subir(f"publicadas/{foto_id}.json",
           json.dumps(meta, ensure_ascii=False).encode("utf-8"), "application/json")
    _subir(f"publicadas/{foto_id}.jpg", descargar(f"pendientes/{foto_id}.jpg"), "image/jpeg")
    rechazar(foto_id)


def rechazar(foto_id: str) -> None:
    _borrar(f"pendientes/{foto_id}.json")
    _borrar(f"pendientes/{foto_id}.jpg")


def listar_publicadas() -> list[dict]:
    out = []
    for nombre in _listar("publicadas"):
        if not nombre.endswith(".json"):
            continue
        fid = nombre[:-5]
        out.append({**json.loads(descargar(f"publicadas/{fid}.json")), "id": fid})
    return out
