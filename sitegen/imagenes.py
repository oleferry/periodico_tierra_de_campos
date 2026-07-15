"""Genera la imagen de portada de un artículo de blog con la API de imágenes
de OpenAI (modelo gpt-image-1). Se usa SOLO si hay OPENAI_API_KEY en el
entorno; si no, el artículo se publica sin imagen (mejor sin imagen que con
una genérica de banco de imágenes — ver kit_marca_visual.md, sección
Fotografía: "no banco de imágenes", "no folclore").

El prompt de la imagen lo escribe la propia IA al redactar el artículo
(ia.py:redactar_investigacion → campo 'prompt_imagen'), a partir de la
escena real del artículo, no de una plantilla genérica — así la imagen
ilustra ESTE artículo, no "un artículo cualquiera de El Terracampino".

Dirección visual (adaptada del kit de marca a la paleta blanco/negro
vigente, ver brand/web/brand-tokens.css — NO la paleta crema del kit):
editorial, sobria, sin folclore (nada de espigas de más, atardeceres de
stock, banderas, tractores de cliché), fondo claro, tinta oscura, acento
terracota puntual, composición tipo periódico contemporáneo.
"""

from __future__ import annotations

import base64
import os

DIRECCION_VISUAL = (
    "Editorial illustration for a serious contemporary local-newspaper website called "
    "'El Terracampino', covering the Tierra de Campos region in Spain. Clean, sober, "
    "documentary style — NOT folkloric, NOT a tourism postcard, NOT stock-photo wheat "
    "fields or dramatic sunsets. Off-white paper background, near-black ink linework, a "
    "single restrained terracotta accent color used sparingly. Flat, editorial composition "
    "with generous negative space, like a modern print newspaper illustration. No text, no "
    "logos, no watermarks, no people's faces rendered photorealistically. Square or near-4:5 "
    "vertical composition."
)


def disponible() -> bool:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    return bool(key) and key != "replace_me"


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI()
    return _client


def generar_imagen(prompt_escena: str) -> bytes:
    """Genera la imagen de portada de un artículo (JPEG/PNG en bytes).
    `prompt_escena` es la descripción concreta de la escena del artículo
    (la escribe la IA al redactarlo, ver ia.py:redactar_investigacion),
    combinada aquí con la dirección visual fija de la marca. Lanza si falla."""
    prompt = f"{DIRECCION_VISUAL}\n\nScene for this specific article: {prompt_escena}"
    resp = _get_client().images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
        quality="medium",
        n=1,
    )
    return base64.b64decode(resp.data[0].b64_json)
