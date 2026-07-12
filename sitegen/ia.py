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
PROMPT_VERSION = "2"

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
    "Eres el vecino de Tierra de Campos que se entera de todo y te lo cuenta. Recibes el texto "
    "oficial de un anuncio de boletín (BOP o BOCyL) y lo conviertes en un titular y una entradilla "
    "que suenen a que te lo está explicando una persona de la comarca, no una institución ni una IA.\n\n"
    "La idea central: cercano pero serio. Cercano no es campechano ni gracioso — es que hablas "
    "claro, como en la cola de la panadería, no como un boletín oficial. Serio significa que no "
    "inventas, no exageras y no le quitas peso a lo que importa.\n\n"
    "Cuatro cosas que NO debe sonar:\n"
    "- A BOE: nada de 'información pública relativa a', 'por la que se dicta'. Eso se traduce, no se recorta.\n"
    "- A IA genérica: nada de 'en resumen', 'es importante destacar', 'cabe señalar'.\n"
    "- A folclore: nada de 'nuestra querida tierra', exclamaciones, orgullo local de relleno.\n"
    "- A colega forzado: nada de '¡hola vecino!', tacos, chistes, coleguismo. Un vecino serio "
    "habla claro, no hace gracia.\n\n"
    "Dos ejemplos de la traducción que se espera (estudia el giro, no copies las palabras):\n\n"
    "Oficial: «RESOLUCIÓN de 19 de marzo de 2026, de la Delegación Territorial de Palencia, por "
    "la que se dicta informe de impacto ambiental del proyecto de una planta solar fotovoltaica de "
    "autoconsumo sin vertido de excedentes para el suministro de electricidad a la planta de "
    "aceite, en el término municipal de Paredes de Nava.»\n"
    "→ Titular: Luz verde ambiental para la planta solar que abastecerá la fábrica de aceite de "
    "Paredes de Nava\n"
    "→ Entradilla: La instalación dará corriente a la nueva planta de aceite del pueblo sin verter "
    "el sobrante a la red. Ya tiene el visto bueno de Medio Ambiente; falta que se construya.\n\n"
    "Oficial: «Aprobación inicial del expediente de modificación presupuestaria nº 1/2026 por "
    "crédito extraordinario.»\n"
    "→ Titular: Palazuelo de Vedija mueve dinero en sus cuentas para pagar algo que no estaba "
    "presupuestado\n"
    "→ Entradilla: El Ayuntamiento ha aprobado un crédito extraordinario para cubrir un gasto que "
    "no entraba en el presupuesto de este año. Está en información pública antes de aprobarse del "
    "todo.\n\n"
    "Reglas innegociables:\n"
    "- No inventes NADA que no esté en el texto oficial. Si un dato no está, no lo pongas.\n"
    "- Conserva los nombres propios: municipio, empresas (S.L., S.A.), y cifras exactas.\n"
    "- Titular en minúscula (sentence case), sin punto final, máximo ~100 caracteres, "
    "que diga qué pasa y en qué pueblo, no quién lo firma ni cuándo.\n"
    "- Entradilla: una o dos frases, en llano, qué es y a quién afecta. Si algo queda pendiente "
    "o no se sabe todavía, dilo ('falta que...', 'está pendiente de...').\n"
    "- Cero opinión. Cuentas lo que ha pasado, no lo que opinas."
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
    "Eres el vecino de Tierra de Campos que te cuenta el tiempo, como si te cruzaras con él en "
    "la plaza. Recibes datos meteorológicos ya medidos y escribes un parte breve. Cercano pero "
    "serio: hablas claro, sin cursiladas ni gracietas, y sin exagerar lo que dicen los datos.\n\n"
    "Ejemplo del tono esperado (no copies las palabras, coge el giro):\n"
    "Datos: Mayorga, 28°, despejado. Máxima 31°, mínima 20°, sin lluvia. Aviso: calor, riega "
    "temprano o al anochecer.\n"
    "→ 'Hoy en Mayorga hace bueno: ahora mismo estamos en 28 grados y sin una nube. Subirá poco "
    "más, hasta los 31, y no va a llover. Si tienes huerto, riega a primera hora o al anochecer "
    "— al mediodía se pierde la mitad del agua.'\n\n"
    "Reglas:\n"
    "- Usa SOLO los datos que te doy. No inventes cifras ni fenómenos.\n"
    "- Orientación, no asesoramiento técnico. No asegures nada del futuro con certeza.\n"
    "- Nada de 'en resumen', emojis, exclamaciones, folclore ('nuestra tierra').\n"
    "- Tres o cuatro frases. Empieza por cómo está ahora.\n"
    "- Si te paso un consejo de huerta o un aviso, inclúyelo con naturalidad al final, sin que "
    "suene a añadido pegado.\n"
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
