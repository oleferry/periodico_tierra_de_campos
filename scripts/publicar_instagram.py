"""Publica en Instagram (@elterracampino) las investigaciones del blog que
todavía no se hayan publicado allí.

Cómo funciona la API de publicación de Instagram (Graph API, dos pasos):
  1. POST /{IG_USER_ID}/media          con image_url + caption  → devuelve un id
  2. POST /{IG_USER_ID}/media_publish  con ese creation_id      → lo publica

Detalle clave: Instagram **descarga la imagen de una URL pública**, no se sube
el fichero. Por eso se usa la imagen ya publicada del artículo
(https://elterracampino.es/assets/blog/<slug>.jpg): el sitio es estático y
público, así que encaja sin infraestructura extra.

Los artículos SIN imagen se saltan: Instagram no admite publicaciones de solo
texto (p. ej. el homenaje a Mariano Haro se publicó sin imagen a propósito —
no se generan retratos de IA de personas reales).

Qué se ha publicado ya se guarda en data/instagram_publicados.json, que el
workflow commitea. Sin ese registro se republicaría lo mismo cada día.

Uso:
    python -m scripts.publicar_instagram --dry-run     # enseña qué publicaría
    python -m scripts.publicar_instagram               # publica (1 por vuelta)
    python -m scripts.publicar_instagram --marcar-existentes   # marca todo como
                                                       # ya publicado, sin publicar
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://elterracampino.es"
REGISTRO = ROOT / "data" / "instagram_publicados.json"
TIMEOUT = 60

# Versión de la Graph API. Meta retira cada versión a los ~2 años: si un día
# empieza a fallar con "Unsupported get request", subir este número.
GRAPH = "v21.0"

# Instagram no admite enlaces clicables en el pie: por eso se remite a la bio.
HASHTAGS = "#TierraDeCampos #Palencia #Valladolid #León #Zamora #EspañaVaciada #PueblosDeEspaña"


class PublicarError(RuntimeError):
    pass


def _credenciales() -> tuple[str, str]:
    uid = (os.getenv("IG_USER_ID") or "").strip()
    token = (os.getenv("IG_ACCESS_TOKEN") or "").strip()
    if not uid or not token:
        raise PublicarError(
            "Faltan IG_USER_ID o IG_ACCESS_TOKEN (secrets del repo / .env). "
            "Ver docs/instagram.md"
        )
    return uid, token


def cargar_registro() -> set[str]:
    if not REGISTRO.exists():
        return set()
    datos = json.loads(REGISTRO.read_text(encoding="utf-8"))
    return {p["slug"] for p in datos.get("publicados", [])}


def guardar_registro(slug: str, media_id: str | None) -> None:
    datos = {"publicados": []}
    if REGISTRO.exists():
        datos = json.loads(REGISTRO.read_text(encoding="utf-8"))
    datos.setdefault("publicados", []).append({
        "slug": slug,
        "media_id": media_id,
        "publicado_en": datetime.now(timezone.utc).isoformat(),
    })
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    REGISTRO.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pie_de_publicacion(art: dict) -> str:
    """Titular + entradilla + remite a la web. Sin inventar nada: se usa lo que
    ya está escrito y revisado en el artículo."""
    return (
        f"{art['titular']}\n\n"
        f"{art['entradilla']}\n\n"
        "Lo contamos entero en elterracampino.es — enlace en la bio.\n\n"
        f"{HASHTAGS}"
    )


def pendientes(articulos: list[dict], ya: set[str]) -> list[dict]:
    """Sin publicar, con imagen, del más reciente al más antiguo (una noticia
    vale más el día que sale)."""
    out = [a for a in articulos if a["slug"] not in ya and a.get("tiene_imagen")]
    out.sort(key=lambda a: a.get("fecha") or "", reverse=True)
    return out


def publicar(art: dict) -> str:
    uid, token = _credenciales()
    imagen = f"{BASE}/assets/blog/{art['slug']}.jpg"

    # Comprobar que la imagen existe ANTES de llamar a Meta: si no, la API
    # devuelve un error genérico difícil de interpretar en los logs del Action.
    r = requests.head(imagen, timeout=TIMEOUT, allow_redirects=True)
    if r.status_code != 200:
        raise PublicarError(f"la imagen no está publicada todavía ({imagen} → HTTP {r.status_code})")

    # Paso 1: contenedor
    r = requests.post(
        f"https://graph.facebook.com/{GRAPH}/{uid}/media",
        data={"image_url": imagen, "caption": pie_de_publicacion(art), "access_token": token},
        timeout=TIMEOUT,
    )
    if not r.ok:
        raise PublicarError(f"creando el contenedor: HTTP {r.status_code} {r.text[:300]}")
    creation_id = r.json().get("id")
    if not creation_id:
        raise PublicarError(f"la API no devolvió id de contenedor: {r.text[:300]}")

    # Paso 2: publicar
    r = requests.post(
        f"https://graph.facebook.com/{GRAPH}/{uid}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=TIMEOUT,
    )
    if not r.ok:
        raise PublicarError(f"publicando: HTTP {r.status_code} {r.text[:300]}")
    return r.json().get("id", "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Publica investigaciones en Instagram")
    ap.add_argument("--dry-run", action="store_true", help="enseña qué publicaría, sin publicar")
    ap.add_argument("--marcar-existentes", action="store_true",
                    help="marca todo lo publicado hasta hoy como ya subido (arranque en frío)")
    args = ap.parse_args()

    manifest = ROOT / "data" / "blog" / "articulos.json"
    if not manifest.exists():
        print("No hay artículos.", file=sys.stderr)
        return 0
    articulos = json.loads(manifest.read_text(encoding="utf-8"))
    ya = cargar_registro()

    if args.marcar_existentes:
        for a in articulos:
            if a["slug"] not in ya:
                guardar_registro(a["slug"], None)
                print(f"marcado como ya publicado: {a['slug']}")
        return 0

    cola = pendientes(articulos, ya)
    sin_imagen = [a["slug"] for a in articulos if a["slug"] not in ya and not a.get("tiene_imagen")]
    if sin_imagen:
        print(f"({len(sin_imagen)} sin imagen, no se pueden publicar en Instagram: {', '.join(sin_imagen)})")

    if not cola:
        print("Nada nuevo que publicar en Instagram.")
        return 0

    art = cola[0]  # uno por vuelta: ni spam ni tocar límites de Instagram
    if args.dry_run:
        print(f"PUBLICARÍA: {art['slug']}\n---\n{pie_de_publicacion(art)}\n---")
        print(f"imagen: {BASE}/assets/blog/{art['slug']}.jpg")
        if len(cola) > 1:
            print(f"(quedarían {len(cola) - 1} en cola para siguientes vueltas)")
        return 0

    try:
        media_id = publicar(art)
    except PublicarError as exc:
        print(f"ERROR publicando {art['slug']}: {exc}", file=sys.stderr)
        return 1
    guardar_registro(art["slug"], media_id)
    print(f"Publicado en Instagram: {art['slug']} (media {media_id})")
    if len(cola) > 1:
        print(f"Quedan {len(cola) - 1} en cola.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
