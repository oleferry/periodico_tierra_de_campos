"""Capa de IA (Claude) para redactar titulares y el parte del tiempo.

Se usa SOLO si hay ANTHROPIC_API_KEY en el entorno; si no, el sitio cae al
redactor por reglas (sitegen/redactor.py). Los resultados se cachean por hash
(sitegen/cache.py) para no repetir llamadas entre builds.

Voz: para NOTICIAS del boletín, factual y sobrio (editorial/politica_editorial.md
§5: intensidad moderada). Para el TIEMPO, más cercano y humano (intensidad alta),
pero siempre honesto: solo los datos dados, orientación no asesoramiento.
"""

from __future__ import annotations

import json
import os

# Versión de los prompts: súbela para invalidar la caché si cambias las instrucciones.
PROMPT_VERSION = "1"

_client = None


def _model() -> str:
    m = (os.getenv("LLM_MODEL") or "").strip()
    return m if m.startswith("claude-") else "claude-opus-4-8"


def disponible() -> bool:
    key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    return bool(key) and key != "replace_me"


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic()
    return _client


_SISTEMA_NOTICIA = (
    "Eres editor de El Terracampino, un medio hiperlocal de la comarca de Tierra de Campos. "
    "Recibes el texto oficial de un anuncio de boletín (BOP o BOCyL) y lo conviertes en un "
    "titular periodístico claro y una entradilla de una o dos frases.\n\n"
    "Reglas innegociables:\n"
    "- Factual y sobrio. Sin alarmismo, sin urgencia artificial, sin adjetivos vacíos "
    "(nada de 'histórico', 'espectacular', 'polémico').\n"
    "- No inventes NADA que no esté en el texto oficial. Si un dato no está, no lo pongas.\n"
    "- Conserva los nombres propios: municipio, empresas (S.L., S.A.), y cifras exactas.\n"
    "- Titular en minúscula (sentence case), sin punto final, máximo ~90 caracteres, "
    "que diga qué pasa y en qué pueblo.\n"
    "- Entradilla: explica en llano qué es y a quién afecta. Una o dos frases. Sin tecnicismos.\n"
    "- Nada de opinión. Eres un observador, no un columnista."
)

_ESQUEMA_NOTICIA = {
    "type": "object",
    "properties": {
        "titular": {"type": "string"},
        "entradilla": {"type": "string"},
    },
    "required": ["titular", "entradilla"],
    "additionalProperties": False,
}


def redactar(doc: dict) -> dict:
    """Devuelve {'titular','entradilla'} con Claude. Lanza si falla."""
    fuente = "BOP de Valladolid" if doc.get("source_type") == "bop" else "BOCyL (Castilla y León)"
    user = (
        f"Municipio: {doc.get('municipality_name','')}\n"
        f"Fuente: {fuente}\n"
        f"Fecha: {doc.get('published_at','')}\n"
        f"Texto oficial:\n{doc.get('title','')}"
    )
    resp = _get_client().messages.create(
        model=_model(),
        max_tokens=400,
        system=_SISTEMA_NOTICIA,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_NOTICIA}},
    )
    text = next(b.text for b in resp.content if b.type == "text")
    data = json.loads(text)
    return {"titular": data["titular"].strip().rstrip("."), "entradilla": data["entradilla"].strip()}


_SISTEMA_TIEMPO = (
    "Eres quien cuenta el tiempo en El Terracampino, para vecinos de los pueblos de Tierra "
    "de Campos. Recibes datos meteorológicos ya medidos y escribes un parte breve, cercano y "
    "claro, como quien te lo cuenta en la plaza.\n\n"
    "Reglas:\n"
    "- Usa SOLO los datos que te doy. No inventes cifras ni fenómenos.\n"
    "- Orientación, no asesoramiento técnico. No asegures nada del futuro con certeza.\n"
    "- Tono humano y sobrio, sin cursiladas, sin emojis, sin exclamaciones.\n"
    "- Tres o cuatro frases. Empieza por cómo está ahora.\n"
    "- Si te paso un consejo de huerta o un aviso, inclúyelo con naturalidad al final.\n"
    "- Devuelve solo el texto del parte, sin preámbulos ni comillas."
)


def tiempo(w: dict) -> str:
    """Reescribe el parte del tiempo desde los datos reales. Lanza si falla."""
    ahora = w["ahora"]
    hoy = w["hoy"]
    manana = w["manana"]
    datos = (
        f"Municipio: {w['municipio']}\n"
        f"Ahora: {ahora['temp']}°, {ahora['desc']}.\n"
        f"Hoy: máxima {hoy['max']}°, mínima {hoy['min']}°, viento {hoy['viento_kmh']} km/h, "
        f"probabilidad de lluvia {hoy['prob_lluvia']}% ({hoy['mm']} mm).\n"
        f"Mañana: {manana['desc']}, hasta {manana['max']}°."
    )
    aviso = ""
    if hoy["max"] >= 34:
        aviso = "Consejo de huerta: con este calor, riega a primera hora o al anochecer, nunca al mediodía."
    elif hoy["min"] <= 1:
        aviso = "Aviso: riesgo de helada de madrugada; protege semilleros y plantas delicadas."
    if aviso:
        datos += f"\n{aviso}"

    resp = _get_client().messages.create(
        model=_model(),
        max_tokens=400,
        system=_SISTEMA_TIEMPO,
        messages=[{"role": "user", "content": datos}],
    )
    return next(b.text for b in resp.content if b.type == "text").strip().strip('"')
