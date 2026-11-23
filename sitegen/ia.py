"""Capa de IA (Claude) para redactar titulares y el parte del tiempo.

Se usa SOLO si hay ANTHROPIC_API_KEY en el entorno; si no, el sitio cae al
redactor por reglas (sitegen/redactor.py). Los resultados se cachean por hash
(sitegen/cache.py) para no repetir llamadas entre builds.

Voz: para NOTICIAS del boletín, factual y sobrio (editorial/politica_editorial.md
§5: intensidad moderada). Para el TIEMPO, más cercano y humano (intensidad alta),
pero siempre honesto: solo los datos dados, orientación no asesoramiento.
"""

from __future__ import annotations

import base64
import json
import os

# Versión de los prompts: súbela para invalidar la caché si cambias las instrucciones.
PROMPT_VERSION = "3"

_client = None


# Cuatro niveles de modelo, cada uno donde rinde (decisión del usuario,
# 2026-11-23: "los más potentes", unos 20 €/mes más). Precios por millón de
# tokens de entrada/salida a esa fecha; comprobar en la documentación de
# Anthropic antes de fiarse de ellos.
#
# EDITORIAL — redacta lo que lleva juicio: titulares, plenos, ayudas, pistas,
# pies de foto. Opus 5 ($5/$25), mismo precio que el Opus 4.8 al que sustituye.
MODELO_EDITORIAL = "claude-opus-5"

# FILTRO — las dos puertas que deciden qué se publica SIN que lo vea nadie:
# qué pista del radar sale sola y qué comentario entra en la web. Sonnet 5
# ($2/$10): bastante más criterio que Haiku por céntimos al día, y es justo
# donde un error sale publicado.
MODELO_FILTRO = "claude-sonnet-5"

# MECÁNICO — transformar datos en texto sin criterio que proteger: el parte del
# tiempo. Haiku 4.5 ($1/$5). NO usarlo para nada que decida qué se publica.
MODELO_MECANICO = "claude-haiku-4-5"

# INVESTIGACIÓN — elegir el tema semanal y escribir la pieza larga: Claude
# Fable 5.1 ($10/$50), el modelo más capaz. Una pieza a la semana: unos 3-5 €.
MODELO_INVESTIGACION = "claude-fable-5-1"


def _forzado() -> str | None:
    """LLM_MODEL (secret opcional) fuerza un modelo para TODO, por si hay que
    salir de un apuro sin tocar código. Vacío o 'replace_me' = no fuerza nada."""
    m = (os.getenv("LLM_MODEL") or "").strip()
    return m if m.startswith("claude-") else None


def _model() -> str:
    return _forzado() or MODELO_EDITORIAL


def _model_filtro() -> str:
    return _forzado() or MODELO_FILTRO


def _model_mecanico() -> str:
    return _forzado() or MODELO_MECANICO


def _model_investigacion() -> str:
    return _forzado() or MODELO_INVESTIGACION


# Si el modelo se niega a una petición (stop_reason "refusal", pasa muy rara vez
# y casi siempre por falsos positivos), la API la reintenta sola con otro modelo
# adecuado en vez de devolverla vacía. Solo para los modelos que lo admiten.
_CON_RESCATE = {"claude-opus-5", "claude-fable-5-1"}


class RespuestaVacia(Exception):
    """La IA no devolvió texto utilizable (rechazo o corte por longitud). Quien
    llama la trata como cualquier otro fallo: el redactor cae a reglas."""


def _llamar(**kwargs):
    """messages.create con el rescate ante rechazos donde aplica."""
    if kwargs.get("model") in _CON_RESCATE:
        return _get_client().beta.messages.create(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
    return _get_client().messages.create(**kwargs)


def _llamar_largo(*, rescate: bool = True, timeout: float = 900.0, **kwargs):
    """Como _llamar, pero en streaming y con timeout largo: para las piezas de
    investigación, que tardan minutos. Devuelve el mensaje final completo.
    rescate=False en bucles con herramientas: el rescate cambia de modelo a
    mitad de turno y complica retomar un 'pause_turn'."""
    cliente = _get_client().with_options(timeout=timeout, max_retries=2)
    if rescate and kwargs.get("model") in _CON_RESCATE:
        with cliente.beta.messages.stream(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs) as st:
            return st.get_final_message()
    with cliente.messages.stream(**kwargs) as st:
        return st.get_final_message()


def _texto(resp) -> str:
    """Texto de la respuesta, comprobando antes POR QUÉ terminó: con el
    pensamiento activado de los modelos nuevos, un max_tokens corto se lo come
    el razonamiento y la respuesta llega cortada o sin texto."""
    if resp.stop_reason == "refusal":
        raise RespuestaVacia("el modelo rechazó la petición")
    if resp.stop_reason == "max_tokens":
        raise RespuestaVacia("respuesta cortada por max_tokens")
    partes = [b.text for b in resp.content if b.type == "text"]
    if not partes:
        raise RespuestaVacia("respuesta sin texto")
    return "".join(partes)


# Esfuerzo bajo para los textos cortos y repetitivos (titular + entradilla de
# cada noticia del feed): son unas 100 llamadas por build y la tarea es acotada.
# Los artículos largos (plenos, ayudas, investigaciones) NO lo llevan: ahí
# interesa que el modelo piense. Ojo: 'effort' no existe en Haiku 4.5, así que
# no se combina con MODELO_MECANICO.
#
# Opus 5, Sonnet 5 y Fable 5.1 piensan por defecto, y ese razonamiento cuenta
# contra max_tokens: por eso los topes de cada llamada son holgados. Es solo un
# techo, se paga lo que se usa.
ESFUERZO_BAJO = {"effort": "low"}


def disponible() -> bool:
    key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    return bool(key) and key != "replace_me"


def _get_client():
    global _client
    if _client is None:
        import anthropic
        # Timeout corto y sin reintentos largos: si la red falla, mejor que
        # falle rápido y caiga al redactor por reglas (ver sitegen/redactor.py)
        # que no que el build entero se quede colgado esperando una llamada.
        _client = anthropic.Anthropic(timeout=25.0, max_retries=1)
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
    if doc.get("source_type") == "bop":
        fuente = "BOP de Valladolid"
    elif doc.get("source_type") == "municipal_news":
        fuente = f"web oficial del Ayuntamiento de {doc.get('municipality_name', '')}"
    elif doc.get("source_type") == "municipal_plenary":
        fuente = f"acta de pleno del Ayuntamiento de {doc.get('municipality_name', '')}"
    elif doc.get("source_type") == "bocyl":
        fuente = "BOCyL (Castilla y León)"
    elif doc.get("source_type") == "subvencion":
        fuente = "Base de Datos Nacional de Subvenciones (BDNS)"
    else:
        # Antes cualquier otro tipo se le presentaba a la IA como BOCyL, y la IA
        # podía citar el boletín en el titular. Mejor no nombrar ninguna fuente
        # que nombrar la que no es.
        fuente = "documento público (sin identificar)"
    user = (
        f"Municipio: {doc.get('municipality_name','')}\n"
        f"Fuente: {fuente}\n"
        f"Fecha: {doc.get('published_at','')}\n"
        f"Texto oficial:\n{doc.get('title','')}"
    )
    resp = _llamar(
        model=_model(),
        max_tokens=3000,
        system=_SISTEMA_NOTICIA,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_NOTICIA},
                       **ESFUERZO_BAJO},
    )
    text = _texto(resp)
    data = json.loads(text)
    return {"titular": data["titular"].strip().rstrip("."), "entradilla": data["entradilla"].strip()}


_SISTEMA_PLENO = (
    "Eres el vecino de Tierra de Campos que fue al pleno (o se ha leído el acta) y escribe la "
    "noticia completa, no un enlace con dos frases. Recibes el texto completo de un acta de "
    "sesión plenaria de un ayuntamiento y tienes que convertirla en un ARTÍCULO real: la gente "
    "que lo lea no debería necesitar abrir el PDF del acta para enterarse de qué pasó.\n\n"
    "Cómo elegir qué contar y en qué orden:\n"
    "- Empieza por el acuerdo más relevante (dinero, obras, urbanismo, personal, subvenciones, "
    "ordenanzas — lo que cambia algo del pueblo), no por el orden del día.\n"
    "- Ignora del todo los puntos de puro trámite (aprobación del acta anterior, dar cuenta de "
    "decretos de alcaldía) salvo que ahí se cuele algo que sí importe.\n"
    "- Si hay más de un acuerdo con sustancia, cuéntalos todos en el cuerpo, no solo el primero — "
    "para eso es un artículo y no un titular suelto.\n"
    "- Si hubo debate o votación dividida (no por unanimidad), dilo: quién votó qué si el acta lo "
    "recoge, aunque sea de pasada.\n"
    "- Si de verdad no hay nada más que trámite interno en toda el acta, dilo tal cual (p.ej. "
    "'el pleno de Mayorga se limitó a trámites internos, sin acuerdos de fondo') y no alargues el "
    "cuerpo inventando sustancia donde no la hay — un párrafo corto y honesto basta.\n\n"
    "Mismas reglas de voz que para el resto: cercano pero serio, nada de sonar a acta municipal "
    "copiada, nada de IA genérica ('en resumen', 'cabe destacar'), nada de folclore ni de colega "
    "forzado.\n\n"
    "Reglas innegociables:\n"
    "- Solo lo que dice el acta. Si el resultado de una votación no está claro, no lo afirmes.\n"
    "- Titular en minúscula (sentence case), sin punto final, máximo ~100 caracteres, con el "
    "pueblo y el acuerdo concreto.\n"
    "- Entradilla: una o dos frases, el resumen que engancha — es lo que se ve en la tarjeta antes "
    "de abrir el artículo.\n"
    "- Cuerpo: entre 2 y 4 párrafos (una lista de strings, un párrafo por elemento), con el "
    "desarrollo completo de todos los acuerdos con sustancia. Nada de repetir la entradilla tal "
    "cual como primer párrafo — el cuerpo añade detalle, no repite.\n"
    "- Cero opinión sobre si el acuerdo es bueno o malo."
)

_ESQUEMA_PLENO = {
    "type": "object",
    "properties": {
        "titular": {"type": "string"},
        "entradilla": {"type": "string"},
        "cuerpo": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["titular", "entradilla", "cuerpo"],
    "additionalProperties": False,
}


def redactar_pleno(doc: dict) -> dict:
    """Devuelve {'titular','entradilla','cuerpo'} — artículo completo sobre los
    acuerdos de un acta de pleno (doc['acta_texto']), no solo el principal.
    'cuerpo' es una lista de párrafos. Lanza si falla."""
    user = (
        f"Municipio: {doc.get('municipality_name', '')}\n"
        f"Fecha del acta: {doc.get('published_at', '')}\n"
        f"Texto completo del acta:\n{doc.get('acta_texto', '')}"
    )
    resp = _llamar(
        model=_model(),
        max_tokens=8000,
        system=_SISTEMA_PLENO,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_PLENO}},
    )
    text = _texto(resp)
    data = json.loads(text)
    return {
        "titular": data["titular"].strip().rstrip("."),
        "entradilla": data["entradilla"].strip(),
        "cuerpo": [p.strip() for p in data["cuerpo"] if p.strip()],
    }


_SISTEMA_AYUDA = (
    "Eres el vecino de Tierra de Campos que se entera de que hay una ayuda o subvención nueva y te "
    "explica si te interesa y qué tienes que hacer. Recibes los datos oficiales de una convocatoria "
    "de la Base de Datos Nacional de Subvenciones y tienes que convertirlos en un artículo práctico, "
    "no en un resumen administrativo.\n\n"
    "Lo que de verdad importa para alguien que lee esto:\n"
    "- ¿Quién puede pedirla? (una persona concreta, una asociación, una empresa, el propio "
    "ayuntamiento para repartirla luego...)\n"
    "- ¿Cuánto dinero hay y para qué sirve?\n"
    "- ¿Hasta cuándo hay plazo, y sigue abierto ahora mismo o ya se cerró?\n"
    "- Si es una subvención nominativa a una asociación o club concreto (no algo a lo que un vecino "
    "pueda presentarse), dilo tal cual: es una noticia de que el Ayuntamiento ha dado dinero a esa "
    "entidad, no una convocatoria abierta — no la vendas como 'ayuda para ti' si no lo es.\n\n"
    "Mismas reglas de voz que para el resto: cercano pero serio, nada de sonar a bases reguladoras "
    "copiadas, nada de IA genérica, nada de folclore ni de colega forzado.\n\n"
    "Reglas innegociables:\n"
    "- Solo los datos que te doy. Si el importe o el plazo no aparecen, no los inventes — di que no "
    "se ha especificado.\n"
    "- Titular en minúscula (sentence case), sin punto final, máximo ~100 caracteres. Si es una "
    "ayuda a la que puede optar un vecino, que quede claro en el titular quién puede pedirla.\n"
    "- Entradilla: una o dos frases con lo esencial (para qué, cuánto, hasta cuándo).\n"
    "- Cuerpo: 1 a 3 párrafos con el resto del detalle práctico (requisitos si los hay, cómo y dónde "
    "solicitarla si se sabe, importe exacto). No repitas la entradilla.\n"
    "- Cero opinión sobre si la ayuda es suficiente o no."
)


def redactar_ayuda(doc: dict) -> dict:
    """Devuelve {'titular','entradilla','cuerpo'} sobre una convocatoria de la
    BDNS (doc['ayuda_texto']). Lanza si falla."""
    user = (
        f"Entidad convocante: {doc.get('metadata', {}).get('organismo', '')}\n"
        f"Fecha de publicación: {doc.get('published_at', '')}\n"
        f"Datos oficiales de la convocatoria:\n{doc.get('ayuda_texto', '')}"
    )
    resp = _llamar(
        model=_model(),
        max_tokens=8000,
        system=_SISTEMA_AYUDA,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_PLENO}},
    )
    text = _texto(resp)
    data = json.loads(text)
    return {
        "titular": data["titular"].strip().rstrip("."),
        "entradilla": data["entradilla"].strip(),
        "cuerpo": [p.strip() for p in data["cuerpo"] if p.strip()],
    }


# Desarrollo de una pista del radar (scrapers/radar_noticias.py) en pieza propia.
# El material de partida es la noticia de OTRO medio local: se usa como fuente de
# HECHOS, nunca como texto a reescribir. De ahí que este prompt sea más duro que
# los demás: el riesgo aquí no es inventar, es plagiar.
_SISTEMA_PISTA = (
    "Eres redactor de El Terracampino, un medio hiperlocal de Tierra de Campos. Te llega el texto "
    "de una noticia publicada por OTRO medio local de la zona.\n\n"
    "Tu trabajo NO es reescribir esa noticia. Es leerla, quedarte con los HECHOS, y contarlos "
    "desde cero con nuestra voz, dando crédito a quien lo publicó primero.\n\n"
    "Reglas innegociables:\n"
    "- PROHIBIDO copiar frases del original, y prohibido parafrasear frase por frase (cambiar "
    "cuatro palabras y mantener la estructura ES plagio). Lee, entiende, cierra los ojos y "
    "cuéntalo como se lo contarías a un vecino.\n"
    "- CITA SIEMPRE al medio de origen dentro del cuerpo, con naturalidad y al menos una vez: "
    "'según informa <medio>', 'lo adelantó <medio>'. Nunca presentes su trabajo como nuestro.\n"
    "- No añadas NI UN hecho, cifra, nombre, causa o consecuencia que no esté en el material. "
    "Si no sabes la causa de algo, no la insinúes.\n"
    "- Si el material da para poco, escribe poco. Una pieza corta y honesta es mejor que una "
    "rellena. No estires con contexto que no te han dado.\n"
    "- Si el original atribuye algo a una fuente (la Junta, la Guardia Civil, el alcalde), "
    "mantén esa atribución: no conviertas en hecho probado lo que es una versión.\n\n"
    "Voz: humana, directa, local, clara, prudente. Sin alarmismo, sin adjetivos vacíos, sin "
    "emojis, sin tono de nota de prensa, sin clichés de IA ('cabe destacar', 'en resumen').\n\n"
    "Personas: no des nombres de particulares, ni detalles que permitan identificarlos, ni datos "
    "de menores. Cargos públicos sí, por su cargo — y esto incluye a quien ejerció un cargo "
    "público en el pasado (exalcalde, exconcejal…) aunque ya no lo tenga hoy, por ejemplo en un "
    "obituario: si la fuente ya lo nombra abiertamente por haber sido alcalde, nómbralo tú "
    "también.\n\n"
    "Formato: titular claro y sin sensacionalismo; entradilla de una o dos frases con lo "
    "esencial; cuerpo de 2 a 5 párrafos cortos."
)


def redactar_pista(doc: dict) -> dict:
    """Pieza propia a partir de una pista del radar. `doc['pista_texto']` es el
    material de la noticia ajena (hechos), `doc['metadata']['fuente']` el medio
    que la publicó. Devuelve {'titular','entradilla','cuerpo'}. Lanza si falla."""
    meta = doc.get("metadata", {})
    user = (
        f"Pueblo: {doc.get('municipality_name', '')}\n"
        f"Medio que lo publicó (cítalo): {meta.get('fuente', '')}\n"
        f"Fecha: {doc.get('published_at', '')}\n\n"
        f"Texto original del que extraer los hechos (NO lo reescribas):\n{doc.get('pista_texto', '')}"
    )
    resp = _llamar(
        model=_model(),
        max_tokens=8000,
        system=_SISTEMA_PISTA,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_PLENO}},
    )
    text = _texto(resp)
    data = json.loads(text)
    return {
        "titular": data["titular"].strip().rstrip("."),
        "entradilla": data["entradilla"].strip(),
        "cuerpo": [p.strip() for p in data["cuerpo"] if p.strip()],
    }


_ESQUEMA_CLASIFICACION_PISTA = {
    "type": "object",
    "properties": {
        "categoria": {
            "type": "string",
            "enum": [
                "publicable", "suceso", "fallecimiento", "menores",
                "persona_vulnerable", "repetida", "caducada", "sin_hechos",
            ],
        },
        "motivo": {"type": "string"},
    },
    "required": ["categoria", "motivo"],
    "additionalProperties": False,
}

_SISTEMA_CLASIFICACION_PISTA = (
    "Filtras pistas de la prensa local de Tierra de Campos antes de que El Terracampino las convierta "
    "en una pieza propia. La pieza se publica SIN que ninguna persona la revise después, así que tu "
    "criterio es conservador: ante la duda, NO es publicable.\n\n"
    "Elige UNA categoría:\n"
    "- suceso: accidentes, incendios, heridos, detenciones, delitos, robos, agresiones, estafas, "
    "investigaciones policiales o judiciales penales, rescates, desapariciones, maltrato animal.\n"
    "- fallecimiento: la noticia gira en torno a la muerte de una persona, aunque sea un homenaje. "
    "Eso va por esquelas, con revisión humana.\n"
    "- menores: hay menores identificables, o menores implicados en un hecho delicado.\n"
    "- persona_vulnerable: se identifica a una persona concreta en situación vulnerable (mayor que vive "
    "sola, enfermedad, precariedad) o se exponen datos personales de un particular.\n"
    "- repetida: cuenta el mismo hecho que alguno de los titulares ya publicados de ese pueblo que se te dan.\n"
    "- caducada: anuncia algo (un evento, un plazo, una convocatoria) cuya fecha ya ha pasado respecto a "
    "la fecha de hoy que se te da.\n"
    "- sin_hechos: es opinión, publicidad, promoción sin contenido, o no hay hechos concretos y "
    "verificables suficientes para una pieza.\n"
    "- publicable: todo lo demás que sea información real de la comarca: fiestas y cultura con fecha "
    "futura o recién celebradas, deporte, obras, ayudas, decisiones municipales, economía local, "
    "reconocimientos, patrimonio.\n\n"
    "El motivo es una frase muy corta para un registro interno."
)


def clasificar_pista(*, pueblo: str, titulo: str, texto: str, hoy: str,
                     titulares_recientes: list[str]) -> dict:
    """Puerta editorial del desarrollo AUTOMÁTICO de pistas: devuelve
    {'categoria','motivo'} y solo 'publicable' se desarrolla. Es clasificar,
    no redactar, así que va con el modelo mecánico, igual que la moderación
    de comentarios. Si la llamada falla, el CALLER no publica esa pista (ver
    scripts/desarrollar_pista.py): nunca sale sola una pista sin evaluar."""
    recientes = "\n".join(f"- {t}" for t in titulares_recientes) or "(ninguno)"
    user = (
        f"Fecha de hoy: {hoy}\nPueblo: {pueblo}\n"
        f"Titulares ya publicados de este pueblo en las últimas semanas:\n{recientes}\n\n"
        f"Titular de la pista: {titulo}\n\nTexto de la noticia original:\n{texto[:6000]}"
    )
    resp = _llamar(
        model=_model_filtro(),
        max_tokens=3000,
        system=_SISTEMA_CLASIFICACION_PISTA,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_CLASIFICACION_PISTA}},
    )
    text = _texto(resp)
    return json.loads(text)


_ESQUEMA_MODERACION = {
    "type": "object",
    "properties": {
        "aprobar": {"type": "boolean"},
        "motivo": {"type": "string"},
    },
    "required": ["aprobar", "motivo"],
    "additionalProperties": False,
}

_SISTEMA_MODERACION = (
    "Eres el moderador único y autónomo del tablón de comentarios de El Terracampino, un periódico "
    "hiperlocal de la comarca Tierra de Campos. Los mensajes vienen del grupo de discusión público "
    "ligado al canal de Telegram. Nadie humano revisa tu decisión después — eres tú quien decide si "
    "un comentario se publica en la web o no. Actúa con criterio conservador: ante la duda, RECHAZA.\n\n"
    "Aprueba (aprobar=true) comentarios que sean:\n"
    "- Sobre la comarca, un pueblo, una noticia publicada, el tiempo, fiestas, deporte local, huerta... "
    "cualquier cosa relacionada con Tierra de Campos, aunque sea una queja, una corrección o una broma.\n"
    "- Civiles: pueden ser críticos o informales, pero sin insultar ni atacar a nadie.\n\n"
    "Rechaza (aprobar=false) SIEMPRE que el comentario tenga:\n"
    "- Insultos, acoso, discurso de odio, amenazas, contenido sexual o cualquier cosa que no publicarías "
    "delante del alcalde y del insultado a la vez.\n"
    "- Spam, publicidad, enlaces sueltos, phishing, contenido repetido o sin sentido.\n"
    "- Datos personales de un tercero que no es quien escribe (teléfono, dirección, DNI, acusaciones "
    "contra una persona identificable) — el autor puede hablar de sí mismo, nunca exponer a otro.\n"
    "- Menores de edad identificables.\n"
    "- Cualquier cosa que no tengas claro cómo interpretar, aunque no encaje en las anteriores: si dudas, "
    "rechaza. Es preferible perder un comentario válido que publicar uno problemático sin que nadie lo "
    "revise después.\n\n"
    "El motivo debe ser una frase muy corta, en español, para un registro interno (nunca se le muestra "
    "a nadie)."
)


def moderar_comentario(texto: str) -> dict:
    """Devuelve {'aprobar': bool, 'motivo': str}. Si la llamada a la IA falla,
    el CALLER debe tratarlo como 'no aprobar' (ver scripts/moderar_comentarios.py)
    — nunca se publica un comentario que no se ha podido evaluar de verdad."""
    resp = _llamar(
        model=_model_filtro(),
        max_tokens=3000,
        system=_SISTEMA_MODERACION,
        messages=[{"role": "user", "content": f"Comentario a evaluar:\n\n{texto}"}],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_MODERACION}},
    )
    text = _texto(resp)
    return json.loads(text)


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

    resp = _llamar(
        model=_model_mecanico(),
        max_tokens=400,
        system=_SISTEMA_TIEMPO,
        messages=[{"role": "user", "content": datos}],
    )
    return _texto(resp).strip().strip('"')


PROMPT_VERSION_DIAS = "1"

_SISTEMA_TIEMPO_DIAS = (
    "Eres el vecino de Tierra de Campos que cuenta el tiempo de los próximos días, al estilo de "
    "'El tiempo de Javimo': un titular corto y con gancho para cada día (tipo 'Finde en seco', "
    "'Puente pasado por agua', 'Jueves con opciones de tormenta'), seguido de una o dos frases que "
    "expliquen ese titular con los datos reales. Cercano pero serio: nada de cursiladas, emojis ni "
    "exclamaciones, y sin exagerar lo que dicen los datos.\n\n"
    "Reglas:\n"
    "- Usa SOLO los datos que te doy, día por día. No inventes cifras ni fenómenos.\n"
    "- El titular no lleva el nombre del pueblo, solo el día y el rasgo del tiempo. Sin punto final, "
    "máximo unos 40 caracteres.\n"
    "- El texto son una o dos frases con los datos reales (máxima, mínima, lluvia, viento si afecta), "
    "sin sonar a lista de datos.\n"
    "- Si la probabilidad de lluvia es menor del 50%, habla de posibilidad, no de certeza.\n"
    "- Devuelve un objeto por cada día que te paso, en el mismo orden."
)

_ESQUEMA_TIEMPO_DIAS = {
    "type": "object",
    "properties": {
        "dias": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titular": {"type": "string"},
                    "texto": {"type": "string"},
                },
                "required": ["titular", "texto"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["dias"],
    "additionalProperties": False,
}


def tiempo_dias(municipio: str, dias: list[dict]) -> list[dict]:
    """Devuelve [{'titular','texto'}], uno por cada día de `dias`, en el mismo orden. Lanza si falla."""
    lineas = [
        f"- {d['dia'].capitalize()}: {d['desc']}, máxima {d['max']}°, mínima {d['min']}°, "
        f"viento {d.get('viento_kmh', 0)} km/h, probabilidad de lluvia {d.get('prob_lluvia', 0)}% "
        f"({d.get('mm', 0)} mm)."
        for d in dias
    ]
    user = f"Municipio: {municipio}\n" + "\n".join(lineas)
    resp = _llamar(
        model=_model_mecanico(),
        max_tokens=600,
        system=_SISTEMA_TIEMPO_DIAS,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_TIEMPO_DIAS}},
    )
    text = _texto(resp)
    salida = json.loads(text)["dias"]
    if len(salida) != len(dias):
        raise ValueError("La IA no devolvió un día por cada día pedido")
    return [{"titular": o["titular"].strip().rstrip("."), "texto": o["texto"].strip()} for o in salida]


_SISTEMA_FOTO = (
    "Eres el vecino de Tierra de Campos que mira la foto que ha mandado alguien del pueblo y "
    "escribe el pie de foto para publicarla en la web. Describes SOLO lo que se ve en la imagen "
    "(qué es, qué lugar o escena parece), nunca datos que no puedas ver — nada de nombres de "
    "personas, fechas exactas, ni inventar qué fiesta o evento es si no lo pone en el texto que "
    "manda quien envía la foto.\n\n"
    "Si quien manda la foto escribe algo (una frase, el nombre del sitio), úsalo como dato real, "
    "no como sugerencia a ignorar — es la única fuente fiable de contexto que no se ve en la imagen.\n\n"
    "Mismas reglas de voz que el resto: cercano pero serio. Nada de '¡qué foto más bonita!' ni "
    "exclamaciones — describe, no aduules. Una frase corta, como el pie de foto de un periódico, "
    "no una descripción exhaustiva."
)

_ESQUEMA_FOTO = {
    "type": "object",
    "properties": {"pie": {"type": "string"}},
    "required": ["pie"],
    "additionalProperties": False,
}


def pie_de_foto(imagen_jpeg: bytes, *, pueblo: str, texto_remitente: str = "") -> str:
    """Pie de foto corto a partir de lo que la IA ve en la imagen (Claude con
    visión) + el texto opcional de quien la envía. Lanza si falla."""
    contexto = f"Pueblo: {pueblo}."
    if texto_remitente.strip():
        contexto += f' Texto de quien manda la foto: "{texto_remitente.strip()}"'
    resp = _llamar(
        model=_model(),
        max_tokens=3000,
        system=_SISTEMA_FOTO,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/jpeg",
                    "data": base64.b64encode(imagen_jpeg).decode("ascii"),
                }},
                {"type": "text", "text": contexto},
            ],
        }],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_FOTO}},
    )
    text = _texto(resp)
    return json.loads(text)["pie"].strip()


# Artículo largo de investigación (blog/newsletter), a partir del sistema de
# marca v1.2 del usuario — ver editorial/sistema_marca_v1_2/prompt_maestro_articulos.md
# y guia_storytelling_articulos.md. Reglas de párrafo de esa versión (3-6 frases,
# 45-90 palabras, 14-22 párrafos, máx. 3 párrafos de una frase) porque las
# reglas de fragmentación extrema de la guía de estilo original no se aplican
# a piezas largas — ver editorial/sistema_marca_v1_2/regla_operativa_de_parrafo.md.
_SISTEMA_INVESTIGACION = (
    "Eres redactor de El Terracampino, un medio hiperlocal de Tierra de Campos. Escribes un "
    "artículo de investigación de 1.100 a 1.450 palabras, pensado para una lectura de 6-8 minutos.\n\n"
    "Trabaja ÚNICAMENTE con el dossier que se te da. No inventes cifras, nombres, citas, hechos, "
    "fechas ni resultados que no estén en él.\n\n"
    "La pieza debe tener una historia que sostenga la lectura: real y verificada, anonimizada, "
    "reconstruida desde documentos, un personaje compuesto, o una escena hipotética. Si no es "
    "completamente real, indícalo de forma visible al principio del artículo — nunca hagas pasar "
    "ficción por periodismo.\n\n"
    "Estructura en 7 bloques:\n"
    "1. Escena inicial concreta (120-180 palabras) — una puerta, un cartel, una plaza, un trayecto, "
    "un detalle del campo, con una tensión dentro.\n"
    "2. Pregunta central investigable (80-130 palabras), no decorativa.\n"
    "3. Datos y explicación (220-320 palabras) — entre 3 y 6 datos del dossier, cada uno con fuente "
    "y año, que hagan avanzar la explicación.\n"
    "4. Caso exterior comparable si el dossier lo trae (180-280 palabras) — problema, medida, "
    "resultado, coste o límite; nunca como receta ni milagro.\n"
    "5. Aplicación a Tierra de Campos (280-380 palabras) — pueblos, distancias, población, actores "
    "concretos del dossier.\n"
    "6. Objeción fuerte (120-200 palabras) — no una objeción de cartón, una que de verdad limite "
    "o contradiga la tesis.\n"
    "7. Regreso a la escena inicial y cierre abierto (100-160 palabras) — no resumas, no moralices, "
    "deja una pregunta implícita.\n\n"
    "Voz: humana, directa, local, clara, prudente. Sin humor intencional, sin tono de nota de "
    "prensa, sin adjetivos vacíos, sin emojis, sin hashtags, sin clichés de IA ('en resumen', "
    "'cabe destacar', 'en conclusión', 'la clave está en').\n\n"
    "Ritmo y formato de párrafo:\n"
    "- párrafos narrativos de 3-6 frases y 45-90 palabras como rango habitual;\n"
    "- una escena, argumento o explicación completa por párrafo, antes del punto y aparte;\n"
    "- no rompas párrafo automáticamente antes de 'y', 'pero', 'porque' u 'o';\n"
    "- entre 14 y 22 párrafos de cuerpo en total, agrupados en 4-6 secciones con subtítulo;\n"
    "- máximo 3 párrafos de una sola frase en toda la pieza, y solo si marcan un giro real;\n"
    "- alterna relato, dato y análisis dentro del párrafo; frases de longitud variable.\n\n"
    "Cada cifra debe indicar fuente y año (tal como aparecen en el dossier). Si un dato del dossier "
    "no está claro, no lo afirmes como cierto — dilo como lo que es.\n\n"
    "El cierre no resume, abre: regresa a la imagen inicial y deja una pregunta o decisión abierta. "
    "Prohibido 'en conclusión', 'en definitiva', 'la clave está en', 'el futuro dirá', "
    "'¿y tú qué opinas?', 'esperamos que este artículo haya servido'.\n\n"
    "Para 'prompt_imagen' (la escena que ilustrará la portada, en inglés, para un generador de "
    "imágenes): describe SOLO elementos visuales — nunca pidas que aparezca texto, letras, "
    "carteles con palabras, rótulos, pintadas ni ningún tipo de escritura legible, ni siquiera en "
    "español. Los generadores de imagen renderizan el texto mal o en el idioma equivocado y rompen "
    "la credibilidad de la escena. Si la escena inicial del artículo incluye un cartel, un rótulo o "
    "un letrero, descríbelo por su forma, color, desgaste o estado (p.ej. 'a weathered closed metal "
    "shutter, faded paint, no legible signage') en vez de mencionar qué pone."
)

_ESQUEMA_INVESTIGACION = {
    "type": "object",
    "properties": {
        "titular": {"type": "string"},
        "titulares_alternativos": {"type": "array", "items": {"type": "string"}},
        "entradilla": {"type": "string"},
        "secciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subtitulo": {"type": "string"},
                    "parrafos": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["subtitulo", "parrafos"],
                "additionalProperties": False,
            },
        },
        "resumen_100_palabras": {"type": "string"},
        "version_telegram": {"type": "string"},
        "prompt_imagen": {"type": "string"},
        "fuentes_usadas": {"type": "array", "items": {"type": "string"}},
        "revision_humana": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "titular", "titulares_alternativos", "entradilla", "secciones",
        "resumen_100_palabras", "version_telegram", "prompt_imagen", "fuentes_usadas", "revision_humana",
    ],
    "additionalProperties": False,
}


# ------------------------------------------------ investigación automática
# Fase 1 y 2 de scripts/investigacion_semanal.py. La fase 3 (redactar) es
# redactar_investigacion(), la misma que usan las investigaciones hechas a mano.
# Las dos van con el modelo editorial: elegir qué se investiga y qué fuentes
# valen es criterio periodístico, no transformación mecánica de datos.

_ESQUEMA_TEMA = {
    "type": "object",
    "properties": {
        "tema_clave": {"type": "string"},
        "titulo_de_trabajo": {"type": "string"},
        "pregunta_central": {"type": "string"},
        "por_que_ahora": {"type": "string"},
        "fuentes_a_buscar": {"type": "array", "items": {"type": "string"}},
        "idea_backlog": {"type": ["integer", "null"]},
    },
    "required": ["tema_clave", "titulo_de_trabajo", "pregunta_central", "por_que_ahora",
                 "fuentes_a_buscar", "idea_backlog"],
    "additionalProperties": False,
}

_SISTEMA_TEMA = (
    "Eres el jefe de investigación de El Terracampino, periódico de la comarca de Tierra de Campos "
    "(Palencia, Valladolid, León y Zamora). Cada semana eliges UNA investigación larga que otra IA "
    "documentará solo con búsquedas en internet, sin trabajo de campo, y que se publicará sin que "
    "nadie la reescriba. Por eso el tema tiene que ser investigable de verdad con fuentes públicas "
    "en línea: datos oficiales (INE, BOE, BOCyL, boletines provinciales, Junta, diputaciones, "
    "confederaciones hidrográficas, BDNS, Sacyl, Educación), documentos de ayuntamientos y prensa "
    "de calidad para contrastar.\n\n"
    "Descarta cualquier tema que dependa de entrevistas, visitas, encuestas propias o datos que no "
    "estén publicados: una IA que 'investiga' eso acaba inventando. Descarta también lo que repita "
    "una investigación ya publicada o ya propuesta, y lo que sea opinión en lugar de pregunta.\n\n"
    "Puedes partir de una idea del backlog (di su número en idea_backlog) o de algo que haya "
    "detectado el radar de noticias si abre una pregunta de fondo; si no, idea_backlog es null.\n\n"
    "tema_clave: identificador corto en minúsculas con guiones bajos (p. ej. 'escuelas_rurales'). "
    "pregunta_central: una sola pregunta concreta y respondible con datos. fuentes_a_buscar: "
    "organismos y documentos concretos donde debería estar la respuesta."
)


def elegir_tema_investigacion(*, ideas: str, publicadas: list[str], propuestas: list[str],
                              pistas: list[str], hoy: str) -> dict:
    """Elige el tema de la semana. Devuelve el dict de _ESQUEMA_TEMA. Lanza si falla."""
    def lista(xs: list[str]) -> str:
        return "\n".join(f"- {x}" for x in xs) or "(ninguna)"
    user = (
        f"Fecha de hoy: {hoy}\n\n"
        f"Investigaciones ya publicadas:\n{lista(publicadas)}\n\n"
        f"Investigaciones ya propuestas las últimas semanas (publicadas o rechazadas; no repitas):\n"
        f"{lista(propuestas)}\n\n"
        f"Backlog de ideas investigables (🟢 con datos públicos, 🟡 con fuentes públicas dispersas):\n"
        f"{ideas}\n\n"
        f"Lo que ha detectado el radar en la prensa local estas dos semanas (solo titulares):\n"
        f"{lista(pistas)}"
    )
    resp = _llamar_largo(
        model=_model_investigacion(),
        max_tokens=16000,
        system=_SISTEMA_TEMA,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_TEMA}},
    )
    text = _texto(resp)
    return json.loads(text)


_MARCA_DOSSIER = "=== DOSSIER ==="

_SISTEMA_INVESTIGAR = (
    "Eres investigador de El Terracampino, periódico de la comarca de Tierra de Campos. Documentas "
    "UNA pregunta con búsquedas web reales y entregas un dossier de hechos verificados que después "
    "otra IA convertirá en artículo sin poder comprobar nada más. Todo lo que no esté en tu dossier "
    "no existirá para ella; todo lo que pongas mal, saldrá publicado mal.\n\n"
    "Jerarquía de fuentes, por este orden: (1) oficiales — INE, BOE, BOCyL, boletines provinciales, "
    "Junta de Castilla y León, diputaciones, confederaciones hidrográficas, BDNS, ayuntamientos; "
    "(2) documentos primarios de las entidades implicadas; (3) prensa de calidad, siempre contrastada "
    "con (1) o (2) cuando sea posible.\n\n"
    "Reglas duras:\n"
    "- No inventes datos, importes, fechas, nombres ni citas. Si no hay evidencia, dilo.\n"
    "- Cada cifra con su fuente, su fecha o año y su URL.\n"
    "- Si hablas de una ayuda, convocatoria o plazo, comprueba si sigue vigente y dilo con fecha.\n"
    "- Resume los hechos con tus palabras. Nada de copiar párrafos de otros medios: como mucho una "
    "frase corta entre comillas y atribuida.\n"
    "- No incluyas datos personales de particulares. Cargos públicos, empresas y organismos, sí.\n"
    "- Céntrate en los municipios de Tierra de Campos; lo de fuera, solo como comparación.\n\n"
    f"Cuando termines de investigar, escribe el dossier empezando por una línea que diga exactamente "
    f"{_MARCA_DOSSIER} y con estas secciones: pregunta central; hallazgos (cada uno con fuente, fecha "
    "y URL); cifras verificadas (dato — fuente — año — URL); posiciones de los actores (atribuidas); "
    "caso comparable de fuera si lo hay; lo que no se pudo verificar; advertencias para quien "
    "redacte. La última línea del dossier debe ser exactamente 'VEREDICTO: SUFICIENTE' si hay hechos "
    "verificados de sobra para 1.200 palabras honestas, o 'VEREDICTO: INSUFICIENTE — ' seguido del "
    "motivo si no los hay. Es mejor no publicar que rellenar."
)


def investigar_tema(tema: dict, hoy: str, max_continuaciones: int = 6) -> dict:
    """Fase de investigación con búsqueda y lectura web reales (herramientas de
    servidor de Anthropic). Devuelve {'dossier','suficiente','motivo','busquedas'}.
    Lanza si la API falla.

    La búsqueda corre en los servidores de Anthropic en un bucle propio; si ese
    bucle llega a su límite, la respuesta vuelve con stop_reason 'pause_turn' y
    se retoma reenviando lo acumulado (sin añadir un "continúa", que el servidor
    no necesita). Se usa streaming porque una investigación tarda minutos."""
    tools = [
        {"type": "web_search_20260209", "name": "web_search", "max_uses": 25,
         "user_location": {"type": "approximate", "country": "ES", "timezone": "Europe/Madrid"}},
        {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 20},
    ]
    pregunta = (
        f"Fecha de hoy: {hoy}\n\n"
        f"Tema: {tema['titulo_de_trabajo']}\n"
        f"Pregunta central: {tema['pregunta_central']}\n"
        f"Por qué ahora: {tema['por_que_ahora']}\n"
        f"Dónde debería estar la respuesta: {'; '.join(tema['fuentes_a_buscar'])}"
    )
    acumulado: list = []
    busquedas = 0
    for _ in range(max_continuaciones + 1):
        mensajes = [{"role": "user", "content": pregunta}]
        if acumulado:
            mensajes.append({"role": "assistant", "content": acumulado})
        resp = _llamar_largo(
            rescate=False,
            model=_model_investigacion(),
            max_tokens=64000,
            system=_SISTEMA_INVESTIGAR,
            messages=mensajes,
            tools=tools,
        )
        acumulado = acumulado + list(resp.content)
        uso = getattr(resp.usage, "server_tool_use", None)
        busquedas += getattr(uso, "web_search_requests", 0) or 0
        if resp.stop_reason != "pause_turn":
            break

    texto = "".join(b.text for b in acumulado if b.type == "text")
    if _MARCA_DOSSIER not in texto:
        return {"dossier": "", "suficiente": False, "busquedas": busquedas,
                "motivo": "la investigación terminó sin entregar dossier"}
    dossier = texto[texto.rindex(_MARCA_DOSSIER) + len(_MARCA_DOSSIER):].strip()
    ultima = dossier.splitlines()[-1].strip() if dossier else ""
    suficiente = ultima.upper().startswith("VEREDICTO: SUFICIENTE")
    motivo = "" if suficiente else (ultima.split("—", 1)[-1].strip() if "—" in ultima
                                    else "el dossier no cerró con veredicto")
    return {"dossier": dossier, "suficiente": suficiente, "motivo": motivo, "busquedas": busquedas}


def redactar_investigacion(tema: str, dossier: str) -> dict:
    """Artículo largo de investigación a partir de un dossier factual (texto
    libre: datos, cifras con fuente, contexto). Devuelve titular, entradilla,
    secciones (cada una con su subtítulo y sus párrafos, ya emparejados —
    no dos listas sueltas que haya que adivinar cómo encajar), adaptaciones
    (Telegram, resumen) y un prompt para la imagen de portada (ver
    sitegen.imagenes.generar_imagen). Lanza si falla — sin fallback por
    reglas, un artículo largo sin IA no tiene sustituto razonable."""
    user = (
        f"Tema: {tema}\n\nDossier factual:\n{dossier}\n\n"
        "Devuelve el cuerpo como una lista de 4-6 secciones, cada una con su subtítulo "
        "y sus párrafos (2-4 párrafos por sección, siguiendo las reglas de párrafo indicadas)."
    )
    resp = _llamar_largo(
        model=_model_investigacion(),
        max_tokens=64000,
        system=_SISTEMA_INVESTIGACION,
        messages=[{"role": "user", "content": user}],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA_INVESTIGACION}},
    )
    text = _texto(resp)
    data = json.loads(text)
    data["titular"] = data["titular"].strip().rstrip(".")
    for s in data["secciones"]:
        s["parrafos"] = [p.strip() for p in s["parrafos"] if p.strip()]
    return data
